"""Priced-only Token Mix %/Relative CCost samples versus complete-scope CCost totals."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
import io
import unittest

from development.tests.fixtures.compact_reports import Availability, rendered, report_service
from development.tests.fixtures.pricing_catalog import catalog
from development.tests.fixtures.session_snapshots import make_snapshot
from development.tests.fixtures.watch_runtime import MutableSource
from src.analysis import analyze_snapshot
from src.analysis.comparisons import model_comparison_rows
from src.analysis.models import TraceEntry
from src.analysis.token_mix import priceable_request, priced_sample_mix, priced_token_mix, priced_usage
from src.analysis.valuation import comparison_cost
from src.domain import ModelPricing, ModelRef, PricingTier, TokenUsage
from src.presentation import WatchRenderer
from src.presentation.token_mix import token_mix_lines
from src.pricing.catalog import PricingCatalog
from src.reports import ReportKind, ReportRequest
from src.watch.models import WatchProjection
from src.watch.token_mix import WatchTokenMix

PRICED = ModelRef("github-copilot", "gpt-test")
UNPRICED = ModelRef("github-copilot", "unknown-model")
TIERED = ModelPricing(ModelRef("github-copilot", "tiered", "Tiered"), "USD", tiers=(
    PricingTier(max_input_tokens=1000, per_million_input=Decimal("1"), per_million_cache_read=Decimal("0.1"),
                per_million_output=Decimal("4")),
    PricingTier(min_input_tokens=1001, per_million_input=Decimal("2"), per_million_cache_read=Decimal("0.2")),
))
FREE = ModelPricing(ModelRef("github-copilot", "free", "Free"), "USD", tiers=(
    PricingTier(per_million_input=Decimal(0), per_million_cache_read=Decimal(0), per_million_output=Decimal(0)),))
PRICES = PricingCatalog((*catalog().models, TIERED, FREE))
VALUATION = PRICES.reference_category_valuation


def entry(model: ModelRef, tokens: TokenUsage, order: int = 0) -> TraceEntry:
    return TraceEntry("s", "p", f"m{order}", None, 1000 + order, order, model, None, tokens)


def with_models(snapshot, models: dict[str, ModelRef]):
    return replace(snapshot, invocations=tuple(replace(item, model=models.get(item.invocation_id, item.model))
                                               for item in snapshot.invocations))


class RequestPriceabilityTests(unittest.TestCase):
    def test_reference_rates_complete_telemetry_and_real_usage_are_all_required(self):
        usage = TokenUsage(input=10, output=2)
        self.assertTrue(priceable_request(PRICED, usage, VALUATION))
        self.assertFalse(priceable_request(UNPRICED, usage, VALUATION), "missing pricing is not zero")
        self.assertFalse(priceable_request(PRICED, TokenUsage(), VALUATION), "zero-token request alone")
        self.assertFalse(priceable_request(PRICED, TokenUsage(input=10, known_fields=("input", "output")), VALUATION))
        self.assertTrue(priceable_request(ModelRef("github-copilot", "free"), usage, VALUATION), "exact-zero price")
        self.assertEqual((Decimal(0),) * 4, VALUATION(ModelRef("github-copilot", "free"), usage))

    def test_request_tier_with_missing_rates_is_not_priceable(self):
        tiered = ModelRef("github-copilot", "tiered")
        self.assertTrue(priceable_request(tiered, TokenUsage(input=900, output=10), VALUATION))
        self.assertFalse(priceable_request(tiered, TokenUsage(input=2000, output=10), VALUATION),
                         "the request's own long-context tier lacks an output rate")

    def test_mixed_requests_shares_and_category_costs_share_one_request_set(self):
        entries = (*(entry(PRICED, TokenUsage(input=100, cache_read=800, cache_write=50, output=40, reasoning=10), n)
                     for n in range(3)),
                   entry(UNPRICED, TokenUsage(input=9000, output=9000), 3), entry(UNPRICED, TokenUsage(input=1), 4))
        mix = priced_sample_mix(((e.model, e.tokens) for e in entries), VALUATION, sample_size=1)
        self.assertEqual((300, 2400, 150, 150), mix.totals, "reasoning folds into output once")
        self.assertEqual((3, 3, 1), (mix.request_count, mix.priced_requests, mix.sample_size))
        self.assertTrue(mix.cost_complete)
        self.assertEqual(comparison_cost(entries[:3], PRICES.reference_valuation).known_ccost, sum(mix.costs))
        self.assertEqual(100, sum(mix.percentages))
        self.assertNotIn("?", token_mix_lines("1 prompt", mix)[0])
        everything = priced_token_mix(((e.model, e.tokens) for e in entries), VALUATION)
        self.assertIn("(?", token_mix_lines("1 prompt", everything)[0], "complete-scope CCost keeps `?`")

    def test_relative_mix_uses_only_priceable_requests(self):
        priced = entry(PRICED, TokenUsage(input=10, cache_read=90))
        skewed = entry(UNPRICED, TokenUsage(output=10_000), 1)
        usage = priced_usage((priced, skewed), VALUATION)
        self.assertEqual((10, 90, 0, 0), (usage.input_tokens, usage.cache_read_tokens,
                                          usage.cache_write_tokens, usage.output_tokens))
        rows = {row.model_name: row for row in model_comparison_rows((usage,), catalog())}
        reference = {row.model_name: row for row in model_comparison_rows((usage, usage), catalog())}
        self.assertEqual(Decimal(1), rows["GPT Test"].relative_to_lowest)
        self.assertEqual(Decimal(2), rows["Claude Test"].relative_to_lowest)
        self.assertEqual(rows, reference, "ratios depend on the normalized mix, not the sample size")


class ReportPricedSampleTests(unittest.TestCase):
    def build(self, snapshot, **kwargs):
        service = report_service(self, MutableSource(snapshot), **kwargs)
        return service, service.build(ReportRequest())

    def test_mixed_prompt_counts_once_and_only_priced_requests_contribute(self):
        _service, report = self.build(with_models(make_snapshot(), {"i_child": UNPRICED}))
        mix = report.token_mix
        self.assertEqual(2, mix.sample_size)
        self.assertEqual((40, 0, 0, 7), mix.totals, "i_syn + i_next; unpriced child and zero wrapper excluded")
        self.assertTrue(mix.cost_complete)
        self.assertEqual(2, report.model_comparison_sample_size)
        text = rendered(report)
        self.assertIn("latest 2 priced prompts", text)
        self.assertNotIn("(?", text)

    def test_unpriceable_prompt_is_skipped_by_both_samples(self):
        _service, report = self.build(with_models(make_snapshot(), {"i_next": UNPRICED}))
        self.assertEqual((1, 1), (report.token_mix.sample_size, report.model_comparison_sample_size))

    def test_no_priceable_history_keeps_empty_sample_states(self):
        models = {item.invocation_id: UNPRICED for item in make_snapshot().invocations}
        _service, report = self.build(with_models(make_snapshot(), models))
        self.assertEqual((0, 0), (report.token_mix.request_count, report.model_comparison_sample_size))
        self.assertTrue(all(row.relative_cost is None for row in report.model_comparison))
        text = rendered(report)
        self.assertIn("No priced prompts are available yet.", text)
        self.assertIn("No completed priced prompts are available yet.", text)

    def test_catalog_update_changes_eligibility_without_stale_classification(self):
        newer = ModelRef("github-copilot", "new-model")
        models = {item.invocation_id: newer for item in make_snapshot().invocations}
        service, before = self.build(with_models(make_snapshot(), models))
        self.assertEqual(0, before.token_mix.sample_size)
        price = PricingTier(per_million_input=Decimal(1), per_million_cache_read=Decimal("0.1"),
                            per_million_output=Decimal(4))
        service.catalog = replace(service.catalog, models=(*service.catalog.models, ModelPricing(
            ModelRef("github-copilot", "new-model", "New Model"), "USD", tiers=(price,))))
        service.comparison_pricing_catalog = None
        after = service.build(ReportRequest())
        self.assertEqual((2, 2), (after.token_mix.sample_size, after.model_comparison_sample_size))

    def test_session_totals_keep_incomplete_markers(self):
        service = report_service(self, MutableSource(with_models(make_snapshot(), {"i_child": UNPRICED})))
        report = service.build(ReportRequest(ReportKind.SESSION, session_id="root"))
        self.assertFalse(report.prompt_blocks[0].comparison_cost_complete)
        self.assertTrue(any("CCost totals are incomplete" in note for note in report.notes))

    def test_history_report_keeps_unpriceable_models_and_partial_markers(self):
        snapshot = with_models(make_snapshot(), {"i_child": UNPRICED})
        service = report_service(self, MutableSource(snapshot), availability=Availability(None))
        history = service.build_token_mix_history()
        self.assertIn("unknown-model", {row.model for row in history.model_token_mix})
        self.assertEqual(len(analyze_snapshot(snapshot, now_ms=4000).trace_entries), history.token_mix.request_count)
        self.assertFalse(history.token_mix.cost_complete)


class WatchPricedMixTests(unittest.TestCase):
    def test_displayed_mix_is_priced_only_and_run_total_keeps_completeness(self):
        snapshot = with_models(make_snapshot(), {"i_child": UNPRICED})
        tracker = WatchTokenMix(1000)
        tracker.observe(snapshot, analyze_snapshot(snapshot, now_ms=4000))
        mix, total = tracker.project(VALUATION), tracker.project_total(VALUATION)
        self.assertEqual((3, 3), (mix.request_count, mix.priced_requests))
        self.assertEqual(2, mix.sample_size)
        self.assertEqual((5, 4), (total.request_count, total.priced_requests))
        self.assertEqual(sum(total.costs), sum(mix.costs), "the unpriced request adds no known CCost")
        stream = io.StringIO()
        WatchRenderer({"timezone": "UTC"}, stream=stream, interactive=False, terminal_width=200)._render_quota(
            WatchProjection("Watch", "V2", (), token_mix=mix, run_total=total, now_ms=4000))
        mix_line, total_line = stream.getvalue().splitlines()[:2]
        self.assertNotIn("?", mix_line)
        self.assertTrue(total_line.startswith("CCost · Watch: ?"), total_line)

    def test_run_boundary_and_refresh_dedup_apply_to_priced_mix(self):
        snapshot = with_models(make_snapshot(), {"i_child": UNPRICED})
        tracker = WatchTokenMix(2400)
        bundle = analyze_snapshot(snapshot, now_ms=4000)
        tracker.observe(snapshot, bundle)
        first = tracker.project(VALUATION)
        tracker.observe(snapshot, bundle)
        self.assertEqual(first, tracker.project(VALUATION), "repeated refresh counts requests once")
        self.assertEqual((40, 3, 2, 5), first.totals, "only the post-start compaction request")
        self.assertEqual(1, tracker.project_total(VALUATION).request_count)


if __name__ == "__main__":
    unittest.main()
