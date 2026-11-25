"""Global Watch prompt retention, startup Earlier sessions, session order/headers and warnings."""
from __future__ import annotations

from dataclasses import replace
from datetime import timezone
from decimal import Decimal
import io
import re
import tempfile
import unittest

from development.tests.fixtures.session_snapshots import make_snapshot
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from development.tests.fixtures.watch_runtime import MutableSource, make_service
from src.analysis.context import PriceWarningSeverity
from src.domain import EventKind, NormalizedEvent
from src.presentation import WatchRenderer
from src.reports.models import PromptProjection, SessionPromptBlock
from src.watch import WatchCoordinator
from src.watch.models import WatchProjection
from src.watch.tracker import WatchRowTracker

MINUTE = 60_000
NOW = 1_000 * MINUTE
EXCEEDED = "[Price threshold >200.0K exceeded]"
EARLIER_NOTE = "[Earlier] Session activity before Watch started; excluded from Token Mix and Watch total CCost."


def prompt(number, at_ms, *, duration_ms=1_000, **changes):
    return PromptProjection(
        at_ms=at_ms, prompt_number=number, event_id=f"event-{number}",
        label=f"#{number}", preview=f"prompt {number}", model_effort="model",
        ccost=Decimal(1), cost_estimated=False, unresolved_cost=False, calls=1,
        incoming_context_tokens=None, incoming_context_ccost=None,
        extra_ccost=None, token_mix_percent=None, duration_ms=duration_ms, **changes,
    )


def compaction(number, at_ms):
    return replace(prompt(number, at_ms), is_compaction=True, calls=0, ccost=Decimal(0))


def running(number, at_ms, **changes):
    return prompt(number, at_ms, duration_ms=None, in_progress=True, **changes)


def finished_at(number, end_ms, **changes):
    """A completed prompt whose source end time is ``end_ms``."""
    return prompt(number, end_ms - 1_000, **changes)


def inputs(**sessions):
    base = make_snapshot()
    blocks, snapshots = {}, {}
    for session_id, rows in sessions.items():
        root = replace(base.root, session_id=session_id, title=f"Session {session_id}")
        events = tuple(NormalizedEvent(row.event_id, session_id,
                                       EventKind.COMPACTION if row.is_compaction else EventKind.USER_PROMPT,
                                       row.at_ms, base.events[0].provenance) for row in rows)
        blocks[session_id] = SessionPromptBlock(session_id, root.title, tuple(rows), Decimal(0), 0)
        snapshots[session_id] = replace(base, root=root, sessions=(root,), events=events,
                                        messages=(), parts=(), invocations=())
    return blocks, snapshots


def tracker(*, started_at_ms=0, max_rows=12, recent_seconds=0):
    return WatchRowTracker(started_at_ms=started_at_ms, recent_seconds=recent_seconds, max_rows=max_rows)


def sessions(rows):
    return sorted({row.session_id for row in rows})


def shown(rows):
    return [(row.session_id, row.prompt.prompt_number) for row in rows]


def block_order(rows):
    return list(dict.fromkeys(row.session_id for row in rows))


def warned(number, at_ms, warning=EXCEEDED, severity=PriceWarningSeverity.EXCEEDED, multiplier="1.9", **changes):
    return finished_at(number, at_ms, watch_next_context_warning=warning,
                       watch_next_context_warning_severity=severity, watch_next_context_tokens=210_000,
                       watch_next_context_cost_multiplier=None if multiplier is None else Decimal(multiplier),
                       **changes)


def rendered(projection, *, width=200, config=None, interactive=False):
    stream = io.StringIO()
    WatchRenderer(config or {"colors": {}, "timezone": "UTC"}, stream=stream, interactive=interactive,
                  terminal_width=width).render(projection)
    return stream.getvalue()


