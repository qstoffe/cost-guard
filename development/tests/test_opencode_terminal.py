"""Synthetic durable lifecycle evidence, shared reports and Watch regressions."""
from __future__ import annotations

import copy
from dataclasses import replace
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from development.fixtures.opencode_v2_service import source_with_current_service
from development.fixtures.watch_runtime import make_service
from src.analysis.causal import build_prompt_records
from src.analysis.core import analyze_snapshot
from src.domain import EventKind, MessageRole, TerminalOutcome
from src.presentation import WatchRenderer
from src.reports import ReportKind, ReportRequest
from src.sources.opencode_v2 import OpenCodeV2Source
from src.watch import WatchCoordinator


def unfinished(native, *, usage=True):
    assistant = native.messages["ses_current"][1]
    assistant.pop("finish", None)
    assistant["time"].pop("completed", None)
    if not usage:
        assistant.pop("tokens", None)
        assistant.pop("cost", None)
    return assistant


def idle(*, at=5000, outcome="failed", identity="msg_terminal"):
    return {"id": identity, "type": "idle", "outcome": outcome, "time": {"created": at}}


def records(source, *, now=10_000):
    return build_prompt_records(source.load_session_snapshot("ses_current"),
                                tracked_provider=None, now_ms=now)


def job(identity, *, at, name="shell"):
    """Current-V2 backgrounded tool call: returns at once, the job keeps running."""
    return {"type": "tool", "id": "call_" + identity, "name": name,
            "time": {"created": at - 10, "ran": at, "completed": at + 5},
            "state": {"status": "completed", "input": {"command": "private command", "background": True},
                      "metadata": {"status": "running", "shellID": identity}}}


def notice(identity, *, at, state="completed", exit_code=0):
    return {"id": "msg_notice_" + identity, "type": "synthetic", "text": "private job output",
            "time": {"created": at}, "metadata": {"source": "shell", "shellID": identity, "jobID": identity,
                                                 "state": state, "exit": exit_code}}


def resumed(identity, *, at, finish="stop", content=()):
    return {"id": identity, "type": "assistant", "agent": "build", "content": list(content),
            "model": {"providerID": "openai", "id": "gpt-5.6", "variant": "medium"}, "finish": finish,
            "cost": 0.5, "tokens": {"input": 100, "output": 10, "reasoning": 0, "cache": {"read": 0, "write": 0}},
            "time": {"created": at, "completed": at + 500}}


def waiting(native, *jobs, registry=True):
    """The model started background jobs, then its own turn ended (idle)."""
    native.messages["ses_current"][1].update(finish="tool-calls", content=[
        job(identity, at=3500 + index) for index, identity in enumerate(jobs)])
    native.messages["ses_current"].append(idle(at=4100, outcome="succeeded", identity="msg_idle_1"))
    native.shells = [{"id": identity, "status": "running"} for identity in jobs] if registry else None


