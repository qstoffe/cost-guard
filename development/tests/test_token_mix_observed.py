"""Web best-effort shares are source-qualified, not canonical accounting edits."""
from dataclasses import replace
from decimal import Decimal
import unittest

from development.tests.fixtures.compact_reports import report_service
from src.analysis.models import TraceEntry
from src.application.projection import project
from src.domain import ModelRef, TokenUsage
from src.pricing.catalog import PricingCatalog
from src.reports.token_mix_history import history_projection


class ObservedMixTests(unittest.TestCase):
    def report(self, usages, *, models=None, reference=None):
        service = report_service(self)
        service.model_availability_source.ids = None
        entries = [TraceEntry('s', 'p', f'm{i}', None, 1000 + i, i,
            models[i] if models else ModelRef('route', 'gpt-test'), None, usage,
            invocation_id=f'i{i}', source_instance='test') for i, usage in enumerate(usages)]
        return history_projection(service, reference or service._load_comparison_catalog(), entries,
            {entry: ('s', 'p') for entry in entries}, lambda *_: None,
            valuation=lambda model, _tokens: None if model.model == 'unpriced' else
            (Decimal('0.49'), Decimal('0.50'), Decimal('0.51'), Decimal('0.001')), scope='all')

    def test_known_category_subtotals_ignore_unreported_numeric_defaults_and_keep_canonical_unknowns(self):
        report = self.report([
            TokenUsage(input=1, cache_read=1, output=2),
            TokenUsage(input=1, cache_read=9999, cache_write=9999, output=1,
                       reasoning=1, known_fields=('input', 'output')),
        ])

        dto = project(report).to_json()

        self.assertEqual((2, 1, 0, 4), report.token_mix_observed_totals)
        self.assertEqual((2, None, None, 4), report.token_mix.totals)
        self.assertIsNone(report.token_mix.total_tokens)
        self.assertEqual((None,) * 4, report.token_mix.shares)
        self.assertFalse(report.token_mix.cost_complete)
        self.assertEqual(2, report.token_mix.request_count)
        for mix in (dto['token_mix'], dto['model_token_mix'][0]['mix'], dto['publisher_token_mix'][0]['mix']):
            self.assertEqual(['2', '1', '0', '4'], mix['observed_totals'])
            display = mix['display']
            self.assertEqual(['28.6%', '14.3%', '0%', '57.1%'],
                [display[f'mix_{name}_share'] for name in ('input', 'cache', 'write', 'output')])
            self.assertEqual('7', display['mix_total_tokens'])

    def test_empty_unknown_and_explicit_zero_evidence_display_four_zeroes(self):
        for usages in ([], [TokenUsage(input=123, output=456, known_fields=())], [TokenUsage()]):
            with self.subTest(usages=usages):
                report = self.report(usages)
                dto = project(report).to_json()['token_mix']
                self.assertEqual(['0'] * 4, dto['observed_totals'])
                self.assertEqual(['0%'] * 4,
                    [dto['display'][f'mix_{name}_share'] for name in ('input', 'cache', 'write', 'output')])

    def test_known_costs_survive_unpriced_calls_and_help_rounds_once_half_up(self):
        report = self.report([TokenUsage(input=1), TokenUsage(output=1)],
                            models=[ModelRef('x', 'gpt-test'), ModelRef('x', 'unpriced')])

        dto = project(report).to_json()['token_mix']

        self.assertFalse(report.token_mix.cost_complete)
        self.assertEqual(1, report.token_mix.priced_requests)
        self.assertEqual('1.501', dto['total_cost'])
        for unit, expected in [('credits', ['0 Credits', '1 Credits', '1 Credits', '0 Credits']),
                               ('usd', ['$0.00', '$0.01', '$0.01', '$0.00'])]:
            for name, label, amount in zip(('input', 'cache', 'write', 'output'),
                                           ('Input', 'Cached input', 'Cache write', 'Output'), expected):
                self.assertEqual(f'{label} CCost: {amount}', dto['display_units'][unit][f'mix_{name}_cost_help'])
        self.assertEqual('2', dto['display']['mix_total_cost'])
        self.assertEqual('$0.02', dto['display_units']['usd']['mix_total_cost'])
        zero = project(self.report([TokenUsage()], models=[ModelRef('x', 'unpriced')])).to_json()['token_mix']
        self.assertEqual('Input CCost: 0 Credits', zero['display']['mix_input_cost_help'])

    def test_huge_counts_balance_exactly_without_float_and_keep_zero_categories_zero(self):
        report = self.report([TokenUsage(input=10**100 + 1, cache_read=10**100,
                                        output=10**100, known_fields=('input', 'cache_read', 'output'))])
        dto = project(report).to_json()['token_mix']
        self.assertEqual(str(10**100 + 1), dto['observed_totals'][0])
        self.assertEqual(['33.4%', '33.3%', '0%', '33.3%'],
            [dto['display'][f'mix_{name}_share'] for name in ('input', 'cache', 'write', 'output')])

    def test_unique_catalog_labels_and_publisher_metadata_without_merging_equal_labels(self):
        service = report_service(self)
        template = service._load_comparison_catalog().models[0]
        catalog = PricingCatalog(tuple(replace(template,
            model=ModelRef('github-copilot', model, 'Exact Catalog Name'), metadata={'publisher': 'open ai'})
            for model in ('one', 'two')))
        report = self.report([TokenUsage(input=1), TokenUsage(output=1)],
            models=[ModelRef('account-route', 'one', 'Recorded One'), ModelRef('account-route', 'two', 'Recorded Two')],
            reference=catalog)
        self.assertEqual(['Exact Catalog Name'] * 2, [row.model for row in report.model_token_mix])
        self.assertEqual(['OpenAI'] * 2, [row.publisher for row in report.model_token_mix])
        self.assertEqual(2, len({row.identity for row in report.model_token_mix}))
        self.assertEqual(2, report.publisher_token_mix[0].calls)
        self.assertEqual(1, report.publisher_token_mix[0].prompts)

    def test_ambiguous_or_absent_catalog_match_preserves_actual_recorded_label(self):
        service = report_service(self)
        template = service._load_comparison_catalog().models[0]
        catalog = PricingCatalog(tuple(replace(template, model=ModelRef('github-copilot', 'ambiguous', name),
                                               metadata={'publisher': 'openai'}) for name in ('A', 'B')))
        report = self.report([TokenUsage(input=1), TokenUsage(output=1)],
            models=[ModelRef('route', 'ambiguous', 'Recorded Alias'), ModelRef('route', 'absent', 'Original Generation')],
            reference=catalog)
        self.assertEqual({'Recorded Alias', 'Original Generation'}, {row.model for row in report.model_token_mix})
        self.assertEqual({'—'}, {row.publisher for row in report.model_token_mix})


if __name__ == '__main__':
    unittest.main()
