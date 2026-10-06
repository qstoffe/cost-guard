from __future__ import annotations

import io
import unittest
from dataclasses import replace

from development.tests.test_analysis_core import make_snapshot
from development.tests.test_step6_context_comparisons import catalog as sample_catalog
from src.analysis import analyze_snapshot
from src.presentation import WatchRenderer
from src.reports.prompts import build_prompt_block
from src.watch.models import WatchProjection
from src.watch.tracker import WatchRowTracker


def _v2_zero_call_prompt_after_compaction(*, active: bool):
    """Reproduce current-V2 prompt -> auto-compact -> continuation ownership.

    The visible user prompt itself has no directly attributed model invocation.
    While the root is active it is still the logical running prompt.  Once idle,
    stateless prompt analysis omits that zero-call prompt; Watch must retain it.
    """
    snapshot = make_snapshot(generation="v2", running=False)
    messages = tuple(item for item in snapshot.messages if item.message_id != "a_next")
    invocations = tuple(item for item in snapshot.invocations if item.invocation_id != "i_next")
    root = replace(snapshot.root, active=active)
    sessions = tuple(root if item.session_id == root.session_id else item for item in snapshot.sessions)
    return replace(
        snapshot,
        root=root,
        sessions=sessions,
        messages=messages,
        parts=tuple(part for message in messages for part in message.parts),
        invocations=invocations,
        source_revision=f"v2-watch-compact-{'active' if active else 'idle'}",
    )


def _block(snapshot, *, now_ms: int):
    bundle = analyze_snapshot(snapshot, now_ms=now_ms, tracked_provider=None)
    block = build_prompt_block(
        session_id="root",
        title="DFP-10524 – Review",
        bundle=bundle,
        snapshot=snapshot,
        catalog=sample_catalog(),
        config={"thresholds": {}},
    )
    # Keep this regression focused on the prompt/compaction pair from the bug.
    rows = tuple(row for row in block.rows if row.event_id in {"u_next", "u_comp"})
    rows = tuple(replace(row, prompt_number=13) if row.event_id == "u_next" else row for row in rows)
    return replace(block, rows=rows)


class V7810RegressionTests(unittest.TestCase):
    def test_v2_running_prompt_moves_after_auto_compaction_and_keeps_number_on_completion(self) -> None:
        running_snapshot = _v2_zero_call_prompt_after_compaction(active=True)
        running_block = _block(running_snapshot, now_ms=3_400)
        running_prompt = next(row for row in running_block.rows if row.event_id == "u_next")
        self.assertTrue(running_prompt.in_progress)
        self.assertEqual(0, running_prompt.calls)

        tracker = WatchRowTracker(started_at_ms=0, recent_seconds=30, max_rows=20)
        rows = tracker.project({"root": running_block}, {"root": running_snapshot}, now_ms=3_400)
        event_ids = [row.prompt.event_id for row in rows]
        self.assertEqual(["u_comp", "u_next"], event_ids)
        self.assertTrue(rows[-1].is_latest_session_event)
        self.assertEqual(13, rows[-1].prompt.prompt_number)

        idle_snapshot = _v2_zero_call_prompt_after_compaction(active=False)
        idle_block = _block(idle_snapshot, now_ms=4_000)
        self.assertNotIn("u_next", {row.event_id for row in idle_block.rows}, "fixture must reproduce disappearing stateless row")

        completed = tracker.project({"root": idle_block}, {"root": idle_snapshot}, now_ms=4_000)
        self.assertEqual(["u_comp", "u_next"], [row.prompt.event_id for row in completed])
        retained = completed[-1]
        self.assertFalse(retained.prompt.in_progress)
        self.assertEqual("✓", retained.marker)
        self.assertEqual(13, retained.prompt.prompt_number)
        self.assertTrue(retained.is_latest_session_event)

        projection = WatchProjection(
            title="Cost Guard Watch", source_label="V2", rows=completed,
            active_count=0, status="Idle · Next prompt check: 00:30", now_ms=4_000,
        )
        stream = io.StringIO()
        WatchRenderer({"timezone": "UTC", "colors": {}, "thresholds": {}}, stream=stream, interactive=False).render(projection)
        lines = stream.getvalue().splitlines()
        compact_index = next(index for index, line in enumerate(lines) if "/compact" in line)
        prompt_index = next(index for index, line in enumerate(lines) if "#13 next" in line)
        self.assertLess(compact_index, prompt_index)

        aged = tracker.project({"root": idle_block}, {"root": idle_snapshot}, now_ms=40_000)
        self.assertEqual(["u_comp", "u_next"], [row.prompt.event_id for row in aged])
        self.assertEqual("", aged[-1].marker, "completion color may age out without deleting the retained prompt")
        self.assertEqual(13, aged[-1].prompt.prompt_number)


if __name__ == "__main__":
    unittest.main()