class TerminalLifecycleTests(unittest.TestCase):
    def test_failed_idle_closes_incomplete_assistant_and_freezes_duration(self):
        with source_with_current_service() as (source, native, _):
            unfinished(native)
            native.messages["ses_current"].append(idle())
            early, = records(source)
            late, = records(source, now=100_000_000)
            for record in (early, late):
                self.assertFalse(record.in_progress)
                self.assertTrue(record.watch_error)
                self.assertFalse(record.aborted)
                self.assertFalse(record.completed_successfully)
                self.assertEqual(2000, record.duration_ms)
                self.assertEqual(5000, record.terminal_time_ms)
            self.assertEqual(early.entries, late.entries)

    def test_terminal_outcomes_with_missing_zero_and_positive_usage(self):
        with source_with_current_service() as (source, native, _):
            assistant = unfinished(native, usage=False)
            for usage in (None, {"input": 0, "output": 0}, {"input": 10, "output": 2}):
                assistant.pop("tokens", None)
                if usage is not None:
                    assistant["tokens"] = usage
                for outcome in ("failed", "interrupted", "succeeded"):
                    with self.subTest(usage=usage, outcome=outcome):
                        native.messages["ses_current"] = native.messages["ses_current"][:2] + [idle(outcome=outcome)]
                        record, = records(source)
                        self.assertFalse(record.in_progress)
                        self.assertEqual(outcome == "failed", record.watch_error)
                        self.assertEqual(outcome == "interrupted", record.aborted)
                        self.assertEqual(outcome == "succeeded", record.completed_successfully)
                        self.assertEqual(2000, record.duration_ms)

    def test_inactive_and_unavailable_status_do_not_prove_completion(self):
        with source_with_current_service() as (source, native, _):
            unfinished(native)
            for active in (False, None):
                snapshot = source.load_session_snapshot("ses_current")
                snapshot = replace(snapshot, root=replace(snapshot.root, active=active))
                record, = build_prompt_records(snapshot, tracked_provider=None, now_ms=10_000)
                self.assertTrue(record.in_progress)
                self.assertEqual(7000, record.duration_ms)

    def test_unqualified_status_and_invalid_terminal_rows_are_not_evidence(self):
        with source_with_current_service() as (source, native, _):
            unfinished(native)
            for row in ({"type": "idle"}, idle(outcome="unknown"), idle(at=0),
                        {**idle(), "id": ""}, {**idle(), "sessionID": "different"},
                        {**idle(), "type": "session.status"}, idle(at=3100),
                        idle(at=float("inf")), idle(outcome=[])):
                with self.subTest(row=row):
                    native.messages["ses_current"] = native.messages["ses_current"][:2] + [row]
                    record, = records(source)
                    self.assertTrue(record.in_progress)

    def test_older_idle_does_not_close_newer_attempt_same_prompt(self):
        with source_with_current_service() as (source, native, _):
            original = unfinished(native)
            newer = copy.deepcopy(original)
            newer.update(id="msg_resumed", time={"created": 6000})
            native.messages["ses_current"].extend([idle(), newer])
            record, = records(source)
            self.assertTrue(record.in_progress)
            self.assertFalse(record.watch_error)
            self.assertFalse(record.aborted)
            newer.update(finish="stop", time={"created": 6000, "completed": 7000})
            record, = records(source)
            self.assertFalse(record.in_progress)
            self.assertTrue(record.completed_successfully)
            self.assertFalse(record.watch_error)

    def test_multiple_terminal_rows_are_attempt_scoped_and_order_independent(self):
        with source_with_current_service() as (source, native, _):
            original = unfinished(native)
            original["content"] = [{"type": "tool", "name": "read", "state": {
                "status": "completed", "time": {"start": 3200, "end": 4000}}}]
            newer = copy.deepcopy(original)
            newer.update(id="msg_resumed", time={"created": 6000}, content=[])
            native.messages["ses_current"].extend([
                idle(at=8000, outcome="succeeded", identity="msg_final"), newer, idle()])
            snapshot = source.load_session_snapshot("ses_current")
            record, = build_prompt_records(snapshot, tracked_provider=None, now_ms=10_000)
            self.assertFalse(record.in_progress)
            self.assertTrue(record.completed_successfully)
            self.assertFalse(record.watch_error)
            self.assertEqual(5000, record.duration_ms)
            self.assertEqual(2, sum(m.termination is not None for m in snapshot.messages))

    def test_older_idle_does_not_close_new_prompt_or_live_session(self):
        with source_with_current_service() as (source, native, _):
            original = unfinished(native)
            native.messages["ses_current"].append(idle())
            native.active = {"ses_current": {"type": "running"}}
            self.assertTrue(records(source)[0].in_progress)
            newer = copy.deepcopy(original)
            newer.update(id="msg_new", time={"created": 6100})
            native.messages["ses_current"].extend([
                {"id": "msg_new_user", "type": "user", "text": "synthetic next prompt",
                 "time": {"created": 6000}}, newer])
            old, new = records(source)
            self.assertFalse(old.in_progress)
            self.assertTrue(new.in_progress)

    def test_terminal_ends_stale_tool_but_preserves_live_child(self):
        with source_with_current_service() as (source, native, _):
            assistant = unfinished(native)
            assistant["content"] = [{"id": "task", "type": "tool", "name": "task",
                "time": {"created": 3200, "ran": 3300},
                "state": {"status": "running", "metadata": {"sessionId": "ses_current_child"}}}]
            native.messages["ses_current"].append(idle())
            self.assertFalse(records(source)[0].in_progress)
            native.active = {"ses_current_child": {"type": "running"}}
            self.assertTrue(records(source)[0].in_progress)

    def test_later_tool_activity_and_compaction_boundary_are_preserved(self):
        with source_with_current_service() as (source, native, _):
            assistant = unfinished(native)
            assistant["content"] = [{"id": "tool", "type": "tool", "name": "read",
                "state": {"status": "running"}, "time": {"created": 6000, "ran": 6100}}]
            native.messages["ses_current"].append(idle())
            self.assertTrue(records(source)[0].in_progress)
            assistant["content"] = []
            native.messages["ses_current"].insert(2, {
                "id": "msg_compact", "type": "compaction", "status": "completed",
                "reason": "auto", "summary": "synthetic", "recent": "tail",
                "time": {"created": 4500}})
            # An idle for compaction must not label the earlier prompt failed.
            self.assertFalse(records(source)[0].watch_error)

    def test_tool_continuation_without_terminal_remains_active(self):
        with source_with_current_service() as (source, native, _):
            assistant = native.messages["ses_current"][1]
            assistant["finish"] = "tool-calls"
            self.assertTrue(records(source, now=5000)[0].in_progress)

    def test_terminal_applies_to_stale_tools_from_earlier_steps_of_same_run(self):
        with source_with_current_service() as (source, native, _):
            assistant = unfinished(native)
            earlier = copy.deepcopy(assistant)
            earlier.update(id="msg_tool_step", time={"created": 3050, "completed": 3090},
                           finish="tool-calls", content=[{"type": "tool", "name": "read",
                               "state": {"status": "running"}, "time": {"created": 3060}}])
            native.messages["ses_current"].insert(1, earlier)
            native.messages["ses_current"].append(idle())
            self.assertFalse(records(source)[0].in_progress)

    def test_normalization_leaves_native_completion_usage_and_billing_unchanged(self):
        with source_with_current_service() as (source, native, _):
            unfinished(native)
            before = source.load_session_snapshot("ses_current")
            prior, = build_prompt_records(before, tracked_provider=None, now_ms=10_000)
            native.messages["ses_current"].append(idle())
            after = source.load_session_snapshot("ses_current")
            final, = build_prompt_records(after, tracked_provider=None, now_ms=10_000)
            self.assertEqual(before.invocations, after.invocations)
            self.assertEqual(before.parts, after.parts)
            self.assertEqual(before.messages, tuple(replace(m, termination=None) for m in after.messages))
            for field in ("entries", "cost", "main_cost", "subagent_cost", "input_tokens",
                          "output_tokens", "cache_read_tokens", "cache_write_tokens", "model_costs"):
                self.assertEqual(getattr(prior, field), getattr(final, field), field)
            self.assertFalse(analyze_snapshot(after, tracked_provider=None).cacheable,
                             "an incomplete inference snapshot remains conservatively uncached")
            self.assertEqual(1, source.diagnostic_metadata()["message_terminal_evidence_normalized"])
            self.assertEqual(0, source.diagnostic_metadata()["message_lifecycle_items_ignored"])

    def test_analysis_terminal_semantics_do_not_depend_on_generation(self):
        with source_with_current_service() as (source, native, _):
            unfinished(native)
            native.messages["ses_current"].append(idle())
            snapshot = source.load_session_snapshot("ses_current")
            for generation in ("v1", "v2", "future"):
                messages = tuple(replace(m, provenance=replace(m.provenance, source_generation=generation))
                                 for m in snapshot.messages)
                record, = build_prompt_records(replace(snapshot, messages=messages),
                                                tracked_provider=None, now_ms=10_000)
                self.assertFalse(record.in_progress)
                self.assertTrue(record.watch_error)

    def test_synthetic_boundary_does_not_reassign_terminal_to_prior_attempt(self):
        with source_with_current_service() as (source, native, _):
            unfinished(native)
            native.messages["ses_current"].extend([
                {"id": "msg_synthetic", "type": "synthetic", "text": "synthetic continuation",
                 "time": {"created": 4500}}, idle()])
            snapshot = source.load_session_snapshot("ses_current")
            self.assertFalse(any(m.termination for m in snapshot.messages if m.role is MessageRole.ASSISTANT))

    def test_cold_process_reconstructs_failure_without_watch_or_cache_state(self):
        with source_with_current_service() as (_source, native, registration):
            unfinished(native, usage=False)
            native.messages["ses_current"].append(idle())
            script = """
import json, sys
from src.sources.opencode_v2 import OpenCodeV2Source
from src.analysis.causal import build_prompt_records
source = OpenCodeV2Source(sys.argv[1], timeout_seconds=2)
row, = build_prompt_records(source.load_session_snapshot('ses_current'),
                           tracked_provider=None, now_ms=100000000)
print(json.dumps([row.in_progress, row.duration_ms, row.watch_error,
                  row.aborted, row.completed_successfully]))
"""
            child = subprocess.run([sys.executable, "-B", "-c", script, str(registration)],
                                   capture_output=True, text=True, timeout=10, check=True)
            self.assertEqual([False, 2000, True, False, False], json.loads(child.stdout))

    def test_watch_report_cold_start_and_resync_share_terminal_truth(self):
        with source_with_current_service() as (source, native, registration), tempfile.TemporaryDirectory() as td:
            unfinished(native)
            native.active = {"ses_current": {"type": "running"}}
            config, selection, reports, _ = make_service(td, source)
            clock = [4000]
            watch = WatchCoordinator(selection=selection, report_service=reports, config=config,
                                     session_id="ses_current", clock_ms=lambda: clock[0])
            initial = watch.initialize().projection
            self.assertEqual(1, initial.active_count)
            native.messages["ses_current"].append(idle())
            native.active = {}
            native.sessions[0]["time"]["updated"] = 5000
            for now in (10_000, 50_000, 100_000):
                clock[0] = now
                projection = watch.poll_once(force_resync=True).projection
                self.assertEqual(0, projection.active_count)
                row, = projection.rows
                self.assertFalse(row.prompt.in_progress)
                self.assertTrue(row.prompt.watch_error)
                self.assertFalse(row.prompt.aborted)
                self.assertEqual(2000, row.prompt.duration_ms)
            fresh = OpenCodeV2Source(registration, timeout_seconds=2)
            _, fresh_selection, fresh_reports, _ = make_service(td, fresh, now_ms=100_000)
            report = fresh_reports.build(ReportRequest(kind=ReportKind.SESSION, session_id="ses_current"))
            report_row, = report.prompt_blocks[0].rows
            self.assertFalse(report_row.in_progress)
            self.assertTrue(report_row.watch_error)
            self.assertEqual(2000, report_row.duration_ms)
            restored = WatchCoordinator(selection=fresh_selection, report_service=fresh_reports,
                config=config, session_id="ses_current", clock_ms=lambda: 100_000).initialize().projection
            self.assertEqual(0, restored.active_count)
            self.assertEqual(2000, restored.rows[0].prompt.duration_ms)


