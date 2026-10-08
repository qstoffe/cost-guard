"""Shared-mix context tiers, full-precision ordering and lossless table subfields."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal as D
from types import SimpleNamespace
import re
import unittest

from development.tests import test_compact_reports as compact
from development.tests.test_compact_reports import Availability, rendered
from development.tests.test_step8_watch import MutableSource
from src.analysis.comparisons import model_comparison_rows
from src.domain import ModelPricing, ModelRef, PricingTier, TokenUsage
from src.pricing.catalog import PricingCatalog
from src.pricing.github_copilot import (
    _annotate_promotions, _catalog_from_payload, _catalog_payload, _apply_expired_promotions,
    _preserve_known_promotions, parse_pricing_markdown,
)
from src.reports.model_comparison import price_summary
from src.reports import ReportRequest
from src.reports.models import ModelComparisonProjection, ReportKind, ReportProjection
from src.presentation.model_comparison import aligned_price_summaries, compact_threshold

ANSI = re.compile(r"\x1b\[[0-9;]*m")
SAMPLE = (SimpleNamespace(input_tokens=20, cache_read_tokens=60, cache_write_tokens=10, output_tokens=10),)
COLORS = {"colors": {"modelComparisonPromotion": {"ansi256": 214}, "modelComparisonNew": {"ansi256": 118}}}


def tier(value, *, minimum=None, maximum=None, operator=None, rates=None):
    i, c, w, o = map(D, rates or (value,) * 4)
    return PricingTier(min_input_tokens=minimum, max_input_tokens=maximum, per_million_input=i,
                       per_million_cache_read=c, per_million_cache_write=w, per_million_output=o,
                       input_threshold_operator=operator)


def model(name, base, *levels):
    return ModelPricing(ModelRef("github-copilot", name, name), "USD", tiers=(tier(base), *levels),
                        metadata={"publisher": "Test", "release_date": "2026-10-01"})


def rows(*models, sample=SAMPLE):
    return model_comparison_rows(sample, PricingCatalog(models))


def projection(row, marker=None):
    return ModelComparisonProjection(row.publisher, row.model_name, row.relative_to_lowest, "1/0.1/N/A/5",
                                     row.release_date, promotional=marker is not None, promotion_marker=marker,
                                     relative_levels=row.relative_levels)


class TierCalculationTests(unittest.TestCase):
    def test_each_level_uses_all_four_categories_and_one_base_reference(self):
        priced = model("Mixed", "1", tier("1", minimum=200001, operator=">", rates=("6", "0.5", "8", "12")))
        priced = replace(priced, tiers=(tier("1", maximum=200000, rates=("2", "0.1", "3", "5")), priced.tiers[1]))
        result, reference = rows(priced, model("Reference", "1"))
        self.assertEqual(D(126), result.estimated_ccost)
        self.assertEqual(D("1.26"), result.relative_to_lowest)
        self.assertEqual((D("1.26"), D("3.5")), tuple(level.relative_cost for level in result.relative_levels))
        self.assertEqual((">", 200000), (result.relative_levels[1].threshold_operator, result.relative_levels[1].threshold_tokens))
        self.assertEqual(D(1), reference.relative_to_lowest)
        self.assertNotEqual(result.relative_to_lowest * 2, result.relative_levels[1].relative_cost)

    def test_zero_cache_write_rate_is_not_replaced_with_input(self):
        result, _ = rows(model("Reference", "0.1"), model("ZeroWrite", "1",
                            tier("1", minimum=100001, rates=("2", "1", "0", "3"))))
        self.assertEqual(D(10), result.relative_to_lowest)
        self.assertEqual(D(13), result.relative_levels[1].relative_cost)

    def test_multiple_levels_single_level_and_unknown_rates_are_not_invented(self):
        unknown = replace(tier("5", minimum=500001), per_million_output=None)
        result, reference = rows(model("Many", "8", tier("16", minimum=100001), unknown,
                                      tier("32", minimum=1000000, operator="≥")), model("Reference", "1"))
        self.assertEqual((D(8), D(16), None, D(32)), tuple(level.relative_cost for level in result.relative_levels))
        self.assertEqual(1, len(reference.relative_levels))
        self.assertIn("N/A", rendered(ReportProjection(ReportKind.NORMAL, "Report", "V2", model_comparison=(projection(result),))))

    def test_fallback_mix_sorts_every_level_but_displays_no_synthetic_multipliers(self):
        a = model("A", "8", tier("10", minimum=100001, rates=("1", "20", "1", "1")))
        b = model("B", "8", tier("10", minimum=100001, rates=("30", "10", "1", "1")))
        result = rows(b, a, sample=())
        self.assertEqual(["A", "B"], [row.model_name for row in result])
        self.assertTrue(all(row.estimated_ccost is None and row.relative_to_lowest is None for row in result))
        self.assertTrue(all(level.relative_cost is None for row in result for level in row.relative_levels))

    def test_source_conditions_cache_roundtrip_and_promotion_reconstruction(self):
        markdown = """## Anthropic
