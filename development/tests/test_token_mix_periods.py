"""Web period membership uses canonical calls, cached valuations and exact values."""
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
import unittest
from unittest.mock import patch

from development.tests.fixtures.compact_reports import report_service
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from src.analysis.models import TraceEntry
from src.application.projection import project
from src.domain import ModelRef, TokenUsage
from src.reports import ReportKind, ReportRequest
from src.reports.token_mix_history import history_projection
from src.web.jobs import parse_report


def instant(text):
    return int(datetime.fromisoformat(text).timestamp() * 1000)


class TokenMixPeriodTests(unittest.TestCase):
    def test_five_windows_at_midnight_month_and_dst_have_independent_expected_members(self):
        # Stockholm spring transition: local midnight is 23:00Z, not 24h ago.
        now = instant('2026-03-29T12:34:56.789+00:00')
        stamps = ['2026-02-27T12:34:56.788+00:00', '2026-02-27T12:34:56.789+00:00',
                  '2026-02-28T23:00:00+00:00', '2026-03-22T12:34:56.788+00:00',
                  '2026-03-22T12:34:56.789+00:00', '2026-03-28T22:59:59.999+00:00',
                  '2026-03-28T23:00:00+00:00', '2026-03-29T12:34:56.789+00:00',
                  '2026-03-29T12:34:56.790+00:00']
        service = report_service(self, now_ms=now, timezone_id='Europe/Stockholm')
        service.model_availability_source.ids = None
        reference = service._load_comparison_catalog()
        entries = [TraceEntry(f's{i}', 'prompt', f'm{i}', None, instant(stamp), i,
            ModelRef('synthetic', f'model-{i}'), None, TokenUsage(input=i + 1, output=1),
            invocation_id=f'call-{i}', source_instance='synthetic')
            for i, stamp in enumerate(stamps)]
        # Child call whose parent prompt is old still belongs by its own time.
        entries[6] = replace(entries[6], parent_session_id='old-parent', root_session_id='old-parent')
        prompts = {entry: ('old-parent', 'same-prompt') for entry in entries}
        for scope, members, start in [
            ('today', (6, 7), '2026-03-28T23:00:00+00:00'),
            ('7-days', (4, 5, 6, 7), stamps[4]), ('30-days', tuple(range(1, 8)), stamps[1]),
            ('month', tuple(range(2, 8)), stamps[2]), ('all', tuple(range(8)), stamps[0]),
        ]:
            with self.subTest(scope=scope):
                report = history_projection(service, reference, [*entries, entries[6]], prompts,
                    lambda *_: None, scope=scope, valuation=lambda _model, tokens:
                    (Decimal(tokens.input), Decimal(0), Decimal(0), Decimal(tokens.output) * 3))

                self.assertEqual({f'model-{i}' for i in members}, {row.model for row in report.model_token_mix})
                self.assertEqual(len(members), report.token_mix.request_count)
                self.assertEqual(sum(i + 2 for i in members), report.token_mix.total_tokens)
                self.assertEqual(Decimal(sum(i + 1 for i in members)), report.token_mix.costs[0])
                self.assertEqual(Decimal(3 * len(members)), report.token_mix.costs[3])
                self.assertEqual(report.token_mix, report.publisher_token_mix[0].mix)
                self.assertEqual(1, report.token_mix.sample_size)
                self.assertEqual(instant(start), report.token_mix_period['start_ms'])
                self.assertEqual(now, report.token_mix_period['end_ms'])

    def test_fall_dst_month_rollover_undated_and_unpriced_are_not_fabricated(self):
        service = report_service(self, now_ms=instant('2026-11-01T00:30:00+00:00'),
                                 timezone_id='Europe/Stockholm')
        service.model_availability_source.ids = None
        entry = TraceEntry('s', 'p', 'm', None, 0, 0, ModelRef('x', 'unknown'), None,
                           TokenUsage(input=9007199254740993, known_fields=('input',)))
        reference = service._load_comparison_catalog()
        all_time = history_projection(service, reference, [entry], {entry: ('s', 'p')}, lambda *_: None,
                                      scope='all', valuation=lambda *_: None)
        month = history_projection(service, reference, [entry], {}, lambda *_: None,
                                   scope='month', valuation=lambda *_: None)

        self.assertEqual(9007199254740993, all_time.token_mix.known_total_tokens)
        self.assertIsNone(all_time.token_mix.total_tokens)
        self.assertFalse(all_time.token_mix.cost_complete)
        self.assertIsNone(all_time.token_mix_period['start_ms'])
        self.assertIsNone(all_time.token_mix_period['end_ms'])
        self.assertEqual(instant('2026-10-31T23:00:00+00:00'), month.token_mix_period['start_ms'])
        self.assertEqual(0, month.token_mix.request_count)
        self.assertTrue(any('Request time unavailable' in warning for warning in month.source_warnings))
        help_text = project(all_time).to_json()['token_mix']['display_units']
        self.assertIn('Input CCost: 0 USD', help_text['usd']['mix_input_cost_help'])
        self.assertIn('not zero', help_text['credits']['mix_input_cost_help'])

    def test_period_changes_reuse_warm_root_evidence_without_hydration_or_repricing(self):
        source = SyntheticMonthSource(40, 2, month_start_ms=instant('2026-03-01T00:00:00+00:00'))
        service = report_service(self, source, now_ms=instant('2026-03-29T12:00:00+00:00'))
        service.cache_token_mix_history = True
        service.build_token_mix_history(scope='all')
        loads = source.load_count
        with patch.object(source, 'load_session_snapshot', side_effect=AssertionError('full rescan')), \
                patch.object(type(service._load_comparison_catalog()), 'reference_category_valuation',
                             side_effect=AssertionError('reprice')):
            for scope in ('today', '7-days', '30-days', 'month', 'all'):
                report = service.build_token_mix_history(scope=scope)
                self.assertEqual(scope, report.token_mix_period['period'])
        self.assertEqual(loads, source.load_count)

    def test_fall_dst_today_includes_both_repeated_clock_hours(self):
        service = report_service(self, now_ms=instant('2026-10-25T12:00:00+00:00'),
                                 timezone_id='Europe/Stockholm')
        service.model_availability_source.ids = None
        stamps = ['2026-10-24T21:59:59.999+00:00', '2026-10-24T22:00:00+00:00',
                  '2026-10-25T00:30:00+00:00', '2026-10-25T01:30:00+00:00']
        entries = [TraceEntry('s', 'p', f'm{i}', None, instant(stamp), i,
            ModelRef('x', 'model'), None, TokenUsage(input=1, output=1))
            for i, stamp in enumerate(stamps)]
        report = history_projection(service, service._load_comparison_catalog(), entries, {},
            lambda *_: None, scope='today', valuation=lambda *_: (Decimal('0.123456789'),) * 4)

        self.assertEqual(3, report.token_mix.request_count)
        self.assertEqual(instant(stamps[1]), report.token_mix_period['start_ms'])
        help_text = project(report).to_json()['token_mix']['display_units']
        self.assertIn('0.370370367 Credits', help_text['credits']['mix_input_cost_help'])
        self.assertIn('0.00370370367 USD', help_text['usd']['mix_input_cost_help'])

    def test_http_scope_identity_and_defaults_are_page_specific(self):
        self.assertEqual('all', parse_report({'kind': 'token-mix'}).token_mix_scope)
        self.assertEqual('30-days', parse_report({'kind': 'ai-stats'}).stats_scope)
        for scope in ('today', '7-days', '30-days', 'month', 'all'):
            self.assertEqual(ReportRequest(ReportKind.TOKEN_MIX, token_mix_scope=scope),
                             parse_report({'kind': 'token-mix', 'token_mix_scope': scope}))
        for value in ({'kind': 'token-mix', 'token_mix_scope': 'yesterday'},
                      {'kind': 'normal', 'token_mix_scope': 'today'}):
            with self.assertRaises(ValueError):
                parse_report(value)


if __name__ == '__main__':
    unittest.main()