class BackgroundLifecycleTests(unittest.TestCase):
    def test_background_job_keeps_idle_model_prompt_active_without_usage_growth(self):
        with source_with_current_service() as (source, native, _):
            waiting(native, "sh_job1")
            snapshot = source.load_session_snapshot("ses_current")
            activity, = snapshot.background
            self.assertEqual(("shell", True, None), (activity.kind, activity.running, activity.outcome))
            self.assertNotIn("sh_job1", activity.activity_id)
            self.assertFalse(analyze_snapshot(snapshot, tracked_provider=None).cacheable)
            early, = records(source, now=10_000)
            late, = records(source, now=70_000)
            for record, duration in ((early, 7000), (late, 67_000)):
                self.assertTrue(record.in_progress)
                self.assertTrue(record.background_only)
                self.assertEqual(("shell",), record.background_kinds)
                self.assertEqual(3500, record.background_started_ms)
                self.assertEqual(duration, record.duration_ms)
            self.assertEqual((1, early.cost), (late.model_calls, late.cost))

    def test_completion_resumes_same_prompt_and_repeated_cycles_stay_one_prompt(self):
        with source_with_current_service() as (source, native, _):
            waiting(native, "sh_job1")
            native.messages["ses_current"] += [
                notice("sh_job1", at=8000),
                resumed("msg_resume_1", at=8100, finish="tool-calls", content=[job("sh_job2", at=8200)]),
                idle(at=8700, outcome="succeeded", identity="msg_idle_2")]
            native.shells = [{"id": "sh_job2", "status": "running"}]
            record, = records(source, now=20_000)
            self.assertTrue(record.in_progress and record.background_only)
            self.assertEqual((2, 17_000), (record.model_calls, record.duration_ms))
            native.messages["ses_current"] += [
                notice("sh_job2", at=12_000), resumed("msg_resume_2", at=12_100),
                idle(at=12_700, outcome="succeeded", identity="msg_idle_3")]
            native.shells = []
            snapshot = source.load_session_snapshot("ses_current")
            self.assertEqual(2, sum(event.kind is EventKind.BACKGROUND_COMPLETION for event in snapshot.events))
            self.assertEqual([TerminalOutcome.SUCCESS] * 2, [item.outcome for item in snapshot.background])
            record, = build_prompt_records(snapshot, tracked_provider=None, now_ms=50_000)
            self.assertFalse(record.in_progress)
            self.assertTrue(record.completed_successfully)
            self.assertEqual(3, record.model_calls, "resumed work stays on the initiating row, once each")
            self.assertEqual(len(snapshot.invocations), record.model_calls)
            self.assertEqual(9700, record.duration_ms)
            self.assertEqual(((), False), (record.background_kinds, record.background_only))

    def test_prompt_waits_for_last_of_several_jobs(self):
        with source_with_current_service() as (source, native, _):
            waiting(native, "sh_job1", "sh_job2")
            self.assertEqual(("shell", "shell"), records(source)[0].background_kinds)
            native.messages["ses_current"] += [notice("sh_job1", at=6000), resumed("msg_resume_1", at=6100),
                                               idle(at=6700, outcome="succeeded", identity="msg_idle_2")]
            native.shells = [{"id": "sh_job2", "status": "running"}]
            record, = records(source)
            self.assertTrue(record.in_progress and record.background_only)
            self.assertEqual(("shell",), record.background_kinds)
            native.messages["ses_current"].append(notice("sh_job2", at=9000))
            native.shells = []
            record, = records(source, now=60_000)
            self.assertFalse(record.in_progress)
            self.assertEqual(6000, record.duration_ms, "the last job's end bounds the logical task")

    def test_failure_cancellation_and_unknown_ends_close_without_success(self):
        for state, exit_code, outcome in (("completed", 1, TerminalOutcome.FAILURE),
                                          ("killed", None, TerminalOutcome.CANCELLATION),
                                          ("timeout", None, TerminalOutcome.FAILURE),
                                          ("future-state", 0, None)):
            with self.subTest(state=state), source_with_current_service() as (source, native, _):
                waiting(native, "sh_job1")
                native.messages["ses_current"].append(notice("sh_job1", at=6000, state=state, exit_code=exit_code))
                native.shells = []
                snapshot = source.load_session_snapshot("ses_current")
                activity, = snapshot.background
                self.assertEqual((False, outcome, 6000), (activity.running, activity.outcome, activity.ended_at_ms))
                record, = build_prompt_records(snapshot, tracked_provider=None, now_ms=60_000)
                self.assertFalse(record.in_progress)
                self.assertEqual(3000, record.duration_ms)

    def test_end_needs_native_evidence_not_idle_time_or_unobservable_registry(self):
        with source_with_current_service() as (source, native, _):
            waiting(native, "sh_job1", registry=False)  # registry unavailable: never invent an end
            for now in (10_000, 10_000_000):
                self.assertTrue(records(source, now=now)[0].in_progress)
            native.shells = [{"id": "sh_other", "status": "running"}]  # registry no longer lists the job
            snapshot = source.load_session_snapshot("ses_current")
            activity, = snapshot.background
            self.assertEqual((False, None, None), (activity.running, activity.outcome, activity.ended_at_ms))
            record, = build_prompt_records(snapshot, tracked_provider=None, now_ms=60_000)
            self.assertFalse(record.in_progress)
            self.assertEqual(1100, record.duration_ms)

    def test_newer_prompt_takes_over_the_wait_and_old_row_stops(self):
        with source_with_current_service() as (source, native, _):
            waiting(native, "sh_job1")
            native.messages["ses_current"] += [
                {"id": "msg_next_user", "type": "user", "text": "next", "time": {"created": 5000}},
                resumed("msg_next_answer", at=5100),
                idle(at=5700, outcome="succeeded", identity="msg_idle_2")]
            old, new = records(source)
            self.assertFalse(old.in_progress)
            self.assertTrue(new.in_progress and new.background_only)

    def test_watch_footer_and_status_stay_active_through_resume(self):
        with source_with_current_service() as (source, native, _), tempfile.TemporaryDirectory() as td:
            waiting(native, "sh_job1")
            config, selection, reports, _ = make_service(td, source)
            clock = [10_000]
            watch = WatchCoordinator(selection=selection, report_service=reports, config=config,
                                     session_id="ses_current", clock_ms=lambda: clock[0])
            projection = watch.initialize().projection
            self.assertEqual(1, projection.active_count)
            self.assertIn("1 prompt running · background shell · Next refresh:", projection.status)
            clock[0] = 70_000
            projection = watch.poll_once().projection
            row, = projection.rows
            self.assertEqual((1, 67_000), (row.prompt.calls, row.prompt.duration_ms))
            self.assertEqual((("shell",), 66_500), (row.tool.background_kinds, row.tool.background_ms))
            stream = io.StringIO()
            WatchRenderer(config, stream=stream, interactive=False, terminal_width=160).render(projection)
            self.assertIn("background: shell 1m7s", stream.getvalue())
            self.assertNotIn("sh_job1", stream.getvalue())
            native.messages["ses_current"] += [notice("sh_job1", at=71_000), resumed("msg_resume_1", at=71_100),
                                               idle(at=71_700, outcome="succeeded", identity="msg_idle_2")]
            native.shells = []
            native.sessions[0]["time"]["updated"] = 71_700
            clock[0] = 80_000
            projection = watch.poll_once(force_resync=True).projection
            row, = projection.rows
            self.assertEqual(0, projection.active_count)
            self.assertTrue(projection.status.startswith("Idle"))
            self.assertEqual((2, 68_700), (row.prompt.calls, row.prompt.duration_ms))

    def test_core_and_watch_never_read_native_background_fields(self):
        root = Path(__file__).resolve().parents[2] / "src"
        for path in [*root.glob("analysis/*.py"), *root.glob("watch/*.py"), *root.glob("presentation/*.py")]:
            text = path.read_text(encoding="utf-8")
            for native_field in ("shellID", "jobID", '"synthetic"'):
                self.assertNotIn(native_field, text, f"{path.name} reads native field {native_field}")


if __name__ == "__main__":
    unittest.main()
