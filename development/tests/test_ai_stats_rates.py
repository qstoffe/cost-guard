"""Independent calendar denominators, active intensity and both-unit projection oracles."""
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
from src.application.ai_stats import rate_tokens
from src.domain import ModelRef, TokenUsage
from src.reports import ReportKind, ReportRequest
from src.reports.models import ReportProjection


def evidence(at, hours, credits):
    entry = TraceEntry('root', 'prompt', 'request', None, at, 0,
        ModelRef('synthetic', 'model'), None, TokenUsage(input=credits))
    return StatsRoot('root', 'Synthetic', (entry,), ((at, hours * HOUR_MS, False),))


def calculate(roots, now, period='7-days', calendar='SE', zone='Europe/Stockholm', valuation=None):
    stats = period_stats(roots, valuation or (lambda _model, tokens: Decimal(tokens.input)),
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
        self.assertEqual(('5 CCost/h', '21 CCost/h', '30 CCost/h'),
            tuple(dto['display'][key] for key in ('calendar_rate', 'workday_rate', 'active_rate')))
        self.assertEqual(('$0.05/h', '$0.21/h', '$0.30/h'),
            tuple(dto['display_units']['usd'][key] for key in ('calendar_rate', 'workday_rate', 'active_rate')))
        self.assertIn("hourly appetite when it's actually working", dto['display']['rate_help'])
        self.assertNotIn('rate_help', dto['display_units']['usd'])
        self.assertEqual('30', dto['rates']['active_rate'])
        faster, faster_dto = calculate((replace(root, intervals=((root.intervals[0][0], 7 * HOUR_MS, False),)),), now)
        self.assertEqual((Decimal('5'), Decimal('21'), Decimal('120')),
            (faster.metrics[0].rates.calendar_rate, faster.metrics[0].rates.workday_rate, faster.metrics[0].rates.active_rate))
        self.assertEqual('120 CCost/h', faster_dto['display']['active_rate'])

    def test_christmas_and_weekend_only_calendar_change_workdays_not_active_intensity(self):
        now = epoch('2026-12-27T20:00:00+00:00')
        root = evidence(epoch('2026-12-21T06:00:00+00:00'), 32, 960)

        holiday, holiday_dto = calculate((root,), now)
        weekdays, weekdays_dto = calculate((root,), now, calendar='')

        se, plain = holiday.metrics[0].rates, weekdays.metrics[0].rates
        self.assertEqual((4, Decimal('30'), Decimal('240'), Decimal('960')),
                         (se.workdays, se.workday_rate, se.robot_day, se.robot_period))
        self.assertEqual((5, Decimal('24'), Decimal('240'), Decimal('1200')),
                         (plain.workdays, plain.workday_rate, plain.robot_day, plain.robot_period))
        self.assertEqual(Decimal('960') / 168, se.calendar_rate)
        self.assertEqual(se.calendar_rate, plain.calendar_rate)
        self.assertEqual(('30 CCost/h', '24 CCost/h'),
            (holiday_dto['display']['workday_rate'], weekdays_dto['display']['workday_rate']))
        for key in ('calendar_rate', 'active_rate'):
            self.assertEqual(holiday_dto['display'][key], weekdays_dto['display'][key])

    def test_today_is_nominal_even_in_morning_and_weekend_keeps_active_rate(self):
        for day, expected_workdays in (('2026-11-09', 1), ('2026-11-07', 0), ('2026-12-25', 0)):
            with self.subTest(day=day):
                root = evidence(epoch(day + 'T03:00:00+00:00'), 4, 240)
                stats, dto = calculate((root,), epoch(day + 'T08:00:00+00:00'), 'today')

                rates = stats.metrics[0].rates
                self.assertEqual((1, expected_workdays, Decimal('10'), Decimal('480')),
                    (rates.calendar_days, rates.workdays, rates.calendar_rate, rates.robot_day))
                self.assertEqual(Decimal('30') if expected_workdays else None, rates.workday_rate)
                self.assertEqual('30 CCost/h' if expected_workdays else 'No workdays', dto['display']['workday_rate'])
                self.assertEqual('60 CCost/h', dto['display']['active_rate'])
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

    def test_tiny_positive_active_time_keeps_raw_intensity_with_compact_formula(self):
        now = epoch('2026-11-09T12:00:00+00:00')
        root = evidence(now - HOUR_MS, 1, 1)
        root = replace(root, intervals=((now - HOUR_MS, 1, False),))

        stats, dto = calculate((root,), now, 'today')

        self.assertEqual(3_600_000, stats.metrics[0].rates.active_rate)
        self.assertEqual('3600000 CCost/h', dto['display']['active_rate'])
        self.assertIn('deluxe hourly buffet', dto['display']['rate_help'])
        self.assertTrue(dto['display']['rate_help'].endswith('(Total CCost ÷ active AI hours)'))

    def test_copy_tiers_use_unrounded_active_credits_and_leave_trait_unchanged(self):
        now = epoch('2026-11-09T12:00:00+00:00')
        for rate, punchline in (('0', "hasn't started"), ('0.0001', 'nibbles'),
                ('9.9999', 'nibbles'), ('10', 'hourly appetite'), ('99.9999', 'hourly appetite'),
                ('100', 'buffet'), ('100.0001', 'buffet')):
            with self.subTest(rate=rate):
                root = evidence(now - HOUR_MS, 1, 1)

                stats, dto = calculate((root,), now, 'today', valuation=lambda *_: Decimal(rate))

                self.assertEqual(Decimal(rate), stats.metrics[0].rates.active_rate)
                self.assertEqual(Decimal(rate), stats.metrics[0].value)
                self.assertIn(punchline, dto['display']['rate_help'])
                self.assertNotIn('rate_help', dto['display_units']['usd'])
                self.assertEqual('Budget build. Dangerous potential.' if Decimal(rate) < Decimal('.3') else
                    'Premium silicon has expensive tastes.' if Decimal(rate) >= 3 else
                    'Standard-issue silicon. Surprisingly functional.', dto['display']['trait'])

    def test_all_periods_both_units_have_three_short_plain_text_paragraphs(self):
        now = epoch('2026-11-09T12:00:00+00:00')
        root = evidence(now - HOUR_MS, 1, 4)
        for period in ('today', '7-days', '30-days', 'month', 'all'):
            _stats, dto = calculate((root,), now, period)
            for unit in ('credits', 'usd'):
                display = {**dto['display'], **dto['display_units'][unit]}
                paragraphs = display['rate_help'].split('\n\n')
                self.assertEqual(3, len(paragraphs))
                formulas = ('(Total CCost ÷ (calendar days × 24))', '(Total CCost ÷ (workdays × 8))',
                            '(Total CCost ÷ active AI hours)')
                for paragraph, label, formula in zip(paragraphs,
                        ('Calendar average:', 'Workday average:', 'Active AI average:'), formulas):
                    self.assertTrue(paragraph.startswith(label))
                    self.assertEqual(paragraph.strip(), paragraph)
                    self.assertNotIn('\n', paragraph)
                    sentence, _formula = paragraph.rsplit(' (', 1)
                    self.assertEqual(1, sentence.count('.'))
                    self.assertTrue(paragraph.endswith(formula))
                    self.assertLessEqual(len(paragraph.split()), 25)
                self.assertNotRegex(display['rate_help'], r'shift|salary|replacement|weekend|holiday|DST|Partial|Unavailable|Estimated')

    def test_missing_or_weak_basis_uses_neutral_active_copy_without_status_prose(self):
        raw = dict(calendar_rate=1, workday_rate=3, workdays=1, active_rate=1, total=24, active_hours=24)
        for reasons in (('unknown-duration',), ('missing-price',), ('source-incomplete',), ('running-executions',)):
            self.assertIn('hourly appetite', rate_tokens(raw, reasons)['rate_help'])
        for missing in ('active_hours', 'total', 'active_rate'):
            self.assertIn("hasn't started", rate_tokens({**raw, missing: None})['rate_help'])
        no_workdays = rate_tokens({**raw, 'workdays': 0, 'workday_rate': None})
        self.assertEqual('No workdays', no_workdays['workday_rate'])
        self.assertIn('office calendar is taking a nap', no_workdays['rate_help'])
        self.assertIn('nibbles', no_workdays['rate_help'])

    def test_two_hours_and_one_minute_use_elapsed_union_not_agent_duration_sum(self):
        now = epoch('2026-11-09T12:00:00+00:00')
        for duration, expected in ((2 * HOUR_MS, '50 CCost/h'), (60_000, '6000 CCost/h')):
            with self.subTest(duration=duration):
                at = now - duration
                first = evidence(at, 1, 40)
                first = replace(first, intervals=((at, duration, False),))
                second = evidence(at, 1, 60)
                second = replace(second, session_id='parallel',
                    entries=(replace(second.entries[0], session_id='parallel'),),
                    intervals=((at, duration, False),))

                stats, dto = calculate((first, second), now, 'today')

                self.assertEqual(duration, stats.metrics[2].value)
                self.assertEqual(100, stats.metrics[1].value)
                self.assertEqual(expected, dto['display']['active_rate'])

    def test_display_uses_raw_active_rate_not_rounded_shift_or_capped_metric(self):
        raw = dict(calendar_rate=1, workday_rate=3, workdays=1,
            active_rate=Decimal('50.000000001'), robot_day=Decimal('400'), total=100, active_hours=2)

        display = rate_tokens(raw)

        self.assertEqual('51 CCost/h', display['active_rate'])


if __name__ == '__main__':
    unittest.main()
