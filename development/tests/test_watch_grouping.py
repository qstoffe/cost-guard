"""Global Watch grouping without changing selection or per-session lifecycle."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
import io
from itertools import groupby
import unittest

from development.tests.test_analysis_core import make_snapshot
from src.domain import EventKind, NormalizedEvent
from src.presentation import WatchRenderer
from src.reports.models import PromptProjection, SessionPromptBlock
from src.watch.models import WatchProjection
from src.watch.tracker import WatchRowTracker


def prompt(number, at_ms, **changes):
    return PromptProjection(
        at_ms=at_ms, prompt_number=number, event_id=f"event-{number}",
        label=f"#{number}", preview=f"prompt {number}", model_effort="model",
        ccost=Decimal(0), cost_estimated=False, unresolved_cost=False, calls=0,
        incoming_context_tokens=None, incoming_context_ccost=None,
        extra_ccost=None, token_mix_percent=None, **changes,
    )


def inputs(**sessions):
    base = make_snapshot()
    blocks, snapshots = {}, {}
    for session_id, rows in sessions.items():
        root = replace(base.root, session_id=session_id, title=f"Session {session_id}")
        events = tuple(NormalizedEvent(
            row.event_id, session_id,
            EventKind.COMPACTION if row.is_compaction else EventKind.USER_PROMPT,
            row.at_ms, base.events[0].provenance,
        ) for row in rows)
        blocks[session_id] = SessionPromptBlock(session_id, root.title, tuple(rows), Decimal(0), 0)
        snapshots[session_id] = replace(
            base, root=root, sessions=(root,), events=events,
            messages=(), parts=(), invocations=(),
        )
    return blocks, snapshots


def tracker(*, max_rows=20, recent_seconds=0, session_scope=False):
    return WatchRowTracker(
        started_at_ms=0, recent_seconds=recent_seconds,
        max_rows=max_rows, session_scope=session_scope,
    )


class WatchGroupingTests(unittest.TestCase):
    def assert_contiguous(self, rows):
        blocks = [session_id for session_id, _ in groupby(rows, key=lambda row: row.session_id)]
        self.assertEqual(len(set(blocks)), len(blocks))
        return blocks

    def test_interleaved_prompts_are_contiguous_and_render_one_header_each(self):
        blocks, snapshots = inputs(
            A=(prompt(1, 100), prompt(2, 300)),
            B=(prompt(1, 200), prompt(2, 400)),
        )
        rows = tracker().project(blocks, snapshots, now_ms=500)
        self.assertEqual(["A", "B"], self.assert_contiguous(rows))
        self.assertEqual([("A", 1), ("A", 2), ("B", 1), ("B", 2)],
                         [(row.session_id, row.prompt.prompt_number) for row in rows])
        for session_id in blocks:
            single = tracker(session_scope=True).project(
                {session_id: blocks[session_id]}, {session_id: snapshots[session_id]}, now_ms=500,
            )
            self.assertEqual(single, tuple(row for row in rows if row.session_id == session_id))
        output = io.StringIO()
        renderer = WatchRenderer({"colors": {}}, stream=output, interactive=False)
        projection = WatchProjection("Watch", "V2", rows, now_ms=500)
        table, styles, _ = renderer._table_rows(projection)
        headers = [row[0] for row, style in zip(table, styles) if style[0] == "watchSessionHeader"]
        self.assertEqual(["Session A", "Session B"], headers)
        renderer.render(projection)
        self.assertEqual(1, output.getvalue().count("Session A"))
        self.assertEqual(1, output.getvalue().count("Session B"))

    def test_block_order_uses_latest_activity_not_first_prompt(self):
        blocks, snapshots = inputs(
            A=(prompt(1, 100), prompt(2, 500)),
            B=(prompt(1, 200), prompt(2, 300)),
        )
        rows = tracker().project(blocks, snapshots, now_ms=600)
        self.assertEqual(["B", "A"], self.assert_contiguous(rows))

    def test_equal_activity_uses_session_id_not_input_order_or_event_sequence(self):
        blocks, snapshots = inputs(
            B=(prompt(1, 100), prompt(2, 300)), A=(prompt(1, 300),),
        )
        expected = tracker().project(blocks, snapshots, now_ms=400)
        self.assertEqual(["A", "B"], self.assert_contiguous(expected))
        reversed_rows = tracker().project(dict(reversed(list(blocks.items()))), snapshots, now_ms=400)
        self.assertEqual(expected, reversed_rows)

    def test_compaction_continuation_retention_and_warnings_keep_canonical_order(self):
        warning = "[context threshold exceeded]"
        running = prompt(1, 100, in_progress=True, watch_next_context_warning=warning)
        compact = prompt(2, 300, is_compaction=True)
        blocks, snapshots = inputs(A=(running, compact), B=(prompt(1, 200), prompt(2, 400)))
        global_tracker = tracker(recent_seconds=30)
        single_tracker = tracker(recent_seconds=30, session_scope=True)
        for now_ms, missing in ((500, False), (600, True), (40_000, True)):
            if missing:
                blocks["A"] = replace(blocks["A"], rows=(compact,))
            rows = global_tracker.project(blocks, snapshots, now_ms=now_ms)
            self.assertEqual(["A", "B"], self.assert_contiguous(rows))
            session_rows = tuple(row for row in rows if row.session_id == "A")
            single = single_tracker.project({"A": blocks["A"]}, {"A": snapshots["A"]}, now_ms=now_ms)
            self.assertEqual(single, session_rows)
            self.assertEqual([2, 1], [row.prompt.prompt_number for row in session_rows])
            self.assertEqual("", session_rows[0].next_context_warning)
            self.assertEqual(warning, session_rows[-1].next_context_warning)
            self.assertTrue(session_rows[-1].is_latest_session_event)
            self.assertEqual("+" if not missing else ("✓" if now_ms == 600 else ""), session_rows[-1].marker)
            self.assertEqual(not missing, session_rows[-1].prompt.in_progress)
            output = io.StringIO()
            renderer = WatchRenderer({"colors": {}}, stream=output, interactive=False)
            projection = WatchProjection("Watch", "V2", rows, now_ms=now_ms, session_warnings={"A": warning})
            _table, styles, _activities = renderer._table_rows(projection)
            self.assertEqual(2, sum(style[0] == "watchSessionHeader" for style in styles))
            renderer.render(projection)
            self.assertEqual(1, output.getvalue().count("Session A"))
            self.assertEqual(1, output.getvalue().count("*1 Next Ictx:"))

    def test_max_rows_keeps_same_globally_newest_ordinary_and_all_protected_rows(self):
        blocks, snapshots = inputs(
            A=(prompt(1, 10, in_progress=True), prompt(2, 100), prompt(3, 500)),
            B=(prompt(1, 20, watch_error=True), prompt(2, 200), prompt(3, 400)),
        )
        ordinary = [("A", "event-2"), ("B", "event-2"), ("B", "event-3"), ("A", "event-3")]
        protected = {("A", "event-1"), ("B", "event-1")}
        for limit in range(1, 7):
            with self.subTest(max_rows=limit):
                rows = tracker(max_rows=limit).project(blocks, snapshots, now_ms=600)
                self.assert_contiguous(rows)
                room = max(0, limit - len(protected))
                expected = protected | (set(ordinary[-room:]) if room else set())
                self.assertEqual(expected, {(row.session_id, row.prompt.event_id) for row in rows})
                self.assertEqual(max(limit, len(protected)), len(rows))

    def test_block_activity_uses_selected_rows_not_excluded_session_history(self):
        blocks, snapshots = inputs(
            A=(prompt(1, 100, in_progress=True), prompt(2, 1100)),
            B=(prompt(1, 200, in_progress=True), prompt(2, 1000)),
        )
        rows = tracker(max_rows=2).project(blocks, snapshots, now_ms=1200)
        self.assertEqual(["A", "B"], self.assert_contiguous(rows))
        self.assertEqual([1, 1], [row.prompt.prompt_number for row in rows])

    def test_recent_markers_remain_protected_over_cap_then_age_normally(self):
        blocks, snapshots = inputs(
            A=(prompt(1, 100), prompt(2, 300, in_progress=True)),
            B=(prompt(1, 200), prompt(2, 400, aborted=True)),
        )
        observed = tracker(max_rows=2, recent_seconds=30)
        rows = observed.project(blocks, snapshots, now_ms=500)
        self.assertEqual(["A", "B"], self.assert_contiguous(rows))
        self.assertEqual(["✓", "+", "✓", "!"], [row.marker for row in rows])
        self.assertEqual(4, len(rows), "recent/protected rows can exceed max_rows")
        rows = observed.project(blocks, snapshots, now_ms=40_000)
        self.assertEqual(["A", "B"], self.assert_contiguous(rows))
        self.assertEqual([("A", 2), ("B", 2)], [(row.session_id, row.prompt.prompt_number) for row in rows])
        self.assertEqual(["", ""], [row.marker for row in rows])
        self.assertTrue(rows[0].prompt.in_progress, "active row stays protected after + expires")
        self.assertTrue(rows[1].prompt.aborted)

    def test_empty_projection_and_single_session_historical_rows_are_unchanged(self):
        self.assertEqual((), tracker().project({}, {}, now_ms=500))
        blocks, snapshots = inputs(A=(prompt(2, 300), prompt(1, 100)))
        scoped = WatchRowTracker(started_at_ms=500, recent_seconds=0, max_rows=1, session_scope=True)
        rows = scoped.project(blocks, snapshots, now_ms=600)
        self.assertEqual([2], [row.prompt.prompt_number for row in rows])
        self.assertEqual((), WatchRowTracker(started_at_ms=500, recent_seconds=0, max_rows=1).project(
            blocks, snapshots, now_ms=600,
        ))


if __name__ == "__main__":
    unittest.main()