| Model | Input | Cached input | Cache write | Output | Threshold (input tokens) |
| --- | --- | --- | --- | --- | --- |
| Claude Test | $2.123456789 | $0.0000123456 | Not applicable | $8 | ≤200K |
| Claude Test | $4.1 | $0.3 | $6.2 | $17.03 | >200K |
| Claude Test | $8.2 | $0.6 | $12.4 | $34.06 | ≥1M |

Claude Test has promotional pricing at 50% off through October 31, 2026.
"""
        native = parse_pricing_markdown(markdown)[0]
        self.assertEqual((None, 200001, 1000000), tuple(t.min_input_tokens for t in native.tiers))
        self.assertTrue(native.tiers[0].matches(200000))
        self.assertFalse(native.tiers[1].matches(200000))
        self.assertTrue(native.tiers[1].matches(200001))
        self.assertTrue(native.tiers[2].matches(1000000))
        self.assertFalse(native.tiers[1].matches(1000000))
        catalog = PricingCatalog(_annotate_promotions((native,), markdown))
        rebuilt = _catalog_from_payload(_catalog_payload(catalog))
        self.assertEqual(catalog.models, rebuilt.models)
        result, _ = rows(rebuilt.models[0], model("Reference", "1"))
        self.assertEqual(((">", 200000), ("≥", 1000000)),
                         tuple((level.threshold_operator, level.threshold_tokens) for level in result.relative_levels[1:]))
        summary = price_summary(rebuilt, "Claude Test")
        self.assertEqual("2.123456789/0.0000123456/-/8→4.1/0.3/6.2/17.03 (>200000)→8.2/0.6/12.4/34.06 (≥1000000)", summary)
        expired = _apply_expired_promotions(rebuilt, now_ms=1_800_000_000_000).models[0]
        self.assertEqual(D("4.246913578"), expired.tiers[0].per_million_input)
        self.assertEqual((None, ">", "≥"), tuple(t.input_threshold_operator for t in expired.tiers))

    def test_legacy_exclusive_boundary_and_ordered_catalog_tiers(self):
        base = tier("1", maximum=200000)
        high = tier("2", minimum=200001)
        priced = replace(model("Legacy", "1"), tiers=(high, base))
        (result,) = rows(priced)
        self.assertEqual((D(1), D(2)), tuple(level.relative_cost for level in result.relative_levels))
        self.assertEqual((">", 200000), (result.relative_levels[1].threshold_operator, result.relative_levels[1].threshold_tokens))

    def test_legacy_cached_promotions_retain_validity_and_start_after_operator_upgrade(self):
        priced = model("Claude Test", "8", tier("16", minimum=200001, operator=">"))
        promoted = replace(priced, metadata={**priced.metadata, "promotion_active": "true",
                                            "promotion_starts_ms": "100", "promotion_expires_ms": "10000000"})
        payload = _catalog_payload(PricingCatalog((promoted,)))
        for value in payload["models"][0]["tiers"]:
            value.pop("threshold_operator")
        legacy = _catalog_from_payload(payload)
        for metadata in ({"promotion_active": "true", "promotion_expires_ms": "10000000"}, {}):
            current = replace(priced, metadata={**priced.metadata, **metadata})
            (retained,) = _preserve_known_promotions((current,), legacy, now_ms=1000)
            self.assertEqual("100", retained.metadata["promotion_starts_ms"])
            self.assertEqual("10000000", retained.metadata["promotion_expires_ms"])
            self.assertEqual(">", retained.tiers[1].input_threshold_operator)

    def test_ascii_and_unicode_inclusive_exclusive_source_boundaries(self):
        header = "## OpenAI\n| Model | Input | Cached input | Output | Threshold (input tokens) |\n| --- | --- | --- | --- | --- |\n"
        for lower, upper, minimum, operator in ((">200K", "≤200K", 200001, ">"),
                                                ("≥200K", "<200K", 200000, "≥"),
                                                (">=200K", "<200K", 200000, "≥")):
            markdown = header + f"| GPT Test | $1 | $0.1 | $5 | {upper} |\n| GPT Test | $2 | $0.2 | $10 | {lower} |\n"
            (native,) = parse_pricing_markdown(markdown)
            self.assertEqual(minimum - 1, native.tiers[0].max_input_tokens)
            self.assertEqual(minimum, native.tiers[1].min_input_tokens)
            (result,) = rows(native)
            self.assertEqual(operator, result.relative_levels[1].threshold_operator)
            self.assertEqual(200000, result.relative_levels[1].threshold_tokens)
            self.assertIs(native.tiers[0], native.selected_tier(minimum - 1))
            self.assertIs(native.tiers[1], native.selected_tier(minimum))


class TierSortingTests(unittest.TestCase):
    def assert_order(self, expected, *models):
        for sample in (SAMPLE, ()):
            self.assertEqual(expected, [row.model_name for row in rows(*models, sample=sample)])

    def test_a_base_price_descending(self):
        self.assert_order(["B", "A", "C"], model("A", "8"), model("B", "20"), model("C", "1"))

    def test_b_identical_base_higher_price_descending(self):
        self.assert_order(["C", "B", "A"], model("A", "8", tier("12", minimum=100001)),
                          model("B", "8", tier("16", minimum=200001)), model("C", "8", tier("20", minimum=500001)))

    def test_c_identical_prices_earliest_numeric_boundary(self):
        self.assert_order(["C", "B", "A"], model("A", "8", tier("16", minimum=1000001)),
                          model("B", "8", tier("16", minimum=500001)), model("C", "8", tier("16", minimum=100001)))

    def test_d_no_increase_is_cheaper_and_equal_tiers_do_not_create_threshold_differences(self):
        self.assert_order(["C", "A", "B"], model("B", "8", tier("8", minimum=100001)),
                          model("A", "8"), model("C", "8", tier("16", minimum=500001)))

    def test_e_identical_prices_and_boundaries_use_alphabetical_name(self):
        self.assert_order(["alpha", "Beta", "Zeta"], *(model(name, "8", tier("16", minimum=100001))
                                                       for name in ("Zeta", "Beta", "alpha")))

    def test_f_display_rounding_never_controls_order(self):
        result = rows(model("A", "8.01"), model("Z", "8.04"), model("Reference", "1"))
        self.assertEqual(["Z", "A", "Reference"], [row.model_name for row in result])
        self.assertEqual(["8.0x", "8.0x"], [f"{row.relative_to_lowest:.1f}x" for row in result[:2]])
        self.assertGreater(result[0].relative_to_lowest, result[1].relative_to_lowest)

    def test_g_additional_prices_then_boundaries_are_tie_breakers(self):
        first = tier("16", minimum=100001)
        self.assert_order(["C", "B", "A"], model("A", "8", first, tier("24", minimum=500001)),
                          model("B", "8", first, tier("32", minimum=1000001)),
                          model("C", "8", first, tier("32", minimum=500001)))

    def test_inclusive_boundary_starts_one_token_earlier_than_exclusive(self):
        self.assert_order(["Z", "A"], model("A", "8", tier("16", minimum=200001, operator=">")),
                          model("Z", "8", tier("16", minimum=200000, operator="≥")))

    def test_unknown_higher_rate_stays_unknown_not_unchanged_or_zero(self):
        unknown = replace(tier("16", minimum=100001), per_million_input=None)
        self.assert_order(["B", "A"], model("A", "8", unknown), model("B", "8"))


class TierPresentationTests(unittest.TestCase):
    def test_internal_fields_align_across_tiers_markers_colors_and_terminal_widths(self):
        result = rows(model("Many", "125.4", tier("125.5", minimum=200001, operator=">"),
                           tier("250", minimum=1000000, operator="≥")),
                      model("Two", "8", tier("16", minimum=100001, operator=">")), model("Single", "1"))
        items = tuple(projection(row, marker) for row, marker in zip(result, (1, 12, None)))
        for kind in (ReportKind.NORMAL, ReportKind.ALL_MODELS):
            for width in (40, 80, 120, 200, 400):
                report = ReportProjection(kind, "Report", "V2", model_comparison=items)
                plain = rendered(report, COLORS, width=width, color=False)
                colored = rendered(report, COLORS, width=width, color=True)
                self.assertEqual(plain, ANSI.sub("", colored))
                lines = [line for line in plain.splitlines() if line.startswith("| Test")]
                cells = [line.split("|")[3] for line in lines]
                self.assertEqual(3, len(cells))
                self.assertTrue(cells[0].startswith(" *1 "))
                self.assertTrue(cells[1].startswith(" *12 "))
                base_ends = [re.search(r"\d+\.\d+x", cell).end() for cell in cells]
                self.assertEqual(1, len(set(base_ends)))
                self.assertEqual(cells[0].index("→"), cells[1].index("→"))
                self.assertEqual(cells[0].index("("), cells[1].index("("))
                self.assertEqual(3, cells[0].count("x"))
                self.assertIn("125.5x", cells[0])
                self.assertIn("(≥1M)", cells[0])
                self.assertNotIn("...", "".join(cells))
                header = next(line for line in plain.splitlines() if line.startswith("| Publisher"))
                self.assertEqual(5 if kind == ReportKind.ALL_MODELS else 4, len(header.split("|")[1:-1]))
                self.assertEqual(kind == ReportKind.ALL_MODELS, "GitHub USD/M I/C/W/O" in header)
                self.assertNotIn("Copilot CCost/M", plain)

    def test_exact_rates_keep_precision_categories_tiers_and_boundaries_without_a_mix(self):
        summaries = ("2.123456789/0.0000123/-/8→4.1/0.3/6.2/17.03 (>200000)→8/1/9/31 (≥1000000)",
                     "125/12/9/300→250/24/18/600 (>100000)→500/48/36/1200 (>2000000)")
        aligned = aligned_price_summaries(summaries)
        self.assertEqual([m.start() for m in re.finditer("/", aligned[0])],
                         [m.start() for m in re.finditer("/", aligned[1])])
        self.assertIn("2.123456789", aligned[0])
        items = tuple(ModelComparisonProjection("Test", f"M{i}", None, value, None, promotion_marker=i + 1)
                      for i, value in enumerate(summaries))
        text = rendered(ReportProjection(ReportKind.ALL_MODELS, "All", "V2", model_comparison=items), width=40)
        for expected in ("2.123456789", "0.0000123", "(>200K)", "(≥1M)", "(>2M)", "*1", "*2"):
            self.assertIn(expected, text)
        table = [line for line in text.splitlines() if line.startswith("| Test")]
        self.assertNotIn("x", "".join(line.split("|")[3] for line in table))
        self.assertNotIn("...", "".join(line.split("|")[4] for line in table))

    def test_threshold_compaction_never_rounds_away_actual_token_values(self):
        for value, expected in ((100000, "100K"), (200000, "200K"), (1000000, "1M"),
                                (1234567, "1.234567M"), (100001, "100.001K"), (999, "999")):
            self.assertEqual(expected, compact_threshold(value))

    def test_both_report_modes_share_order_and_normal_keeps_availability_selection(self):
        service = compact.CompactReportTests.service(self, MutableSource(), availability=Availability(("github-copilot/gpt-test", "github-copilot/claude-test")))
        prices = service.pricing_provider.catalog
        prices = replace(prices, models=tuple(replace(m, tiers=(tier("8"), tier("20" if i else "16", minimum=100001)))
                                             for i, m in enumerate(prices.models)))
        service.pricing_provider.catalog = prices
        normal = service.build(ReportRequest())
        all_models = service.build(ReportRequest(ReportKind.ALL_MODELS))
        self.assertEqual([r.model for r in normal.model_comparison], [r.model for r in all_models.model_comparison])
        self.assertEqual([r.relative_levels for r in normal.model_comparison], [r.relative_levels for r in all_models.model_comparison])
        self.assertIn("GitHub USD/M I/C/W/O", rendered(all_models))
        self.assertNotIn("GitHub USD/M I/C/W/O", rendered(normal))


if __name__ == "__main__":
    unittest.main()
