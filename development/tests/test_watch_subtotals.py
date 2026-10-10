"""Displayed Watch-row CCost subtotals are independent of request-run accounting."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from decimal import Decimal
import io
import tempfile
import unittest

from development.fixtures.session_snapshots import MODEL, make_snapshot, message, prov
from development.tests.test_session_move import moved
from development.fixtures.watch_runtime import MutableSource, make_service
from development.tests.test_token_mix import one_request
from development.tests.test_watch_grouping import inputs, prompt
from src.domain import MessageRole, ModelPricing, ModelRef, TokenUsage
from src.presentation import WatchRenderer
from src.pricing.catalog import PricingCatalog
from src.watch import WatchCoordinator
from src.watch.coordinator import WatchCycle


def startup_prompt(*, unknown_history=False):
    snapshot = one_request(usage=TokenUsage(input=59))
    old = message("a_old", "root", MessageRole.ASSISTANT, 2050, parent="u_next",
                  completed=2090, model=MODEL, finish="tool-calls")
    old = replace(old, tokens=TokenUsage(input=19))
    invocation = replace(snapshot.invocations[0], invocation_id="i_old", message_id=old.message_id,
                         created_at_ms=2050, completed_at_ms=2090, tokens=old.tokens,
                         provenance=prov("root", "i_old"),
                         model=ModelRef("github-copilot", "unknown") if unknown_history else MODEL)
    return replace(snapshot, messages=(snapshot.messages[0], old, snapshot.messages[1]),
                   invocations=(invocation, *snapshot.invocations))


@contextmanager
def watch_for(snapshot=None, *, start=2200, max_rows=14, session_id=None):
    with tempfile.TemporaryDirectory() as td:
        source = MutableSource(snapshot)
        config, selection, service, _ = make_service(td, source)
        config.update(watchRecentEventSeconds=0, watchDashboardMaxRows=max_rows)
        # Exactly one CCost per input/output token, independent of billed money.
        service.comparison_pricing_catalog = PricingCatalog((ModelPricing(
            MODEL, "USD", Decimal(10000), Decimal(10000), Decimal(10000), Decimal(10000),
        ),))
        clock = [start]
        watch = WatchCoordinator(selection=selection, report_service=service, config=config,
                                 session_id=session_id, clock_ms=lambda: clock[0])
        yield watch, source, clock


def table_for(projection):
    renderer = WatchRenderer({}, stream=io.StringIO(), interactive=False)
    table, styles, _ = renderer._table_rows(projection)
    headers = {row[0]: row[2] for row, style in zip(table, styles) if style[0] == "watchSessionHeader"}
    return table, headers


class WatchSessionSubtotalTests(unittest.TestCase):
    def assert_row_scope(self, projection):
        sessions = {row.session_id for row in projection.rows}
        self.assertEqual(sessions, set(projection.session_subtotals))
        for session in sessions:
            rows = [row.prompt for row in projection.rows if row.session_id == session]
            subtotal = projection.session_subtotals[session]
            self.assertEqual(sum((row.ccost for row in rows), Decimal(0)), subtotal.ccost)
            self.assertEqual(any(row.unresolved_cost for row in rows), subtotal.unresolved_cost)

    def test_mid_prompt_start_header_includes_history_but_run_total_does_not(self):
        with watch_for(startup_prompt()) as (watch, source, clock):
            first = watch.initialize().projection
            self.assertEqual(1, len(first.rows))
            self.assertEqual(Decimal(78), first.rows[0].prompt.ccost)
            table, headers = table_for(first)
            self.assertEqual("78", table[1][2])
            self.assertEqual("Σ 78", headers["Root"])
            self.assert_row_scope(first)
            self.assertEqual(Decimal(59), sum(first.token_mix.costs))
            self.assertEqual(1, first.token_mix.request_count)
            self.assertEqual((59, 0, 0, 0), first.token_mix.totals)
            stream = io.StringIO()
            WatchRenderer({}, stream=stream, interactive=False).render(first)
            self.assertIn("Watch total CCost: 59", stream.getvalue())
            source.snapshot = moved(source.snapshot, 2250)
            clock[0] = 2400
            for cycle in (watch.poll_once(), watch.poll_once(force_resync=True), watch.poll_once()):
                self.assert_row_scope(cycle.projection)
                self.assertEqual(first.session_subtotals, cycle.projection.session_subtotals)
                self.assertEqual(first.token_mix, cycle.projection.token_mix)
                self.assertEqual(1, len(cycle.projection.rows))

    def test_start_before_prompt_and_completion_keep_ordinary_reconciliation(self):
        snapshot = one_request(usage=TokenUsage(input=59))
        with watch_for(snapshot, start=1900) as (watch, source, clock):
            first = watch.initialize().projection
            self.assert_row_scope(first)
            self.assertEqual(Decimal(59), first.session_subtotals["root"].ccost)
            self.assertEqual(Decimal(59), sum(first.token_mix.costs))
            source.snapshot = replace(one_request(running=False, usage=TokenUsage(input=59)), source_revision="done")
            clock[0] = 2400
            completed = watch.poll_once(force_resync=True).projection
            self.assert_row_scope(completed)
            self.assertFalse(completed.rows[0].prompt.in_progress)
            self.assertEqual(first.session_subtotals, completed.session_subtotals)
            self.assertEqual(first.token_mix, completed.token_mix)

    def test_multiple_sessions_sum_decimal_rows_once_before_rounding(self):
        blocks, snapshots = inputs(
            A=(replace(prompt(1, 100), ccost=Decimal("1.01")),
               replace(prompt(2, 300), ccost=Decimal("1.01"))),
            B=(replace(prompt(1, 200), ccost=Decimal("0.04")),
               replace(prompt(2, 400), ccost=Decimal("0.04"), is_compaction=True, calls=1)),
        )
        with watch_for(start=0) as (watch, _, _):
            watch.blocks, watch.snapshots = blocks, snapshots
            for _ in range(3):
                projection = watch._projection(now_ms=500)
                self.assert_row_scope(projection)
                self.assertEqual(Decimal("2.02"), projection.session_subtotals["A"].ccost)
                self.assertEqual(Decimal("0.08"), projection.session_subtotals["B"].ccost)
                table, headers = table_for(projection)
                self.assertEqual({"Session A": "Σ 3", "Session B": "Σ <0.1"}, headers)
                self.assertEqual("2", table[1][2])
                self.assertEqual("2", table[2][2])
                self.assertEqual(0, projection.token_mix.request_count, "row projection never feeds run usage")

    def test_cap_and_protected_rows_exclude_evicted_costs(self):
        blocks, snapshots = inputs(
            A=(replace(prompt(1, 100, in_progress=True), ccost=Decimal(5)),
               replace(prompt(2, 200), ccost=Decimal(1000))),
            B=(replace(prompt(1, 300), ccost=Decimal(2000)),
               replace(prompt(2, 400), ccost=Decimal(7))),
        )
        for cap, expected in ((1, {"A": Decimal(5)}), (2, {"A": Decimal(5), "B": Decimal(7)})):
            with self.subTest(cap=cap), watch_for(start=0, max_rows=cap) as (watch, _, _):
                watch.blocks, watch.snapshots = blocks, snapshots
                projection = watch._projection(now_ms=500)
                self.assert_row_scope(projection)
                self.assertEqual(expected, {key: value.ccost for key, value in projection.session_subtotals.items()})

    def test_session_scope_can_include_history_without_adding_run_usage(self):
        with watch_for(one_request(running=False, usage=TokenUsage(input=59)), start=4000,
                       session_id="root") as (watch, _, _):
            projection = watch.initialize().projection
            self.assert_row_scope(projection)
            self.assertEqual(Decimal(59), projection.session_subtotals["root"].ccost)
            self.assertEqual("Σ 59", table_for(projection)[1]["Root"])
            self.assertEqual(0, projection.token_mix.request_count)

    def test_row_cap_changes_subtotals_without_changing_run_accounting(self):
        projections = []
        for cap in (1, 14):
            with watch_for(make_snapshot(), start=1000, max_rows=cap) as (watch, _, _):
                projection = watch.initialize().projection
                self.assert_row_scope(projection)
                projections.append(projection)
                self.assertEqual(min(cap, 3), len(projection.rows))
        capped, full = projections
        self.assertEqual(full.token_mix, capped.token_mix, "all qualifying requests survive row eviction")
        self.assertLess(capped.session_subtotals["root"].ccost, full.session_subtotals["root"].ccost)
        self.assertEqual(sum(full.token_mix.costs), full.session_subtotals["root"].ccost)

    def test_retained_missing_prompt_contributes_only_while_selected(self):
        running = replace(prompt(1, 100, in_progress=True), ccost=Decimal(9))
        compact = prompt(2, 300, is_compaction=True)
        blocks, snapshots = inputs(A=(running, compact))
        with watch_for(start=0, max_rows=2) as (watch, _, _):
            watch.blocks, watch.snapshots = blocks, snapshots
            first = watch._projection(now_ms=500)
            watch.blocks["A"] = replace(blocks["A"], rows=(compact,))
            retained = watch._projection(now_ms=600)
            self.assert_row_scope(retained)
            self.assertEqual(first.session_subtotals, retained.session_subtotals)
            self.assertFalse(retained.rows[-1].prompt.in_progress)
            newer = replace(prompt(3, 700), ccost=Decimal(2))
            newest = replace(prompt(4, 800), ccost=Decimal(3))
            watch.blocks, watch.snapshots = inputs(A=(compact, newer, newest))
            evicted = watch._projection(now_ms=900)
            self.assert_row_scope(evicted)
            self.assertEqual([3, 4], [row.prompt.prompt_number for row in evicted.rows])
            self.assertEqual(Decimal(5), evicted.session_subtotals["A"].ccost)

    def test_unpriceable_pre_watch_history_marks_header_not_run_total(self):
        with watch_for(startup_prompt(unknown_history=True)) as (watch, _, _):
            projection = watch.initialize().projection
            self.assert_row_scope(projection)
            self.assertTrue(projection.rows[0].prompt.unresolved_cost)
            table, headers = table_for(projection)
            self.assertEqual("?59", table[1][2])
            self.assertEqual("Σ ?59", headers["Root"])
            self.assertTrue(projection.token_mix.cost_complete)
            self.assertEqual(Decimal(59), sum(projection.token_mix.costs))

    def test_zero_partial_and_native_compaction_keep_truthful_presentation(self):
        for costs, unresolved, expected in (((0,), False, "Σ 0"), ((0,), True, "Σ N/A"),
                                             ((0, 7), True, "Σ ?7")):
            with self.subTest(costs=costs, unresolved=unresolved), watch_for(start=0) as (watch, _, _):
                rows = tuple(replace(prompt(i + 1, 100 + i), ccost=Decimal(cost),
                                     unresolved_cost=unresolved and i == 0) for i, cost in enumerate(costs))
                watch.blocks, watch.snapshots = inputs(A=rows)
                projection = watch._projection(now_ms=500)
                self.assert_row_scope(projection)
                self.assertEqual(expected, table_for(projection)[1]["Session A"])
        with watch_for(start=0) as (watch, _, _):
            watch.blocks, watch.snapshots = inputs(A=(prompt(1, 100, is_compaction=True),))
            projection = watch._projection(now_ms=500)
            self.assert_row_scope(projection)
            table, headers = table_for(projection)
            self.assertEqual("Σ 0", headers["Session A"])
            self.assertEqual("", table[1][2])
            self.assertEqual("Σ N/A", table_for(replace(projection, session_subtotals={}))[1]["Session A"],
                             "missing projected cost must not invent a known zero")

    def test_subtotal_amount_and_unresolved_state_affect_visible_signature(self):
        with watch_for(start=0) as (watch, _, _):
            watch.blocks, watch.snapshots = inputs(A=(replace(prompt(1, 100), ccost=Decimal(1)),))
            first = watch._projection(now_ms=500)
            subtotal = first.session_subtotals["A"]
            for changed in (replace(subtotal, ccost=Decimal(2)), replace(subtotal, unresolved_cost=True)):
                projection = replace(first, session_subtotals={"A": changed})
                self.assertNotEqual(watch._visible_signature(first), watch._visible_signature(projection))
                self.assertTrue(watch._needs_full_render(first, projection, WatchCycle(projection, (), ())))


if __name__ == "__main__":
    unittest.main()