class GlobalRetentionTests(unittest.TestCase):
    def test_one_session_keeps_ten_prompts_and_only_the_newest_twelve_of_twenty(self):
        blocks, snapshots = inputs(A=tuple(prompt(number, number * 1_000) for number in range(1, 11)))
        self.assertEqual(10, len(tracker().project(blocks, snapshots, now_ms=NOW)))
        blocks, snapshots = inputs(A=tuple(prompt(number, number * 1_000) for number in range(1, 21)))
        rows = tracker().project(blocks, snapshots, now_ms=NOW)
        self.assertEqual(list(range(9, 21)), [row.prompt.prompt_number for row in rows])

    def test_sessions_share_one_budget_and_disappear_only_after_their_last_prompt(self):
        observed = tracker(max_rows=4)
        older = tuple(prompt(number, number * 1_000) for number in range(1, 4))
        for count in range(1, 5):
            blocks, snapshots = inputs(A=older, B=tuple(prompt(n, 10_000 + n) for n in range(1, count + 1)))
            rows = observed.project(blocks, snapshots, now_ms=NOW)
            self.assertEqual(4, len(rows))
            self.assertEqual(min(3, 4 - count), sum(row.session_id == "A" for row in rows))
        self.assertEqual(["B"], sessions(rows), "A vanishes only once its final prompt is evicted")

    def test_no_idle_expiry_and_new_session_evicts_nothing_while_capacity_remains(self):
        blocks, snapshots = inputs(A=(finished_at(1, NOW - 60 * MINUTE),), B=(finished_at(1, NOW - 50 * MINUTE),))
        observed = tracker()
        for day in (0, 1, 30):
            self.assertEqual(["A", "B"], sessions(observed.project(blocks, snapshots, now_ms=NOW + day * 1_440 * MINUTE)))
        more, more_snapshots = inputs(C=(running(1, NOW),))
        blocks.update(more)
        snapshots.update(more_snapshots)
        self.assertEqual(["A", "B", "C"], sessions(observed.project(blocks, snapshots, now_ms=NOW + 1)))

    def test_running_and_highlighted_rows_form_a_soft_limit(self):
        names = "ABCDE"
        blocks, snapshots = inputs(**{name: tuple(running(n, NOW + index * 10 + n) for n in range(1, 4))
                                      for index, name in enumerate(names)})
        observed = tracker(started_at_ms=NOW, recent_seconds=30)
        self.assertEqual(15, len(observed.project(blocks, snapshots, now_ms=NOW + 100)))
        done = {name: replace(block, rows=tuple(replace(row, in_progress=False, duration_ms=5) for row in block.rows))
                for name, block in blocks.items()}
        rows = observed.project(done, snapshots, now_ms=NOW + 1_000)
        self.assertEqual(15 * ["✓"], [row.marker for row in rows], "recent green rows stay protected")
        rows = observed.project(done, snapshots, now_ms=NOW + 31_000)
        self.assertEqual(12, len(rows), "marker expiry alone restores the ordinary limit")
        self.assertNotIn("A", sessions(rows))

    def test_eight_running_prompts_fill_the_rest_with_newest_history(self):
        history = tuple(prompt(number, NOW + number) for number in range(1, 21))
        active = tuple(running(number, NOW + 100 + number) for number in range(21, 29))
        blocks, snapshots = inputs(A=history + active)
        rows = tracker(started_at_ms=NOW).project(blocks, snapshots, now_ms=NOW + 200)
        self.assertEqual(list(range(17, 29)), [row.prompt.prompt_number for row in rows])
        twelve, twelve_snapshots = inputs(A=history + tuple(running(n, NOW + 100 + n) for n in range(21, 33)))
        rows = tracker(started_at_ms=NOW).project(twelve, twelve_snapshots, now_ms=NOW + 200)
        self.assertTrue(all(row.prompt.in_progress for row in rows))
        self.assertEqual(12, len(rows))

    def test_compaction_is_an_ordinary_prompt_like_row(self):
        blocks, snapshots = inputs(A=(prompt(1, 100), prompt(2, 300)), B=(compaction(1, 400),))
        rows = tracker(max_rows=2).project(blocks, snapshots, now_ms=NOW)
        self.assertEqual([("A", 2), ("B", 1)], shown(rows), "/compact takes a slot and orders its session")
        self.assertIn("/compact", rendered(WatchProjection("Watch", "V2", rows, now_ms=NOW)))


