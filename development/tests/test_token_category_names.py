"""GitHub display vocabulary without telemetry, pricing or field-order changes."""
from decimal import Decimal as D
import unittest

from development.tests.fixtures.compact_reports import rendered
from src.analysis.token_mix import priced_token_mix
from src.application.display import with_display
from src.application.projection import project, token_mix as project_mix
from src.domain import ModelRef, TokenUsage
from src.presentation.token_mix import MIX_LABELS, mix_cells, token_mix_lines
from src.pricing.catalog import PricingCatalog
from src.pricing.github_copilot import parse_pricing_markdown
from src.reports.models import ModelTokenMixProjection, PublisherTokenMixProjection, ReportKind, ReportProjection


LABELS = ("Input", "Cached input", "Cache write", "Output")
KEYS = ("input", "cache", "write", "output")


def prices(write="$0.30"):
    return PricingCatalog(parse_pricing_markdown(
        "## OpenAI\n"
        "Model | Tier | Threshold (input tokens) | Input | Cached input | Cache write | Output\n"
        "--- | --- | --- | --- | --- | --- | ---\n"
        f"GPT-X | Default | Not applicable | $1 | $0.20 | {write} | $4\n"))


def observed(usage, catalog=None):
    return priced_token_mix(((ModelRef("openai", "GPT-X"), usage),),
                            (catalog or prices()).reference_category_valuation, sample_size=1)


class TokenCategoryNamesTests(unittest.TestCase):
    def test_normal_and_history_model_publisher_keep_counts_shares_and_category_cost_order(self):
        mix = observed(TokenUsage(input=10_000_000, cache_read=20_000_000, cache_write=30_000_000,
                                  output=40_000_000, reasoning=5_000_000))
        self.assertEqual((10_000_000, 20_000_000, 30_000_000, 45_000_000), mix.totals)
        self.assertEqual((D(1000), D(400), D(900), D(18000)), mix.costs)
        expected = ("9.5% (1000)", "19% (400)", "28.6% (900)", "42.9% (18000)")
        self.assertEqual(LABELS, MIX_LABELS)
        self.assertEqual(expected, mix_cells(mix, labels=False))
        for kind in (ReportKind.NORMAL, ReportKind.TOKEN_MIX):
            report = ReportProjection(kind, "Categories", "V2", token_mix=mix,
                model_token_mix=(ModelTokenMixProjection("GPT-X", 1, 1, mix),),
                publisher_token_mix=(PublisherTokenMixProjection("OpenAI", 1, 1, mix),))
            dto = project(report).to_json()
            targets = [dto["token_mix"], dto["model_token_mix"][0]["mix"], dto["publisher_token_mix"][0]["mix"]]
            for target in targets:
                self.assertEqual([10_000_000, 20_000_000, 30_000_000, 45_000_000], target["totals"])
                self.assertEqual(["1000", "400.00", "900.00", "18000"], target["costs"])
                self.assertEqual(expected, tuple(target["display"][key] for key in KEYS))
                self.assertEqual(dict(zip(KEYS, LABELS)), target["display"]["token_categories"])
                self.assertEqual("105M", target["display"]["total_tokens"])
                self.assertEqual("20300", target["display"]["total_cost"])
            text = rendered(report)
            for label in LABELS:
                self.assertIn(label, text)
            self.assertNotRegex(text, r"\b(?:Cache|Write):")

    def test_observed_zero_cache_write_is_still_zero(self):
        mix = observed(TokenUsage(input=100, cache_read=200, cache_write=0, output=100))
        dto = with_display(project_mix(mix)).to_json()
        self.assertEqual(0, dto["totals"][2])
        self.assertEqual("0% (0)", dto["display"]["write"])
        self.assertIn("Cache write: 0% (0)", token_mix_lines("1 prompt", mix)[0])

    def test_missing_cache_write_telemetry_does_not_become_observed_zero(self):
        usage = TokenUsage(input=100, cache_read=200, output=100, known_fields=("input", "cache_read", "output"))
        mix = observed(usage)
        dto = with_display(project_mix(mix)).to_json()
        self.assertIsNone(dto["totals"][2])
        self.assertEqual([None] * 4, dto["shares"])
        self.assertEqual("100/200/--/100", dto["display"]["totals"])
        self.assertEqual("400", dto["display"]["total_tokens"])
        self.assertTrue(dto["display"]["write"].startswith("--"))
        self.assertIn("Cache write: --", token_mix_lines("1 prompt", mix)[0])

    def test_published_cache_write_price_with_no_usage_does_not_create_observations(self):
        catalog = prices()
        self.assertEqual(D("0.30"), catalog.models[0].tiers[0].per_million_cache_write)
        mix = priced_token_mix((), catalog.reference_category_valuation)
        dto = with_display(project_mix(mix)).to_json()
        self.assertEqual(0, dto["request_count"])
        self.assertEqual([None] * 4, dto["totals"])
        self.assertEqual("N/A", dto["display"]["total_tokens"])
        self.assertEqual(["Token Mix % · 0 prompts · no token data yet"], token_mix_lines("0 prompts", mix))

    def test_catalog_not_applicable_rate_is_unpublished_not_usage(self):
        catalog = prices("Not applicable")
        self.assertIsNone(catalog.models[0].tiers[0].per_million_cache_write)
        # Preserve the established input-rate fallback, but only for observed tokens.
        mix = observed(TokenUsage(input=1_000_000, cache_write=2_000_000), catalog)
        dto = with_display(project_mix(mix)).to_json()
        self.assertEqual([1_000_000, 0, 2_000_000, 0], dto["totals"])
        self.assertEqual(D(200), mix.costs[2])
        self.assertEqual("66.7% (200)", dto["display"]["write"])


if __name__ == "__main__":
    unittest.main()
