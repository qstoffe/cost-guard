"""Current V2 compaction lifecycle and shared event-numbering regressions."""
from __future__ import annotations

import io
import unittest
from dataclasses import replace

from development.fixtures.session_snapshots import make_snapshot, message, part
from development.fixtures.pricing_catalog import catalog
from development.fixtures.opencode_v2_service import source_with_current_service
from src.analysis import analyze_snapshot
from src.analysis.causal import prompt_references
from src.domain import EventKind, MessageRole, NormalizedEvent
from src.presentation import ReportRenderer, WatchRenderer
from src.reports.prompts import build_prompt_block
from src.watch.models import WatchProjection
from src.watch.tracker import WatchRowTracker


def _stage(stage: str):
    base = make_snapshot(generation="v2", running=False)
    root = replace(base.root, active=stage != "completed")
    sessions = tuple(root if item.session_id == root.session_id else item for item in base.sessions)
    if stage == "before":
        messages = tuple(item for item in base.messages if item.message_id not in {"u_comp", "a_comp"})
        events = tuple(item for item in base.events if item.event_id != "u_comp")
    else:
        data = {"auto": True, "status": "running" if stage == "active" else "completed"}
        if stage == "completed":
            data["summary"] = "done"
            data["recent"] = "tail"
        compact = message(
            "u_comp", "root", MessageRole.USER, 3000,
            parts=(part("p_comp", "u_comp", "root", "compaction", data, 3000),),
            completed=None if stage == "active" else 3300,
        )
        messages = tuple(compact if item.message_id == "u_comp" else item for item in base.messages if item.message_id != "a_comp")
        events = base.events
    return replace(
        base, root=root, sessions=sessions, messages=messages,
        parts=tuple(p for item in messages for p in item.parts), events=events,
        invocations=tuple(item for item in base.invocations if item.invocation_id != "i_comp"),
        source_revision=f"compact-{stage}",
    )


def _block(snapshot):
    bundle = analyze_snapshot(snapshot, now_ms=3400, tracked_provider=None)
    block = build_prompt_block(
        session_id="root", title="Test", bundle=bundle, snapshot=snapshot,
        catalog=catalog(), config={"thresholds": {}},
    )
    return bundle, block


class V7811CompactionTests(unittest.TestCase):
    def test_current_v2_running_compaction_is_a_distinct_active_event(self):
        with source_with_current_service() as (source, service, _):
            service.active = {"ses_current": {"type": "running"}}
            service.messages["ses_current"].append({
                "id": "msg_compacting", "type": "compaction", "status": "running",
                "reason": "auto", "time": {"created": 5000},
            })
            snapshot = source.load_session_snapshot("ses_current")
            self.assertTrue(snapshot.root.active)
            self.assertEqual("running", next(p for p in snapshot.parts if p.kind == "compaction").data["status"])
            bundle = analyze_snapshot(snapshot, now_ms=5100, tracked_provider=None)
            self.assertEqual(["msg_compacting"], [item.user_message_id for item in bundle.compactions])
            self.assertTrue(bundle.compactions[0].in_progress)
            self.assertFalse(any(item.in_progress for item in bundle.prompts))

    def test_running_compaction_replaces_old_running_highlight_and_finishes_with_same_number(self):
        tracker = WatchRowTracker(started_at_ms=0, recent_seconds=30, max_rows=20)
        before = _stage("before")
        _bundle, block = _block(before)
        self.assertTrue(next(row for row in block.rows if row.event_id == "u_next").in_progress)
        tracker.project({"root": block}, {"root": before}, now_ms=2400)

        active = _stage("active")
        bundle, block = _block(active)
        self.assertFalse(bundle.cacheable)
        self.assertEqual(1, len(bundle.compactions))
        self.assertTrue(bundle.compactions[0].in_progress)
        self.assertEqual(3, next(row.prompt_number for row in block.rows if row.event_id == "u_comp"))
        active_compact = next(row for row in block.rows if row.event_id == "u_comp")
        self.assertIsNone(active_compact.next_context_tokens, "no finished shrink before the summary")
        rows = tracker.project({"root": block}, {"root": active}, now_ms=3400)
        self.assertFalse(next(row for row in rows if row.prompt.event_id == "u_next").prompt.in_progress)
        self.assertEqual(["u_comp"], [row.prompt.event_id for row in rows if row.prompt.in_progress])
        self.assertTrue(rows[-1].is_latest_session_event)
        output = io.StringIO()
        WatchRenderer({"timezone": "UTC", "colors": {}, "thresholds": {}}, stream=output, interactive=False).render(
            WatchProjection("Watch", "V2", rows, active_count=1, status="1 prompt running", now_ms=3400),
        )
        self.assertIn("#3 /compact", output.getvalue())
        self.assertIn("#2 next", output.getvalue())
        report_output = io.StringIO()
        ReportRenderer({"timezone": "UTC", "thresholds": {}}, stream=report_output, color_enabled=False)._render_prompt_block(block)
        self.assertIn("#3 /compact (auto) [RUNNING]", report_output.getvalue())

        completed = _stage("completed")
        bundle, block = _block(completed)
        self.assertFalse(bundle.compactions[0].in_progress)
        rows = tracker.project({"root": block}, {"root": completed}, now_ms=3600)
        self.assertEqual([], [row for row in rows if row.prompt.in_progress])
        self.assertEqual(3, next(row.prompt.prompt_number for row in rows if row.prompt.event_id == "u_comp"))
        report_output = io.StringIO()
        ReportRenderer({"timezone": "UTC", "thresholds": {}}, stream=report_output, color_enabled=False)._render_prompt_block(block)
        self.assertIn("#3 /compact (auto)", report_output.getvalue())
        self.assertNotIn("#3 /compact (auto) [RUNNING]", report_output.getvalue())

    def test_next_ordinary_prompt_has_distinct_number_after_compaction(self):
        snapshot = _stage("completed")
        later = NormalizedEvent("u_later", "root", EventKind.USER_PROMPT, 4000,
                                snapshot.events[0].provenance, "later")
        snapshot = replace(snapshot, root=replace(snapshot.root, active=True),
                           events=snapshot.events + (later,))
        self.assertEqual(4, prompt_references(snapshot)[-1].prompt_number)

    def test_failed_or_idle_incomplete_compaction_does_not_appear_running(self):
        active = _stage("active")
        idle = replace(active, root=replace(active.root, active=False))
        self.assertEqual((), analyze_snapshot(idle, now_ms=3400).compactions)
        failed = replace(active, messages=tuple(
            replace(item, parts=tuple(replace(p, data={**p.data, "status": "failed"}) for p in item.parts))
            if item.message_id == "u_comp" else item for item in active.messages
        ))
        self.assertEqual((), analyze_snapshot(failed, now_ms=3400).compactions)


if __name__ == "__main__":
    unittest.main()
