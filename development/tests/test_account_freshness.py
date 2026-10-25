"""Start-anchored budgets, lane isolation, recovery and bounded mailbox evidence."""
from dataclasses import replace
from decimal import Decimal
import json
import io
import tempfile
from pathlib import Path
import threading
import unittest

from development.tests.fixtures.account_workers import ControlledQuota, Provider, wait_for
from development.tests.fixtures.session_snapshots import make_snapshot
from development.tests.fixtures.watch_runtime import MutableSource, make_service
from src.accounts.refresh_loop import AccountRefreshLoop
from src.accounts.refresh_policy import ProviderRefresh
from src.watch.account_refresh import WatchAccountRefresh
from src.watch import WatchCoordinator
from src.presentation import WatchRenderer
from src.cache.account_refresh_state import STATE_FILE, persist_refresh_state, read_refresh_state
from unittest.mock import patch


class MailboxWork:
    def __init__(self, loop):
        self.loop = loop

    def set_now_ms(self, now): self.now = now
    def begin_account_refresh(self): pass  # The account clock is already running.
    def poll_account_refresh(self): return self.loop.poll(self.now)
    @property
    def accounts_pending(self): return self.loop.pending
    def close_accounts(self): self.loop.close()


class ManualLoop(AccountRefreshLoop):
    def start(self, now_ms):
        return False  # The test drives exactly the production scheduler's turns.


class AccountFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.clock = [0.0]

    def loop(self, providers):
        loop = AccountRefreshLoop(providers, "fixture", clock=lambda: self.clock[0],
                                  wall_ms=lambda: int(100_000 + self.clock[0] * 1000))
        self.addCleanup(loop.close)
        return loop

    def complete(self, loop, provider, *, at):
        self.clock[0] = at
        provider.gate.set()
        wait_for(lambda: any(result[1] == 0 for result in tuple(loop.engine._results.queue)))
        loop.tick()

    def test_provider_latency_never_accumulates_into_cadence(self):
        provider = ControlledQuota(self.clock)
        self.addCleanup(provider.gate.set)
        loop = self.loop((provider,))
        for start in (0, 30, 60, 90, 120):
            self.clock[0] = start
            loop.tick()
            wait_for(lambda: len(provider.starts) == start // 30 + 1)
            self.complete(loop, provider, at=start + 19)
            self.assertIsNotNone(loop.poll(int(100_000 + (start + 19) * 1000)))
        self.assertEqual([0, 30, 60, 90, 120], provider.starts)

    def test_changed_native_values_reach_watch_within_sixty_seconds(self):
        for latency in (0, 1, 10, 20):
            with self.subTest(latency=latency):
                self.clock[0] = 0
                provider = ControlledQuota(self.clock)
                loop = self.loop((provider,))
                watch = WatchAccountRefresh(MailboxWork(loop), clock_ms=loop.wall_ms, monotonic=lambda: self.clock[0])
                loop.tick()
                wait_for(lambda: len(provider.starts) == 1)
                provider.value = Decimal(".50")  # Upstream changes just AFTER request captured its old value.
                changed_at = .001
                self.complete(loop, provider, at=latency)
                watch.refresh(now_ms=loop.wall_ms())
                self.assertEqual(Decimal(".75"), watch.snapshots[0].quotas[0].remaining_fraction)
                self.clock[0] = 30
                loop.tick()
                wait_for(lambda: len(provider.starts) == 2)
                self.complete(loop, provider, at=30 + latency)
                self.clock[0] += 2  # Include publication wake AND render budget.
                watch.refresh(now_ms=loop.wall_ms())
                self.assertEqual(Decimal(".50"), watch.snapshots[0].quotas[0].remaining_fraction)
                self.assertLessEqual(self.clock[0] - changed_at, 60)
                self.assertEqual(100_000 + (30 + latency) * 1000, watch.seen_ms[watch.snapshots[0].key])
                loop.close()

    def test_four_blocked_providers_cannot_starve_other_lanes_or_spawn_replacements(self):
        gates = [threading.Event() for _ in range(4)]
        providers = [Provider(str(i), gate=gate) for i, gate in enumerate(gates)]
        for gate in gates:
            self.addCleanup(gate.set)
        fast = Provider("healthy")
        loop = self.loop((*providers, fast))
        loop.tick()
        self.assertTrue(all(p.entered.wait(1) for p in providers))
        wait_for(lambda: fast.calls == 1)
        for second in (1, 20, 30, 60, 90):
            self.clock[0] = second
            loop.tick()
            if second >= 30:
                wait_for(lambda: fast.calls == second // 30 + 1)
                wait_for(lambda: any(s.ref.provider_id == "healthy" and s.fetched_at_ms == fast.calls
                                     for s in loop.engine.snapshots) or not loop.engine._results.empty())
                loop.tick()
        self.assertEqual([1] * 4, [p.calls for p in providers])
        self.assertEqual(4, fast.calls)
        self.assertEqual(5, len(loop.engine._threads))
        self.assertEqual(4, loop.diagnostics()["blocked_lanes"])

    def test_success_then_transient_failure_gets_bounded_local_backoff_and_recovers(self):
        provider, healthy = ControlledQuota(self.clock), Provider("healthy")
        self.addCleanup(provider.gate.set)
        loop = self.loop((provider, healthy))
        loop.tick()
        wait_for(lambda: len(provider.starts) == 1)
        self.complete(loop, provider, at=1)
        good = loop.engine.snapshots[0]
        provider.snapshot = replace(good, availability="error", quotas=(), observations={"parser_reason": "network_failure"})
        for start, finish in ((30, 31), (36, 37), (47, 48), (68, 69), (129, 130)):
            self.clock[0] = start
            loop.tick()
            wait_for(lambda: provider.starts and provider.starts[-1] == start)
            self.complete(loop, provider, at=finish)
        self.assertEqual([0, 30, 36, 47, 68, 129], provider.starts)
        self.assertEqual(3, loop.engine.refresh[0].retries)
        provider.snapshot = good
        self.clock[0] = 190
        loop.tick()
        wait_for(lambda: provider.starts[-1] == 190)
        self.complete(loop, provider, at=191)
        self.assertEqual("success", loop.engine.refresh[0].outcome)
        self.assertLessEqual(loop.engine.refresh[0].due, 220)
        self.assertGreater(loop.engine.refresh[0].due, 191)

    def test_durable_errors_never_use_fast_retry_schedule(self):
        provider = ControlledQuota(self.clock)
        self.addCleanup(provider.gate.set)
        loop = self.loop((provider,))
        loop.tick()
        wait_for(lambda: provider.starts == [0])
        self.complete(loop, provider, at=1)
        good = loop.engine.snapshots[0]
        for reason in ({"http_status": 401}, {"http_status": 403}, {"parser_reason": "format_changed"},
                       {"parser_reason": "method_missing"}, {"parser_reason": "software_failure"}):
            state = ProviderRefresh(None)
            state.begin(0)
            state.complete((replace(good, availability="error", observations=reason),), 1)
            self.assertEqual(61, state.due)
            self.assertEqual(0, state.retries)

    def test_mailbox_age_and_stale_expiry_are_not_new_observations(self):
        provider = ControlledQuota(self.clock)
        self.addCleanup(provider.gate.set)
        loop = self.loop((provider,))
        watch = WatchAccountRefresh(MailboxWork(loop), clock_ms=loop.wall_ms, monotonic=lambda: self.clock[0])
        loop.tick()
        wait_for(lambda: provider.starts == [0])
        self.complete(loop, provider, at=1)
        self.clock[0] = 70  # Source hydration delayed mailbox consumption, not acquisition.
        watch.refresh(now_ms=loop.wall_ms())
        key = watch.snapshots[0].key
        self.assertTrue(watch.stale)
        self.assertEqual(101_000, watch.seen_ms[key])
        self.clock[0] = 302
        watch.refresh(now_ms=loop.wall_ms())
        self.assertFalse(watch.snapshots[0].quotas)
        self.assertEqual(101_000, watch.seen_ms[key])
        evidence = json.dumps({**loop.diagnostics(), **watch.diagnostics()})
        for secret in ("Private account", "controlled", "fixture", "account_id", "source_account"):
            self.assertNotIn(secret, evidence)
        self.assertIn('"display_state": "unavailable"', evidence)

    def test_repeated_success_with_unchanged_values_advances_observation_not_requests(self):
        provider = ControlledQuota(self.clock)
        self.addCleanup(provider.gate.set)
        loop = self.loop((provider,))
        for start in (0, 30):
            self.clock[0] = start
            loop.tick()
            wait_for(lambda: provider.starts and provider.starts[-1] == start)
            self.complete(loop, provider, at=start + 1)
            for _ in range(100):
                loop.tick()
                loop.poll(loop.wall_ms())
        self.assertEqual([0, 30], provider.starts)
        self.assertEqual(31, loop.engine.refresh[0].observed)

    def test_stopped_loop_cannot_start_workers_or_publish_again(self):
        provider = Provider("healthy")
        loop = self.loop((provider,))
        loop.tick()
        wait_for(lambda: provider.calls == 1)
        loop.close()
        self.clock[0] = 100
        loop.tick()
        self.assertIsNone(loop.poll(loop.wall_ms()))
        self.assertEqual(1, provider.calls)

    def test_account_clock_runs_without_source_polls_redraws_or_mailbox_consumption(self):
        provider = Provider("healthy")
        loop = self.loop((provider,))
        loop.start(loop.wall_ms())
        wait_for(lambda: provider.calls == 1)
        wait_for(lambda: loop.diagnostics().get("providers", {}).get("0", {}).get("outcome") == "success")
        for second in (30, 60, 90):
            self.clock[0] = second
            wait_for(lambda: provider.calls == second // 30 + 1)
            wait_for(lambda: loop.diagnostics()["acquisition_elapsed_ms"] == second * 1000
                     and loop.diagnostics()["providers"]["0"]["observation_age_seconds"] == 0)
        update = loop.poll(loop.wall_ms())
        self.assertEqual(4, update.snapshots[0].fetched_at_ms)
        self.assertEqual(1, len(loop.engine._threads))
        loop.close()
        self.assertFalse(loop._thread.is_alive())

    def test_scheduler_software_fault_propagates_to_thread_boundary_and_closes_acquisition(self):
        loop = self.loop(())
        with patch.object(loop, "tick", side_effect=RuntimeError("fixture defect")):
            with self.assertRaises(RuntimeError):
                loop._run()
        self.assertTrue(loop.engine._stop.is_set())
        self.assertIsNone(loop.poll(loop.wall_ms()))

    def test_persisted_refresh_evidence_is_bounded_allowlisted_and_not_rewritten_per_wake(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            evidence = {"worker_limit": 7, "secret": "PRIVATE", "providers": {
                "0": {"attempt_age_seconds": 5, "outcome": "timeout", "raw_response": "PRIVATE"},
                "account-email": {"attempt_age_seconds": 1}},
                "watch": {"accounts": [{"display_state": "stale", "account_id": "PRIVATE"}] * 200}}
            persist_refresh_state(root, evidence)
            state = read_refresh_state(root)
            self.assertNotIn("PRIVATE", json.dumps(state))
            self.assertNotIn("account-email", json.dumps(state))
            self.assertEqual(128, len(state["evidence"]["watch"]["accounts"]))
            self.assertEqual("timeout", state["evidence"]["providers"]["0"]["outcome"])
            (root / STATE_FILE).write_bytes(b"\xff")
            self.assertEqual({}, read_refresh_state(root))
        recorded = []
        loop = AccountRefreshLoop((), "fixture", clock=lambda: self.clock[0], evidence_sink=recorded.append)
        self.addCleanup(loop.close)
        for _ in range(100):
            loop.tick()
        self.clock[0] = 5
        loop.tick()
        self.assertEqual(2, len(recorded))

    def test_idle_and_active_dashboards_render_changed_values_inside_freshness_budget(self):
        for active in (False, True):
            with self.subTest(active=active), tempfile.TemporaryDirectory() as td:
                self.clock[0] = 0
                provider = ControlledQuota(self.clock)
                loop = ManualLoop((provider,), "fixture", clock=lambda: self.clock[0],
                                  wall_ms=lambda: int(100_000 + self.clock[0] * 1000))
                source = MutableSource(make_snapshot(running=active))
                config, selection, service, _ = make_service(td, source, async_accounts=True)
                service._account_work = loop
                watch = WatchCoordinator(selection=selection, report_service=service, config=config,
                                         clock_ms=loop.wall_ms, monotonic=lambda: self.clock[0], record_observations=False)
                self.addCleanup(watch.close)
                output = io.StringIO()
                renderer = WatchRenderer(config, stream=output, interactive=True, terminal_width=160)
                watch._render(renderer, watch.initialize().projection)
                changes = {1: Decimal(".50"), 61: Decimal(".25"), 121: Decimal(".10")}
                shown = {}
                for second in range(181):
                    self.clock[0] = second
                    if second in changes:
                        provider.value = changes[second]
                    if second >= 20 and second % 30 == 20:
                        self.complete(loop, provider, at=second)
                    else:
                        loop.tick()
                    if second % 30 == 0:
                        wait_for(lambda: provider.starts and provider.starts[-1] == second)
                    if active and second % 5 == 0:
                        source.snapshot = replace(source.snapshot, source_revision=str(second))
                        watch.poll_once(hinted_session_ids=("root",))
                    frame = watch.status_projection(seconds_until_check=5)
                    watch._render_wake(renderer, frame, watch._rendered_projection)
                    if watch._rendered_projection.quota.accounts:
                        value = watch._rendered_projection.quota.accounts[0].account.quotas[0].remaining_fraction
                        shown.setdefault(value, second)
                for changed_at, value in changes.items():
                    self.assertLessEqual(shown[value] - changed_at, 60)
                    self.assertIn(f"{int(value * 100)}%", output.getvalue())
                self.assertEqual(list(range(0, 181, 30)), provider.starts)
                provider.gate.set()
                watch.close()


if __name__ == "__main__":
    unittest.main()
