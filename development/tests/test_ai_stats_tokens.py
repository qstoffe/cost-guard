"""Observed token traffic, independent integer/category oracles and rate evidence."""
from dataclasses import replace
from decimal import Decimal
import unittest

from development.tests.fixtures.active_hour import epoch
from src.analysis.ai_stats import DAY_MS, StatsRoot, period_stats, windows
from src.analysis.active_hour import HOUR_MS
from src.analysis.models import TraceEntry
from src.application.projection import project
from src.domain import ModelRef, TokenUsage
from src.reports.models import ReportKind, ReportProjection


def entry(sid, stamp, tokens, *, message='m', step=None):
    return TraceEntry(sid, 'prompt', message, step, stamp, 0,
                      ModelRef('synthetic', 'unpriced'), None, tokens)


def calculate(roots, now, period='all', *, complete=True, calendar='SE', zone='Europe/Stockholm'):
    row = period_stats(roots, lambda *_: None, period=period, start=dict(windows(zone, now))[period],
        now=now, zone=zone, workday_calendar=calendar, source_complete=complete)
    dto = project(ReportProjection(ReportKind.AI_STATS, 'AI Stats', 'SYNTHETIC', ai_stats=(row,))).to_json()
    return {m.metric: m for m in row.metrics}, {m['metric']: m for m in dto['ai_stats'][0]['metrics']}


