"""Bounded, privacy-safe Watch diagnostics regression tests."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.watch import observation_diagnostics as observations


class WatchObservationTests(unittest.TestCase):
    def test_empty_watch_reports_filtered_existing_history_without_ids(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(observations, "FILE", Path(tmp) / "watch.json"), patch.dict("os.environ", {"COST_GUARD_TEST_MODE": ""}):
            session = SimpleNamespace(active=False)
            prompt = SimpleNamespace(in_progress=False, at_ms=100)
            observed = SimpleNamespace(sessions=(session,), roots=(session,))
            observations.record_scan("v2", observed, {"private-session-id": SimpleNamespace(rows=(prompt,))}, (), 200, 300)
            event = observations.recent_events()[0]
            self.assertEqual(("no_eligible_prompts", 1, 0),
                             (event["reason"], event["older_completed"], event["visible_prompts"]))
            self.assertNotIn("private-session-id", observations.FILE.read_text(encoding="utf-8"))

    def test_unreadable_stage_is_recorded_without_native_payload(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(observations, "FILE", Path(tmp) / "watch.json"), patch.dict("os.environ", {"COST_GUARD_TEST_MODE": ""}):
            provider = SimpleNamespace(diagnostic_metadata=lambda: {"last_snapshot_stage": "revision_changed", "secret": "DO_NOT_INCLUDE"})
            observations.record_source_error("v2", "unreadable", provider)
            event = observations.recent_events()[0]
            self.assertEqual(("source_error", "unreadable", "revision_changed"),
                             (event["event"], event["kind"], event["phase"]))
            self.assertNotIn("DO_NOT_INCLUDE", observations.FILE.read_text(encoding="utf-8"))

    def test_unchanged_refresh_does_not_write_redundant_records(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(observations, "FILE", Path(tmp) / "watch.json"), patch.dict("os.environ", {"COST_GUARD_TEST_MODE": ""}):
            empty = SimpleNamespace(sessions=(), roots=())
            for _ in range(4):
                observations.record_scan("v2", empty, {}, (), 0, 0)
            self.assertEqual(1, len(observations.recent_events()))

    def test_test_mode_never_creates_observations(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(observations, "FILE", Path(tmp) / "watch.json"), patch.dict("os.environ", {"COST_GUARD_TEST_MODE": "1"}):
            observations.record_scan("v2", SimpleNamespace(sessions=(), roots=()), {}, (), 0, 0)
            self.assertFalse(observations.FILE.exists())


if __name__ == "__main__":
    unittest.main()
