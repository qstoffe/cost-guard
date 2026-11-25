"""Report CCost / Token Mix % / Relative CCost definitions and the --token-mix total and alignment."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
import unittest

from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from development.tests.fixtures import compact_reports as compact
from development.tests.fixtures.session_snapshots import make_snapshot
from src.reports.sampling import latest_prompts, latest_token_prompts
from development.tests.fixtures.compact_reports import Availability, rendered
from development.tests.fixtures.quota_rendering import quotas, rolling
from development.tests.fixtures.watch_runtime import MutableSource
from src.analysis.token_mix import TokenMix, token_mix
from src.domain import ModelRef, TokenUsage
from src.pricing.catalog import normalized_average_token_mix
from src.numbers import balanced_share_percents
from src.presentation.token_mix import mix_cells, token_mix_line
from src.reports import ReportKind, ReportProjection, ReportRequest


def large_mix(sample_size: int = 100) -> TokenMix:
    mix = token_mix((TokenUsage(input=4_113_000, cache_read=112_422_000, cache_write=1_371_000,
                                output=19_194_000),), sample_size=sample_size)
    return replace(mix, costs=(Decimal(123), Decimal(456), Decimal(12), Decimal(789)), priced_requests=1)


def report(mix: TokenMix | None = None, sample: int = 100, **changes) -> ReportProjection:
    return ReportProjection(ReportKind.NORMAL, "Report", "V2", accounts_quotas=quotas(rolling()),
                            token_mix=mix or large_mix(), model_comparison_sample_size=sample, **changes)


class ReportDefinitionTests(unittest.TestCase):
    def test_service_samples_keep_their_distinct_eligibility(self):
        service = compact.report_service(self, SyntheticMonthSource(2, 60, month_start_ms=compact.START))
        built = service.build(ReportRequest())
        roots = tuple(service._analyzed.values())
        priceable = service._priceable()
        self.assertEqual(len(latest_token_prompts(roots, priceable)), built.token_mix.sample_size)
        self.assertEqual(normalized_average_token_mix(service._relative_usage(latest_prompts(roots, priceable)))[4],
                         built.model_comparison_sample_size)
        self.assertEqual((100, 100), (built.token_mix.sample_size, built.model_comparison_sample_size))
        text = rendered(built)
        self.assertIn("Your mix uses the latest 100 priced prompts", text)
        self.assertIn("latest 100 completed priceable prompts", text)
        # Running/aborted prompts qualify only for the displayed mix, as before.
        root = roots[0]
        record = root.bundle.prompts[0]
        root.bundle = replace(root.bundle, prompts=(record, replace(record, prompt_id="running", in_progress=True),
                                                    replace(record, prompt_id="aborted", aborted=True)))
        self.assertEqual(3, len(latest_token_prompts((root,), priceable)))
        self.assertEqual(1, service._model_comparison((root,), all_models=True)[1])


class TokenMixHistoryTotalTests(unittest.TestCase):
    def service(self, availability):
        snapshot = make_snapshot()
        claude = ModelRef("github-copilot", "claude-test")
        snapshot = replace(snapshot, invocations=tuple(
            replace(item, model=claude, tokens=replace(item.tokens, cache_read=5_000)) if item.invocation_id == "i_child"
            else item for item in snapshot.invocations))
        return compact.report_service(self, MutableSource(snapshot), availability=availability)

    def test_total_is_recomputed_from_shown_requests_and_rendered_before_table(self):
        service = self.service(Availability(None))
        built = service.build_token_mix_history()
        self.assertEqual(2, len(built.model_token_mix))
        total = built.token_mix
        rows = [row.mix for row in built.model_token_mix]
        self.assertEqual(tuple(map(sum, zip(*(row.totals for row in rows)))), total.totals)
        self.assertEqual(sum(sum(row.costs) for row in rows), sum(total.costs))
        self.assertEqual(sum(row.request_count for row in rows), total.request_count)
        self.assertEqual(token_mix(TokenUsage(input=a, cache_read=b, cache_write=c, output=d)
                                   for a, b, c, d in (total.totals,)).percentages, total.percentages)
        text = rendered(built)
        lines = text.splitlines()
        self.assertEqual("Token Mix % by model", lines[1])
        heading = next(i for i, line in enumerate(lines) if line.startswith("Total Token Mix %"))
        self.assertRegex(lines[heading], r"^Total Token Mix % · \S+ tokens$")
        self.assertTrue(lines[heading + 1].startswith("Input: "))
        self.assertLess(heading, next(i for i, line in enumerate(lines) if line.startswith("| Model")))

    def test_total_and_rows_keep_all_observed_models_regardless_of_availability(self):
        built = self.service(Availability(("github-copilot/gpt-test",))).build_token_mix_history()
        self.assertEqual(2, len(built.model_token_mix))
        self.assertEqual(built.token_mix.request_count, sum(row.calls for row in built.model_token_mix))
        self.assertEqual(sum(built.token_mix.costs), sum(sum(row.mix.costs) for row in built.model_token_mix))
        hidden = self.service(Availability(("openai/other",))).build_token_mix_history()
        self.assertEqual(built, hidden)
        self.assertIn("Total Token Mix %", rendered(hidden))


class BalancedShareTests(unittest.TestCase):
    def test_largest_remainder_tenths_and_compact_integers(self):
        for values, expected in (
            ((184, 9607, 146, 63), ("1.8%", "96.1%", "1.5%", "0.6%")),
            ((1, 1, 1, 0), ("33.4%", "33.3%", "33.3%", "0%")),
            ((200, 9580, 130, 90), ("2%", "95.8%", "1.3%", "0.9%")),
            ((99999, 1, 0, 0), ("100%", "0%", "0%", "0%")),
        ):
            with self.subTest(values=values):
                self.assertEqual(expected, balanced_share_percents(values))
                self.assertEqual(Decimal(100), sum(Decimal(p[:-1]) for p in expected))

    def test_correction_follows_fractional_error_not_a_fixed_category(self):
        from itertools import permutations
        for values in permutations((1004, 2003, 3002, 3991)):
            shown = [Decimal(p[:-1]) for p in balanced_share_percents(values)]
            self.assertEqual(Decimal(100), sum(shown))
            floors = [Decimal(v // 10) / 10 for v in values]
            corrected = [i for i in range(4) if shown[i] > floors[i]]
            self.assertEqual([values.index(1004)], corrected)

    def test_rendered_categories_total_exactly_100_over_awkward_distributions(self):
        from random import Random
        random = Random(43)
        for _ in range(500):
            values = tuple(random.randrange(0, 10**12) for _ in range(4))
            mix = token_mix((TokenUsage(*values),))
            shares = [Decimal(cell.split(": ")[1].split("%")[0]) for cell in mix_cells(mix)]
            self.assertEqual(Decimal(100), sum(shares))
            for exact, rounded in zip(mix.shares, shares):
                self.assertLess(abs(exact - rounded), Decimal("0.1"))
            self.assertEqual(values, mix.totals)

    def test_small_expensive_output_share_is_visible_not_zero(self):
        # Shape of an Opus-style prompt: output is ~0.4% of tokens but a large CCost part.
        mix = replace(token_mix((TokenUsage(input=30, cache_read=3_000_000, cache_write=30_000, output=12_000),),
                                sample_size=1), costs=(Decimal("0.01"), Decimal(60), Decimal(15), Decimal(24)),
                      priced_requests=1)
        self.assertEqual(0, mix.percentages[3], "integer apportionment is unchanged for analysis/diagnostics")
        self.assertEqual(100, sum(mix.percentages))
        self.assertEqual(sum(mix.totals), mix.total_tokens)
        self.assertLess(abs(Decimal(100) - sum(mix.shares)), Decimal("1e-20"))
        self.assertEqual(("Input: 0% (<0.1)", "Cached input: 98.6% (60)", "Cache write: 1% (15)", "Output: 0.4% (24)"),
                          mix_cells(mix))
        self.assertEqual("Token Mix % · 1 prompt · Input: 0% (<0.1)   Cached input: 98.6% (60)   Cache write: 1% (15)   "
                         "Output: 0.4% (24)", token_mix_line("1 prompt", mix))
        self.assertIn("Output: 0.4% (24)", rendered(report(mix, sample=1)))

    def test_undefined_and_unknown_shares_stay_dashes(self):
        self.assertEqual((None,) * 4, token_mix((TokenUsage(),)).shares)
        unknown = token_mix((TokenUsage(input=5, known_fields=("input",)),))
        self.assertEqual((None,) * 4, unknown.shares)
        self.assertEqual(4, token_mix_line("x", unknown).count("--"))


if __name__ == "__main__":
    unittest.main()
