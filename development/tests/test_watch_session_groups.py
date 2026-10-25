"""Lifecycle-aware global block ordering, truthful header times and divider geometry."""
from dataclasses import replace
from decimal import Decimal
import io
import tempfile
import unittest
from unittest.mock import Mock

from development.tests.fixtures.quota_rendering import quotas, rolling
from development.tests.fixtures.watch_rows import inputs, prompt, tracker
from development.tests.fixtures.watch_runtime import MutableSource, make_service
from src.analysis.context import PriceWarningSeverity
from src.presentation import WatchRenderer
from src.watch import WatchCoordinator
from src.watch.models import SkillObservation, ToolObservation, WatchProjection, WatchSessionSubtotal
from src.watch.redraw import needs_full_render, transient_signature, visible_signature
from src.watch.tracker import WatchRowTracker

MINUTE = 60_000


def order(rows):
    return list(dict.fromkeys(row.session_id for row in rows))


def rendered(rows, **changes):
    output = io.StringIO()
    WatchRenderer({"timezone": "UTC", "colors": {}}, stream=output,
                  interactive=False, terminal_width=200).render(WatchProjection("Watch", "V2", rows, **changes))
    return output.getvalue()


def rules(output):
    return [line for line in output.splitlines() if line.startswith("|-")]


