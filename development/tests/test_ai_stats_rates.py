"""Independent calendar denominators, robot intensity and both-unit projection oracles."""
from dataclasses import replace
from decimal import Decimal
import unittest

from development.tests.fixtures.active_hour import epoch
from development.tests.fixtures.compact_reports import report_service
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from src.analysis.ai_stats import DAY_MS, StatsRoot, period_stats, windows
from src.analysis.active_hour import HOUR_MS
from src.analysis.models import TraceEntry
from src.application.projection import project
from src.domain import ModelRef, TokenUsage
from src.reports import ReportKind, ReportRequest
from src.reports.models import ReportProjection


def evidence(at, hours, credits):
    entry = TraceEntry('root', 'prompt', 'request', None, at, 0,
        ModelRef('synthetic', 'model'), None, TokenUsage(input=credits))
    return StatsRoot('root', 'Synthetic', (entry,), ((at, hours * HOUR_MS, False),))


def calculate(roots, now, period='7-days', calendar='SE', zone='Europe/Stockholm'):
    stats = period_stats(roots, lambda _model, tokens: Decimal(tokens.input),
        period=period, start=dict(windows(zone, now))[period], now=now, zone=zone, workday_calendar=calendar)
    dto = project(ReportProjection(ReportKind.AI_STATS, 'AI Stats', 'SYNTHETIC', ai_stats=(stats,))).to_json()
    return stats, dto['ai_stats'][0]['metrics'][0]