class EarlierSessionTests(unittest.TestCase):
    def history(self):
        return inputs(A=(prompt(1, 1_000), prompt(2, 2_000)), B=(prompt(1, 1_500), prompt(2, 3_000)),
                      C=(prompt(1, 500),))

    def test_earlier_sessions_show_only_their_latest_prompt_and_resume_into_current_run(self):
        blocks, snapshots = self.history()
        observed = tracker(started_at_ms=NOW)
        observed.set_earlier_sessions(("B", "A"))
        rows = observed.project(blocks, snapshots, now_ms=NOW)
        self.assertEqual([("A", 2), ("B", 2)], shown(rows))
        self.assertEqual([True, True], [row.earlier for row in rows])
        self.assertEqual([2_000, 3_000], [row.session_latest_ms for row in rows])
        blocks["A"] = replace(blocks["A"], rows=blocks["A"].rows + (running(3, NOW + 1_000),))
        for now_ms in (NOW + 1_100, NOW + 2_000, NOW + 3_000):
            rows = observed.project(blocks, snapshots, now_ms=now_ms)
            self.assertEqual([("B", 2), ("A", 3)], shown(rows), "the placeholder is replaced and never reappears")
            self.assertEqual([True, False], [row.earlier for row in rows])
        blocks["A"] = replace(blocks["A"], rows=blocks["A"].rows[:2] + (prompt(3, NOW + 1_000), prompt(4, NOW + 5_000)))
        rows = observed.project(blocks, snapshots, now_ms=NOW + 6_000)
        self.assertEqual([("B", 2), ("A", 3), ("A", 4)], shown(rows))

    def test_resumed_by_compaction_and_running_representative_is_not_earlier(self):
        blocks, snapshots = self.history()
        blocks["A"] = replace(blocks["A"], rows=blocks["A"].rows + (compaction(3, NOW + 10),))
        blocks["B"] = replace(blocks["B"], rows=(prompt(1, 1_500), running(2, 3_000)))
        observed = tracker(started_at_ms=NOW)
        observed.set_earlier_sessions(("A", "B"))
        rows = observed.project(blocks, snapshots, now_ms=NOW + 20)
        self.assertEqual([("A", 3), ("B", 2)], shown(rows))
        self.assertEqual([False, False], [row.earlier for row in rows])
        self.assertTrue(rows[1].prompt.in_progress)

    def test_evicted_representatives_are_not_resurrected(self):
        blocks, snapshots = self.history()
        observed = tracker(started_at_ms=NOW, max_rows=2)
        observed.set_earlier_sessions(("B", "A"))
        self.assertEqual(["A", "B"], sessions(observed.project(blocks, snapshots, now_ms=NOW)))
        current, current_snapshots = inputs(D=(prompt(1, NOW + 1),))
        observed.project({**blocks, **current}, {**snapshots, **current_snapshots}, now_ms=NOW + 2)
        for _ in range(3):  # resync/idle polls after the newer session disappears
            self.assertEqual(["B"], sessions(observed.project(blocks, snapshots, now_ms=NOW + 3)))

    def test_earlier_representatives_compete_for_the_global_soft_cap_with_running_prompts(self):
        for running_count in range(17):
            data = {"A": (prompt(1, 1_000),), "B": (prompt(1, 2_000),)}
            if running_count:
                data["R"] = tuple(running(number, NOW + number) for number in range(1, running_count + 1))
            blocks, snapshots = inputs(**data)
            observed = tracker(started_at_ms=NOW, max_rows=15)
            observed.set_earlier_sessions(("B", "A"))
            rows = observed.project(blocks, snapshots, now_ms=NOW + running_count + 10)
            expected_earlier = min(2, max(0, 15 - running_count))
            self.assertEqual(expected_earlier, sum(row.earlier for row in rows), running_count)
            self.assertEqual(running_count + expected_earlier, len(rows), running_count)

    def test_newer_ordinary_row_can_evict_earlier_and_protected_completion_wins(self):
        blocks, snapshots = inputs(A=(prompt(1, 1_000),), B=(prompt(1, 2_000),),
                                   C=(prompt(1, NOW + 1),), R=(running(1, NOW + 2),))
        observed = tracker(started_at_ms=NOW, max_rows=3)
        observed.set_earlier_sessions(("B", "A"))
        rows = observed.project(blocks, snapshots, now_ms=NOW + 10)
        self.assertEqual(["B", "C", "R"], block_order(rows))
        self.assertEqual([True, False, False], [row.earlier for row in rows])

        blocks, snapshots = inputs(A=(prompt(1, 1_000),), C=(prompt(1, NOW + 1),))
        observed = tracker(started_at_ms=NOW, max_rows=1, recent_seconds=30)
        observed.set_earlier_sessions(("A",))
        rows = observed.project(blocks, snapshots, now_ms=NOW + 10)
        self.assertEqual(["C"], sessions(rows))
        self.assertEqual("✓", rows[0].marker)

    def coordinator(self, td, count, *, metadata_newest="root-0000"):
        source = SyntheticMonthSource(6, 2, month_start_ms=NOW - 60 * MINUTE)
        root = source.snapshots[metadata_newest].root
        source.snapshots[metadata_newest] = replace(source.snapshots[metadata_newest],
                                                    root=replace(root, updated_at_ms=NOW))
        config, selection, service, _ = make_service(td, source, now_ms=NOW)
        config.update(watchStartupEarlierSessions=count)
        watch = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: NOW)
        self.addCleanup(watch.close)
        return watch, source

    def test_startup_selects_earlier_sessions_by_latest_prompt_start_not_metadata(self):
        for count, expected in ((0, []), (1, ["root-0005"]), (2, ["root-0004", "root-0005"]),
                                (5, ["root-0001", "root-0002", "root-0003", "root-0004", "root-0005"])):
            with self.subTest(count=count), tempfile.TemporaryDirectory() as td:
                watch, _source = self.coordinator(td, count)
                projection = watch.initialize().projection
                self.assertEqual(expected, block_order(projection.rows))
                self.assertEqual([1] * count, [sum(r.session_id == s for r in projection.rows) for s in expected])
                self.assertTrue(all(row.earlier and row.prompt.prompt_number == 2 for row in projection.rows))
                self.assertEqual(0, projection.token_mix.request_count, "historical rows never enter run usage")
                self.assertEqual(0, projection.run_total.request_count)
                self.assertEqual(int(count > 0), rendered(projection).count(EARLIER_NOTE))

    def test_cached_quiet_roots_keep_the_same_selection_and_hydrate_only_earlier(self):
        with tempfile.TemporaryDirectory() as td:
            watch, source = self.coordinator(td, 2)
            first = watch.initialize().projection
            again = WatchCoordinator(selection=watch.selection, report_service=watch.report_service,
                                     config=watch.config, clock_ms=lambda: NOW + MINUTE)
            self.addCleanup(again.close)
            loads = source.load_count
            cycle = again.initialize()
            self.assertEqual(block_order(first.rows), block_order(cycle.projection.rows))
            self.assertEqual(2, source.load_count - loads, "quiet non-Earlier roots stay unhydrated")
            self.assertEqual(4, again.startup_quiet_roots)


