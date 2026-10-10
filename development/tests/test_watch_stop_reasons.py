"""Explicit native stop causes through normalization, reports and Watch rendering."""
from __future__ import annotations

from dataclasses import replace
import io
import tempfile
import unittest

from development.fixtures.opencode_v2_service import source_with_current_service
from development.fixtures.watch_runtime import make_service
from src.analysis.causal import build_prompt_records
from src.presentation import WatchRenderer
from src.sources.opencode_errors import normalize_abort_reason, normalize_error_name
from src.watch import WatchCoordinator


class WatchStopReasonTests(unittest.TestCase):
    def test_explicit_assistant_and_idle_causes_reach_watch_and_survive_resync(self):
        cases = (
            ({"name": "AbortedError", "data": {"message": "Request aborted by user"}}, "user"),
            ({"type": "provider.request", "message": "You've hit your usage limit. Try again later."}, "quota limit"),
            ({"type": "provider.request", "message": "You exceeded your current quota, please check your plan."}, "quota limit"),
            ({"type": "provider.request", "message": "Provider rejected request", "response": {
                "body": '{"error":{"code":"insufficient_quota"}}'}}, "quota limit"),
            ({"type": "provider.request", "message": "Rate limit exceeded.", "response": {
                "body": '{"error":{"code":"insufficient_quota"}}'}}, "quota limit"),
            ({"type": "MaxToolCalls", "message": "Maximum number of tool calls reached"}, "tool call limit"),
            ({"type": "MaxStepsError", "message": "Maximum number of steps reached"}, "step limit"),
            ({"type": "provider.request", "message": "Rate limit exceeded."}, "rate limit"),
        )
        for error, label in cases:
            for location in ("assistant", "idle"):
                with self.subTest(label=label, location=location):
                    with source_with_current_service() as (source, native, _), tempfile.TemporaryDirectory() as td:
                        assistant = native.messages["ses_current"][1]
                        if location == "assistant":
                            assistant.update(error=error, finish="error")
                        else:
                            assistant["finish"] = "tool-calls"
                            native.messages["ses_current"].append({
                                "id": "terminal", "type": "idle", "outcome": "failed",
                                "error": error, "time": {"created": 5000}})
                        config, selection, reports, _ = make_service(td, source)
                        clock = [10_000]
                        watch = WatchCoordinator(selection=selection, report_service=reports, config=config,
                                                 session_id="ses_current", clock_ms=lambda: clock[0])
                        renderer = WatchRenderer(config, stream=io.StringIO(), interactive=True)

                        recent = watch.initialize().projection.rows[0]
                        clock[0] = 100_000
                        aged = watch.poll_once(force_resync=True).projection.rows[0]

                        for row in (recent, aged):
                            self.assertTrue(row.prompt.aborted)
                            self.assertFalse(row.prompt.watch_error)
                            self.assertFalse(row.prompt.in_progress)
                            self.assertFalse(row.prompt.completed_successfully)
                            self.assertIn(f"[ABORTED by {label}]", renderer._row_label(row))
                            long_preview = replace(row, prompt=replace(row.prompt, preview="x" * 500, prompt_number=123))
                            row_label = renderer._row_label(long_preview)
                            self.assertLessEqual(len(row_label), 35)
                            self.assertIn(f"[ABORTED by {label}]", row_label)
                        self.assertEqual("", aged.marker)
                        watch.close()

    def test_ambiguous_abort_and_arbitrary_error_mentions_do_not_invent_a_cause(self):
        for error in ({"name": "AbortedError", "message": "Aborted"},
                      {"type": "provider.transport", "message": "Connection aborted after quota check"},
                      {"name": "APIError", "message": "Tool call limit could not be loaded"},
                      {"name": "APIError", "data": {"stack": "insufficient_quota"}},
                      {"type": "APIError", "status": 429, "message": "Provider rejected request"},
                      {"type": "APIError", "response": {"body": '{"text":"quota exceeded"}'}}):
            with self.subTest(error=error):
                self.assertEqual("", normalize_abort_reason(error))
        self.assertEqual("AbortedError", normalize_error_name({"name": "AbortedError"}))

    def test_success_after_an_earlier_abort_clears_reason(self):
        with source_with_current_service() as (source, native, _):
            native.messages["ses_current"][1].update(error={"name": "MaxToolCalls"}, finish="error")
            native.messages["ses_current"].append({
                "id": "terminal", "type": "idle", "outcome": "succeeded", "time": {"created": 5000}})

            record, = build_prompt_records(source.load_session_snapshot("ses_current"), tracked_provider=None)

            self.assertFalse(record.aborted)
            self.assertEqual("", record.abort_reason)
            self.assertTrue(record.completed_successfully)

    def test_success_after_tool_calls_is_neutral_not_a_guessed_limit(self):
        with source_with_current_service() as (source, native, _), tempfile.TemporaryDirectory() as td:
            native.messages["ses_current"][1]["finish"] = "tool-calls"
            native.messages["ses_current"].append({
                "id": "terminal", "type": "idle", "outcome": "succeeded", "time": {"created": 5000}})
            config, selection, reports, _ = make_service(td, source)
            watch = WatchCoordinator(selection=selection, report_service=reports, config=config,
                                     session_id="ses_current", clock_ms=lambda: 10_000)

            row = watch.initialize().projection.rows[0]

            self.assertFalse(row.prompt.aborted)
            self.assertTrue(row.prompt.ended_after_tool_calls)
            renderer = WatchRenderer(config, stream=io.StringIO(), interactive=True)
            self.assertIn("[ENDED after tool calls]", renderer._row_label(row))
            plain = replace(row, prompt=replace(row.prompt, ended_after_tool_calls=False))
            self.assertNotIn("[ENDED", renderer._row_label(plain))
            watch.close()

    def test_terminal_generic_failure_does_not_inherit_earlier_limit_cause(self):
        with source_with_current_service() as (source, native, _):
            native.messages["ses_current"][1].update(error={"name": "MaxToolCalls"}, finish="error")
            native.messages["ses_current"].append({
                "id": "terminal", "type": "idle", "outcome": "failed", "time": {"created": 5000},
                "error": {"type": "provider.transport", "message": "Connection failed"}})

            record, = build_prompt_records(source.load_session_snapshot("ses_current"), tracked_provider=None)

            self.assertFalse(record.aborted)
            self.assertTrue(record.watch_error)
            self.assertEqual("", record.abort_reason)


if __name__ == "__main__":
    unittest.main()
