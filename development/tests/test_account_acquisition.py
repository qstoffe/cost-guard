"""Read-only inventory, bounded work, incremental Watch and shutdown regressions."""
from __future__ import annotations

from contextlib import closing
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from development.fixtures.watch_runtime import MutableSource, make_service
from src.accounts.acquisition import AccountAcquisition
from src.accounts.discovery import AccountDiscovery
from src.accounts.simple_http import SIMPLE_HTTP_PROVIDERS, SimpleHttpAccountProvider
from src.accounts.openai_subscription import OpenAIAccountProvider
from src.accounts.github_copilot import GitHubCopilotAccountProvider
from src.accounts.claude_code import ClaudeCodeAccountProvider
from src.accounts.credentials import read_credentials
from src.domain import AccountRef, AccountSnapshot, IntegrationHealth, QuotaComponent
from src.reports import ReportRequest
from src.watch import WatchCoordinator


class Provider:
    def __init__(self, name, *, gate=None, failure=None, callback=None):
        self.provider_id = name
        self.gate, self.failure, self.callback = gate, failure, callback
        self.entered = threading.Event()
        self.returned = threading.Event()
        self.calls = 0

    def probe(self):
        return IntegrationHealth(True, True, "fixture")

    def get_account_snapshots(self):
        self.calls += 1
        self.entered.set()
        if self.callback:
            self.callback()
        if self.gate and not self.gate.wait(2):
            raise TimeoutError("fixture deadline")
        self.returned.set()
        if self.failure:
            raise self.failure
        return (AccountSnapshot(AccountRef("fixture", self.provider_id, "account"), self.calls,
                                self.provider_id, quotas=(QuotaComponent("quota", remaining_fraction=Decimal("0.5")),)),)


