"""Synthetic V2 cancellation retains only the initiating child's execution."""
from dataclasses import replace
import io
import json
import shutil
import subprocess
from types import SimpleNamespace
import unittest

from development.tests.fixtures.subagent_sessions import assistant, incident_source, link, user
from src.analysis import analyze_snapshot
from development.tests.fixtures.stopped_parent_watch import stopped_parent_captures
from src.application.live_projection import project_live
from src.presentation import WatchRenderer
from src.reports import ReportKind, ReportRequest
from src.reports.session_history import SessionHistory, analyze_observed
from src.reports.sampling import AnalyzedRoot
from src.watch.tracker import WatchRowTracker
from src.watch.running import running_prompts


def stop_parent(server):
    server.messages["ses_current"] = server.messages["ses_current"][:2]
    server.messages["ses_current"][1].update(
        error={"name": "MessageAbortedError"}, finish="error")


class StoppedParentChildrenTests(unittest.TestCase):
    def test_native_capture_watch_detail_cli_and_rendered_lifecycle_share_truth(self):
        frames = []
        detail = SessionHistory()
        tracker = WatchRowTracker(started_at_ms=4500, recent_seconds=30, max_rows=20)
        final_duration = None
        for stage, reports, cards, frame in stopped_parent_captures():
            entry = cards.sessions["ses_current"]
            row = (frame.active_cards or frame.history_cards)[0].rows[0]
            running = stage in {"initial", "stopped", "repeated"}
            self.assertEqual(running, row.prompt.in_progress, stage)
            self.assertEqual(not running, row.prompt.aborted, stage)
            self.assertFalse(row.prompt.completed_successfully)
            self.assertEqual("u1", row.prompt.event_id)
            block, snapshot, _ = reports.build_watch_root(entry.root, force_fresh=True)
            cli, = tracker.project({"ses_current": block}, {"ses_current": snapshot}, now_ms=frame.now_ms)
            detailed, _ = detail.acquire(reports, "ses_current")
            finite = reports.build(ReportRequest(ReportKind.SESSION, "ses_current")).prompt_blocks[0].rows[0]
            catalog, = reports._session_rows((AnalyzedRoot(snapshot.root,
                analyze_snapshot(snapshot, now_ms=frame.now_ms), False, snapshot),))
            self.assertEqual(running, catalog.running)
            for counterpart in (cli.prompt, detailed.prompt_blocks[0].rows[0], finite):
                self.assertEqual((row.prompt.in_progress, row.prompt.aborted, row.prompt.calls, row.prompt.ccost),
                    (counterpart.in_progress, counterpart.aborted, counterpart.calls, counterpart.ccost), stage)
            if stage in {"stopped", "repeated"}:
                self.assertTrue(row.prompt.subagent_active)
                self.assertEqual("cancellation", row.prompt.parent_outcome)
                label = WatchRenderer(reports.config, stream=io.StringIO())._row_label(cli)
                self.assertIn("[SUBAGENT RUNNING]", label)
                self.assertFalse(row.tool.running_tool, "terminal parent tool must not reopen")
            if not running:
                self.assertEqual(2, row.prompt.calls)
                final_duration = row.prompt.duration_ms if final_duration is None else final_duration
                self.assertEqual(final_duration, row.prompt.duration_ms)
                self.assertEqual((4000, 12_000), (row.prompt.parent_terminal_time_ms, row.prompt.completed_at_ms))
            frames.append(project_live(frame).to_json())
        if shutil.which("node"):
            result = subprocess.run([shutil.which("node"), "development/tests/integration/web_live.cjs"],
                input=json.dumps(dict(lifecycle=frames, stopped="ses_current", runningFrames=3)),
                text=True, capture_output=True, timeout=15)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_partial_child_omission_retains_work_but_complete_terminal_retires_it(self):
        with incident_source() as (source, server):
            stop_parent(server)
            server.active = {"ses_current_child": {"type": "running"}}
            server.messages["ses_current_child"][1] = assistant("ca", 3400, None)
            previous = source.load_session_snapshot("ses_current")
            partial = replace(previous, sessions=(previous.root,),
                messages=tuple(m for m in previous.messages if m.session_id == previous.root.session_id),
                parts=tuple(p for p in previous.parts if p.session_id == previous.root.session_id),
                complete=False)
            service = SimpleNamespace(_analyze_snapshot=lambda snapshot: analyze_snapshot(snapshot, now_ms=15_000))
            retained, bundle, missing = analyze_observed(service, previous, partial)
            self.assertTrue(missing)
            self.assertTrue(bundle.prompts[0].in_progress)
            server.active = {}
            server.messages["ses_current_child"][1] = assistant("ca", 3400, 14_000)
            fresh = source.load_session_snapshot("ses_current")
            _, final, _ = analyze_observed(service, retained, fresh)
            self.assertFalse(final.prompts[0].in_progress)
            self.assertTrue(final.prompts[0].aborted)
            self.assertEqual(14_000, final.prompts[0].terminal_time_ms)

    def test_full_watch_keeps_distinct_causal_prompts_and_counts(self):
        for stage, _reports, cards, frame in stopped_parent_captures():
            if stage != "stopped":
                continue
            entry = cards.sessions["ses_current"]
            old = entry.capture.rows[0]
            newer = replace(old, event_id="new", at_ms=4500, prompt_number=2,
                in_progress=False, subagent_active=False, aborted=False, completed_successfully=True)
            entry.capture = replace(entry.capture, rows=(old, newer))
            self.assertEqual("u1", cards.project(frame.now_ms)[0][0].focal_id)
            newer = replace(newer, in_progress=True, completed_successfully=False)
            entry.capture = replace(entry.capture, rows=(old, newer))
            active, _, state = cards.project(frame.now_ms)
            self.assertEqual(2, len(active))
            self.assertEqual(("u1", "new"), tuple(card.focal_id for card in active))
            self.assertEqual(2, running_prompts(active, state).count)
            self.assertTrue(entry.capture.rows[0].in_progress)

    def test_closed_tool_does_not_end_bound_child_or_drop_late_usage(self):
        with incident_source() as (source, server):
            stop_parent(server)
            server.active = {"ses_current_child": {"type": "running"}}
            server.messages["ses_current_child"][1] = assistant("ca", 3400, None)
            running = source.load_session_snapshot("ses_current")
            record, = analyze_snapshot(running, now_ms=10_000).prompts
            self.assertTrue(record.in_progress)
            self.assertFalse(record.aborted)
            self.assertFalse(record.completed_successfully)
            self.assertTrue(record.subagent_active)
            self.assertEqual("cancellation", record.parent_outcome)
            self.assertEqual(4000, record.parent_terminal_time_ms)
            self.assertEqual("AbortedError", running.messages[1].error_name)

            server.active = {}
            server.messages["ses_current_child"][1] = assistant("ca", 3400, 12_000)
            finished = source.load_session_snapshot("ses_current")
            for now in (13_000, 80_000):
                record, = analyze_snapshot(finished, now_ms=now).prompts
                self.assertFalse(record.in_progress)
                self.assertTrue(record.aborted)
                self.assertFalse(record.completed_successfully)
                self.assertEqual(2, record.model_calls)
                self.assertEqual(12_000, record.terminal_time_ms)
                self.assertEqual(9000, record.execution_duration_ms)

    def test_quiet_bound_child_without_an_assistant_is_running_not_a_model_call(self):
        with incident_source() as (source, server):
            stop_parent(server)
            server.messages["ses_current_child"] = [user("cu", 3300)]
            server.active = {"ses_current_child": {"type": "running"}}
            record, = analyze_snapshot(source.load_session_snapshot("ses_current"), now_ms=10**9).prompts
            self.assertTrue(record.in_progress)
            self.assertEqual(1, record.model_calls)
            server.messages["ses_current_child"].append(assistant("late", 5000, 12_000))
            server.active = {}
            final, = analyze_snapshot(source.load_session_snapshot("ses_current"), now_ms=13_000).prompts
            self.assertFalse(final.in_progress)
            self.assertTrue(final.aborted)
            self.assertEqual((2, 12_000), (final.model_calls, final.terminal_time_ms))

    def test_new_child_created_in_launch_can_publish_its_first_turn_after_tool_return(self):
        with incident_source() as (source, server):
            stop_parent(server)
            server.sessions[1]["time"]["created"] = 3300
            server.messages["ses_current_child"] = []
            server.active = {"ses_current_child": {"type": "running"}}
            self.assertTrue(analyze_snapshot(source.load_session_snapshot("ses_current"), now_ms=4500).prompts[0].in_progress)
            server.messages["ses_current_child"] = [user("late-user", 5000), assistant("late", 5100, None)]
            self.assertTrue(analyze_snapshot(source.load_session_snapshot("ses_current"), now_ms=6000).prompts[0].in_progress)
            server.active = {}
            server.messages["ses_current_child"][1] = assistant("late", 5100, 7000)
            final, = analyze_snapshot(source.load_session_snapshot("ses_current"), now_ms=8000).prompts
            self.assertTrue(final.aborted)
            self.assertEqual((2, 7000), (final.model_calls, final.terminal_time_ms))

    def test_superseding_prompt_does_not_borrow_or_suppress_original_child(self):
        with incident_source(background=True) as (source, server):
            stop_parent(server)
            server.messages["ses_current_child"][1] = assistant("ca", 3400, None)
            server.active = {"ses_current_child": {"type": "running"}}
            server.messages["ses_current"].extend((user("u2", 5000), assistant("a2", 5100, 5200)))
            old, new = analyze_snapshot(source.load_session_snapshot("ses_current"), now_ms=20_000).prompts
            self.assertTrue(old.in_progress)
            self.assertFalse(new.in_progress)
            self.assertEqual(("ses_current_child",), old.linked_session_ids)
            self.assertEqual((), new.linked_session_ids)

    def test_active_compaction_does_not_suppress_original_child(self):
        with incident_source() as (source, server):
            stop_parent(server)
            server.messages["ses_current_child"][1] = assistant("ca", 3400, None)
            server.active = {"ses_current": {"type": "running"}, "ses_current_child": {"type": "running"}}
            server.messages["ses_current"].append({
                "id": "compact", "type": "compaction", "time": {"created": 5000}})
            record, = analyze_snapshot(source.load_session_snapshot("ses_current"), now_ms=6000).prompts
            self.assertTrue(record.in_progress)
            self.assertTrue(record.subagent_active)
            self.assertEqual("cancellation", record.parent_outcome)

    def test_unrelated_later_child_work_and_inactive_children_do_not_reopen_parent(self):
        with incident_source() as (source, server):
            stop_parent(server)
            server.messages["ses_current_child"].extend((user("other", 6000), assistant("later", 6100, None)))
            server.active = {"ses_current_child": {"type": "running"}}
            snapshot = source.load_session_snapshot("ses_current")
            record, = analyze_snapshot(snapshot, now_ms=20_000).prompts
            self.assertFalse(record.in_progress)
            self.assertTrue(record.aborted)
            self.assertEqual(2, record.model_calls)
            unrelated = replace(snapshot, sessions=tuple(
                replace(session, parent_session_id="other") if session.parent_session_id else session
                for session in snapshot.sessions))
            self.assertFalse(analyze_snapshot(unrelated, now_ms=20_000).prompts[0].in_progress)

    def test_siblings_and_nested_background_child_end_independently(self):
        with incident_source() as (source, server):
            stop_parent(server)
            sibling = link(child="sibling", start=3250, end=3900, background=True)
            sibling.update(id="sibling-link", callID="sibling-call")
            server.messages["ses_current"][1]["content"].append(sibling)
            template = server.sessions[1]
            server.sessions.extend(({**template, "id": "sibling"},
                {**template, "id": "nested", "parentID": "ses_current_child"}))
            server.messages["sibling"] = [user("su", 3300), assistant("sa", 3400, None)]
            server.messages["ses_current_child"][1]["content"] = [
                link(child="nested", start=3450, end=3500, background=True)]
            server.messages["nested"] = [user("nu", 3500), assistant("na", 3600, None)]
            server.active = {"sibling": {"type": "running"}, "nested": {"type": "running"}}
            self.assertTrue(analyze_snapshot(source.load_session_snapshot("ses_current"), now_ms=10_000).prompts[0].in_progress)
            server.messages["sibling"][1] = assistant("sa", 3400, 11_000)
            server.active.pop("sibling")
            nested_only = source.load_session_snapshot("ses_current")
            self.assertTrue(analyze_snapshot(nested_only, now_ms=12_000).prompts[0].in_progress)
            server.messages["nested"][1] = assistant("na", 3600, 13_000, count=0)
            server.active = {}
            final, = analyze_snapshot(source.load_session_snapshot("ses_current"), now_ms=14_000).prompts
            self.assertFalse(final.in_progress)
            self.assertTrue(final.aborted)
            self.assertEqual((4, 13_000), (final.model_calls, final.terminal_time_ms))

    def test_both_native_tool_names_and_background_shapes_share_lifecycle(self):
        for name in ("task", "subagent"):
            for background in (False, True):
                with self.subTest(name=name, background=background), incident_source(
                        name=name, background=background, end=0) as (source, server):
                    stop_parent(server)
                    server.messages["ses_current_child"][1] = assistant("ca", 3400, None)
                    server.active = {"ses_current_child": {"type": "running"}}
                    record, = analyze_snapshot(source.load_session_snapshot("ses_current"), now_ms=10_000).prompts
                    self.assertTrue(record.in_progress)

    def test_local_inactivity_is_unverified_until_owned_child_terminal(self):
        with incident_source() as (source, server):
            stop_parent(server)
            server.messages["ses_current_child"][1] = assistant("ca", 3400, None)
            server.active = {}
            record, = analyze_snapshot(source.load_session_snapshot("ses_current"), now_ms=10_000).prompts
            self.assertFalse(record.in_progress)
            self.assertTrue(record.execution_unverified)
            self.assertFalse(record.completed_successfully)
            self.assertIsNone(record.execution_duration_ms)
            server.messages["ses_current_child"].append({
                "id": "idle_child", "type": "idle", "outcome": "interrupted", "time": {"created": 12_000}})
            final, = analyze_snapshot(source.load_session_snapshot("ses_current"), now_ms=14_000).prompts
            self.assertFalse(final.execution_unverified)
            self.assertTrue(final.aborted)
            self.assertEqual(12_000, final.terminal_time_ms)

    def test_child_terminal_before_any_assistant_supplies_tree_end_without_fake_call(self):
        with incident_source() as (source, server):
            stop_parent(server)
            server.messages["ses_current_child"] = [user("cu", 3300),
                {"id": "idle_child", "type": "idle", "outcome": "interrupted", "time": {"created": 12_000}}]
            server.active = {"ses_current_child": {"type": "running"}}  # stale native flag loses to durable end
            record, = analyze_snapshot(source.load_session_snapshot("ses_current"), now_ms=20_000).prompts
            self.assertFalse(record.in_progress)
            self.assertFalse(record.execution_unverified)
            self.assertTrue(record.aborted)
            self.assertEqual((1, 12_000, 9000), (record.model_calls, record.terminal_time_ms, record.execution_duration_ms))

    def test_native_active_flag_cannot_resurrect_durable_child_end_or_lend_reused_work(self):
        with incident_source(background=True) as (source, server):
            stop_parent(server)
            server.active = {"ses_current_child": {"type": "running"}}
            # The owned attempt has a final response, not an unfinished request.
            self.assertFalse(analyze_snapshot(source.load_session_snapshot("ses_current"), now_ms=5000).prompts[0].in_progress)
            server.messages["ses_current"].extend((user("u2", 5000),
                assistant("a2", 5100, 5500, content=[{**link(start=5200, end=0),
                    "id": "second-link", "callID": "second-call"}], finish="tool-calls")))
            server.messages["ses_current_child"].extend((user("cu2", 5300), assistant("ca2", 5400, None)))
            old, current = analyze_snapshot(source.load_session_snapshot("ses_current"), now_ms=6000).prompts
            self.assertFalse(old.in_progress)
            self.assertTrue(current.in_progress)
            self.assertEqual(2, old.model_calls)

    def test_parent_failure_is_not_success_while_children_run_or_after_they_end(self):
        with incident_source() as (source, server):
            stop_parent(server)
            server.messages["ses_current"][1]["error"] = {"name": "APIError"}
            server.messages["ses_current_child"][1] = assistant("ca", 3400, None)
            server.active = {"ses_current_child": {"type": "running"}}
            running, = analyze_snapshot(source.load_session_snapshot("ses_current"), now_ms=5000).prompts
            self.assertTrue(running.in_progress)
            self.assertFalse(running.watch_error)
            self.assertFalse(running.completed_successfully)
            server.messages["ses_current_child"][1] = assistant("ca", 3400, 6000)
            server.active = {}
            final, = analyze_snapshot(source.load_session_snapshot("ses_current"), now_ms=7000).prompts
            self.assertTrue(final.watch_error)
            self.assertFalse(final.completed_successfully)


if __name__ == "__main__":
    unittest.main()