class SessionGroupLifecycleTests(unittest.TestCase):
    def test_history_uses_latest_completion_including_long_older_prompts(self):
        blocks, snapshots = inputs(
            A=(prompt(1, 100, completed_at_ms=900), prompt(2, 400, completed_at_ms=500)),
            B=(prompt(1, 200, completed_at_ms=800),),
            C=(prompt(1, 50, in_progress=True),),
            D=(prompt(1, 40, in_progress=True),),
        )

        rows = tracker().project(blocks, snapshots, now_ms=1000)

        self.assertEqual(["B", "A", "D", "C"], order(rows))
        self.assertEqual([800, 900, 900, 40, 50], [row.session_latest_ms for row in rows])
        self.assertEqual([False, False, False, True, True], [row.session_active for row in rows])
        self.assertEqual([1, 2], [row.prompt.prompt_number for row in rows if row.session_id == "A"])
        output = rendered(rows)
        self.assertEqual(4, len(rules(output)))
        self.assertEqual(1, len(set(rules(output))))
        self.assertEqual(1, output.count("Session A"))
        self.assertLess(output.index("Session A"), output.index("Session D"))
        self.assertTrue(output.split("Session D")[0].splitlines()[-1].startswith("| ▶"))

    def test_success_and_abort_keep_start_until_exact_existing_highlight_expiry(self):
        start = (18 * 60 + 10) * MINUTE
        end = (18 * 60 + 20) * MINUTE
        for aborted in (False, True):
            with self.subTest(aborted=aborted):
                observed = tracker(recent_seconds=60)
                blocks, snapshots = inputs(A=(prompt(1, start, in_progress=True),))
                observed.project(blocks, snapshots, now_ms=start + MINUTE)
                blocks["A"] = replace(blocks["A"], rows=(prompt(
                    1, start, completed_at_ms=end, duration_ms=end - start,
                    aborted=aborted, completed_successfully=not aborted),))

                recent = observed.project(blocks, snapshots, now_ms=end + 2000)
                before = observed.project(blocks, snapshots, now_ms=end + 61_999)
                history = observed.project(blocks, snapshots, now_ms=end + 62_000)

                self.assertEqual(recent, before)
                self.assertTrue(recent[0].session_active)
                self.assertEqual("!" if aborted else "✓", recent[0].marker)
                self.assertEqual(start, recent[0].session_latest_ms)
                self.assertIn("18:10 Session A", rendered(recent))
                self.assertFalse(history[0].session_active)
                self.assertEqual(end, history[0].session_latest_ms)
                self.assertIn("18:20 Session A", rendered(history))
                self.assertEqual("", history[0].marker)
                self.assertEqual(history, observed.project(blocks, snapshots, now_ms=end + 1_000_000))

    def test_final_highlight_of_any_prompt_controls_indivisible_block(self):
        observed = tracker(recent_seconds=1)
        blocks, snapshots = inputs(A=(prompt(1, 100, in_progress=True), prompt(2, 200, in_progress=True)))
        observed.project(blocks, snapshots, now_ms=300)
        blocks["A"] = replace(blocks["A"], rows=(prompt(1, 100, completed_at_ms=400), blocks["A"].rows[1]))
        observed.project(blocks, snapshots, now_ms=500)
        blocks["A"] = replace(blocks["A"], rows=(blocks["A"].rows[0], prompt(2, 200, completed_at_ms=600)))
        observed.project(blocks, snapshots, now_ms=700)

        recent = observed.project(blocks, snapshots, now_ms=1500)
        history = observed.project(blocks, snapshots, now_ms=1700)

        self.assertEqual(["", "✓"], [row.marker for row in recent])
        self.assertTrue(all(row.session_active and row.session_latest_ms == 200 for row in recent))
        self.assertTrue(all(not row.session_active and row.session_latest_ms == 600 for row in history))

    def test_reactivation_by_prompt_or_compaction_moves_once_and_preserves_row_order(self):
        for compact in (False, True):
            with self.subTest(compact=compact):
                blocks, snapshots = inputs(A=(prompt(1, 100, completed_at_ms=900),),
                                           B=(prompt(1, 500, in_progress=True),))
                observed = tracker()
                self.assertEqual(["A", "B"], order(observed.project(blocks, snapshots, now_ms=1000)))
                new_rows = blocks["A"].rows + (prompt(2, 1100, is_compaction=compact, in_progress=True),)
                blocks, snapshots = inputs(A=new_rows, B=blocks["B"].rows)

                rows = observed.project(blocks, snapshots, now_ms=1200)

                self.assertEqual(["B", "A"], order(rows))
                self.assertEqual([1, 2], [row.prompt.prompt_number for row in rows if row.session_id == "A"])
                self.assertTrue(all(row.session_active for row in rows))
                self.assertEqual([500, 1100, 1100], [row.session_latest_ms for row in rows])
                self.assertEqual(3, len(rules(rendered(rows))))

    def test_running_order_ignores_completion_updates_tools_and_poll_time(self):
        blocks, snapshots = inputs(A=(prompt(1, 100, in_progress=True), prompt(2, 500, completed_at_ms=600)),
                                   B=(prompt(1, 200, in_progress=True), prompt(2, 400, completed_at_ms=900)))
        observed = tracker(max_rows=2)
        before = observed.project(blocks, snapshots, now_ms=1000)
        blocks["A"] = replace(blocks["A"], rows=(blocks["A"].rows[0], replace(blocks["A"].rows[1], completed_at_ms=1200)))

        after = observed.project(blocks, snapshots, now_ms=9000)

        self.assertEqual(["B", "A"], order(after))
        self.assertEqual([400, 500], [row.session_latest_ms for row in after])
        self.assertEqual(before, after, "capped-out rows still establish latest start; polls/tools do not reorder")

    def test_history_timestamp_uses_uncapped_event_not_duration_or_observation(self):
        blocks, snapshots = inputs(A=(prompt(1, 100, completed_at_ms=900), prompt(2, 500, duration_ms=999_999)),
                                   B=(prompt(1, 600, completed_at_ms=800),))
        observed = tracker(max_rows=2)

        rows = observed.project(blocks, snapshots, now_ms=5000)

        self.assertEqual(["B", "A"], order(rows))
        self.assertEqual([800, 900], [row.session_latest_ms for row in rows])
        self.assertEqual([1, 1], [row.prompt.prompt_number for row in rows],
                         "supported ends win history membership; duration cannot rank A's unknown-end #2")

    def test_error_joins_recent_group_until_finite_highlight_expires(self):
        observed = tracker(recent_seconds=1)
        blocks, snapshots = inputs(E=(prompt(1, 100, watch_error=True, completed_at_ms=200),),
                                   R=(prompt(1, 50, in_progress=True),))
        initial = observed.project(blocks, snapshots, now_ms=300)
        protected = tracker(max_rows=1, recent_seconds=1).project(blocks, snapshots, now_ms=300)

        rows = observed.project(blocks, snapshots, now_ms=1300)

        self.assertEqual(["E", "R"], order(rows))
        self.assertTrue(initial[-1].session_active)
        self.assertEqual("E", initial[-1].session_id)
        self.assertEqual("!", initial[-1].marker)
        self.assertEqual(2, len(protected), "existing soft-cap protection is independent of grouping")
        self.assertFalse(rows[0].session_active)
        self.assertEqual("", rows[0].marker)
        renderer = WatchRenderer({"colors": {}}, stream=io.StringIO(), interactive=True)
        self.assertIsNone(renderer._row_style(rows[0]))
        self.assertIn("[ERROR]", renderer._row_label(rows[0]))
        capped = tracker(max_rows=1, recent_seconds=0).project(blocks, snapshots, now_ms=1300)
        self.assertEqual(["R"], order(capped))
        self.assertEqual(4, len(rules(rendered(rows))))

    def test_retained_post_compaction_prompt_never_uses_observation_derived_duration_as_end(self):
        compact = prompt(2, 500, is_compaction=True, completed_at_ms=700)
        blocks, snapshots = inputs(A=(prompt(1, 100, in_progress=True), compact))
        observed = tracker(recent_seconds=1)
        observed.project(blocks, snapshots, now_ms=1000)
        blocks["A"] = replace(blocks["A"], rows=(compact,))
        observed.project(blocks, snapshots, now_ms=1100)

        rows = observed.project(blocks, snapshots, now_ms=2200)

        self.assertEqual([2, 1], [row.prompt.prompt_number for row in rows])
        self.assertEqual(1000, rows[-1].prompt.duration_ms, "existing retained duration is observation-based")
        self.assertEqual([700, 700], [row.session_latest_ms for row in rows])
        self.assertTrue(all(not row.session_active for row in rows))

    def test_rejected_success_to_abort_downgrade_cannot_change_historical_header_time(self):
        blocks, snapshots = inputs(A=(prompt(1, 100, completed_successfully=True, completed_at_ms=500),))
        observed = tracker()
        before = observed.project(blocks, snapshots, now_ms=1000)
        blocks["A"] = replace(blocks["A"], rows=(prompt(1, 100, aborted=True, completed_at_ms=900),))

        after = observed.project(blocks, snapshots, now_ms=2000)

        self.assertEqual(before, after)
        self.assertEqual(500, after[0].session_latest_ms)

    def test_earlier_unknown_end_falls_back_to_start_without_poll_drift(self):
        blocks, snapshots = inputs(A=(prompt(1, 100), prompt(2, 300, watch_error=True)),
                                   B=(prompt(1, 200, completed_at_ms=500),))
        observed = WatchRowTracker(started_at_ms=1000, recent_seconds=30, max_rows=12)
        observed.set_earlier_sessions(("B", "A"))

        rows = observed.project(blocks, snapshots, now_ms=1000)

        self.assertEqual(["A", "B"], order(rows))
        self.assertEqual([300, 500], [row.session_latest_ms for row in rows])
        self.assertTrue(all(row.earlier and not row.session_active and not row.marker for row in rows))
        self.assertEqual(rows, observed.project(blocks, snapshots, now_ms=1_000_000))
        renderer = WatchRenderer({}, stream=io.StringIO(), interactive=True)
        self.assertIn('[ERROR]', renderer._row_label(rows[0]))
        self.assertIsNone(renderer._row_style(rows[0]))
        self.assertIsNone(rows[0].tool)
        self.assertIn("excluded from Token Mix and Watch total CCost", rendered(rows))

    def test_ties_and_unchanged_history_are_deterministic_in_both_groups(self):
        blocks, snapshots = inputs(D=(prompt(1, 100, in_progress=True),),
                                   C=(prompt(1, 100, in_progress=True),),
                                   B=(prompt(1, 200, completed_at_ms=500),),
                                   A=(prompt(1, 300, completed_at_ms=500),))
        observed = tracker()

        before = observed.project(blocks, snapshots, now_ms=1000)
        after = observed.project(dict(reversed(list(blocks.items()))), snapshots, now_ms=100_000)

        self.assertEqual(["A", "B", "C", "D"], order(before))
        self.assertEqual(before, after)
        blocks["B"] = replace(blocks["B"], rows=(replace(blocks["B"].rows[0], completed_at_ms=400),))
        self.assertEqual(["B", "A", "C", "D"], order(observed.project(blocks, snapshots, now_ms=100_001)))

    def test_scoped_watch_keeps_start_header_no_grouping_and_same_selection(self):
        blocks, snapshots = inputs(A=(prompt(1, 100, completed_at_ms=900), prompt(2, 200, completed_at_ms=700)))

        global_rows = tracker().project(blocks, snapshots, now_ms=1000)
        scoped_rows = tracker(session_scope=True).project(blocks, snapshots, now_ms=1000)

        self.assertEqual([row.prompt for row in global_rows], [row.prompt for row in scoped_rows])
        self.assertEqual([900, 900], [row.session_latest_ms for row in global_rows])
        self.assertEqual([200, 200], [row.session_latest_ms for row in scoped_rows])
        self.assertTrue(all(not row.session_active for row in scoped_rows))
        self.assertEqual(3, len(rules(rendered(scoped_rows))))


