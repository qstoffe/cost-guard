"""Independent known-subtotal, non-inference and temporal-proof regressions."""
from dataclasses import asdict, replace
from decimal import Decimal
import unittest

from development.tests.fixtures.active_hour import epoch
from development.tests.fixtures.session_snapshots import make_native_v2_compaction_snapshot
from development.tests.fixtures.compact_reports import report_service
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from src.analysis.ai_stats import DAY_MS, StatsRoot, period_stats
from src.analysis.compaction import completed_compactions
from src.analysis.models import TraceEntry
from src.application.ai_stats import stat_tokens
from src.domain import ModelRef, TokenUsage
from src.reports import ReportKind, ReportRequest

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
        self.assertIsNone(values['hourly-rate'].value)
        self.assertIsNone(report.ai_stats[-1].matched)

    def test_one_unknown_keeps_safe_subtotals_but_never_ratio_streak_or_peak(self):
        good = root('good', NOW - 2 * HOUR)
        bad = replace(root('bad', NOW - DAY_MS), intervals=((NOW - DAY_MS, None, False),))

        values = calculate((good, bad))

        for key in ('working-time', 'longest-session', 'busiest-day'):
            self.assertEqual((HOUR, 'partial', ('unknown-duration',)),
                             (values[key].value, values[key].status, values[key].reasons))
        self.assertEqual('good', values['longest-session'].session_id)
        self.assertEqual(8, values['total-cost'].value)
        self.assertEqual(4, values['average-cost'].value)
        for key in ('hourly-rate', 'night-owl', 'streak', 'parallel'):
            self.assertEqual((None, 'unavailable'), (values[key].value, values[key].status))

    def test_missing_price_or_tokens_never_erases_time_or_fabricates_an_average(self):
        good, bad = root('good', NOW - HOUR, 8), root('bad', NOW - 2 * HOUR, 99)
        for damaged, valuation, reason in (
            (bad, lambda _m, t: None if t.input == 99 else Decimal(t.input), 'unpriced-requests'),
            (replace(bad, entries=(replace(bad.entries[0], tokens=TokenUsage(input=2, known_fields=('input',))),)),
             None, 'missing-token-usage'),
            (replace(bad, cost_pending=True), None, 'pending-usage')):

            values = calculate((good, damaged), valuation=valuation)

            self.assertEqual((2 * HOUR, 'complete'), (values['working-time'].value, values['working-time'].status))
            self.assertIsNone(values['average-cost'].value)
            self.assertIsNone(values['hourly-rate'].value)
            winner = values['expensive-session']
            self.assertGreater(winner.value, 0)
            self.assertEqual('partial', winner.status)
            self.assertIn(reason, winner.reasons)
            self.assertIn('not a verified overall winner', stat_tokens(asdict(winner))['explanation'])

    def test_incomplete_root_and_membership_gaps_keep_only_qualified_observations(self):
        good = root('good', NOW - HOUR)
        for roots, complete in (((replace(good, source_complete=False),), True), ((good,), False)):
            values = calculate(roots, complete=complete)

            self.assertEqual((HOUR, 'partial', ('source-incomplete',)),
                             (values['working-time'].value, values['working-time'].status, values['working-time'].reasons))
            self.assertIsNone(values['parallel'].value)
            self.assertIsNone(values['average-cost'].value)

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

    def test_unknown_only_is_not_a_fake_zero_and_lower_bound_display_never_rounds_up(self):
        missing = replace(root('bad', NOW - HOUR), intervals=((NOW - HOUR, None, False),))
        values = calculate((missing,))
        self.assertIsNone(values['working-time'].value)
        for duration, expected in ((999, '≥ 0s'), (1599, '≥ 1s'), (59999, '≥ 59s')):
            good = replace(root('good', NOW - HOUR), intervals=((NOW - HOUR, duration, False),))
            observed = calculate((missing, good))['working-time']
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


if __name__ == '__main__':
    unittest.main()
