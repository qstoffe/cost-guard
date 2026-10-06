"""Report CCost / Token Mix % / Rel CCost definitions and the --token-mix total and alignment."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
import re
import unittest

from development.fixtures.synthetic_month import SyntheticMonthSource
from development.tests import test_compact_reports as compact
from development.tests.test_analysis_core import make_snapshot
from development.tests.test_compact_reports import Availability, rendered
from development.tests.test_quota_presentation import quotas, rolling
from development.tests.test_step8_watch import MutableSource
from src.analysis.token_mix import TokenMix, priced_token_mix, token_mix
from src.analysis.valuation import comparison_cost, unique_usage
from src.cli import CommandKind, help_text, parse_command
from src.domain import ModelRef, TokenUsage
from src.pricing.catalog import normalized_average_token_mix
from src.presentation.definitions import DEFINITION_WIDTH
from src.numbers import balanced_share_percents
from src.presentation.token_mix import aligned_mix_cells, mix_cells, token_mix_line
from src.reports import ReportKind, ReportProjection, ReportRequest
from src.reports.models import ModelTokenMixProjection

ANSI = re.compile(r"\x1b\[[0-9;]*m")
CONFIG = {"timezone": "UTC", "colors": {"reportDefinitionLabel": {"ansi256": 226},
                                       "reportDefinitionValue": {"ansi256": 227}}}
LABELS = ("CCost:", "Token Mix %:", "Rel CCost:")


def large_mix(sample_size: int = 100) -> TokenMix:
    mix = token_mix((TokenUsage(input=4_113_000, cache_read=112_422_000, cache_write=1_371_000,
                                output=19_194_000),), sample_size=sample_size)
    return replace(mix, costs=(Decimal(123), Decimal(456), Decimal(12), Decimal(789)), priced_requests=1)


def report(mix: TokenMix | None = None, sample: int = 100, **changes) -> ReportProjection:
    return ReportProjection(ReportKind.NORMAL, "Report", "V2", accounts_quotas=quotas(rolling()),
                            token_mix=mix or large_mix(), model_comparison_sample_size=sample, **changes)


def blocks(text: str) -> list[list[str]]:
    lines = ANSI.sub("", text).splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("CCost:"))
    end = next(i for i, line in enumerate(lines) if line.startswith("Pricing/cache metadata:"))
    groups: list[list[str]] = [[]]
    for line in lines[start:end - 1]:  # one blank line separates definitions from the metadata
        if line:
            groups[-1].append(line)
        else:
            groups.append([])
    return groups


class ReportDefinitionTests(unittest.TestCase):
    def test_three_blocks_in_order_separated_by_one_blank_line_above_table(self):
        text = rendered(report())
        groups = blocks(text)
        self.assertEqual(3, len(groups), "exactly one blank line between blocks")
        for group, label in zip(groups, LABELS):
            self.assertTrue(group[0].startswith(label + " "), group[0])
        self.assertLess(text.index("Rel CCost: Applies"), text.index("| Publisher"))
        self.assertEqual([
            "CCost:  1 CCost equals 1 Copilot AI credit.",
            "        Flat-rate accounts use Copilot's published token rates, not the billed cost.",
            "        Unlabeled cost figures in Cost Guard are CCost unless stated otherwise.",
        ], groups[0])
        self.assertEqual([
            "Token Mix %: The I/C/W/O percentage split of your observed token usage.",
            "             Your mix uses the latest 100 prompts with token data, totaling 137.1M tokens.",
            "             Input: 3% (123)   Cache: 82% (456)   Write: 1% (12)   Output: 14% (789)",
        ], groups[1])
        self.assertEqual([
            "Rel CCost: Applies Token Mix % from 100 completed prompts to each model's CCost/M rates.",
            "           The cheapest result is 1.0x; other models are shown relative to it.",
        ], groups[2])

    def test_continuations_align_sentences_split_and_width_bounded(self):
        for width in (40, 72, 120, 300):
            for color in (False, True):
                with self.subTest(width=width, color=color):
                    for group in blocks(rendered(report(), CONFIG, width=width, color=color)):
                        label = next(item for item in LABELS if group[0].startswith(item))
                        indent = group[0].index(group[0][len(label):].lstrip(), len(label))
                        self.assertEqual(len(label) + (2 if label == "CCost:" else 1), indent)
                        for line in group:
                            self.assertLessEqual(len(line), min(DEFINITION_WIDTH, width), line)
                            self.assertNotRegex(line[indent:], r"\.\s+[A-Z]", "one sentence per line")
                        for line in group[1:]:
                            self.assertTrue(line.startswith(" " * indent) and line[indent] != " ", line)

    def test_only_labels_and_live_values_are_emphasized(self):
        colored = rendered(report(), CONFIG, color=True)
        self.assertEqual(list(LABELS), re.findall(r"\x1b\[38;5;226m(.*?)\x1b\[0m", colored))
        for label in LABELS:
            self.assertIn(f"\x1b[38;5;226m{label}\x1b[0m ", colored)
        cells = "Input: 3% (123)   Cache: 82% (456)   Write: 1% (12)   Output: 14% (789)"
        self.assertEqual(["100", "137.1M", cells], re.findall(r"\x1b\[38;5;227m(.*?)\x1b\[0m", colored))
        self.assertIn(" " * 13 + f"\x1b[38;5;227m{cells}\x1b[0m\n", colored, "indent stays unstyled")
        self.assertIn("the latest \x1b[38;5;227m100\x1b[0m prompts with token data, totaling "
                      "\x1b[38;5;227m137.1M\x1b[0m tokens.", colored)
        self.assertEqual(ANSI.sub("", colored), rendered(report()))
        # Wrapped narrow cells stay emphasized per line, never across the indent.
        narrow = rendered(report(), CONFIG, width=40, color=True)
        self.assertEqual(cells.split("   "), [cell for segment in re.findall(r"\x1b\[38;5;227m(.*?)\x1b\[0m", narrow)
                                              if segment.startswith(("Input", "Cache", "Write", "Output"))
                                              for cell in segment.split("   ")])

    def test_default_palettes_use_plain_yellow_not_promotion_gold(self):
        from src.config import load_configuration
        schemes = load_configuration(compact.ROOT).values["colorSchemes"]
        classic = schemes["classic"]
        plain = {"foreground": "Yellow", "background": None, "ansi256": None}
        self.assertEqual(plain, classic["reportDefinitionLabel"])
        self.assertEqual(plain, classic["reportDefinitionValue"])
        self.assertNotEqual(classic["modelComparisonPromotion"], classic["reportDefinitionLabel"])
        light = schemes["modus-operandi-tinted"]
        self.assertEqual(light["costQuotaWarning"], light["reportDefinitionLabel"])
        self.assertEqual(light["reportDefinitionLabel"], light["reportDefinitionValue"])

    def test_pricing_metadata_directly_above_table(self):
        lines = rendered(report()).splitlines()
        index = next(i for i, line in enumerate(lines) if line.startswith("Pricing/cache metadata:"))
        self.assertEqual("", lines[index - 1])
        self.assertTrue(lines[index + 1].startswith("|---"), lines[index + 1])

    def test_wording_header_and_removed_duplicate_mix_line(self):
        text = rendered(report())
        self.assertNotIn("does not predict model behavior", text)
        self.assertNotIn("Token mix", text)
        self.assertNotIn("Token Mix % · last", text)
        self.assertIn("Copilot CCost/M tokens I/C/W/O", text)
        self.assertEqual(1, text.count("Input: 3% (123)"), "live mix only in the definitions")
        lines = text.splitlines()
        accounts = lines.index("Accounts Overview")
        self.assertTrue(lines[accounts - 2].startswith("|"))
        self.assertIs(CommandKind.TOKEN_MIX, parse_command(["--token-mix"]).kind)
        self.assertIn("--token-mix", help_text())
        self.assertIn("Token Mix %", help_text())

    def test_dynamic_count_human_tokens_and_empty_states(self):
        one = replace(token_mix((TokenUsage(input=842_300),), sample_size=1), costs=(Decimal(1),) * 4,
                      priced_requests=1)
        text = rendered(report(one, sample=1))
        self.assertIn("Your mix uses the latest 1 prompt with token data, totaling 842.3K tokens.", text)
        self.assertIn("Applies Token Mix % from 1 completed prompt to each", text)
        twelve = replace(large_mix(37), totals=(700_000, 10_000_000, 0, 2_000_000))
        self.assertIn("latest 37 prompts with token data, totaling 12.7M tokens.", rendered(report(twelve)))
        empty = rendered(report(TokenMix(), sample=0))
        self.assertIn("Token Mix %: The I/C/W/O percentage split of your observed token usage.", empty)
        self.assertIn("No prompts with token data are available yet.", empty)
        self.assertIn("Rel CCost: No completed prompts with token data are available yet.", empty)
        self.assertIn("Rel CCost stays blank", empty)

    def test_service_samples_keep_their_distinct_eligibility(self):
        service = compact.CompactReportTests.service(self, SyntheticMonthSource(2, 60, month_start_ms=compact.START))
        built = service.build(ReportRequest())
        roots = tuple(service._analyzed.values())
        self.assertEqual(len(service._latest_token_prompts(roots)), built.token_mix.sample_size)
        self.assertEqual(normalized_average_token_mix(service._latest_prompts(roots))[4],
                         built.model_comparison_sample_size)
        self.assertEqual((100, 100), (built.token_mix.sample_size, built.model_comparison_sample_size))
        text = rendered(built)
        self.assertIn("Your mix uses the latest 100 prompts with token data", text)
        self.assertIn("Rel CCost: Applies Token Mix % from 100 completed prompts", text)
        # Running/aborted prompts qualify only for the displayed mix, as before.
        root = roots[0]
        record = root.bundle.prompts[0]
        root.bundle = replace(root.bundle, prompts=(record, replace(record, prompt_id="running", in_progress=True),
                                                    replace(record, prompt_id="aborted", aborted=True)))
        self.assertEqual(3, len(service._latest_token_prompts((root,))))
        self.assertEqual(1, service._model_comparison((root,), all_models=True)[1])


class TokenMixHistoryTotalTests(unittest.TestCase):
    def service(self, availability):
        snapshot = make_snapshot()
        claude = ModelRef("github-copilot", "claude-test")
        snapshot = replace(snapshot, invocations=tuple(
            replace(item, model=claude, tokens=replace(item.tokens, cache_read=5_000)) if item.invocation_id == "i_child"
            else item for item in snapshot.invocations))
        return compact.CompactReportTests.service(self, MutableSource(snapshot), availability=availability)

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

    def test_total_uses_the_same_availability_filter_as_rows(self):
        built = self.service(Availability(("github-copilot/gpt-test",))).build_token_mix_history()
        (row,) = built.model_token_mix
        self.assertEqual((row.mix.totals, row.mix.costs, row.mix.percentages),
                         (built.token_mix.totals, built.token_mix.costs, built.token_mix.percentages))
        hidden = self.service(Availability(("openai/other",))).build_token_mix_history()
        self.assertEqual(0, hidden.token_mix.request_count)
        self.assertNotIn("Total Token Mix %", rendered(hidden))

    def test_percent_and_ccost_parts_align_independently(self):
        def mix(counts, costs):
            return replace(token_mix((TokenUsage(input=counts[0], cache_read=counts[1], cache_write=counts[2],
                                                 output=counts[3]),)),
                           costs=tuple(map(Decimal, costs)), priced_requests=1)
        mixes = [mix((3, 82, 1, 14), (123, 12345, 7, 1)), mix((82, 3, 14, 1), (12345, 7, 123, 99)),
                 mix((1, 1, 1, 97), (7, 1, 12345, 5)), mix((4, 9956, 0, 40), (1, 2, 0, 3))]
        cells = aligned_mix_cells(mixes)
        self.assertEqual((" 3% (  123)", "  82% (12345)", " 1% (    7)", " 14% ( 1)"), cells[0])
        self.assertEqual((" 0% (    1)", "99.6% (    2)", " 0% (    0)", "0.4% ( 3)"), cells[3])
        for column in zip(*cells):
            self.assertEqual(1, len({len(cell) for cell in column}), "no wider than required")
            self.assertEqual(1, len({cell.index("%") for cell in column}))
            self.assertEqual(1, len({cell.index("(") for cell in column}))
        projection = ReportProjection(ReportKind.TOKEN_MIX, "Token Mix % by model", "V2",
                                      model_token_mix=tuple(ModelTokenMixProjection(f"M{i}", 1, 1, m)
                                                            for i, m in enumerate(mixes)),
                                      token_mix=priced_token_mix((), lambda *_: None))
        table = [line for line in rendered(projection).splitlines() if re.match(r"\| M\d", line)]
        self.assertEqual(4, len(table))
        for index in (4, 5, 6, 7):
            column = [line.split("|")[index] for line in table]
            self.assertEqual(1, len({cell.index("%") for cell in column}))
            self.assertEqual(1, len({cell.index(")") for cell in column}))


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
            shares = [Decimal(cell.split(": ")[1][:-1]) for cell in mix_cells(mix)]
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
        self.assertEqual(("Input: 0% (<0.1)", "Cache: 98.6% (60)", "Write: 1% (15)", "Output: 0.4% (24)"),
                          mix_cells(mix))
        self.assertEqual("Token Mix % · 1 prompt · Input: 0% (<0.1)   Cache: 98.6% (60)   Write: 1% (15)   "
                         "Output: 0.4% (24)", token_mix_line("1 prompt", mix))
        self.assertIn("Output: 0.4% (24)", rendered(report(mix, sample=1)))

    def test_undefined_and_unknown_shares_stay_dashes(self):
        self.assertEqual((None,) * 4, token_mix((TokenUsage(),)).shares)
        unknown = token_mix((TokenUsage(input=5, known_fields=("input",)),))
        self.assertEqual((None,) * 4, unknown.shares)
        self.assertEqual(4, token_mix_line("x", unknown).count("--"))


if __name__ == "__main__":
    unittest.main()
