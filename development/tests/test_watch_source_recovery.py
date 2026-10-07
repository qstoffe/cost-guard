"""Watch keeps running across transient failures of its already-selected source."""
from __future__ import annotations

import io
import json
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from development.tests.test_analysis_core import make_snapshot
from development.tests.test_opencode_v2 import FakeV2Service, fixture, source_with_service
from development.tests.test_step8_watch import CountingAccountProvider, FakeLiveSource, MutableSource, make_service
from src.presentation import WatchRenderer
from src.sources.errors import SourceDataError, SourceError, SourceSchemaError, SourceUnavailableError
from src.sources.selection import MigrationGapDiagnostic, MigrationGapSession
from src.watch import WatchCoordinator
from src.watch.coordinator import SOURCE_RETRY_SECONDS, SOURCE_UNREADABLE_RETRIES

ROOT = Path(__file__).resolve().parents[2]


class FailingMixin:
    """Raise one normalized source failure from every read while ``failure`` is set."""

    failure: SourceError | None = None
    reads = 0

    def _check(self):
        self.reads += 1
        if self.failure is not None:
            raise self.failure

    def list_sessions(self, since_ms=None):
        self._check()
        return super().list_sessions(since_ms)

    def get_session_tree_revisions(self, session_ids):
        self._check()
        return super().get_session_tree_revisions(session_ids)

    def load_session_snapshot(self, session_id):
        self._check()
        return super().load_session_snapshot(session_id)


class FailingV1(FailingMixin, MutableSource):
    pass


class FailingV2(FailingMixin, FakeLiveSource):
    pass


class Recorder:
    def __init__(self):
        self.renders, self.statuses, self.finished = [], [], []

    def render(self, projection):
        self.renders.append(projection)

    def render_status(self, projection):
        self.statuses.append(projection)

    def finish(self, text):
        self.finished.append(text)


def _forbid_subprocess():
    def fail(*_args, **_kwargs):
        raise AssertionError("source recovery must not start a subprocess")
    return mock.patch.multiple(subprocess, run=fail, Popen=fail)


