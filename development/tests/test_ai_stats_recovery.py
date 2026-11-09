"""Independent fun-first fallback rules and unchanged canonical timing regressions."""
from dataclasses import asdict, replace
from decimal import Decimal
import unittest

from development.tests.fixtures.active_hour import epoch
from development.tests.fixtures.session_snapshots import make_native_v2_compaction_snapshot
from development.tests.fixtures.compact_reports import report_service
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from src.analysis.ai_stats import DAY_MS, StatsRoot, period_stats, windows
from src.analysis.compaction import completed_compactions
from src.analysis.models import TraceEntry
from src.application.ai_stats import stat_tokens
from src.application.projection import project
from src.domain import ModelRef, TokenUsage
from src.reports import ReportKind, ReportRequest
from src.reports.models import ReportProjection

NOW = epoch('2026-11-07T12:00:00+00:00')
HOUR = 3_600_000


def root(sid, at, cost=4):
    entry = TraceEntry(sid, 'prompt', 'message-' + sid, None, at, 0,
                       ModelRef('provider', 'model'), None, TokenUsage(input=cost))
    return StatsRoot(sid, 'Synthetic ' + sid, (entry,), ((at, HOUR, False),))


def calculate(roots, *, start=None, complete=True, valuation=None):
    result = period_stats(roots, valuation or (lambda _m, t: Decimal(t.input)),
        period='all', start=start, now=NOW, zone='Europe/Stockholm', source_complete=complete)
    return {m.metric: m for m in result.metrics}


