"""One-shot session lifecycle and evidence-qualified provisional report metrics."""
from dataclasses import replace
from decimal import Decimal
import unittest

from development.tests.fixtures.compact_reports import rendered, report_service
from development.tests.fixtures.pricing_catalog import catalog
from development.tests.fixtures.report_runtime import FakeSource
from development.tests.fixtures.session_snapshots import make_snapshot, make_uncompacted_snapshot
from src.analysis import analyze_snapshot
from src.domain import ModelRef, TokenUsage
from src.reports import ReportKind, ReportRequest
from src.reports.prompt_rows import PromptRowProjector


class SessionSnapshotTests(unittest.TestCase):
    def detail(self, snapshot, now=4000):
        return report_service(self, FakeSource(snapshot), now_ms=now).build(
            ReportRequest(ReportKind.SESSION, session_id="root"))

    def with_usage(self, tokens, *, model=None):
        snapshot = make_uncompacted_snapshot(running=True)
        return replace(snapshot, invocations=tuple(
            replace(item, tokens=tokens, model=model or item.model) if item.invocation_id == "i_next" else item
            for item in snapshot.invocations))

    def test_running_observed_metrics_match_completed_definitions_and_totals(self):
        for generation in ("v1", "v2"):
            with self.subTest(generation=generation):
                running = self.detail(make_snapshot(generation=generation, running=True))
                completed = self.detail(make_snapshot(generation=generation))
                block = running.prompt_blocks[0]
                row = next(row for row in block.rows if row.event_id == "u_next")
                self.assertTrue(row.in_progress)
                self.assertIsNone(row.completed_at_ms)
                self.assertEqual((88, 0, 0, 12), row.token_mix_percent)
                self.assertEqual(Decimal("0.0030"), row.incoming_context_ccost)
                self.assertEqual(Decimal("0.0016"), row.extra_ccost)
                self.assertEqual(Decimal("0.0046"), row.ccost)
                self.assertEqual(1, row.calls)
                for name in ("total_ccost", "total_calls", "total_mix_text", "total_ictx_cost_text", "total_extra_cost_text"):
                    self.assertEqual(getattr(completed.prompt_blocks[0], name), getattr(block, name))
                text = rendered(running)
                self.assertIn("[RUNNING]", text)
                self.assertIn("88/0/0/12", text)
                self.assertIn("provisional observed usage", text)
                self.assertIn("no automatic refresh", text)

    def test_missing_telemetry_withholds_mix_and_extra_but_keeps_known_context(self):
        snapshot = self.with_usage(TokenUsage(input=30, output=4, known_fields=("input", "cache_read", "cache_write")))

        block = self.detail(snapshot).prompt_blocks[0]
        row = block.rows[-1]

        self.assertIsNone(row.token_mix_percent)
        self.assertEqual(Decimal("0.0030"), row.incoming_context_ccost)
        self.assertIsNone(row.extra_ccost)
        self.assertEqual("N/A", block.total_mix_text)
        self.assertEqual("N/A", block.total_extra_cost_text)

    def test_long_running_prompt_keeps_marker_visible_in_narrow_report(self):
        snapshot = make_uncompacted_snapshot(running=True)
        snapshot = replace(snapshot, events=tuple(replace(event, text="Long prompt " * 100)
                                                  if event.event_id == "u_next" else event for event in snapshot.events))

        text = rendered(self.detail(snapshot), width=100)

        self.assertTrue(any("[RUNNING]" in line for line in text.splitlines() if line.startswith("|")))

    def test_missing_input_or_price_never_fabricates_context_or_extra(self):
        cases = (
            self.with_usage(TokenUsage(output=4, known_fields=("output",))),
            self.with_usage(TokenUsage(input=30, output=4), model=ModelRef("provider", "unknown-model")),
        )
        for snapshot in cases:
            with self.subTest(usage=snapshot.invocations[-1].tokens):
                block = self.detail(snapshot).prompt_blocks[0]
                row = block.rows[-1]
                self.assertIsNone(row.incoming_context_ccost)
                self.assertIsNone(row.extra_ccost)
                self.assertEqual("N/A", block.total_ictx_cost_text)

    def test_running_before_first_call_has_unknown_metrics_and_frozen_duration(self):
        snapshot = make_uncompacted_snapshot(running=True)
        snapshot = replace(snapshot, invocations=tuple(i for i in snapshot.invocations if i.invocation_id != "i_next"))

        early = self.detail(snapshot)
        text = rendered(early)
        late = self.detail(snapshot, now=8000)

        row = early.prompt_blocks[0].rows[-1]
        self.assertTrue(row.in_progress)
        self.assertEqual(0, row.calls)
        self.assertIsNone(row.token_mix_percent)
        self.assertIsNone(row.incoming_context_ccost)
        self.assertIsNone(row.extra_ccost)
        self.assertEqual(2000, row.duration_ms)
        self.assertEqual(6000, late.prompt_blocks[0].rows[-1].duration_ms)
        self.assertEqual(text, rendered(early))

    def test_ambiguous_attribution_withholds_provisional_breakdown(self):
        snapshot = make_uncompacted_snapshot(running=True)
        bundle = analyze_snapshot(snapshot, now_ms=4000)
        record = replace(bundle.prompts[-1], breakdown_known=False)
        projector = PromptRowProjector(snapshot=snapshot, bundle=bundle, catalog=catalog(), config={},
                                       snapshot_running_metrics=True)

        row = projector.prompt(record)

        self.assertIsNone(row.token_mix_percent)
        self.assertIsNone(row.incoming_context_ccost)
        self.assertIsNone(row.extra_ccost)
        self.assertGreater(row.ccost, 0)

    def test_watch_and_date_keep_their_existing_running_projection(self):
        snapshot = make_uncompacted_snapshot(running=True)
        service = report_service(self, FakeSource(snapshot), now_ms=4000)

        watch, _, _ = service.build_watch_root(snapshot.root)
        date = service.build(ReportRequest(ReportKind.DATE, date_text="1970-01-01"))

        for block in (watch, date.prompt_blocks[0]):
            row = block.rows[-1]
            self.assertTrue(row.in_progress)
            self.assertIsNone(row.token_mix_percent)
            self.assertIsNone(row.incoming_context_ccost)
            self.assertIsNone(row.extra_ccost)
        self.assertNotIn("provisional observed usage", rendered(date))


if __name__ == "__main__":
    unittest.main()