def wait_for(predicate, *, timeout=2):
    deadline = time.monotonic() + timeout
    wake = threading.Event()
    while time.monotonic() < deadline:
        if predicate():
            return
        wake.wait(0.002)
    raise AssertionError("fixture completion deadline exceeded")


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.auth = self.root / "auth.json"
        self.db = self.root / "credentials.db"

    def adapters(self):
        kwargs = {"auth_json_path": str(self.auth)}
        return (GitHubCopilotAccountProvider(**kwargs), OpenAIAccountProvider(**kwargs),
                *(SimpleHttpAccountProvider(d, **kwargs, http_get=lambda *_: self.fail("unexpected HTTPS"))
                  for d in SIMPLE_HTTP_PROVIDERS))

    def test_only_relevant_accounts_and_one_shared_read_among_many_providers(self):
        self.auth.write_text(json.dumps({"github-copilot": {"type": "oauth", "access": "fixture"},
                                         "openai": {"type": "api", "key": "fixture"}}))
        providers = self.adapters()
        inventory = AccountDiscovery(providers * 25)
        with patch("src.accounts.discovery.read_credentials", wraps=read_credentials) as reads:
            found = inventory.discover()
            again = inventory.discover()
        self.assertEqual(1, reads.call_count)
        self.assertEqual({"github-copilot", "openai"}, {c.provider.provider_id for c in found})
        self.assertEqual(len(found), len(again))
        self.assertFalse(any(c.provider.provider_id in {"openrouter", "deepseek"} for c in found))

    def test_v2_priority_multiple_accounts_and_explicit_override(self):
        self.auth.write_text(json.dumps({"openai": {"type": "api", "key": "legacy"},
                                         "deepseek": {"type": "api", "key": "fallback"}}))
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("CREATE TABLE credential(id TEXT, integration_id TEXT, value TEXT, active INTEGER)")
            for identity in ("a", "b"):
                conn.execute("INSERT INTO credential VALUES(?,?,?,?)", (identity, "openai",
                             json.dumps({"type": "api", "key": "fixture", "accountId": identity}), 1))
            conn.commit()
        view = read_credentials(self.auth, self.db, None)
        self.assertTrue(view.healthy)
        self.assertEqual(["a", "b"], [r.ref.account_id for r in view.records if r.ref.provider_id == "openai"])
        self.assertEqual(1, sum(r.ref.provider_id == "deepseek" for r in view.records))
        provider = OpenAIAccountProvider(auth_json_path=str(self.auth), credential_db_path=self.db)
        self.assertIsNone(provider.credential_db_path)
        self.assertEqual(1, len(AccountDiscovery((provider,)).discover()[0].records))

    def test_broken_storage_fails_closed_and_repr_never_contains_credentials(self):
        self.db.write_bytes(b"not SQLite")
        self.auth.write_text(json.dumps({"openai": {"type": "api", "key": "do-not-expose"}}))
        view = read_credentials(self.auth, self.db, None)
        self.assertFalse(view.healthy)
        self.assertFalse(view.records)
        provider = OpenAIAccountProvider(auth_json_path=str(self.auth))
        candidate = AccountDiscovery((provider,)).discover()[0]
        self.assertNotIn("do-not-expose", repr(candidate))
        self.assertNotIn("do-not-expose", repr(candidate.records))
        self.auth.write_bytes(b"\xff")
        self.assertFalse(read_credentials(self.auth, None, None).healthy)

    def test_no_http_requests_for_absent_http_providers(self):
        self.auth.write_text("{}")
        engine = AccountAcquisition(self.adapters(), "fixture")
        self.addCleanup(engine.close)
        self.assertFalse(engine.start(1000))
        self.assertEqual((), engine.finish(1000))
        self.assertEqual(0, engine.checks_started)

    def test_other_auth_source_is_not_filtered_by_opencode_inventory(self):
        auth = lambda: {"loggedIn": True, "apiProvider": "firstParty", "authMethod": "api_key", "email": "fixture"}
        claude = ClaudeCodeAccountProvider(auth_reader=auth, usage_reader=lambda: self.fail("no subscription"))
        engine = AccountAcquisition((claude,), "fixture")
        self.addCleanup(engine.close)
        engine.start(1000)
        snapshots = engine.finish(1000)
        self.assertEqual("API pay as you go", snapshots[0].plan)

    def test_account_added_removed_and_changed_under_watch_without_restart(self):
        self.auth.write_text("{}")
        provider = OpenAIAccountProvider(auth_json_path=str(self.auth))
        engine = AccountAcquisition((provider,), "fixture")
        self.addCleanup(engine.close)
        engine.start(1000)
        self.assertEqual((), engine.finish(1000))
        self.auth.write_text(json.dumps({"openai": {"type": "api", "key": "fixture"}}))
        engine.start(2000)
        snapshots = engine.finish(2000)
        self.assertEqual(1, len(snapshots))
        self.auth.write_text("{}")
        engine.start(3000)
        update = engine.poll(3000)
        self.assertEqual("unavailable", update.snapshots[0].availability)
        self.assertEqual("auth_failure", update.snapshots[0].observations["parser_reason"])

    def test_v2_wal_reinventory_pins_one_shared_view_and_ignores_unrelated_changes(self):
        self.auth.write_text("{}")
        provider = OpenAIAccountProvider()
        provider.auth_json_path, provider.credential_db_path = self.auth, self.db
        inventory = AccountDiscovery((provider,))
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("CREATE TABLE credential(id TEXT, integration_id TEXT, value TEXT, active INTEGER)")
            conn.execute("CREATE TABLE unrelated(value TEXT)")
            conn.execute("INSERT INTO credential VALUES('a','openai',?,1)", (json.dumps({"type": "api", "key": "fixture"}),))
            conn.commit()
            with patch("src.accounts.discovery.read_credentials", wraps=read_credentials) as reads:
                first = inventory.discover()[0]
                first.provider.probe()
                first.provider.get_account_snapshots()
                self.assertEqual(1, reads.call_count)
                conn.execute("INSERT INTO unrelated VALUES('changed')")
                conn.commit()
                self.assertEqual(first.revision, inventory.discover()[0].revision)
                conn.execute("INSERT INTO credential VALUES('b','openai',?,0)", (json.dumps({"type": "api", "key": "second"}),))
                conn.commit()
                second = inventory.discover()[0]
            self.assertEqual(2, len(second.records))
            self.assertFalse(second.records[1].active)
            self.assertNotEqual(first.revision, second.revision)

    def test_changed_credentials_discard_old_generation_without_concurrent_refresh(self):
        gate = threading.Event()
        self.addCleanup(gate.set)
        entered = threading.Event()

        class PinnedProvider(OpenAIAccountProvider):
            def get_account_snapshots(inner):
                record = inner.credential_records[0]
                if record.ref.account_id == "old":
                    entered.set()
                    gate.wait(2)
                return (AccountSnapshot(record.ref, 1000, "OpenAI"),)

        def write(identity):
            self.auth.write_text(json.dumps({"openai": {"type": "api", "key": "fixture", "accountId": identity}}))

        write("old")
        engine = AccountAcquisition((PinnedProvider(auth_json_path=str(self.auth)),), "fixture")
        self.addCleanup(engine.close)
        engine.start(1000)
        self.assertTrue(entered.wait(1))
        write("new")
        engine.start(2000)
        self.assertEqual(1, engine.checks_started)
        gate.set()
        snapshots = engine.finish(3000)
        self.assertEqual(["new"], [s.ref.account_id for s in snapshots])

    def test_corrupted_storage_does_not_claim_account_was_signed_out(self):
        self.auth.write_text(json.dumps({"openai": {"type": "api", "key": "fixture"}}))
        engine = AccountAcquisition((OpenAIAccountProvider(auth_json_path=str(self.auth)),), "fixture")
        self.addCleanup(engine.close)
        engine.start(1000)
        engine.finish(1000)
        self.auth.write_text("broken JSON")
        engine.start(2000)
        snapshot = engine.poll(2000).snapshots[0]
        self.assertEqual("error", snapshot.availability)
        self.assertEqual("discovery_failure", snapshot.observations["parser_reason"])