class ObservedStatsTests(unittest.TestCase):
    def test_one_incomplete_snapshot_among_thousands_preserves_observed_work(self):
        source = SyntheticMonthSource(2700, 1, month_start_ms=NOW - DAY_MS)
        source.snapshots = {sid: replace(s, complete=index != 0)
                            for index, (sid, s) in enumerate(source.snapshots.items())}
        service = report_service(self, source, now_ms=NOW)
        service.selection = replace(service.selection, warnings=())

        report = service.build(ReportRequest(ReportKind.AI_STATS, stats_scope='all'))

        values = {m.metric: m for m in report.ai_stats[-1].metrics}
        self.assertGreater(values['working-time'].value, 0)
        self.assertEqual(('partial', ('source-incomplete',)),
                         (values['working-time'].status, values['working-time'].reasons))
        self.assertEqual(2700, source.load_count)
        self.assertGreater(values['hourly-rate'].value, 0)
        self.assertIsNone(report.ai_stats[-1].matched)

    def test_one_unknown_supplements_the_timeline_and_keeps_ratios_streak_and_peak(self):
        good = root('good', NOW - 2 * HOUR)
        bad = replace(root('bad', NOW - DAY_MS), intervals=((NOW - DAY_MS, None, False),))

        values = calculate((good, bad))

        self.assertEqual(HOUR + 60_000, values['working-time'].value)
        for key in ('longest-session', 'busiest-day'):
            self.assertEqual((HOUR, 'partial', ('unknown-duration',)),
                             (values[key].value, values[key].status, values[key].reasons))
        self.assertEqual('good', values['longest-session'].session_id)
        self.assertEqual(8, values['total-cost'].value)
        self.assertEqual(4, values['average-cost'].value)
        self.assertEqual(Decimal(8) * HOUR / (HOUR + 60_000), values['hourly-rate'].value)
        self.assertEqual(0, values['night-owl'].value)
        self.assertEqual(2, values['streak'].value)
        self.assertEqual(1, values['parallel'].value)

    def test_missing_price_or_tokens_supplements_cost_without_erasing_measured_time(self):
        good, bad = root('good', NOW - HOUR, 8), root('bad', NOW - 2 * HOUR, 99)
        for damaged, valuation, reason in (
            (bad, lambda _m, t: None if t.input == 99 else Decimal(t.input), 'unpriced-requests'),
            (replace(bad, entries=(replace(bad.entries[0], tokens=TokenUsage(input=2, known_fields=('input',))),)),
             None, 'missing-token-usage'),
            (replace(bad, cost_pending=True), None, 'pending-usage')):

            values = calculate((good, damaged), valuation=valuation)

            self.assertEqual((2 * HOUR, 'complete'), (values['working-time'].value, values['working-time'].status))
            self.assertGreater(values['average-cost'].value, 4)
            self.assertEqual(values['average-cost'].value, values['hourly-rate'].value)
            winner = values['expensive-session']
            self.assertGreater(winner.value, 0)
            self.assertEqual('partial', winner.status)
            self.assertIn(reason, winner.reasons)
            self.assertEqual({'value', 'trait'}, set(stat_tokens(asdict(winner))))

    def test_incomplete_root_and_membership_gaps_keep_only_qualified_observations(self):
        good = root('good', NOW - HOUR)
        for roots, complete in (((replace(good, source_complete=False),), True), ((good,), False)):
            values = calculate(roots, complete=complete)

            self.assertEqual((HOUR, 'partial', ('source-incomplete',)),
                             (values['working-time'].value, values['working-time'].status, values['working-time'].reasons))
            self.assertEqual(1, values['parallel'].value)
            self.assertEqual(4, values['average-cost'].value)

    def test_known_old_end_excludes_only_safe_roots_and_does_not_hide_global_gaps(self):
        old = root('old', NOW - 60 * DAY_MS)
        recent = root('recent', NOW - HOUR)
        variants = (old, replace(old, intervals=((NOW - 60 * DAY_MS, None, False),)),
                    replace(old, source_complete=False), replace(old, cost_pending=True))
        for index, candidate in enumerate(variants):
            short = calculate((candidate, recent), start=NOW - 30 * DAY_MS)
            all_time = calculate((candidate, recent))

            self.assertEqual('complete' if index == 0 or index == 3 else 'partial', short['working-time'].status)
            self.assertEqual(HOUR, short['working-time'].value)
            self.assertEqual(8, all_time['total-cost'].value)
            if index:
                self.assertTrue(short['working-time'].reasons or short['total-cost'].reasons)
        gap = calculate((old, recent), start=NOW - 30 * DAY_MS, complete=False)
        self.assertEqual('partial', gap['working-time'].status)

    def test_broken_only_activity_is_one_minute_and_measured_work_keeps_normal_rounding(self):
        missing = replace(root('bad', NOW - HOUR), intervals=((NOW - HOUR, None, False),))
        values = calculate((missing,))
        self.assertEqual(60_000, values['working-time'].value)
        for duration, expected in ((999, '1s'), (1599, '2s'), (59999, '1m')):
            good = replace(root('good', NOW - HOUR), intervals=((NOW - HOUR, duration, False),))
            observed = calculate((good,), complete=False)['working-time']
            self.assertEqual(expected, stat_tokens(asdict(observed))['value'])

    def test_compaction_uses_explicit_part_end_but_never_creation_or_summary_as_end(self):
        snapshot = make_native_v2_compaction_snapshot()
        native = next(m for m in snapshot.messages if any(p.kind == 'compaction' for p in m.parts))
        compact = next(p for p in native.parts if p.kind == 'compaction')
        for end, expected in ((native.created_at_ms + 300, 300), (None, None), (True, None),
                              (native.created_at_ms - 1, None)):
            changed_part = replace(compact, data={**compact.data, 'time': {'end': end}})
            changed_message = replace(native, completed_at_ms=None,
                parts=tuple(changed_part if p is compact else p for p in native.parts))
            changed = replace(snapshot, messages=tuple(changed_message if m is native else m for m in snapshot.messages))

            records = completed_compactions(changed)

            self.assertEqual(expected, records[0].duration_ms)

    def test_mixed_damage_has_ten_finite_playful_values_in_every_period_and_unit(self):
        good = root('good', NOW - HOUR, 8)
        request_only = replace(root('requests', NOW - 2 * HOUR), intervals=())
        missing_start = replace(root('start', NOW - HOUR), intervals=((0, None, False),))
        invalid = replace(root('negative', NOW - HOUR), intervals=((NOW - HOUR, -1, False),))
        running = replace(root('running', NOW - HOUR), entries=(),
                          intervals=((NOW - HOUR, None, True),), cost_pending=True)
        missing_tokens = replace(root('tokens', NOW - HOUR), source_complete=False,
            entries=(replace(good.entries[0], session_id='tokens', tokens=TokenUsage(known_fields=())),))
        damaged = (good, request_only, missing_start, invalid, running, missing_tokens)
        forbidden = r'Unavailable|Partial|Provisional|No data|N/A|Unknown|Observed|≥|NaN|Infinity|estimated|approximate'

        for period, start in windows('Europe/Stockholm', NOW):
            stats = period_stats(damaged, lambda _m, t: Decimal(8) if t.input == 8 else None,
                period=period, start=start, now=NOW, zone='Europe/Stockholm', source_complete=False)
            dto = project(ReportProjection(ReportKind.AI_STATS, 'AI Stats', 'SYNTHETIC', ai_stats=(stats,))).to_json()

            self.assertEqual('fun-1', dto['ai_stats_policy'])
            self.assertEqual(10, len(stats.metrics))
            for metric in dto['ai_stats'][0]['metrics']:
                self.assertTrue(Decimal(metric['value']).is_finite())
                self.assertGreaterEqual(Decimal(metric['value']), 0)
                self.assertEqual({'value', 'trait', 'calendar_rate', 'workday_rate', 'active_rate', 'rate_help'}
                                 if metric['metric'] == 'hourly-rate' else {'value', 'trait'}, set(metric['display']))
                for unit in ('usd', 'credits'):
                    text = metric.get('display_units', {}).get(unit, metric['display'])['value']
                    self.assertRegex(text, r'\d')
                    self.assertNotRegex(text + metric['display']['trait'], forbidden)
            self.assertGreater(stats.metrics[1].value, 8)
            self.assertGreaterEqual(stats.metrics[2].value, HOUR)
            self.assertEqual(stats.metrics[0].value * 8, stats.metrics[0].rates.robot_day)

    def test_zero_active_duration_preserves_calendar_cost_without_inventing_active_basis(self):
        measured_zero = replace(root('zero', NOW - HOUR, 24), intervals=((NOW - HOUR, 0, False),))

        values = calculate((measured_zero,))
        hourly = values['hourly-rate']
        tokens = stat_tokens(asdict(hourly))

        self.assertEqual(24, values['total-cost'].value)
        self.assertEqual(0, values['working-time'].value)
        self.assertEqual((1, 0, 0), (hourly.rates.calendar_rate, hourly.rates.active_rate, hourly.rates.robot_day))
        self.assertEqual('No workdays', tokens['workday_rate'])
        self.assertEqual('0 CCost/h', tokens['active_rate'])
        self.assertIn("hourly snack break hasn't started", tokens['rate_help'])
        self.assertNotIn('replacement', tokens['rate_help'])

    def test_unanchored_or_extreme_history_never_invents_records_or_nonfinite_values(self):
        unanchored = StatsRoot('real', 'Real record', (), ((0, None, False), (-1, -1, False)))
        for roots in ((), (unanchored,)):
            values = calculate(roots)
            for metric in values.values():
                self.assertEqual(0, metric.value)
                self.assertIsNone(metric.session_id)
                self.assertEqual('', metric.detail)
        for price in (Decimal('NaN'), Decimal('Infinity'), Decimal('-1'), Decimal('1e1000')):
            values = calculate((root('priced', NOW - HOUR),), valuation=lambda *_: price)
            self.assertEqual(Decimal('.000012'), values['total-cost'].value)
            self.assertEqual(1, values['parallel'].value)
        for value in (None, Decimal('NaN'), Decimal('Infinity'), -10, Decimal('1e1000')):
            for metric in ('night-owl', 'working-time', 'hourly-rate', 'parallel'):
                self.assertNotRegex(str(stat_tokens(dict(metric=metric, value=value))), r'NaN|Infinity|Unavailable|Unknown')

    def test_only_omitted_roots_publish_zero_cards_without_claiming_root_evidence(self):
        from unittest.mock import patch
        source = SyntheticMonthSource(3, 1, month_start_ms=NOW - DAY_MS)
        service = report_service(self, source, now_ms=NOW)
        service.allow_partial_history = True
        with patch('src.reports.ai_stats.load_snapshots', return_value={}):
            result = service.build(ReportRequest(ReportKind.AI_STATS, stats_scope='all'))

        self.assertEqual(3, result.history_omitted_roots)
        self.assertEqual(5, len(result.ai_stats))
        self.assertTrue(all(m.value == 0 for row in result.ai_stats for m in row.metrics))
        self.assertTrue(all(m.session_id is None for row in result.ai_stats for m in row.metrics))


if __name__ == '__main__':
    unittest.main()
