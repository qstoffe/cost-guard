"""Offline regressions for service startup and Watch abort/warning display."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from development.fixtures.session_snapshots import make_snapshot, message, MODEL
from development.fixtures.watch_runtime import MutableSource, make_service
from src import bootstrap
from src.config import load_configuration
from src.domain import CostKind, CostObservation, MessageRole, TokenUsage
from src.presentation import WatchRenderer
from src.sources.errors import SourceUnavailableError
from src.sources.opencode_v1 import _error_name as v1_error_name
from src.sources.opencode_errors import normalize_error_name as v2_error_name
from src.watch import WatchCoordinator

ROOT = Path(__file__).resolve().parents[2]


class StartupTests(unittest.TestCase):
    def test_watch_waits_and_reselects_when_service_appears_without_cli_polling(self):
        selected = object()
        selector = mock.Mock()
        selector.select.side_effect = [SourceUnavailableError("offline"), selected]
        renderer = mock.Mock(interactive=True)
        delays = []
        with mock.patch.object(bootstrap, "SourceSelector", return_value=selector), \
             mock.patch.object(bootstrap.subprocess, "run") as run:
            self.assertIs(bootstrap._wait_for_watch_source("v2", renderer, sleep=delays.append), selected)
        self.assertEqual([5, 5], delays)
        self.assertEqual([mock.call("v2"), mock.call("v2")], selector.select.call_args_list)
        self.assertIn("Waiting for OpenCode source", renderer.render_startup_status.call_args.args[0])
        run.assert_not_called()

    def test_watch_wait_is_cancelable(self):
        renderer = mock.Mock(interactive=True)
        with mock.patch.object(bootstrap, "SourceSelector") as factory:
            with self.assertRaises(KeyboardInterrupt):
                bootstrap._wait_for_watch_source("auto", renderer, sleep=mock.Mock(side_effect=KeyboardInterrupt))
            factory.return_value.select.assert_not_called()

    def test_watch_startup_uses_wait_path_but_normal_report_still_fails_fast(self):
        selection = mock.Mock(selected="v2")
        with mock.patch.object(bootstrap, "load_configuration", return_value=mock.Mock(values={"openCode": {"source": "auto"}})), \
             mock.patch.object(bootstrap, "_select_source", side_effect=SourceUnavailableError("offline")), \
             mock.patch.object(bootstrap, "_wait_for_watch_source", return_value=selection) as wait, \
             mock.patch.object(bootstrap, "WatchRenderer") as renderer, \
             mock.patch.object(bootstrap, "StartupProgress"), \
             mock.patch.object(bootstrap, "CacheDatabase"), \
             mock.patch.object(bootstrap, "ReportService"), \
             mock.patch.object(bootstrap, "WatchCoordinator") as coordinator, \
             mock.patch.object(bootstrap, "_print_error"):
            renderer.return_value.interactive = True
            self.assertEqual(0, bootstrap.main(["--watch"]))
            wait.assert_called_once_with("auto", renderer.return_value)
            coordinator.return_value.run_forever.assert_called_once()
            self.assertEqual(1, bootstrap.main([]))
            wait.assert_called_once()

    def test_offline_auto_wakes_shared_service_once_then_selects_v2(self):
        selected = object()
        selector = mock.Mock()
        selector.select.side_effect = [SourceUnavailableError("no source"), selected]
        with mock.patch.object(bootstrap, "SourceSelector", return_value=selector), \
             mock.patch.object(bootstrap.shutil, "which", return_value="opencode"), \
             mock.patch.object(bootstrap.subprocess, "run", return_value=mock.Mock(returncode=0)) as run:
            self.assertIs(bootstrap._select_source("auto"), selected)
        self.assertEqual([mock.call("auto"), mock.call("auto")], selector.select.call_args_list)
        self.assertEqual(["opencode", "api", "get", "/api/info"], run.call_args.args[0])
        self.assertEqual(20, run.call_args.kwargs["timeout"])
        self.assertEqual(bootstrap.subprocess.DEVNULL, run.call_args.kwargs["stderr"])

    def test_healthy_selection_and_forced_v1_do_not_start_cli(self):
        selector = mock.Mock()
        selected = object()
        selector.select.side_effect = [selected, SourceUnavailableError("V1 missing")]
        with mock.patch.object(bootstrap, "SourceSelector", return_value=selector), \
             mock.patch.object(bootstrap.subprocess, "run") as run:
            self.assertIs(bootstrap._select_source("auto"), selected)
            with self.assertRaises(SourceUnavailableError):
                bootstrap._select_source("v1")
        run.assert_not_called()

    def test_windows_cmd_shim_uses_comspec_without_a_shell(self):
        selector = mock.Mock()
        selector.select.side_effect = [SourceUnavailableError("offline"), object()]
        with mock.patch.object(bootstrap, "SourceSelector", return_value=selector), \
             mock.patch.object(bootstrap.shutil, "which", return_value=r"C:\tools\opencode.cmd"), \
             mock.patch.dict(bootstrap.os.environ, {"COMSPEC": r"C:\Windows\System32\cmd.exe"}), \
             mock.patch.object(bootstrap.subprocess, "run", return_value=mock.Mock(returncode=0)) as run:
            bootstrap._select_source("v2")
        command = run.call_args.args[0]
        self.assertEqual([r"C:\Windows\System32\cmd.exe", "/d", "/s", "/c"], command[:4])
        self.assertIn("opencode.cmd", command[4])
        self.assertIn("/api/info", command[4])

    def test_cli_failure_is_bounded_and_does_not_expose_cli_output(self):
        with mock.patch.object(bootstrap, "SourceSelector") as factory, \
             mock.patch.object(bootstrap.shutil, "which", return_value="opencode"), \
             mock.patch.object(bootstrap.subprocess, "run", return_value=mock.Mock(returncode=1)):
            factory.return_value.select.side_effect = SourceUnavailableError("offline")
            with self.assertRaisesRegex(SourceUnavailableError, "background service could not be started"):
                bootstrap._select_source("v2")
            factory.return_value.select.assert_called_once_with("v2")


class AbortAndWarningTests(unittest.TestCase):
    def test_earlier_aborted_attempt_does_not_abort_successful_prompt(self):
        from src.analysis.causal import build_prompt_records
        snapshot = make_snapshot()
        earlier = message(
            "a_failed", "root", MessageRole.ASSISTANT, 2050, parent="u_next",
            completed=2070, model=MODEL, error="AbortedError",
        )
        snapshot = replace(snapshot, messages=snapshot.messages + (earlier,))
        record = next(p for p in build_prompt_records(snapshot, now_ms=4000) if p.prompt_id == "u_next")
        self.assertFalse(record.aborted)
        self.assertFalse(record.in_progress)
        self.assertEqual(Decimal("0.30"), record.cost)

        terminal_failure = replace(
            snapshot, messages=tuple(
                replace(item, error_name="AbortedError") if item.message_id == "a_next" else item
                for item in snapshot.messages
            ),
        )
        failed = next(p for p in build_prompt_records(terminal_failure, now_ms=4000) if p.prompt_id == "u_next")
        self.assertTrue(failed.aborted)

    def test_generic_error_with_abort_message_is_normalized_without_exposing_text(self):
        error = {"name": "Error", "message": "Request aborted by user"}
        for normalize in (v1_error_name, v2_error_name):
            self.assertEqual("AbortedError", normalize(error))
            self.assertEqual("ProviderError", normalize({"name": "ProviderError", "message": "bad request"}))

    def test_shared_parser_reads_only_safe_cancellation_fields(self):
        self.assertIs(v1_error_name, v2_error_name)
        for normalize in (v1_error_name, v2_error_name):
            self.assertIsNone(normalize(None))
            self.assertEqual("AbortedError", normalize("MessageAbortedError"))
            self.assertEqual("AbortedError", normalize({"name": "UnknownError", "data": {"message": "Aborted"}}))
            for error in (
                {"name": "ProviderError", "message": "request was not aborted"},
                {"name": "ProviderError", "message": "timeout", "stack": "Aborted"},
                {"name": "ProviderError", "data": {"payload": {"message": "Aborted"}}},
                {"name": "ProviderError", "message": "authentication failure after aborted request"},
            ):
                self.assertEqual("ProviderError", normalize(error))

    def test_watch_aborted_label_survives_truncation_and_red_ages_out(self):
        with tempfile.TemporaryDirectory() as td:
            source = MutableSource(make_snapshot(running=True))
            config, selection, service, _ = make_service(td, source)
            clock = [2200]
            watch = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: clock[0])
            watch.initialize()
            finished = make_snapshot(running=False)
            messages = tuple(
                replace(item, error_name="AbortedError") if item.message_id == "a_next" else item
                for item in finished.messages
            )
            source.snapshot = replace(finished, messages=messages, source_revision="abort")
            clock[0] = 2400
            recent = next(row for row in watch.poll_once().projection.rows if row.prompt.event_id == "u_next")
            self.assertTrue(recent.prompt.aborted)
            self.assertEqual("!", recent.marker)
            renderer = WatchRenderer(config, stream=io.StringIO(), interactive=True)
            self.assertEqual("costQuotaCritical", renderer._row_style(recent))
            long_prompt = replace(recent, prompt=replace(recent.prompt, preview="x" * 80))
            self.assertIn("! #2 [ABORTED]", renderer._row_label(long_prompt)[:35])
            clock[0] = 32_401
            aged = next(row for row in watch.poll_once().projection.rows if row.prompt.event_id == "u_next")
            self.assertEqual("", aged.marker)
            self.assertIsNone(renderer._row_style(aged))
            self.assertIn("[ABORTED]", renderer._row_label(aged))

    def test_zero_usage_generic_error_is_not_misclassified_as_abort(self):
        from src.analysis.causal import build_prompt_records
        snapshot = make_snapshot()
        messages = tuple(replace(m, error_name="ProviderError") if m.message_id == "a_next" else m for m in snapshot.messages)
        invocations = tuple(
            replace(i, tokens=TokenUsage(), cost=CostObservation(Decimal(0), "USD", CostKind.PROVIDER_REPORTED))
            if i.invocation_id == "i_next" else i for i in snapshot.invocations
        )
        record = next(p for p in build_prompt_records(replace(snapshot, messages=messages, invocations=invocations), now_ms=4000) if p.prompt_id == "u_next")
        self.assertFalse(record.aborted)
        self.assertTrue(record.watch_error)

    def test_watch_retains_recent_quota_on_transient_failure_but_not_indefinitely(self):
        with tempfile.TemporaryDirectory() as td:
            source = MutableSource(make_snapshot(running=False))
            config, selection, service, _ = make_service(td, source)
            clock = [100_000]
            watch = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: clock[0])
            initial = watch.initialize().projection
            self.assertTrue(initial.quota.accounts)
            with mock.patch.object(service, "account_quota_snapshots", return_value=()):
                clock[0] += 60_001
                recent = watch.poll_once().projection
                self.assertEqual(initial.quota.accounts[0].account.quotas, recent.quota.accounts[0].account.quotas)
                self.assertTrue(recent.quota_stale)
                stream = io.StringIO()
                WatchRenderer(config, stream=stream, interactive=False).render(recent)
                self.assertIn("last known account values", stream.getvalue())
                self.assertIn("Month", stream.getvalue())
                for _ in range(5):
                    clock[0] += 60_001  # ordinary runtime, not a simulated sleep
                    expired = watch.poll_once().projection
                self.assertFalse(expired.quota.accounts[0].account.quotas)
                self.assertFalse(expired.quota_stale)
                self.assertFalse(expired.quota_recovering_accounts)

    def test_explicit_unavailable_quota_is_not_replaced_by_old_values(self):
        with tempfile.TemporaryDirectory() as td:
            source = MutableSource(make_snapshot(running=False))
            config, selection, service, _ = make_service(td, source)
            clock = [100_000]
            watch = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: clock[0])
            initial = watch.initialize().projection
            unavailable = replace(watch.accounts.snapshots[0], availability="unavailable", quotas=())
            with mock.patch.object(service, "account_quota_snapshots", return_value=(unavailable,)):
                clock[0] += 60_001
                current = watch.poll_once().projection
            self.assertNotEqual(initial.quota.accounts, current.quota.accounts)
            self.assertFalse(current.quota_stale)

    def test_paused_triangle_has_two_spaces_and_role_in_watch(self):
        config = load_configuration(ROOT).values
        with tempfile.TemporaryDirectory() as td:
            source = MutableSource()
            _cfg, selection, service, _ = make_service(td, source)
            projection = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: 2200).initialize().projection
            self.assertIsNotNone(projection.quota)
            account = projection.quota.accounts[0]
            account = replace(account, account=replace(account.account, warnings=("⚠  COPILOT PAUSED: GitHub reported hasQuota=false.",)))
            projection = replace(projection, quota=replace(projection.quota, accounts=(account,)))
            stream = io.StringIO()
            renderer = WatchRenderer(config, stream=stream, interactive=True)
            renderer.render(projection)
            self.assertIn(renderer.styler.apply("⚠  COPILOT PAUSED: GitHub reported hasQuota=false.", "copilotPausedWarning"), stream.getvalue())


class _RecoveryClock:
    def __init__(self):
        self.wall = 100_000
        self.monotonic = 0.0

    def advance(self, seconds):
        self.wall += int(seconds * 1000)
        self.monotonic += seconds


class QuotaResumeRecoveryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.clock = _RecoveryClock()
        self.source = MutableSource(make_snapshot(running=False))
        self.config, self.selection, self.service, _ = make_service(temp.name, self.source)
        self.watch = WatchCoordinator(selection=self.selection, report_service=self.service, config=self.config,
                                      clock_ms=lambda: self.clock.wall, monotonic=lambda: self.clock.monotonic,
                                      sleep=self.clock.advance)
        self.initial = self.watch.initialize().projection
        self.good = self.watch.accounts.snapshots[0]
        self.error = replace(self.good, availability="error", quotas=(), billing=(),
                             observations={"parser_reason": "network_failure"})
        patcher = mock.patch.object(self.service, "account_quota_snapshots", return_value=(self.error,))
        self.fetch = patcher.start()
        self.addCleanup(patcher.stop)

    def wake(self):
        self.clock.advance(600)
        return self.watch.poll_once().projection

    def test_expired_wake_capacity_is_stale_then_success_ends_recovery_immediately(self):
        resumed = self.wake()
        self.assertEqual(self.good.quotas, resumed.quota.accounts[0].account.quotas)
        self.assertTrue(resumed.quota_stale)
        self.assertEqual((self.good.key,), resumed.quota_recovering_accounts)
        self.assertEqual(100_000, self.watch.accounts.seen_ms[self.good.key])
        self.assertEqual(self.good.fetched_at_ms, resumed.quota.accounts[0].account.fetched_at_ms)
        stream = io.StringIO()
        WatchRenderer(self.config, stream=stream, interactive=False).render(resumed)
        self.assertIn("STALE / RECONNECTING", stream.getvalue())
        self.assertNotIn("up to 5 min old", stream.getvalue())
        self.assertNotIn("ERROR", stream.getvalue())
        self.fetch.return_value = (self.good,)
        self.clock.advance(5)
        recovered = self.watch.poll_once().projection
        self.assertFalse(recovered.quota_stale)
        self.assertFalse(recovered.quota_recovering_accounts)
        self.assertIsNone(self.watch.accounts.recovery_until)
        self.assertEqual(705_000, self.watch.accounts.seen_ms[self.good.key])
        stream = io.StringIO()
        WatchRenderer(self.config, stream=stream, interactive=False).render(recovered)
        self.assertNotIn("recovering", stream.getvalue())
        self.assertNotIn("STALE", stream.getvalue())
        self.clock.advance(59)
        self.watch.poll_once()
        self.assertEqual(2, self.fetch.call_count)
        self.clock.advance(1)
        self.watch.poll_once()
        self.assertEqual(3, self.fetch.call_count)

    def test_retry_backoff_expiry_and_source_hints_cannot_amplify_requests(self):
        self.wake()
        self.assertEqual(5, self.watch._wait_delay_seconds(0))
        for elapsed in range(1, 61):
            self.clock.advance(1)
            self.source.snapshot = replace(self.source.snapshot, source_revision=f"activity-{elapsed}")
            cycle = self.watch.poll_once(hinted_session_ids=("root",))
            expected = 1 + sum(elapsed >= t for t in (5, 15, 35))
            self.assertEqual(expected, self.fetch.call_count, f"retry at {elapsed}s")
        expired = cycle.projection
        self.assertFalse(expired.quota_recovering_accounts)
        self.assertFalse(expired.quota_stale)
        self.assertFalse(expired.quota.accounts[0].account.quotas)
        self.assertEqual(100_000, self.watch.accounts.seen_ms[self.good.key])
        self.clock.advance(34)
        self.watch.poll_once()
        self.assertEqual(4, self.fetch.call_count)
        self.clock.advance(1)
        self.watch.poll_once()
        self.assertEqual(5, self.fetch.call_count, "normal minute from last recovery request")

    def test_auth_or_explicit_unavailable_has_no_fast_retry_or_old_capacity(self):
        for availability, observations in (("error", {"http_status": 401}),
                                           ("error", {"http_status": 403}),
                                           ("error", {"parser_reason": "auth_failure"}),
                                           ("unavailable", {})):
            self.fetch.return_value = (replace(self.error, availability=availability, observations=observations),)
            resumed = self.wake()
            self.assertFalse(resumed.quota.accounts[0].account.quotas)
            self.assertFalse(resumed.quota_recovering_accounts)
            calls = self.fetch.call_count
            self.clock.advance(30)
            self.watch.poll_once()
            self.assertEqual(calls, self.fetch.call_count)

    def test_slow_provider_processing_and_ordinary_waits_do_not_trigger_recovery(self):
        def slow_success():
            self.clock.advance(180)
            return (self.good,)
        self.fetch.side_effect = slow_success
        self.clock.advance(60)
        completed = self.watch.poll_once().projection
        self.assertFalse(completed.quota_recovering_accounts)
        self.assertIsNone(self.watch.accounts.recovery_until)
        self.fetch.side_effect = None
        self.fetch.return_value = (self.good,)
        self.clock.advance(30)
        self.watch.poll_once()
        self.assertEqual(1, self.fetch.call_count)
        self.assertIsNone(self.watch.accounts.recovery_until)
        self.watch.interval_seconds = 120
        self.watch.idle_interval_seconds = 360
        self.clock.advance(360)
        self.watch.poll_once()
        self.assertIsNone(self.watch.accounts.recovery_until, "configured long waits are not scheduling gaps")

    def test_wait_wakes_on_wall_gap_even_when_monotonic_excludes_os_sleep(self):
        def suspend(_seconds):
            self.clock.wall += 600_000
        self.watch.sleep = suspend
        self.watch._v1_wait(mock.Mock())
        self.assertIsNotNone(self.watch.accounts.recovery_until)
        deadline = self.watch.accounts.recovery_until
        resumed = self.watch.poll_once().projection
        self.assertTrue(resumed.quota_recovering_accounts)
        self.assertEqual(deadline, self.watch.accounts.recovery_until, "one gap must not re-arm grace")
        self.watch.sleep = self.clock.advance
        start = self.clock.monotonic
        self.watch._v1_wait(mock.Mock())
        self.assertEqual(5, self.clock.monotonic - start)

    def test_no_usable_previous_values_get_retrying_not_permanent_error(self):
        # Start a second Watch while this provider is already offline.
        watch = WatchCoordinator(selection=self.selection, report_service=self.service, config=self.config,
                                  clock_ms=lambda: self.clock.wall, monotonic=lambda: self.clock.monotonic)
        watch.initialize()
        self.clock.advance(600)
        resumed = watch.poll_once().projection
        self.assertTrue(resumed.quota_recovering_accounts)
        stream = io.StringIO()
        WatchRenderer(self.config, stream=stream, interactive=False, terminal_width=40).render(resumed)
        self.assertIn("Quota temporarily unavailable", stream.getvalue())
        self.assertIn("Retrying...", stream.getvalue())
        self.assertNotIn("ERROR", stream.getvalue())

    def new_watch(self):
        return WatchCoordinator(selection=self.selection, report_service=self.service, config=self.config,
                                clock_ms=lambda: self.clock.wall, monotonic=lambda: self.clock.monotonic)

    def test_startup_error_without_capacity_gets_bounded_retries_once(self):
        self.fetch.return_value = (replace(self.error, observations={"parser_reason": "timeout"}),)
        watch = self.new_watch()
        started = watch.initialize().projection
        self.assertEqual((self.good.key,), started.quota_recovering_accounts)
        stream = io.StringIO()
        WatchRenderer(self.config, stream=stream, interactive=False, terminal_width=200).render(started)
        self.assertIn("Quota temporarily unavailable (timed out) · Retrying...", stream.getvalue())
        self.assertNotIn("Quota error", stream.getvalue())
        self.assertEqual(5, watch._wait_delay_seconds(0))
        for elapsed in range(1, 61):
            self.clock.advance(1)
            cycle = watch.poll_once()
            self.assertEqual(1 + sum(elapsed >= t for t in (5, 15, 35)), self.fetch.call_count, f"retry at {elapsed}s")
        self.assertFalse(cycle.projection.quota_recovering_accounts)
        self.clock.advance(60)
        watch.poll_once()
        self.assertEqual(5, self.fetch.call_count)
        self.assertIsNone(watch.accounts.recovery_until, "one startup retry window per account")

    def test_startup_retry_ends_on_success_and_skips_durable_failures(self):
        watch = self.new_watch()
        watch.initialize()
        self.fetch.return_value = (self.good,)
        self.clock.advance(5)
        recovered = watch.poll_once().projection
        self.assertFalse(recovered.quota_recovering_accounts)
        self.assertIsNone(watch.accounts.retry_at)
        self.assertEqual("available", recovered.quota.accounts[0].account.availability)
        for observations in ({"parser_reason": "auth_failure"}, {"http_status": 401}):
            self.fetch.return_value = (replace(self.error, observations=observations),)
            calls = self.fetch.call_count
            watch = self.new_watch()
            self.assertFalse(watch.initialize().projection.quota_recovering_accounts)
            self.clock.advance(30)
            watch.poll_once()
            self.assertEqual(calls + 1, self.fetch.call_count)

    def test_v2_wait_honors_recovery_deadline_without_event_request_amplification(self):
        self.wake()
        pump = mock.Mock()
        pump.get.side_effect = lambda timeout: self.clock.advance(timeout)
        self.watch._event_pump = pump
        started = self.clock.monotonic
        resync, hints = self.watch._v2_wait(mock.Mock())
        self.assertFalse(resync)
        self.assertFalse(hints)
        self.assertEqual(5, self.clock.monotonic - started)
        self.assertEqual(1, self.fetch.call_count, "waiting cannot query provider quota")
        self.watch.poll_once()
        self.assertEqual(2, self.fetch.call_count)

    def test_mixed_accounts_recover_independently_and_expiry_is_not_an_observation(self):
        other = replace(self.good, ref=replace(self.good.ref, account_id="other"))
        self.watch.accounts.snapshots = (self.good, other)
        self.watch.accounts.seen_ms[other.key] = 100_000
        self.fetch.return_value = (self.good, replace(self.error, ref=other.ref))
        resumed = self.wake()
        self.assertEqual((other.key,), resumed.quota_recovering_accounts)
        by_key = {row.account.key: row.account for row in resumed.quota.accounts}
        self.assertEqual("available", by_key[self.good.key].availability)
        self.assertEqual("stale", by_key[other.key].availability)
        for delay in (5, 10, 20, 25):
            self.clock.advance(delay)
            expired = self.watch.poll_once().projection
        self.assertFalse(expired.quota_recovering_accounts)
        self.assertEqual(735_000, self.watch.accounts.seen_ms[self.good.key])
        self.assertEqual(100_000, self.watch.accounts.seen_ms[other.key])
        expired_by_key = {row.account.key: row.account for row in expired.quota.accounts}
        self.assertFalse(expired_by_key[other.key].quotas)
        self.assertEqual(4, self.fetch.call_count)

    def test_successful_first_wake_refresh_never_enters_visible_recovery(self):
        self.fetch.return_value = (self.good,)
        resumed = self.wake()
        self.assertFalse(resumed.quota_recovering_accounts)
        self.assertFalse(resumed.quota_stale)
        self.assertIsNone(self.watch.accounts.retry_at)
        self.assertEqual(1, self.fetch.call_count)

    def test_grace_deadline_is_bounded_even_if_request_takes_longer_than_grace(self):
        def slow_failure():
            self.clock.advance(70)
            return (self.error,)
        self.fetch.side_effect = slow_failure
        resumed = self.wake()
        self.assertFalse(resumed.quota_recovering_accounts)
        self.assertFalse(resumed.quota.accounts[0].account.quotas)
        self.assertIsNone(self.watch.accounts.recovery_until)
        self.assertEqual(1, self.fetch.call_count)


if __name__ == "__main__":
    unittest.main()
