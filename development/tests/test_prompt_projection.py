"""Prompt row vs block ownership, lazy warnings and retained aggregation rules."""
from dataclasses import replace
from decimal import Decimal
import unittest
from unittest import mock

from development.fixtures.pricing_catalog import catalog
from development.fixtures.session_snapshots import make_snapshot, make_native_v2_compaction_snapshot
from src.analysis import analyze_snapshot
from src.analysis.context import ContextEpochs, build_context_timeline
from src.domain import ModelRef
from src.reports.prompt_rows import PromptRowProjector
from src.reports.prompts import build_prompt_block


class PromptProjectionTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = make_snapshot()
        self.bundle = analyze_snapshot(self.snapshot, now_ms=4000)
        self.prices = catalog()
        self.record = next(item for item in self.bundle.prompts if item.prompt_id == "u_next")

    def projector(self, bundle=None, multiplier=None):
        return PromptRowProjector(snapshot=self.snapshot, bundle=bundle or self.bundle, catalog=self.prices,
                                  config={}, threshold_multiplier=multiplier)

    def block(self, bundle=None, **kwargs):
        return build_prompt_block(session_id="root", title="Synthetic", bundle=bundle or self.bundle,
                                  snapshot=self.snapshot, catalog=self.prices, config={}, **kwargs)

    def test_single_row_projection_is_identical_to_block_row(self):
        bundle = replace(self.bundle, prompts=(self.record,), compactions=())

        row = self.projector(bundle).prompt(self.record)
        block = self.block(bundle)

        self.assertEqual((row,), block.rows)
        self.assertEqual(row.ccost, block.total_ccost)
        self.assertEqual(row.billed_cost, block.billed_cost)

    def test_block_builds_one_shared_context_index_with_unchanged_timeline(self):
        snapshot = make_native_v2_compaction_snapshot()
        bundle = analyze_snapshot(snapshot, now_ms=10_000)
        original = ContextEpochs.__init__
        built = []

        def counting(epochs, *args):
            built.append(epochs)
            original(epochs, *args)

        with mock.patch.object(ContextEpochs, "__init__", counting):
            projector = PromptRowProjector(snapshot=snapshot, bundle=bundle, catalog=self.prices, config={})

        self.assertEqual([projector.epochs], built)
        self.assertEqual(build_context_timeline(snapshot, bundle, self.prices),
                         tuple(projector.timeline.values()))

    def test_unwarned_projection_does_not_acquire_comparison_sample(self):
        def forbidden(_model, _threshold):
            raise AssertionError("No comparison lookup without an actual threshold warning")

        row = self.projector(multiplier=forbidden).prompt(self.record)
        block = self.block(threshold_multiplier=forbidden)

        self.assertIsNone(row.next_context_cost_multiplier)
        self.assertIsNone(block.next_context_cost_multiplier)

    def test_running_usage_counts_in_ccost_but_not_completed_mix_diagnostics(self):
        running = replace(self.record, in_progress=True)
        bundle = replace(self.bundle, prompts=(running,), compactions=())

        block = self.block(bundle)

        self.assertGreater(block.total_ccost, 0)
        self.assertEqual("", block.total_mix_text)
        self.assertEqual("", block.total_ictx_cost_text)
        self.assertIsNone(block.rows[0].incoming_context_ccost)
        self.assertIsNone(block.rows[0].completed_at_ms)

    def test_terminal_timestamp_projects_existing_analysis_evidence_not_duration(self):
        for generation in ("v1", "v2"):
            snapshot = make_snapshot(generation=generation)
            bundle = analyze_snapshot(snapshot, now_ms=10_000)
            projector = PromptRowProjector(snapshot=snapshot, bundle=bundle, catalog=self.prices, config={})

            for record in bundle.prompts:
                row = projector.prompt(replace(record, duration_ms=999_999))
                self.assertEqual(None if record.in_progress else record.terminal_time_ms or None, row.completed_at_ms)
            for record in bundle.compactions:
                row = projector.compaction(record, 1)
                self.assertEqual(None if record.in_progress else record.completed_at_ms or None, row.completed_at_ms)

    def test_missing_terminal_time_stays_unknown(self):
        record = replace(self.record, in_progress=False, terminal_time_ms=0, duration_ms=999_999)

        row = self.projector().prompt(record)

        self.assertIsNone(row.completed_at_ms)

    def test_range_filter_does_not_erase_the_unfiltered_latest_context_anchor(self):
        complete = self.block()

        empty = self.block(start_ms=4500, end_ms=8000)

        self.assertEqual((), empty.rows)
        self.assertEqual(Decimal(0), empty.total_ccost)
        self.assertEqual(Decimal(0), empty.billed_cost)
        self.assertEqual(complete.current_context_tokens, empty.current_context_tokens)
        self.assertEqual(complete.next_context_tokens, empty.next_context_tokens)

    def test_unknown_reference_price_propagates_incomplete_totals_not_billing_fallback(self):
        unknown = replace(self.record, entries=tuple(replace(item, model=ModelRef("provider", "unknown-model"))
                                                    for item in self.record.entries))
        bundle = replace(self.bundle, prompts=(unknown,), compactions=())

        block = self.block(bundle)

        self.assertFalse(block.comparison_cost_complete)
        self.assertEqual("N/A", block.total_ictx_cost_text)
        self.assertEqual("N/A", block.total_extra_cost_text)
        self.assertGreater(block.billed_cost, 0)

    def test_native_compaction_retains_zero_billable_usage_and_event_number(self):
        snapshot = make_native_v2_compaction_snapshot()
        bundle = analyze_snapshot(snapshot, now_ms=4000)

        block = build_prompt_block(session_id="root", title="Synthetic", bundle=bundle,
                                   snapshot=snapshot, catalog=self.prices, config={})

        compact = next(row for row in block.rows if row.is_compaction)
        self.assertEqual("/compact (auto)", compact.label)
        self.assertEqual(Decimal(0), compact.ccost)
        self.assertEqual(2, compact.prompt_number)
        record = next(item for item in bundle.compactions if item.user_message_id == compact.event_id)
        self.assertEqual(record.completed_at_ms, compact.completed_at_ms)