class OrderingAndHeaderTests(unittest.TestCase):
    def test_active_blocks_follow_exact_latest_prompt_start_not_completion_or_polling(self):
        blocks, snapshots = inputs(A=(prompt(1, NOW + 1, duration_ms=50 * MINUTE),), B=(prompt(1, NOW),),
                                   C=(prompt(1, NOW + 1),))
        observed = tracker(recent_seconds=120 * 60)
        self.assertEqual(["B", "A", "C"], block_order(observed.project(blocks, snapshots, now_ms=NOW + MINUTE)),
                         "millisecond precision within one displayed minute; session ID breaks ties")
        blocks["B"] = replace(blocks["B"], title="Renamed", rows=(prompt(1, NOW, duration_ms=90 * MINUTE),))
        self.assertEqual(["B", "A", "C"], block_order(observed.project(blocks, snapshots, now_ms=NOW + 99 * MINUTE)))
        blocks["A"] = replace(blocks["A"], rows=blocks["A"].rows + (running(2, NOW + 2 * MINUTE),))
        self.assertEqual(["B", "C", "A"], block_order(observed.project(blocks, snapshots, now_ms=NOW + 3 * MINUTE)))

    def header_line(self, output, title):
        return next(line for line in output.splitlines() if title in line)


class WarningConsolidationTests(unittest.TestCase):
    def coordinator_projection(self, blocks, snapshots, now_ms):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        config, selection, service, _ = make_service(temp.name, MutableSource())
        watch = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: 0)
        self.addCleanup(watch.close)
        watch.blocks, watch.snapshots = blocks, snapshots
        return watch, watch._projection(now_ms=now_ms)

    def test_evicted_session_marker_leaves_the_group_and_last_group_disappears(self):
        blocks, snapshots = inputs(A=(finished_at(1, NOW),), B=(finished_at(1, NOW - 1),),
                                   C=(warned(1, NOW - 2 * MINUTE),), D=(warned(1, NOW - 3 * MINUTE),))
        watch, before = self.coordinator_projection(blocks, snapshots, NOW)
        self.assertIn("*1,2 Context:", rendered(before))
        watch.tracker.recent_ms = 0  # green first-observation markers no longer protect the rows
        watch.tracker.max_rows = 3
        after = watch._projection(now_ms=NOW)
        self.assertNotEqual(watch._transient_signature(before), watch._transient_signature(after),
                            "eviction repaints without a source change")
        self.assertIn("*1 Context: Price threshold", rendered(after))
        self.assertEqual(["A", "B", "C"], sessions(after.rows))
        watch.tracker.max_rows = 2
        gone = watch._projection(now_ms=NOW)
        self.assertNotIn("Context:", rendered(gone))
        self.assertEqual({}, dict(gone.session_warnings))


if __name__ == "__main__":
    unittest.main()
