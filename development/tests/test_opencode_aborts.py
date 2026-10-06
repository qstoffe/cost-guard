"""Source-to-Watch cancellation regressions using sanitized live V2 evidence."""
from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from development.tests.test_opencode_v2 import source_with_current_service
from development.tests.test_step8_watch import make_service
from src.analysis.causal import build_prompt_records
from src.presentation import WatchRenderer
from src.sources.opencode_v2 import OpenCodeV2Source
from src.watch import WatchCoordinator

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/opencode_v2/aborted-error.json"


class V2AbortRegressionTests(unittest.TestCase):
    @staticmethod
    def live_error():
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_native_and_wrapped_abort_errors_reconstruct_terminal_state(self):
        errors = [self.live_error(), {"name": "MessageAbortedError"},
                  {"name": "UnknownError", "data": {"message": "Aborted"}},
                  {"name": "UnknownError", "data": {"name": "MessageAbortedError"}},
                  {"name": "UnknownError", "data": {"code": "ERR_CANCELED"}},
                  {"type": "cancelled"}, {"code": "ABORT_ERR"}]
        with source_with_current_service() as (source, service, _):
            assistant = service.messages["ses_current"][1]
            assistant.pop("tokens")
            assistant.pop("cost")
            assistant["finish"] = "error"
            for error in errors:
                with self.subTest(error=error):
                    assistant["error"] = error
                    snapshot = source.load_session_snapshot("ses_current")
                    self.assertEqual("AbortedError", snapshot.messages[-1].error_name)
                    record, = build_prompt_records(snapshot, tracked_provider=None, now_ms=5000)
                    self.assertTrue(record.aborted)
                    self.assertFalse(record.watch_error)
                    self.assertFalse(record.in_progress)

    def test_genuine_errors_remain_errors_with_missing_zero_or_positive_usage(self):
        errors = [{"type": "provider.transport", "message": "provider timeout"},
                  {"name": "AuthenticationError", "data": {"message": "authentication failure"}},
                  {"name": "APIError", "message": "connection aborted after provider timeout"},
                  {"name": "ToolRuntimeError", "message": "failed to abort worker"},
                  {"name": "NotAbortedError"}]
        with source_with_current_service() as (source, service, _):
            assistant = service.messages["ses_current"][1]
            assistant["finish"] = "error"
            assistant["cost"] = 0
            for error in errors:
                for usage in (None, {"input": 0, "output": 0}, {"input": 10, "output": 2}):
                    with self.subTest(error=error, usage=usage):
                        assistant["error"] = error
                        assistant.pop("tokens", None)
                        if usage is not None:
                            assistant["tokens"] = usage
                        snapshot = source.load_session_snapshot("ses_current")
                        record, = build_prompt_records(snapshot, tracked_provider=None, now_ms=5000)
                        self.assertFalse(record.aborted)
                        self.assertTrue(record.watch_error)
                        self.assertFalse(record.completed_successfully)

    def test_compatibility_wire_shapes_use_the_same_abort_parser(self):
        with source_with_current_service() as (source, service, _):
            user = {"id": "u", "sessionID": "ses_current", "role": "user", "time": {"created": 3000}}
            assistant = {"id": "a", "sessionID": "ses_current", "role": "assistant",
                         "parentID": "u", "time": {"created": 3100, "completed": 4000},
                         "finish": "error", "error": self.live_error()}
            legacy = [{"info": user, "parts": [{"id": "p", "type": "text", "text": "test"}]},
                      {"info": assistant, "parts": []}]
            interim = [{"id": "u", "role": "user", "metadata": {"time": user["time"]},
                        "parts": [{"type": "text", "text": "test"}]},
                       {"id": "a", "role": "assistant", "metadata": {
                           "time": assistant["time"], "error": self.live_error()}, "parts": []}]
            for shape in (legacy, interim):
                with self.subTest(shape=shape[0].keys()):
                    service.messages["ses_current"] = shape
                    record, = build_prompt_records(
                        source.load_session_snapshot("ses_current"), tracked_provider=None, now_ms=5000)
                    self.assertTrue(record.aborted)
                    self.assertFalse(record.watch_error)

    def test_later_success_overrides_native_abort_even_with_zero_usage(self):
        with source_with_current_service() as (source, service, _):
            earlier = copy.deepcopy(service.messages["ses_current"][1])
            earlier.update(id="msg_earlier", error=self.live_error(), finish="error",
                           time={"created": 3050, "completed": 3090})
            service.messages["ses_current"].insert(1, earlier)
            final = service.messages["ses_current"][-1]
            final["tokens"] = {"input": 0, "output": 0}
            final["cost"] = 0
            record, = build_prompt_records(
                source.load_session_snapshot("ses_current"), tracked_provider=None, now_ms=5000)
            self.assertFalse(record.aborted)
            self.assertFalse(record.watch_error)
            self.assertTrue(record.completed_successfully)

    def test_genuine_error_keeps_generic_watch_rendering_after_timeout(self):
        with source_with_current_service() as (source, native, _), tempfile.TemporaryDirectory() as td:
            assistant = native.messages["ses_current"][1]
            assistant.update(error={"type": "provider.transport", "message": "provider timeout"}, finish="error")
            assistant.pop("tokens")
            config, selection, reports, _ = make_service(td, source)
            clock = [5000]
            watch = WatchCoordinator(selection=selection, report_service=reports, config=config,
                                     session_id="ses_current", clock_ms=lambda: clock[0])
            renderer = WatchRenderer(config, stream=io.StringIO(), interactive=True)
            initial = watch.initialize().projection.rows[0]
            clock[0] = 50_000
            aged = watch.poll_once(force_resync=True).projection.rows[0]
            for row in (initial, aged):
                self.assertFalse(row.prompt.aborted)
                self.assertTrue(row.prompt.watch_error)
                self.assertEqual("!", row.marker)
                self.assertEqual("costQuotaCritical", renderer._row_style(row))
                self.assertNotIn("[ABORTED]", renderer._row_label(row))

    def test_watch_native_abort_survives_hints_refresh_reconstruction_and_timeout(self):
        with source_with_current_service() as (source, native, registration), tempfile.TemporaryDirectory() as td:
            native.messages["ses_current"][0]["text"] = "x" * 200
            assistant = native.messages["ses_current"][1]
            assistant.pop("tokens")
            assistant.pop("cost")
            assistant.pop("finish")
            assistant["time"].pop("completed")
            native.active = {"ses_current": {"type": "running"}}
            config, selection, reports, _ = make_service(td, source)
            clock = [3200]
            watch = WatchCoordinator(selection=selection, report_service=reports,
                                     config=config, clock_ms=lambda: clock[0])
            initial = watch.initialize().projection.rows[0]
            self.assertTrue(initial.prompt.in_progress)
            assistant.update(error=self.live_error(), finish="error")
            assistant["time"]["completed"] = 4000
            native.active = {}
            native.sessions[0]["time"]["updated"] = 10000
            clock[0] = 10_000
            recent = watch.poll_once(hinted_session_ids=("ses_current",)).projection.rows[0]
            renderer = WatchRenderer(config, stream=io.StringIO(), interactive=True)
            self.assertTrue(recent.prompt.aborted)
            self.assertFalse(recent.prompt.watch_error)
            self.assertEqual("!", recent.marker)
            self.assertEqual("costQuotaCritical", renderer._row_style(recent))
            self.assertIn("! #1 [ABORTED]", renderer._row_label(recent))
            truncated = replace(recent, prompt=replace(recent.prompt, preview="x" * 500))
            self.assertIn("[ABORTED]", renderer._row_label(truncated))
            for now in (15_000, 25_000, 40_001, 50_000):
                clock[0] = now
                native.sessions[0]["time"]["updated"] = now
                row = watch.poll_once(force_resync=True).projection.rows[0]
                self.assertTrue(row.prompt.aborted)
                self.assertFalse(row.prompt.watch_error)
                self.assertIn("[ABORTED]", renderer._row_label(row))
                self.assertEqual("!" if now < 40_000 else "", row.marker)
                self.assertEqual("costQuotaCritical" if now < 40_000 else None, renderer._row_style(row))
            # A fresh adapter must reconstruct the status without tracker retention.
            fresh = OpenCodeV2Source(registration, timeout_seconds=2)
            record, = build_prompt_records(
                fresh.load_session_snapshot("ses_current"), tracked_provider=None, now_ms=50_000)
            self.assertTrue(record.aborted)
            self.assertFalse(record.watch_error)
            _, fresh_selection, fresh_reports, _ = make_service(td, fresh)
            restored = WatchCoordinator(
                selection=fresh_selection, report_service=fresh_reports, config=config,
                session_id="ses_current", clock_ms=lambda: 50_000).initialize().projection.rows[0]
            self.assertTrue(restored.prompt.aborted)
            self.assertFalse(restored.prompt.watch_error)
            self.assertEqual("", restored.marker)
            self.assertIsNone(renderer._row_style(restored))
            self.assertIn("[ABORTED]", renderer._row_label(restored))


if __name__ == "__main__":
    unittest.main()