class WatchSourceRecoveryTests(unittest.TestCase):
    def _watch(self, td, source, *, account=None, clock=None):
        config, selection, service, _db = make_service(td, source, account_provider=account)
        clock = clock if clock is not None else [2200]
        sleeps: list[float] = []
        watch = WatchCoordinator(selection=selection, report_service=service, config=config,
                                 clock_ms=lambda: clock[0], sleep=sleeps.append)
        return watch, sleeps, clock

    def test_v2_resync_failure_retains_dashboard_and_recovers_from_fresh_snapshot(self):
        with tempfile.TemporaryDirectory() as td, _forbid_subprocess():
            source = FailingV2()
            account = CountingAccountProvider()
            watch, sleeps, clock = self._watch(td, source, account=account)
            initial = watch.initialize()
            running = [row.prompt.event_id for row in initial.projection.rows if row.prompt.in_progress]
            self.assertTrue(running)
            account_calls, loads = account.calls, source.load_count
            calls_during: list[int] = []
            source.failure = SourceUnavailableError("OpenCode V2 service could not be reached")

            def sleep(seconds):
                sleeps.append(seconds)
                calls_during.append(account.calls)
                clock[0] += int(seconds * 1000) + 60_000  # a long outage must not arm quota resume
                if len(sleeps) == 3:
                    source.failure = None
                    source.snapshot = replace(make_snapshot(generation="v2", running=False), source_revision="fresh")
            watch.sleep = sleep
            renderer = Recorder()
            pumps = []
            with mock.patch.object(watch, "_v2_wait", return_value=(True, ())), \
                 mock.patch.object(watch, "_start_event_pump", side_effect=lambda: pumps.append(1)):
                cycle = watch._advance(renderer, initial)

            entry = renderer.renders[0]
            self.assertEqual("OpenCode V2 source unavailable · retrying every 5s", entry.status)
            self.assertEqual(initial.projection.rows, entry.rows, "the last dashboard stays visible")
            self.assertEqual(running, [row.prompt.event_id for row in entry.rows if row.prompt.in_progress],
                             "transport failure never completes a prompt")
            self.assertTrue(all("retrying every 5s" in item.status for item in renderer.statuses[1:3]))
            self.assertEqual([SOURCE_RETRY_SECONDS] * 3, sleeps, "bounded cadence, no busy loop")
            self.assertEqual([account_calls] * 3, calls_during, "source retries never query account providers")
            self.assertEqual(account_calls + 1, account.calls, "only the normal minute cadence refreshes after recovery")
            self.assertIsNone(watch._quota_recovery_until, "an observed outage is not a suspend/resume gap")
            self.assertTrue(cycle.recovered and cycle.resynced)
            self.assertEqual([1], pumps, "the event pump restarts after the authoritative snapshot")
            self.assertGreater(source.load_count, loads)
            self.assertFalse(any(row.prompt.in_progress for row in cycle.projection.rows), "fresh snapshot applied")
            self.assertIn("Next prompt check", cycle.projection.status)
            self.assertIs(source, watch.source)
            self.assertEqual("v2", watch.selection.selected)
            self.assertEqual((1, "unavailable"), (watch.source_recoveries, watch.last_source_recovery_kind))
            self.assertIs(cycle.projection, renderer.renders[-1], "recovery ends with a full fresh render")

    def test_v2_first_resync_success_keeps_normal_path(self):
        with tempfile.TemporaryDirectory() as td:
            source = FailingV2()
            watch, sleeps, _clock = self._watch(td, source)
            initial = watch.initialize()
            pumps = []
            with mock.patch.object(watch, "_v2_wait", return_value=(True, ())), \
                 mock.patch.object(watch, "_start_event_pump", side_effect=lambda: pumps.append(1)):
                cycle = watch._advance(Recorder(), initial)
            self.assertEqual(([], [1], 0), (sleeps, pumps, watch.source_recoveries))
            self.assertTrue(cycle.resynced)
            self.assertFalse(cycle.recovered)

    def test_v1_read_failure_retries_same_source_without_generation_switch(self):
        with tempfile.TemporaryDirectory() as td, _forbid_subprocess():
            source = FailingV1(make_snapshot(running=False))
            watch, sleeps, _clock = self._watch(td, source)
            initial = watch.initialize()
            source.failure = SourceUnavailableError("OpenCode V1 database could not be opened read-only")

            def sleep(seconds):
                sleeps.append(seconds)
                source.failure = None
            watch.sleep = sleep
            renderer = Recorder()
            with mock.patch.object(watch, "_v1_wait"), \
                 mock.patch("src.sources.selection.SourceSelector.select", side_effect=AssertionError("no reselection")):
                cycle = watch._advance(renderer, initial)
            self.assertEqual("OpenCode V1 source unavailable · retrying every 5s", renderer.renders[0].status)
            self.assertTrue(cycle.recovered)
            self.assertFalse(cycle.resynced)
            self.assertIsNone(watch._event_pump)
            self.assertEqual(("v1", source), (watch.selection.selected, watch.source))
            self.assertEqual("V1", cycle.projection.source_label)

    def test_unsupported_schema_ends_watch_visibly_without_retry(self):
        with tempfile.TemporaryDirectory() as td:
            source = FailingV1(make_snapshot(running=False))
            watch, sleeps, _clock = self._watch(td, source)
            initial = watch.initialize()
            source.failure = SourceSchemaError("OpenCode V1 message schema is not supported")
            renderer = Recorder()
            with mock.patch.object(watch, "_v1_wait"):
                with self.assertRaises(SourceSchemaError):
                    watch.run_forever(renderer, initial_cycle=initial)
            self.assertEqual([], sleeps)
            self.assertEqual(["Watch stopped: OpenCode V1 source failed."], renderer.finished)

    def test_unreadable_data_retries_boundedly_then_fails(self):
        with tempfile.TemporaryDirectory() as td:
            source = FailingV2()
            watch, sleeps, _clock = self._watch(td, source)
            initial = watch.initialize()
            source.failure = SourceDataError("OpenCode V2 session changed repeatedly while it was being read")
            renderer = Recorder()
            with mock.patch.object(watch, "_v2_wait", return_value=(False, ())):
                with self.assertRaises(SourceDataError):
                    watch.run_forever(renderer, initial_cycle=initial)
            self.assertEqual(SOURCE_UNREADABLE_RETRIES, len(sleeps))
            self.assertEqual("OpenCode V2 source unreadable · retrying every 5s", renderer.renders[1].status)
            self.assertEqual(["Watch stopped: OpenCode V2 source failed."], renderer.finished)

    def test_bootstrap_reports_terminal_watch_failure_as_nonzero_exit(self):
        from src import bootstrap

        class Coordinator:
            def __init__(self, **_kwargs):
                pass

            def initialize(self):
                return None

            def run_forever(self, *_args, **_kwargs):
                raise SourceSchemaError("OpenCode V1 message schema is not supported")

        selection = mock.Mock(selected="v1", warnings=(), source=mock.Mock())
        stdout = io.StringIO()
        with mock.patch.object(bootstrap, "_select_source", return_value=selection), \
             mock.patch.object(bootstrap, "WatchCoordinator", Coordinator), \
             mock.patch.object(bootstrap, "ReportService"), mock.patch.object(bootstrap, "CacheDatabase"), \
             mock.patch.object(bootstrap, "CacheRepository"), \
             mock.patch.object(bootstrap, "GitHubCopilotPricingProvider"), \
             mock.patch.object(bootstrap, "_account_providers", return_value=()), \
             mock.patch("sys.stdout", stdout):
            code = bootstrap.main(["--watch"])
        self.assertEqual(1, code)
        self.assertIn("Cost Guard - Runtime error", stdout.getvalue())
        self.assertIn("schema is not supported", stdout.getvalue())

    def test_source_warnings_and_migration_gap_never_drive_lifecycle(self):
        with tempfile.TemporaryDirectory() as td:
            source = FailingV2()
            watch, sleeps, _clock = self._watch(td, source)
            gap = MigrationGapDiagnostic(True, ("old",), sessions=(MigrationGapSession("old", "old", "missing_in_v2", 1, 2),))
            watch.selection = replace(watch.selection, warnings=("OpenCode V2 was unavailable earlier",), migration_gap=gap)
            projection = watch.initialize().projection
            reads = source.reads
            stream = io.StringIO()
            renderer = WatchRenderer(watch.config, stream=stream, interactive=False)
            for _ in range(3):
                renderer.render(watch.status_projection(seconds_until_check=5))
            self.assertEqual(reads, source.reads, "rendering warnings performs no source reads")
            self.assertEqual(("OpenCode V2 was unavailable earlier",), projection.source_warnings)
            self.assertNotIn("migration", stream.getvalue().lower())
            self.assertEqual(([], 0), (sleeps, watch.source_recoveries))

    def test_v2_source_rereads_rewritten_service_registration(self):
        with source_with_service() as (source, first, registration):
            source.list_sessions()
            first.__exit__()
            with self.assertRaises(SourceUnavailableError):
                source.list_sessions()
            with FakeV2Service(fixture(), password="restarted") as second:
                registration.write_text(json.dumps({
                    "url": second.url, "pid": 4343, "version": "2.0.18", "password": "restarted", "restarted": True,
                }), encoding="utf-8")
                self.assertTrue(source.list_sessions())
                self.assertTrue(second.requests)
            first.__enter__()  # let the fixture context shut down a live server


class WatchLauncherExitTests(unittest.TestCase):
    def test_windows_watch_launcher_preserves_only_unexpected_exit(self):
        text = (ROOT / "windows/Cost Guard Watch.cmd").read_text(encoding="utf-8")
        command = text.split('start "Cost Guard Watch" powershell.exe', 1)[1].splitlines()[0]
        self.assertNotIn("-NoExit", command, "a clean stop must still close the window")
        self.assertIn("$code = $LASTEXITCODE; if ($code)", command)
        self.assertIn("'Cost Guard Watch exited unexpectedly (code ' + $code + ').'", command)
        self.assertIn("Read-Host 'Press Enter to close'", command)
        self.assertLess(command.index("--watch"), command.index("exited unexpectedly"),
                        "the launcher message follows Cost Guard's own output")
        self.assertIn("exit $code", command)


if __name__ == "__main__":
    unittest.main()