class AcquisitionTests(unittest.TestCase):
    def engine(self, providers, **kwargs):
        engine = AccountAcquisition(providers, "fixture", **kwargs)
        self.addCleanup(engine.close)
        return engine

    def test_worker_cap_incremental_completion_and_no_overlapping_provider(self):
        gates = [threading.Event() for _ in range(7)]
        for gate in gates:
            self.addCleanup(gate.set)
        providers = [Provider(str(i), gate=gate) for i, gate in enumerate(gates)]
        engine = self.engine(providers)
        engine.start(1000)
        self.assertTrue(all(p.entered.wait(1) for p in providers[:4]))
        self.assertFalse(any(p.entered.is_set() for p in providers[4:]))
        engine.start(1100)
        self.assertTrue(all(p.calls == 1 for p in providers[:4]))
        gates[2].set()
        wait_for(lambda: engine.poll(1200) is not None)
        self.assertEqual(["2"], [s.ref.provider_id for s in engine.snapshots])
        self.assertTrue(providers[4].entered.wait(1))
        self.assertEqual(4, len(engine._threads))
        for gate in gates:
            gate.set()
        self.assertEqual(7, len(engine.finish(1300)))

    def test_slow_provider_does_not_block_fast_provider_and_remaining_wait_is_bounded(self):
        gate = threading.Event()
        self.addCleanup(gate.set)
        slow, fast = Provider("slow", gate=gate), Provider("fast")
        engine = self.engine((slow, fast))
        engine.start(1000)
        self.assertTrue(fast.returned.wait(1))
        wait_for(lambda: engine.poll(1000) is not None)
        self.assertEqual(["fast"], [s.ref.provider_id for s in engine.snapshots])
        snapshots = engine.finish(1000, remaining_wait=0)
        self.assertEqual({"available", "error"}, {s.availability for s in snapshots})
        self.assertFalse(next(s for s in snapshots if s.ref.provider_id == "slow").quotas)

    def test_timeout_keeps_worker_slot_and_late_response_cannot_overwrite(self):
        gate = threading.Event()
        self.addCleanup(gate.set)
        provider = Provider("slow", gate=gate)
        clock = [0.0]
        engine = self.engine((provider,), timeout=5, clock=lambda: clock[0])
        engine.start(1000)
        self.assertTrue(provider.entered.wait(1))
        clock[0] = 6
        update = engine.poll(7000)
        self.assertEqual("timeout", update.snapshots[0].observations["parser_reason"])
        for _ in range(10):
            engine.start(7000)
        self.assertEqual(1, provider.calls)
        gate.set()
        self.assertTrue(provider.returned.wait(1))
        wait_for(lambda: (engine.poll(8000), provider.calls == 2)[1])
        self.assertEqual(1, len(engine._threads))
        self.assertEqual(2, engine.finish(8000)[0].fetched_at_ms)

    def test_response_completed_after_deadline_is_rejected_even_when_main_was_busy(self):
        clock = [0.0]
        provider = Provider("slow", callback=lambda: clock.__setitem__(0, 6.0))
        engine = self.engine((provider,), timeout=5, clock=lambda: clock[0])
        engine.start(1000)
        self.assertTrue(provider.returned.wait(1))
        wait_for(lambda: engine.poll(7000) is not None)
        self.assertEqual("timeout", engine.snapshots[0].observations["parser_reason"])
        self.assertFalse(engine.snapshots[0].quotas)

    def test_faults_are_isolated_and_software_error_is_sanitized(self):
        providers = (Provider("good"), Provider("http", failure=OSError("secret")),
                     Provider("broken", failure=RuntimeError("secret")))
        engine = self.engine(providers)
        with patch("src.accounts.acquisition.recoverable") as log:
            engine.start(1000)
            snapshots = engine.finish(1000)
        self.assertEqual(["available", "error", "error"], [s.availability for s in snapshots])
        self.assertEqual(1, log.call_count)
        self.assertNotIn("secret", repr(snapshots))

    def test_close_is_nonblocking_and_discards_post_exit_results(self):
        gate = threading.Event()
        self.addCleanup(gate.set)
        provider = Provider("slow", gate=gate)
        engine = self.engine((provider,))
        engine.start(1000)
        self.assertTrue(provider.entered.wait(1))
        engine.close()
        gate.set()
        self.assertTrue(provider.returned.wait(1))
        self.assertIsNone(engine.poll(2000))
        self.assertFalse(engine.start(2000))
        self.assertEqual((), engine.snapshots)
        self.assertTrue(all(thread.daemon for thread in engine._threads))

    def test_normal_analysis_overlaps_provider_work_and_progress_has_main_thread_ownership(self):
        gate, analyzing = threading.Event(), threading.Event()
        self.addCleanup(gate.set)
        provider = Provider("quota", gate=gate)
        with tempfile.TemporaryDirectory() as td:
            source = MutableSource()
            config, selection, service, _ = make_service(td, source, account_provider=provider, async_accounts=True)
            original = source.list_sessions

            def sessions():
                self.assertTrue(provider.entered.wait(1))
                analyzing.set()
                gate.set()
                return original()

            source.list_sessions = sessions
            threads = []
            service.progress = lambda text: threads.append(threading.get_ident())
            report = service.build(ReportRequest())
        self.assertTrue(analyzing.is_set())
        self.assertEqual(1, len(report.accounts_quotas.accounts))
        self.assertEqual({threading.get_ident()}, set(threads))

    def test_watch_first_view_is_nonblocking_and_accounts_arrive_a_c_b(self):
        gates = [threading.Event() for _ in range(3)]
        for gate in gates:
            self.addCleanup(gate.set)
        providers = [Provider(name, gate=gate) for name, gate in zip(("A", "B", "C"), gates)]
        with tempfile.TemporaryDirectory() as td:
            source = MutableSource()
            config, selection, service, _ = make_service(td, source, account_provider=providers[0], async_accounts=True)
            service.account_providers = tuple(providers)
            self.addCleanup(service.close_accounts)
            watch = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: 2200)
            initial = watch.initialize().projection
            self.assertTrue(initial.rows)
            self.assertFalse(initial.quota.accounts)
            for index, expected in ((0, {"A"}), (2, {"A", "C"}), (1, {"A", "B", "C"})):
                gates[index].set()
                self.assertTrue(providers[index].returned.wait(1))

                def shown():
                    view = watch.status_projection()
                    return {a.account.ref.provider_id for a in view.quota.accounts} == expected

                wait_for(shown)
            self.assertEqual([1, 1, 1], [p.calls for p in providers])

    def test_incremental_results_do_not_refresh_other_accounts_success_timestamps(self):
        from src.watch.accounts import reconcile_accounts
        a, b = Provider("A").get_account_snapshots()[0], Provider("B").get_account_snapshots()[0]
        previous, seen, _ = reconcile_accounts((), (a,), {}, now_ms=1000, observed_keys=(a.key,))
        _, seen, _ = reconcile_accounts(previous, (a, b), seen, now_ms=5000, observed_keys=(b.key,))
        self.assertEqual({a.key: 1000, b.key: 5000}, seen)
        stale = replace(a, availability="stale", reason="Last known capacity")
        values, seen, _ = reconcile_accounts((stale,), (a, b), {a.key: 1000}, now_ms=5000, observed_keys=(b.key,))
        self.assertEqual(stale, values[0])
        self.assertEqual(1000, seen[a.key])

    def test_unrelated_completion_never_spends_or_postpones_recovery_retry(self):
        from src.accounts.acquisition import AccountUpdate
        from unittest.mock import PropertyMock
        with tempfile.TemporaryDirectory() as td:
            config, selection, service, _ = make_service(td, MutableSource())
            wall, monotonic = [100_000], [0.0]
            watch = WatchCoordinator(selection=selection, report_service=service, config=config,
                                     clock_ms=lambda: wall[0], monotonic=lambda: monotonic[0])
            watch.initialize()
            good = watch.accounts.snapshots[0]
            bad = replace(good, availability="error", quotas=(), observations={"parser_reason": "network_failure"})
            other = Provider("other").get_account_snapshots()[0]
            service.poll_account_refresh = lambda: AccountUpdate((bad,), (bad.key,))
            watch.accounts.recovery_until = 60
            watch.accounts.refresh(now_ms=wall[0])
            first_retry, index = watch.accounts.retry_at, watch.accounts.retry_index
            wall[0] += 1000
            monotonic[0] += 1
            service.poll_account_refresh = lambda: AccountUpdate((bad, other), (other.key,))
            with patch.object(type(service), "accounts_pending", new_callable=PropertyMock, return_value=True):
                watch.accounts.refresh(now_ms=wall[0])
            self.assertEqual(first_retry, watch.accounts.retry_at)
            self.assertEqual(index, watch.accounts.retry_index)
            self.assertEqual("stale", watch.accounts.snapshots[0].availability)
            watch.close()

    def test_watch_close_after_first_render_and_no_refresh_after_exit(self):
        gate = threading.Event()
        self.addCleanup(gate.set)
        provider = Provider("slow", gate=gate)
        with tempfile.TemporaryDirectory() as td:
            source = MutableSource()
            config, selection, service, _ = make_service(td, source, account_provider=provider, async_accounts=True)
            watch = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: 2200)

            class Renderer:
                def render(inner, projection):
                    self.assertTrue(projection.rows)
                    self.assertFalse(projection.quota.accounts)
                    raise KeyboardInterrupt

                def finish(inner, _text):
                    pass

            watch.run_forever(Renderer())
            self.assertTrue(watch._closed)
            self.assertIsNone(service._account_work)
            gate.set()
            watch.status_projection()
            self.assertIsNone(service._account_work)


if __name__ == "__main__":
    unittest.main()
