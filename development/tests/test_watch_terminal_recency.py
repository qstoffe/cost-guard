"""Global history membership uses terminal evidence, not prompt display placement."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
import io
import tempfile
import unittest

from development.tests.fixtures.opencode_v2_service import source_with_current_service
from development.tests.fixtures.session_snapshots import make_snapshot
from development.tests.fixtures.watch_runtime import make_service
from src.domain import EventKind, NormalizedEvent
from src.presentation import WatchRenderer
from src.reports.models import PromptProjection, SessionPromptBlock
from src.watch import WatchCoordinator
from src.watch.tracker import WatchRowTracker


def prompt(number, start, end=None, **state):
    return PromptProjection(
        at_ms=start, prompt_number=number, event_id=f"event-{number}", label=f"#{number}",
        preview="synthetic", model_effort="model", ccost=Decimal(1), cost_estimated=False,
        unresolved_cost=False, calls=1, incoming_context_tokens=None, incoming_context_ccost=None,
        extra_ccost=None, token_mix_percent=None, duration_ms=None, completed_at_ms=end, **state,
    )


def inputs(**sessions):
    base = make_snapshot()
    blocks, snapshots = {}, {}
    for session_id, rows in sessions.items():
        root = replace(base.root, session_id=session_id, title=session_id)
        events = tuple(NormalizedEvent(row.event_id, session_id,
                       EventKind.COMPACTION if row.is_compaction else EventKind.USER_PROMPT,
                       row.at_ms, base.events[0].provenance) for row in rows)
        blocks[session_id] = SessionPromptBlock(session_id, session_id, tuple(rows), Decimal(0), 0)
        snapshots[session_id] = replace(base, root=root, sessions=(root,), events=events,
                                        messages=(), parts=(), invocations=())
    return blocks, snapshots


class TerminalRecencyTests(unittest.TestCase):
    def test_long_running_prompt_survives_exact_highlight_expiry_for_every_outcome(self):
        for state, marker, label in (({"completed_successfully": True}, "✓", ""),
                                     ({"aborted": True}, "!", "[ABORTED]"),
                                     ({"watch_error": True}, "!", "[ERROR]")):
            with self.subTest(state=state):
                tracker = WatchRowTracker(started_at_ms=0, recent_seconds=30, max_rows=2)
                blocks, snapshots = inputs(A=(prompt(1, 100, in_progress=True),),
                                           B=(prompt(1, 200, 300),), C=(prompt(1, 400, 500),),
                                           D=(prompt(1, 600, 700),))
                tracker.project(blocks, snapshots, now_ms=1000)
                blocks["A"] = replace(blocks["A"], rows=(prompt(1, 100, 2000, **state),))
                for now in (2000, 31_999, 32_000, 90_000):
                    rows = tracker.project(blocks, snapshots, now_ms=now)
                    row = next(row for row in rows if row.session_id == "A")
                    self.assertEqual(marker if now < 32_000 else "", row.marker)
                    self.assertEqual(2000, row.prompt.completed_at_ms)
                    if now >= 32_000:
                        self.assertEqual(["D", "A"], [row.session_id for row in rows])
                        self.assertEqual(2000, rows[-1].session_latest_ms)
                        self.assertFalse(rows[-1].session_active)
                        self.assertIsNone(rows[-1].tool)
                    renderer = WatchRenderer({"colors": {}}, stream=io.StringIO(), interactive=True)
                    if label:
                        self.assertIn(label, renderer._row_label(row))
                    if now >= 32_000:
                        self.assertIsNone(renderer._row_style(row))
                newer, newer_snapshots = inputs(E=(prompt(1, 3000, 4000),), F=(prompt(1, 5000, 6000),))
                rows = tracker.project({**blocks, **newer}, {**snapshots, **newer_snapshots}, now_ms=100_000)
                self.assertNotIn("A", [row.session_id for row in rows], "newer completions evict normally")

    def test_unknown_end_uses_start_until_later_authoritative_revision_and_never_poll_time(self):
        tracker = WatchRowTracker(started_at_ms=0, recent_seconds=1, max_rows=1)
        blocks, snapshots = inputs(A=(prompt(1, 100, in_progress=True),), B=(prompt(1, 200, 500),))
        tracker.project(blocks, snapshots, now_ms=1000)
        blocks["A"] = replace(blocks["A"], rows=(prompt(1, 100, aborted=True),))
        recent = tracker.project(blocks, snapshots, now_ms=2000)
        self.assertIn("A", [row.session_id for row in recent])
        for now in (3000, 10_000, 100_000):
            rows = tracker.project(blocks, snapshots, now_ms=now)
            self.assertEqual(["B"], [row.session_id for row in rows])
        blocks["A"] = replace(blocks["A"], title="renamed", rows=(prompt(1, 100, 600, aborted=True),))
        for now in (100_001, 200_000, 900_000):
            snapshots["A"] = replace(snapshots["A"], source_revision=str(now))
            rows = tracker.project(blocks, snapshots, now_ms=now)
            self.assertEqual(["A"], [row.session_id for row in rows])
            self.assertEqual((600, 600, ""), (rows[0].prompt.completed_at_ms, rows[0].session_latest_ms, rows[0].marker))

    def test_history_selection_does_not_reorder_prompts_or_compaction_within_session(self):
        tracker = WatchRowTracker(started_at_ms=0, recent_seconds=0, max_rows=3)
        blocks, snapshots = inputs(A=(prompt(1, 100, 900), prompt(2, 200, 300, is_compaction=True),
                                      prompt(3, 200, 900)), B=(prompt(1, 400, 500),))

        rows = tracker.project(blocks, snapshots, now_ms=1000)

        self.assertEqual([("B", 1), ("A", 1), ("A", 3)],
                         [(row.session_id, row.prompt.prompt_number) for row in rows])
        tracker.max_rows = 4
        rows = tracker.project(dict(reversed(list(blocks.items()))), snapshots, now_ms=2000)
        self.assertEqual([1, 2, 3], [row.prompt.prompt_number for row in rows if row.session_id == "A"])
        self.assertEqual(900, rows[-1].session_latest_ms)

    def test_cold_unknown_end_and_connectivity_gap_do_not_manufacture_recency(self):
        tracker = WatchRowTracker(started_at_ms=0, recent_seconds=0, max_rows=1)
        blocks, snapshots = inputs(A=(prompt(1, 100),), B=(prompt(1, 200),))
        for now in (1000, 900_000):
            rows = tracker.project(blocks, snapshots, now_ms=now)
            self.assertEqual(["B"], [row.session_id for row in rows])
            self.assertEqual(200, rows[0].session_latest_ms)
            self.assertIsNone(rows[0].prompt.completed_at_ms)
        # An unavailable snapshot is not a terminal projection/transition.
        live_blocks, live_snapshots = inputs(A=(prompt(1, 100, in_progress=True),))
        tracker.project(live_blocks, live_snapshots, now_ms=1_000_000)
        self.assertEqual((), tracker.project(live_blocks, {}, now_ms=2_000_000))
        resumed = tracker.project(live_blocks, live_snapshots, now_ms=3_000_000)
        self.assertTrue(resumed[0].prompt.in_progress)
        self.assertIsNone(resumed[0].prompt.completed_at_ms)
        self.assertEqual("▶", resumed[0].marker)

    def test_equal_ends_have_stable_ties_and_session_watch_keeps_start_based_selection(self):
        blocks, snapshots = inputs(A=(prompt(1, 100, 900),), B=(prompt(1, 200, 900),))
        tracker = WatchRowTracker(started_at_ms=0, recent_seconds=0, max_rows=1)
        for mapping in (blocks, dict(reversed(list(blocks.items())))):
            self.assertEqual(["B"], [row.session_id for row in tracker.project(mapping, snapshots, now_ms=1000)])
        blocks, snapshots = inputs(A=(prompt(1, 100, 900), prompt(2, 200, 300)))
        scoped = WatchRowTracker(started_at_ms=0, recent_seconds=0, max_rows=1, session_scope=True)
        self.assertEqual([2], [row.prompt.prompt_number for row in scoped.project(blocks, snapshots, now_ms=1000)])

    def test_disappeared_compaction_row_keeps_identity_without_fabricated_end_ranking(self):
        tracker = WatchRowTracker(started_at_ms=0, recent_seconds=1, max_rows=3)
        compact = prompt(2, 200, 300, is_compaction=True)
        blocks, snapshots = inputs(A=(prompt(1, 100, in_progress=True), compact), B=(prompt(1, 400, 500),))
        tracker.project(blocks, snapshots, now_ms=1000)
        blocks["A"] = replace(blocks["A"], rows=(compact,))
        tracker.project(blocks, snapshots, now_ms=2000)

        rows = tracker.project(blocks, snapshots, now_ms=3000)

        retained = next(row for row in rows if row.session_id == "A" and row.prompt.prompt_number == 1)
        self.assertIsNone(retained.prompt.completed_at_ms)
        self.assertEqual(300, retained.session_latest_ms)
        self.assertEqual([2, 1], [row.prompt.prompt_number for row in rows if row.session_id == "A"])
        tracker.max_rows = 1
        self.assertEqual(["B"], [row.session_id for row in tracker.project(blocks, snapshots, now_ms=9000)])

    def test_earlier_representatives_still_compete_by_start_not_terminal_time(self):
        tracker = WatchRowTracker(started_at_ms=1000, recent_seconds=0, max_rows=1)
        tracker.set_earlier_sessions(("A", "B"))
        blocks, snapshots = inputs(A=(prompt(1, 100, 900),), B=(prompt(1, 200, 300),))
        rows = tracker.project(blocks, snapshots, now_ms=1000)
        self.assertEqual(["B"], [row.session_id for row in rows])
        self.assertTrue(rows[0].earlier)
        tracker.max_rows = 2
        self.assertEqual(["B"], [row.session_id for row in tracker.project(blocks, snapshots, now_ms=2000)])


class NativeTerminalRecencyTests(unittest.TestCase):
    def test_plugin_tool_alone_does_not_finish_prompt_but_native_interruption_ranks_its_end(self):
        with source_with_current_service() as (source, native, _), tempfile.TemporaryDirectory() as td:
            assistant = native.messages["ses_current"][1]
            assistant["finish"] = "tool-calls"
            assistant["content"] = [{"id": "plugin", "type": "tool", "name": "plugin-stop",
                                      "time": {"created": 3500, "completed": 4000},
                                      "state": {"status": "completed"}}]
            config, selection, reports, _ = make_service(td, source)
            clock = [5000]
            watch = WatchCoordinator(selection=selection, report_service=reports, config=config,
                                     clock_ms=lambda: clock[0])
            self.addCleanup(watch.close)
            initial = watch.initialize().projection.rows[0]
            self.assertTrue(initial.prompt.in_progress)
            self.assertFalse(initial.prompt.completed_successfully)
            self.assertIsNone(initial.prompt.completed_at_ms)
            # A synthetic plugin-driven stop supplies the same persisted native
            # interruption as a user stop. The tool name is not terminal evidence.
            native.messages["ses_current"].append({"id": "plugin_terminal", "type": "idle",
                "outcome": "interrupted", "time": {"created": 6000}})
            native.sessions[0]["time"]["updated"] = 6000
            clock[0] = 7000
            terminal = watch.poll_once(force_resync=True).projection.rows[0]
            self.assertEqual((True, False, False, 6000), (terminal.prompt.aborted,
                terminal.prompt.completed_successfully, terminal.prompt.watch_error, terminal.prompt.completed_at_ms))
            self.assertEqual("!", terminal.marker)
            # Global cap: later-started work ended earlier than the plugin stop.
            blocks, snapshots = inputs(newer_start=(prompt(1, 4500, 5500),))
            watch.blocks.update(blocks)
            watch.snapshots.update(snapshots)
            watch.tracker.max_rows = 1
            rows = watch._projection(now_ms=40_000).rows
            self.assertEqual(["ses_current"], [row.session_id for row in rows])
            self.assertEqual((6000, ""), (rows[0].session_latest_ms, rows[0].marker))


if __name__ == "__main__":
    unittest.main()
