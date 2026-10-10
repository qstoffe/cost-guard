"""Next-Ictx warnings state the model table's Relative CCost increase across the threshold."""
from __future__ import annotations

import io
import tempfile
import unittest
from dataclasses import replace
from decimal import Decimal

from development.tests.test_session_move import completed_history
from development.fixtures.watch_runtime import MutableSource, make_service
from development.tests.test_v786_regressions import _running_without_future_compaction
from src.analysis.comparisons import threshold_cost_multiplier
from src.domain import ModelPricing, ModelRef, PricingTier, TokenUsage
from src.presentation import ReportRenderer, WatchRenderer
from src.presentation.context_warnings import threshold_multiplier_text
from src.pricing.catalog import PricingCatalog
from src.reports.models import ReportKind
from src.reports.service import ReportRequest
from src.watch import WatchCoordinator

MIX = (Decimal("0.05"), Decimal("0.9"), Decimal("0"), Decimal("0.05"), 3)


def tier(input_rate, cache, output, *, minimum=None, maximum=None):
    return PricingTier(min_input_tokens=minimum, max_input_tokens=maximum, per_million_input=Decimal(input_rate),
                       per_million_cache_read=Decimal(cache), per_million_output=Decimal(output))


def catalog() -> PricingCatalog:
    # Non-uniform long-context rates: the ratio depends on the shared mix.
    test = ModelPricing(ModelRef("github-copilot", "gpt-test", "GPT Test"), "USD", tiers=(
        tier("1", "0.1", "4", maximum=100_000), tier("2.5", "0.15", "6", minimum=100_001)), metadata={"publisher": "Test"})
    double = ModelPricing(ModelRef("github-copilot", "gpt-double", "GPT Double"), "USD", tiers=(
        tier("2", "0.2", "8", maximum=100_000), tier("4", "0.4", "16", minimum=100_001)), metadata={"publisher": "Test"})
    return PricingCatalog((test, double))


def threshold_snapshot(tokens: int):
    snapshot = _running_without_future_compaction()
    return replace(snapshot, invocations=tuple(
        replace(item, tokens=TokenUsage(input=tokens, output=5)) if item.invocation_id == "i_next" else item
        for item in snapshot.invocations))


class ThresholdMultiplierTests(unittest.TestCase):
    def test_multiplier_is_exact_ratio_of_relative_ccost_levels(self):
        from src.analysis.comparisons import model_comparison_rows

        class Record:
            input_tokens, cache_read_tokens, cache_write_tokens, output_tokens = 50, 900, 0, 50
        rows = {row.model_name: row for row in model_comparison_rows((Record(),), catalog())}
        for model_id, name in (("gpt-test", "GPT Test"), ("gpt-double", "GPT Double")):
            levels = rows[name].relative_levels
            mix = (Decimal("0.05"), Decimal("0.9"), Decimal("0"), Decimal("0.05"), 1)
            with self.subTest(model=model_id):
                self.assertEqual(levels[1].relative_cost / levels[0].relative_cost,
                                 threshold_cost_multiplier(catalog(), model_id, 100_000, mix))
        self.assertEqual(Decimal(2), threshold_cost_multiplier(catalog(), "gpt-double", 100_000, MIX), "2x -> 4x")
        self.assertIsNone(threshold_cost_multiplier(catalog(), "gpt-test", 99_999, MIX), "unknown boundary")
        self.assertIsNone(threshold_cost_multiplier(catalog(), "missing", 100_000, MIX))
        self.assertIsNotNone(threshold_cost_multiplier(catalog(), "gpt-test", 100_000, (0, 0, 0, 0, 0)),
                             "no sample uses the table's hidden sorting mix")

    def test_text_has_at_most_one_decimal(self):
        for value, expected in (("1.9", "(1.9x more expensive)"), ("2", "(2x more expensive)"),
                                ("2.24", "(2.2x more expensive)"), ("1.96", "(2x more expensive)"),
                                ("2.25", "(2.3x more expensive)")):
            with self.subTest(value=value):
                self.assertEqual(expected, threshold_multiplier_text(Decimal(value)))

    def test_watch_and_session_report_replace_ccost_range_with_report_ratio(self):
        source = MutableSource(threshold_snapshot(80_000))
        with tempfile.TemporaryDirectory() as td:
            config, selection, service, _db = make_service(td, source)
            service.pricing_provider.catalog = catalog()
            projection = WatchCoordinator(selection=selection, report_service=service, config=config,
                                          clock_ms=lambda: 2200).initialize().projection
            stream = io.StringIO()
            WatchRenderer({"timezone": "UTC", "colors": {}, "thresholds": {}}, stream=stream,
                          interactive=False).render(projection)
            watch_text = stream.getvalue()
            normal = service.build(ReportRequest(ReportKind.NORMAL))
            levels = next(row for row in normal.model_comparison if row.model == "GPT Test").relative_levels
            expected = threshold_multiplier_text(levels[1].relative_cost / levels[0].relative_cost)
            self.assertIn(f"*1 Context: Approaching price threshold >100.0K {expected}", watch_text)
            self.assertNotIn("Next Ictx CCost", watch_text)

            history = completed_history()
            source.snapshot = replace(history, source_revision="exceeded", invocations=tuple(
                replace(item, tokens=TokenUsage(input=120_000, output=5)) if item.invocation_id == "i_next" else item
                for item in history.invocations))
            service.invalidate_roots(("root",))
            session = service.build(ReportRequest(ReportKind.SESSION, session_id="root"))
            stream = io.StringIO()
            ReportRenderer(config, stream=stream, color_enabled=False, terminal_width=160).render(session)
            self.assertIn(f"Next Ictx: ~120k {expected}", stream.getvalue())

    def test_unpriced_threshold_keeps_ccost_range(self):
        source = MutableSource(threshold_snapshot(80_000))
        with tempfile.TemporaryDirectory() as td:
            config, selection, service, _db = make_service(td, source)
            service.pricing_provider.catalog = catalog()
            service._threshold_multiplier = lambda _model, _threshold: None
            projection = WatchCoordinator(selection=selection, report_service=service, config=config,
                                          clock_ms=lambda: 2200).initialize().projection
            stream = io.StringIO()
            WatchRenderer({"timezone": "UTC", "colors": {}, "thresholds": {}}, stream=stream,
                          interactive=False).render(projection)
            self.assertIn("(Next Ictx CCost", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