class TokenTrafficTests(unittest.TestCase):
    def test_all_five_periods_count_physical_categories_and_reasoning_once_without_prices(self):
        now = epoch('2026-11-12T12:00:00+00:00')
        ages = (HOUR_MS, 2 * DAY_MS, 10 * DAY_MS, 20 * DAY_MS, 40 * DAY_MS)
        roots = tuple(StatsRoot(str(i), 'Root',
            (entry(str(i), now - age, TokenUsage(input=11, cache_read=1000, cache_write=17, output=23, reasoning=29)),),
            ((now - age - HOUR_MS, HOUR_MS, False),)) for i, age in enumerate(ages))

        for period, requests in (('today', 1), ('7-days', 2), ('30-days', 4), ('month', 3), ('all', 5)):
            with self.subTest(period=period):
                metrics, dto = calculate(roots, now, period)

                self.assertEqual(requests * 1080, metrics['total-tokens'].value)
                self.assertEqual('complete', metrics['total-tokens'].status)
                self.assertEqual(str(requests * 1080), dto['total-tokens']['exact_value'])
                self.assertNotIn('display_units', dto['total-tokens'])
                self.assertNotIn('display_units', dto['token-rate'])

    def test_step_precedence_child_usage_and_clone_dedup_use_the_same_integer_numerator(self):
        now = epoch('2026-11-12T12:00:00+00:00')
        at = now - HOUR_MS
        fallback = entry('root', at, TokenUsage(input=999))
        step = replace(fallback, step_part_id='step', tokens=TokenUsage(input=2, cache_read=3, output=5, reasoning=7))
        clone = replace(step, session_id='clone')
        child = entry('child', at + 1, TokenUsage(cache_read=3, cache_write=11), message='child-message')
        roots = (StatsRoot('root', 'Root', (fallback, step, step, child), ((at, HOUR_MS, False),)),
                 StatsRoot('clone', 'Clone', (clone,), ((at, HOUR_MS, False),)))

        metrics, _ = calculate(roots, now)

        self.assertEqual(31, metrics['total-tokens'].value)
        self.assertEqual(31, metrics['token-rate'].rates.total)
        self.assertEqual(31, metrics['token-rate'].rates.active_rate)

    def test_missing_categories_pending_gaps_and_unknown_completion_are_not_evidenced_zero(self):
        now = epoch('2026-11-12T12:00:00+00:00')
        at = now - HOUR_MS
        root = StatsRoot('root', 'Root', (entry('root', at, TokenUsage(input=4)),), ((at, HOUR_MS, False),))
        missing = replace(root, entries=(entry('root', at,
            TokenUsage(input=4, output=999, reasoning=999, known_fields=('input',))),))
        cases = ((missing, True, 4, 'missing-token-usage'), (replace(root, cost_pending=True), True, 4, 'pending-usage'),
            (root, False, 4, 'source-incomplete'),
            (replace(root, entries=(replace(root.entries[0], completed_at_ms=0),)), True, 0, 'unknown-request-time'))

        for evidence, complete, expected, reason in cases:
            metrics, dto = calculate((evidence,), now, complete=complete)

            self.assertEqual(expected, metrics['total-tokens'].value)
            self.assertIn(reason, metrics['total-tokens'].reasons)
            self.assertEqual('Partial 4' if expected else 'Unavailable', dto['total-tokens']['display']['value'])
            self.assertIsNone(metrics['token-rate'].rates.calendar_rate)
            self.assertIsNone(metrics['token-rate'].rates.active_rate)
            self.assertEqual('Unavailable', dto['token-rate']['display']['calendar_rate'])

    def test_unknown_guessed_running_or_zero_active_time_never_produces_a_measured_token_rate(self):
        now = epoch('2026-11-12T12:00:00+00:00')
        at = now - HOUR_MS
        root = StatsRoot('root', 'Root', (entry('root', at, TokenUsage(input=24)),), ())

        for intervals in ((), ((at, None, False),), ((at, HOUR_MS, True),), ((at, 0, False),)):
            metrics, dto = calculate((replace(root, intervals=intervals),), now, 'today')

            self.assertEqual(24, metrics['total-tokens'].value)
            self.assertEqual(1, metrics['token-rate'].rates.calendar_rate)
            self.assertIsNone(metrics['token-rate'].rates.active_rate)
            self.assertEqual('Unavailable', dto['token-rate']['display']['active_rate'])

    def test_identical_calendar_denominators_dst_holidays_midnight_and_empty_periods(self):
        for stamp in ('2026-03-29T20:00:00+00:00', '2026-10-25T20:00:00+00:00',
                      '2026-12-27T20:00:00+00:00', '2027-01-01T00:30:00+00:00'):
            now = epoch(stamp)
            root = StatsRoot('root', 'Root', (entry('root', now - HOUR_MS, TokenUsage(input=840)),),
                             ((now - HOUR_MS, HOUR_MS, False),))
            for calendar in ('SE', ''):
                for period in ('today', '7-days', '30-days', 'month', 'all'):
                    metrics, _ = calculate((root,), now, period, calendar=calendar)
                    cost, tokens = metrics['hourly-rate'].rates, metrics['token-rate'].rates

                    for field in ('calendar_days', 'workdays', 'calendar_hours', 'workday_hours', 'active_hours'):
                        self.assertEqual(getattr(cost, field), getattr(tokens, field))
                    self.assertEqual(Decimal(840) / tokens.calendar_hours, tokens.calendar_rate)
                    self.assertEqual(Decimal(840) / tokens.workday_hours if tokens.workdays else None, tokens.workday_rate)
                    self.assertEqual(840, tokens.active_rate)

        metrics, dto = calculate((), epoch('2026-11-07T12:00:00+00:00'), 'today')
        self.assertEqual((0, 'complete'), (metrics['total-tokens'].value, metrics['total-tokens'].status))
        self.assertEqual('0 tokens/h', dto['token-rate']['display']['active_rate'])
        self.assertEqual('No workdays', dto['token-rate']['display']['workday_rate'])

    def test_large_integer_survives_projection_and_precise_help_without_money_cap(self):
        now = epoch('2026-11-12T12:00:00+00:00')
        amount = 2**60 + 123
        root = StatsRoot('root', 'Root', (entry('root', now - HOUR_MS, TokenUsage(cache_read=amount)),),
                         ((now - HOUR_MS, HOUR_MS, False),))

        metrics, dto = calculate((root,), now)

        self.assertEqual(amount, metrics['total-tokens'].value)
        self.assertEqual(str(amount), dto['total-tokens']['exact_value'])
        self.assertIn(str(amount), dto['total-tokens']['display']['token_help'])
        self.assertEqual(amount, metrics['token-rate'].rates.active_rate)


if __name__ == '__main__':
    unittest.main()