class SessionGroupRenderingTests(unittest.TestCase):
    def test_single_group_and_empty_have_no_additional_rule(self):
        for active in (False, True):
            blocks, snapshots = inputs(A=(prompt(1, 100, in_progress=active),), B=(prompt(1, 200, in_progress=active),))
            rows = tracker().project(blocks, snapshots, now_ms=1000)
            self.assertEqual(3, len(rules(rendered(rows))))
        empty = rendered(())
        self.assertEqual(3, len(rules(empty)))
        self.assertIn("No prompts since Watch started", empty)

    def test_separator_preserves_activity_skills_status_warnings_subtotals_and_quota(self):
        warning = "[Price threshold >200.0K exceeded]"
        blocks, snapshots = inputs(H=(prompt(1, 100, watch_error=True),),
                                   R=(prompt(1, 200, in_progress=True, watch_next_context_warning=warning,
                                             watch_next_context_warning_severity=PriceWarningSeverity.EXCEEDED),))
        rows = tracker().project(blocks, snapshots, now_ms=1000)
        tool = ToolObservation(tool_count=2, tool_counts=(("read", 2),), running_tool="read", running_ms=1000,
                               skills=(SkillObservation("test-skill"),))
        rows = tuple(replace(row, tool=tool) for row in rows)
        quota = quotas(rolling())
        subtotals = {"H": WatchSessionSubtotal(Decimal(3)), "R": WatchSessionSubtotal(Decimal(7))}

        output = rendered(rows, now_ms=1000, quota=quota, session_subtotals=subtotals)

        self.assertEqual(4, len(rules(output)))
        lines = output.splitlines()
        self.assertEqual(2, sum("2 tool calls" in line for line in lines))
        self.assertEqual(2, sum("Skills (1):" in line for line in lines))
        self.assertEqual(1, sum("running: read" in line for line in lines))
        self.assertEqual(2, output.count("test-skill"))
        self.assertIn("Σ 3", next(line for line in lines if "Session H" in line))
        self.assertIn("Σ 7", next(line for line in lines if "Session R" in line))
        self.assertIn("*1 Context:", output)
        self.assertIn("*1", next(line for line in lines if "▶ #1" in line))
        self.assertIn("#1 [ERROR]", output)
        self.assertNotIn("! #1", output)
        self.assertIn("OpenAI Plus", output)
        table_end = max(index for index, line in enumerate(lines) if line.startswith("|-"))
        self.assertTrue(all(len(line) == len(rules(output)[0]) for line in lines[1:table_end + 1] if line.startswith("|")))
        self.assertEqual(7, next(line for line in lines if "▶ #1" in line).count("|"))
        after_table = output.split(rules(output)[0])[-1]
        without_groups = rendered(tuple(replace(row, session_active=False) for row in rows), now_ms=1000,
                                  quota=quota, session_subtotals=subtotals).split(rules(output)[0])[-1]
        self.assertEqual(without_groups, after_table)

    def test_idle_wake_redraws_group_and_time_and_then_repaints_status_only(self):
        with tempfile.TemporaryDirectory() as td:
            config, selection, service, _ = make_service(td, MutableSource())
            now = [1000]
            watch = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: now[0])
            self.addCleanup(watch.close)
            watch.tracker = tracker(recent_seconds=1)
            watch.blocks, watch.snapshots = inputs(E=(prompt(1, 100, watch_error=True, completed_at_ms=500),))
            before = watch._projection(now_ms=1000)
            renderer = Mock()
            watch._render(renderer, before)
            now[0] = 2000

            after = watch.status_projection()
            watch._render_wake(renderer, after, before)

            self.assertEqual("!", before.rows[0].marker)
            self.assertEqual("", after.rows[0].marker)
            self.assertNotEqual(transient_signature(before), transient_signature(after))
            self.assertNotEqual(visible_signature(before), visible_signature(after))
            self.assertTrue(needs_full_render(before, after, source_changed=False))
            self.assertEqual(2, renderer.render.call_count)
            now[0] = 3000
            same = watch.status_projection()
            watch._render_wake(renderer, same, before)
            self.assertFalse(needs_full_render(after, same, source_changed=False))
            self.assertEqual(2, renderer.render.call_count)
            renderer.render_status.assert_called_once_with(same)

    def test_timestamp_only_change_invalidates_both_signatures(self):
        blocks, snapshots = inputs(A=(prompt(1, 100, completed_at_ms=500),))
        rows = tracker().project(blocks, snapshots, now_ms=1000)
        before = WatchProjection("Watch", "V1", rows)
        after = replace(before, rows=(replace(rows[0], session_latest_ms=600),))

        self.assertNotEqual(transient_signature(before), transient_signature(after))
        self.assertTrue(needs_full_render(before, after, source_changed=False))
        self.assertFalse(needs_full_render(before, replace(before, now_ms=100_000), source_changed=False))