class AIStatsRateTests(unittest.TestCase):
    def test_three_way_example_preserves_active_rate_and_prepares_both_units(self):
        now = epoch('2026-11-08T20:00:00+00:00')
        root = evidence(epoch('2026-11-02T06:00:00+00:00'), 28, 840)

        stats, dto = calculate((root,), now)

        rate = stats.metrics[0]
        self.assertEqual((Decimal('30'), Decimal('840'), 28 * HOUR_MS),
                         tuple(m.value for m in stats.metrics[:3]))
        self.assertEqual((7, 5, 168, 40, 28), (rate.rates.calendar_days, rate.rates.workdays,
            rate.rates.calendar_hours, rate.rates.workday_hours, rate.rates.active_hours))
        self.assertEqual((Decimal('5'), Decimal('21'), Decimal('240'), Decimal('1200')),
            (rate.rates.calendar_rate, rate.rates.workday_rate, rate.rates.robot_day, rate.rates.robot_period))
        self.assertEqual(('5 CCost/h', '21 CCost/h', '240 CCost/8h day'),
            tuple(dto['display'][key] for key in ('calendar_rate', 'workday_rate', 'robot_day')))
        self.assertEqual(('$0.05/h', '$0.21/h', '$2.40/8h day'),
            tuple(dto['display_units']['usd'][key] for key in ('calendar_rate', 'workday_rate', 'robot_day')))
        self.assertIn('30 CCost/h', dto['display']['rate_help'])
        self.assertIn('1200 CCost', dto['display']['rate_help'])
        self.assertIn('$12.00', dto['display_units']['usd']['rate_help'])
        self.assertEqual('30', dto['rates']['active_rate'])
        faster, _dto = calculate((replace(root, intervals=((root.intervals[0][0], 7 * HOUR_MS, False),)),), now)
        self.assertEqual((Decimal('5'), Decimal('21'), Decimal('960')),
            (faster.metrics[0].rates.calendar_rate, faster.metrics[0].rates.workday_rate, faster.metrics[0].rates.robot_day))

    def test_christmas_and_weekend_only_calendar_change_workdays_not_robot_intensity(self):
        now = epoch('2026-12-27T20:00:00+00:00')
        root = evidence(epoch('2026-12-21T06:00:00+00:00'), 32, 960)

        holiday, _dto = calculate((root,), now)
        weekdays, _dto = calculate((root,), now, calendar='')

        se, plain = holiday.metrics[0].rates, weekdays.metrics[0].rates
        self.assertEqual((4, Decimal('30'), Decimal('240'), Decimal('960')),
                         (se.workdays, se.workday_rate, se.robot_day, se.robot_period))
        self.assertEqual((5, Decimal('24'), Decimal('240'), Decimal('1200')),
                         (plain.workdays, plain.workday_rate, plain.robot_day, plain.robot_period))
        self.assertEqual(Decimal('960') / 168, se.calendar_rate)
        self.assertEqual(se.calendar_rate, plain.calendar_rate)

    def test_today_is_nominal_even_in_morning_and_weekend_keeps_one_robot_shift(self):
        for day, expected_workdays in (('2026-11-09', 1), ('2026-11-07', 0), ('2026-12-25', 0)):
            with self.subTest(day=day):
                root = evidence(epoch(day + 'T03:00:00+00:00'), 4, 240)
                stats, dto = calculate((root,), epoch(day + 'T08:00:00+00:00'), 'today')

                rates = stats.metrics[0].rates
                self.assertEqual((1, expected_workdays, Decimal('10'), Decimal('480')),
                    (rates.calendar_days, rates.workdays, rates.calendar_rate, rates.robot_day))
                self.assertEqual(Decimal('30') if expected_workdays else None, rates.workday_rate)
                self.assertEqual('30 CCost/h' if expected_workdays else 'No workdays', dto['display']['workday_rate'])
                self.assertEqual(Decimal('480') if expected_workdays else 0, rates.robot_period)

    def test_dst_rolling_slots_month_to_date_and_year_rollover_preserve_cost_windows(self):
        for stamp in ('2026-03-29T20:00:00+00:00', '2026-10-25T20:00:00+00:00',
                      '2027-01-01T00:30:00+00:00'):
            now = epoch(stamp)
            root = evidence(now - 7 * DAY_MS, 1, 840)
            for period, days in (('today', 1), ('7-days', 7), ('30-days', 30),
                                 ('month', int(stamp[8:10]))):
                stats, _dto = calculate((root,), now, period)
                self.assertEqual(days * 24, stats.metrics[0].rates.calendar_hours)
                self.assertEqual(dict(windows('Europe/Stockholm', now))[period], stats.start_ms)
            week, _dto = calculate((root,), now)
            excluded, _dto = calculate((replace(root, entries=(replace(root.entries[0], completed_at_ms=now - 7 * DAY_MS - 1),)),), now)
            self.assertEqual(Decimal('840'), week.metrics[1].value)
            self.assertEqual(0, excluded.metrics[1].value)

    def test_all_time_includes_cost_free_gaps_and_local_request_or_activity_beginning(self):
        now = epoch('2026-11-09T12:00:00+00:00')
        root = evidence(epoch('2026-10-31T23:30:00+00:00'), 1, 240)
        stats, _dto = calculate((root,), now, 'all')
        self.assertEqual((9, 6), (stats.metrics[0].rates.calendar_days, stats.metrics[0].rates.workdays))
        earlier_request = replace(root.entries[0], completed_at_ms=epoch('2026-10-30T23:30:00+00:00'))
        requests, _dto = calculate((replace(root, entries=(earlier_request,), intervals=()),), now, 'all')
        self.assertEqual(10, requests.metrics[0].rates.calendar_days)
        empty, dto = calculate((), now, 'all')
        self.assertEqual((0, 0, 0, None), (empty.metrics[0].rates.calendar_days, empty.metrics[0].rates.workdays,
            empty.metrics[0].rates.calendar_rate, empty.metrics[0].rates.workday_rate))
        self.assertEqual('No workdays', dto['display']['workday_rate'])

    def test_report_threads_configured_calendar_through_warm_cached_evidence(self):
        now = epoch('2026-12-27T20:00:00+00:00')
        source = SyntheticMonthSource(1, 1, month_start_ms=now - DAY_MS)
        service = report_service(self, source, now_ms=now)
        service.config.update(timezone='Europe/Stockholm', workdayCalendar='SE')
        se = service.build(ReportRequest(ReportKind.AI_STATS)).ai_stats[1].metrics[0].rates
        service.config['workdayCalendar'] = ''
        plain = service.build(ReportRequest(ReportKind.AI_STATS)).ai_stats[1].metrics[0].rates
        self.assertEqual((4, 5), (se.workdays, plain.workdays))
        self.assertEqual(se.robot_day, plain.robot_day)

    def test_tiny_positive_active_time_is_not_rounded_to_a_zero_help_denominator(self):
        now = epoch('2026-11-09T12:00:00+00:00')
        root = evidence(now - HOUR_MS, 1, 1)
        root = replace(root, intervals=((now - HOUR_MS, 1, False),))

        stats, dto = calculate((root,), now, 'today')

        self.assertEqual(3_600_000, stats.metrics[0].rates.active_rate)
        self.assertIn('0.0000002777777777777777777777777778 active hours', dto['display']['rate_help'])
        self.assertNotIn('÷ 0 active hours', dto['display']['rate_help'])


if __name__ == '__main__':
    unittest.main()
