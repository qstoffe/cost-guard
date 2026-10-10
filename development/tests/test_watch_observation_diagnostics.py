"""Bounded, privacy-safe Watch diagnostics regression tests."""
from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from development.fixtures.opencode_v2_service import source_with_current_service
from development.tests.test_session_move import completed_history
from development.fixtures.watch_runtime import MutableSource, make_service
from src.watch import WatchCoordinator
from src.watch import coordinator as watch_coordinator
from src.watch import observation_diagnostics as observations
from src.watch import recovery_events


@contextmanager
def recording():
    with tempfile.TemporaryDirectory() as tmp, patch.object(observations, "FILE", Path(tmp) / "watch.json"), \
            patch.dict(observations._last_scan, clear=True), patch.dict("os.environ", {"COST_GUARD_TEST_MODE": ""}):
        yield


class WatchObservationTests(unittest.TestCase):
    def test_empty_watch_reports_filtered_existing_history_without_ids(self):
        with recording():
            session = SimpleNamespace(active=False)
            prompt = SimpleNamespace(in_progress=False, at_ms=100)
            observed = SimpleNamespace(sessions=(session,), roots=(session,))
            observations.record_scan("v2", observed, {"private-session-id": SimpleNamespace(rows=(prompt,))}, (), 200)
            event = observations.recent_events()[0]
            self.assertEqual(("no_eligible_prompts", 1, 0),
                             (event["reason"], event["older_completed"], event["visible_prompts"]))
            self.assertNotIn("private-session-id", observations.FILE.read_text(encoding="utf-8"))

    def test_unreadable_stage_is_recorded_without_native_payload(self):
        with recording():
            provider = SimpleNamespace(diagnostic_metadata=lambda: {"last_snapshot_stage": "revision_changed", "secret": "DO_NOT_INCLUDE"})
            observations.record_source_error("v2", "unreadable", provider)
            event = observations.recent_events()[0]
            self.assertEqual(("source_error", "unreadable", "revision_changed"),
                             (event["event"], event["kind"], event["phase"]))
            self.assertNotIn("DO_NOT_INCLUDE", observations.FILE.read_text(encoding="utf-8"))

    def test_unchanged_refresh_does_not_touch_the_file(self):
        with recording():
            empty = SimpleNamespace(sessions=(), roots=())
            observations.record_scan("v2", empty, {}, (), 0)
            with patch.object(observations, "recent_events", side_effect=AssertionError("file read")):
                for _ in range(3):
                    observations.record_scan("v2", empty, {}, (), 0)
            self.assertEqual(1, len(observations.recent_events()))

    def test_busy_scans_never_evict_rarer_source_errors(self):
        with recording():
            observations.record_source_error("v2", "unavailable", SimpleNamespace(diagnostic_metadata=lambda: {"last_snapshot_stage": "catalog"}))
            for count in range(40):
                sessions = tuple(SimpleNamespace(active=False) for _ in range(count))
                observations.record_scan("v2", SimpleNamespace(sessions=sessions, roots=()), {}, (), 0)
            events = observations.recent_events()
            self.assertEqual(["catalog"], [item["phase"] for item in events if item["event"] == "source_error"])
            self.assertLessEqual(len(events), 24)

    def test_malformed_file_values_are_ignored_not_raised(self):
        with recording():
            observations.FILE.write_text(json.dumps([{"at_ms": 1, "source": ["v2"], "event": {}},
                                                     {"at_ms": 2, "source": "v2", "event": "scan", "reason": ["x"]}]),
                                         encoding="utf-8")
            events = observations.recent_events(now_ms=3)
            self.assertEqual([{"at_ms": 2, "source": "v2", "event": "scan", "version": ""}], events)
            observations.record_source_error("v2", ["bad"], object())  # type: ignore[arg-type]
            self.assertEqual("unsupported", observations.recent_events()[-1]["kind"])

    def test_only_source_scans_record_not_per_second_status_redraws(self):
        with tempfile.TemporaryDirectory() as td, patch.object(watch_coordinator, "record_scan") as recorded:
            config, selection, service, _ = make_service(td, MutableSource(completed_history()))
            watch = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: 4000)
            watch.initialize()
            watch.poll_once()
            for _ in range(3):
                watch.status_projection(seconds_until_check=5)
                watch.activity_projection()
            self.assertEqual(2, recorded.call_count)

    def test_v2_stage_names_the_source_call_that_was_running(self):
        with source_with_current_service() as (source, _service, _registration):
            source.load_session_snapshot("ses_current")
            self.assertEqual("complete", source.diagnostic_metadata()["last_snapshot_stage"])
            source.list_sessions()
            self.assertEqual("catalog", source.diagnostic_metadata()["last_snapshot_stage"],
                             "a later catalog failure must not be reported as a completed snapshot")

    def test_malformed_recovery_history_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(recovery_events, "FILE", Path(tmp) / "r.json"):
            recovery_events.FILE.write_text(json.dumps([{"at_ms": 1, "source": ["v2"], "event": "failed", "kind": "unreadable"}]),
                                            encoding="utf-8")
            self.assertEqual([], recovery_events.recent_events(now_ms=2))

    def test_test_mode_never_creates_observations(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(observations, "FILE", Path(tmp) / "watch.json"), patch.dict("os.environ", {"COST_GUARD_TEST_MODE": "1"}):
            observations.record_scan("v2", SimpleNamespace(sessions=(), roots=()), {}, (), 0)
            self.assertFalse(observations.FILE.exists())


if __name__ == "__main__":
    unittest.main()
