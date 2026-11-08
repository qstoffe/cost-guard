"""Independent AI Stats accounting, calendar boundaries and incremental acquisition."""
from dataclasses import asdict, replace
from decimal import Decimal
from pathlib import Path
import shutil
import subprocess
import time
import unittest
from unittest.mock import patch

from development.tests.fixtures.active_hour import epoch
from development.tests.fixtures.compact_reports import report_service, START, NOW
from development.tests.fixtures.synthetic_month import SyntheticMonthSource, make_root_snapshot
from development.tests.fixtures.ai_stats_views import stats_report
from src.analysis.ai_stats import StatsRoot, period_stats, windows, DAY_MS
from src.analysis.active_hour import HOUR_MS
from src.analysis.models import TraceEntry
from src.application import ReportApplication
from src.application.ai_stats import stat_tokens
from src.application.projection import project
from src.domain import ModelRef, TokenUsage
from src.pricing.catalog import PricingCatalog
from src.reports import ReportKind, ReportRequest, ReportService
from src.sources.selection import MigrationGapDiagnostic
from src.web.jobs import parse_report, ReportJobs


def request(sid, at, amount):
    return TraceEntry(sid, 'prompt', 'message-' + str(at), None, at, 0,
                     ModelRef('provider', 'model'), None, TokenUsage(input=amount))


def metrics(roots, *, start=None, now=None, zone='UTC', valuation=None, complete=True):
    result = period_stats(roots, valuation or (lambda _model, tokens: Decimal(tokens.input)),
        period='all', start=start, now=now or epoch('2026-11-05T12:00:00+00:00'), zone=zone, source_complete=complete)
    return {item.metric: item for item in result.metrics}


class AIStatsAnalysisTests(unittest.TestCase):
    def test_empty_period_distinguishes_true_zero_from_missing_denominators(self):
        result = metrics(())

        for key in ('total-cost', 'working-time', 'streak', 'parallel'):
            self.assertEqual((0, 'complete', ()), (result[key].value, result[key].status, result[key].reasons))
        for key in ('hourly-rate', 'average-cost', 'expensive-session', 'longest-session', 'busiest-day', 'night-owl'):
            item = result[key]
            self.assertEqual((None, 'no-data'), (item.value, item.status))
            display = stat_tokens(asdict(item))
            self.assertEqual('No data', display['value'])
            self.assertIn('completely observed period', display['explanation'])

    def test_evidence_reasons_are_metric_specific_and_never_loading(self):
        at = epoch('2026-11-01T10:00:00+00:00')
        root = StatsRoot('a', 'A', (request('a', at, 4),), ((at, HOUR_MS, False),))
        cases = (
            (replace(root, intervals=((at, None, False),)), {}, 'working-time', 'unknown-duration', None, 'unavailable'),
            (root, {'complete': False}, 'working-time', 'source-incomplete', HOUR_MS, 'partial'),
            (replace(root, source_complete=False), {}, 'hourly-rate', 'source-incomplete', None, 'unavailable'),
            (root, {'valuation': lambda *_: None}, 'average-cost', 'unpriced-requests', None, 'unavailable'),
            (replace(root, entries=(replace(root.entries[0], tokens=TokenUsage(input=4, known_fields=())),)),
             {}, 'expensive-session', 'missing-token-usage', 4, 'partial'),
            (replace(root, cost_pending=True), {}, 'hourly-rate', 'pending-usage', None, 'unavailable'),
        )

        for evidence, options, key, reason, value, status in cases:
            with self.subTest(reason=reason):
                result = metrics((evidence,), **options)
                item = result[key]
                self.assertEqual((value, status), (item.value, item.status))
                self.assertIn(reason, item.reasons)
                display = stat_tokens(asdict(item))
                self.assertEqual(status.capitalize(), display['state'])
                self.assertTrue(display['explanation'])
                self.assertNotIn('Loading', str(display))
                self.assertNotIn('vault', str(display))
        self.assertEqual('complete', metrics((root,), valuation=lambda *_: None)['working-time'].status)
        self.assertEqual('complete', metrics((replace(root, intervals=((at, None, False),)),))['total-cost'].status)

    def test_partial_subtotal_and_provisional_time_have_qualified_copy_in_both_units(self):
        from src.numbers import ccost_display
        at = epoch('2026-11-01T10:00:00+00:00')
        root = StatsRoot('a', 'A', (request('a', at, 4),), ((at, HOUR_MS, True),), cost_pending=True)
        result = metrics((root,))

        self.assertEqual((4, 'partial', ('pending-usage',)),
                         (result['total-cost'].value, result['total-cost'].status, result['total-cost'].reasons))
        self.assertEqual((HOUR_MS, 'provisional', ('running-executions',)),
                         (result['working-time'].value, result['working-time'].status, result['working-time'].reasons))
        for unit in ('credits', 'usd'):
            with ccost_display(unit):
                cost = stat_tokens(asdict(result['total-cost']))
                timing = stat_tokens(asdict(result['working-time']))
            self.assertIn('Observed subtotal only', cost['trait'])
            self.assertIn('not yet reported usage', cost['explanation'])
            self.assertIn('still in progress', timing['trait'])

    def test_older_unpriced_requests_only_invalidate_cost_for_the_scope_that_contains_them(self):
        at = epoch('2026-11-01T10:00:00+00:00')
        recent = StatsRoot('recent', 'Recent', (request('recent', at, 4),), ((at, HOUR_MS, False),))
        old = StatsRoot('old', 'Old', (request('old', at - 40 * DAY_MS, 99),), ((at - 40 * DAY_MS, HOUR_MS, False),))
        valuation = lambda _model, tokens: None if tokens.input == 99 else Decimal(tokens.input)

        short = metrics((recent, old), start=at - DAY_MS, valuation=valuation)
        all_time = metrics((recent, old), valuation=valuation)

        self.assertEqual((4, 'complete', ()), (short['hourly-rate'].value, short['hourly-rate'].status, short['hourly-rate'].reasons))
        self.assertEqual((4, 'partial', ('unpriced-requests',)),
                         (all_time['total-cost'].value, all_time['total-cost'].status, all_time['total-cost'].reasons))
        self.assertIsNone(all_time['hourly-rate'].value)
        self.assertEqual(2 * HOUR_MS, all_time['working-time'].value)

    def test_unknown_explanation_is_explicit_and_unrecognized_codes_are_not_rendered(self):
        display = stat_tokens({'metric': 'working-time', 'value': None, 'status': 'unavailable',
                               'reasons': ('PRIVATE_SOURCE_TEXT',)})

        self.assertIn('reason for missing evidence is unknown', display['trait'])
        self.assertNotIn('PRIVATE_SOURCE_TEXT', str(display))

    def test_ten_metrics_use_period_cost_root_denominator_and_overlap_union(self):
        base = epoch('2026-11-01T23:00:00+00:00')
        a = StatsRoot('a', 'Actual A', (request('a', base + HOUR_MS, 12),), ((base, 2 * HOUR_MS, False),))
        b = StatsRoot('b', 'Actual B', (request('b-child', base + HOUR_MS, 6),), ((base + HOUR_MS, 2 * HOUR_MS, False),))

        result = metrics((a, b))

        self.assertEqual(10, len(result))
        self.assertEqual(Decimal(18), result['total-cost'].value)
        self.assertEqual(3 * HOUR_MS, result['working-time'].value)
        self.assertEqual(Decimal(6), result['hourly-rate'].value)
        self.assertEqual(Decimal(9), result['average-cost'].value)
        self.assertEqual('a', result['expensive-session'].session_id)
        self.assertEqual('a', result['longest-session'].session_id)
        self.assertEqual(2 * HOUR_MS, result['longest-session'].value)
        self.assertEqual('2026-11-02', result['busiest-day'].detail)
        self.assertEqual(2 * HOUR_MS, result['busiest-day'].value)
        self.assertEqual(Decimal(100), result['night-owl'].value)
        self.assertEqual(2, result['streak'].value)
        self.assertEqual(2, result['parallel'].value)

    def test_clipping_cost_event_edge_and_touching_sessions(self):
        start = epoch('2026-11-01T00:00:00+00:00')
        a = StatsRoot('a', 'A', (request('a', start - 1, 99), request('a', start, 7)),
                      ((start - HOUR_MS, 2 * HOUR_MS, False),))
        b = StatsRoot('b', 'B', (), ((start + HOUR_MS, HOUR_MS, False),))
        result = metrics((a, b), start=start, now=start + 2 * HOUR_MS)
        self.assertEqual(7, result['total-cost'].value)
        self.assertEqual(7, result['average-cost'].value)
        self.assertEqual(2 * HOUR_MS, result['working-time'].value)
        self.assertEqual(1, result['parallel'].value)

    def test_night_day_dst_and_local_midnight_streak(self):
        for start, end, night_hours in [('2026-03-28T21:00:00+00:00', '2026-03-29T04:00:00+00:00', 7),
                                      ('2026-10-24T20:00:00+00:00', '2026-10-25T05:00:00+00:00', 9)]:
            left, right = epoch(start), epoch(end)
            root = StatsRoot('a', 'A', (), ((left, right - left, False),))
            result = metrics((root,), zone='Europe/Stockholm', now=right)
            self.assertEqual(night_hours * HOUR_MS, result['working-time'].value)
            self.assertEqual(100, result['night-owl'].value)
            self.assertEqual(2, result['streak'].value)
        left = epoch('2026-11-01T10:00:00+00:00')
        day = metrics((StatsRoot('a', 'A', (), ((left, HOUR_MS, False),)),))
        self.assertEqual(0, day['night-owl'].value)
        line = stat_tokens({'metric': 'night-owl', 'value': 0, 'status': 'complete'})['trait']
        self.assertIn('Day-shift', line)

    def test_windows_31_day_month_timezone_and_rolling_edges(self):
        now = epoch('2026-10-31T22:30:00+00:00')
        local = dict(windows('Europe/Stockholm', now))
        utc = dict(windows('UTC', now))
        self.assertLess(local['month'], local['30-days'])
        self.assertNotEqual(local['today'], utc['today'])
        self.assertEqual(7 * DAY_MS, now - local['7-days'])
        self.assertEqual(30 * DAY_MS, now - local['30-days'])

    def test_zero_unknown_partial_and_provisional_never_invent_exact_rates(self):
        empty = metrics(())
        self.assertEqual(0, empty['total-cost'].value)
        self.assertEqual(0, empty['working-time'].value)
        self.assertIsNone(empty['hourly-rate'].value)
        self.assertIsNone(empty['average-cost'].value)
        self.assertIsNone(empty['night-owl'].value)
        self.assertEqual(0, empty['streak'].value)
        at = epoch('2026-11-01T10:00:00+00:00')
        root = StatsRoot('a', 'A', (request('a', at, 1),), ((at, None, False),))
        unknown = metrics((root,))
        self.assertIsNone(unknown['working-time'].value)
        self.assertIsNone(unknown['hourly-rate'].value)
        priced = metrics((replace(root, intervals=((at, HOUR_MS, True),)),))
        self.assertEqual('provisional', priced['working-time'].status)
        self.assertEqual(1, priced['hourly-rate'].value)
        partial = metrics((root,), valuation=lambda *_: None)
        self.assertEqual('partial', partial['total-cost'].status)
        self.assertIsNone(partial['expensive-session'].session_id)
        missing = replace(root, entries=(replace(root.entries[0], tokens=TokenUsage(input=1, known_fields=())),))
        self.assertEqual('partial', metrics((missing,))['total-cost'].status)

    def test_fallback_steps_clone_dedup_and_stable_record_ties(self):
        at = epoch('2026-11-01T10:00:00+00:00')
        entry = request('a', at, 5)
        step = replace(entry, step_part_id='step')
        clone = replace(step, session_id='clone')
        a = StatsRoot('a', 'A', (entry, step, step), ((at, HOUR_MS, False),))
        b = StatsRoot('b', 'B', (clone,), ((at, HOUR_MS, False),))
        result = metrics((b, a))
        self.assertEqual(5, result['total-cost'].value)
        self.assertEqual('a', result['expensive-session'].session_id)
        self.assertEqual('a', result['longest-session'].session_id)
        self.assertEqual(2, result['parallel'].value)


class AIStatsAcquisitionTests(unittest.TestCase):
    def test_source_warning_or_migration_gap_exposes_only_safe_metric_reasons(self):
        original, _source = self.original(1)
        selections = (
            replace(original.selection, warnings=('PRIVATE_SOURCE_DIAGNOSTIC',)),
            replace(original.selection, migration_gap=MigrationGapDiagnostic(True, ('legacy',))),
        )

        for selection in selections:
            original.selection = selection
            report = self.fresh(original).build(ReportRequest(ReportKind.AI_STATS, stats_scope='all'))
            metric = project(report).to_json()['ai_stats'][-1]['metrics'][2]

            self.assertEqual((900, 'partial', ['source-incomplete']),
                             (metric['value'], metric['status'], metric['reasons']))
            self.assertIn('coverage is incomplete', metric['display']['trait'])
            self.assertNotIn('PRIVATE_SOURCE_DIAGNOSTIC', str(metric))

    def test_incomplete_snapshot_remains_incomplete_after_cached_reuse_and_dto_projection(self):
        original, source = self.original(1)
        sid, snapshot = next(iter(source.snapshots.items()))
        source.snapshots[sid] = replace(snapshot, complete=False)

        first = self.fresh(original).build(ReportRequest(ReportKind.AI_STATS))
        warm = self.fresh(original).build(ReportRequest(ReportKind.AI_STATS))
        dto = project(warm).to_json()

        self.assertEqual(first, warm)
        metric = dto['ai_stats'][-1]['metrics'][2]
        self.assertEqual(('unavailable', None, ['source-incomplete']),
                         (metric['status'], metric['value'], metric['reasons']))
        self.assertIn('coverage is incomplete', metric['display']['explanation'])
        self.assertIsNone(dto['ai_stats'][-1]['matched'])

    def test_actual_finite_process_returns_coherent_ai_stats(self):
        jobs = ReportJobs(target=stats_report)
        self.addCleanup(jobs.close)
        key = jobs.submit(ReportRequest(ReportKind.AI_STATS))
        end = time.monotonic() + 12
        while time.monotonic() < end:
            jobs.tick()
            job = jobs.snapshot(key)
            if job['status'] not in ('queued', 'running'):
                break
            time.sleep(.02)
        self.assertEqual('complete', job['status'], job.get('error'))
        self.assertEqual(10, len(job['result']['view']['ai_stats'][0]['metrics']))

    @unittest.skipUnless(shutil.which('node'), 'optional JavaScript runtime unavailable')
    def test_cached_view_policy_exact_ttl_and_one_hour_edges(self):
        result = subprocess.run([shutil.which('node'), 'development/tests/integration/cached_reports.cjs'],
            cwd=Path(__file__).resolve().parents[2], text=True, capture_output=True, timeout=10)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def fresh(self, original, *, now=NOW):
        return ReportService(selection=original.selection, pricing_provider=original.pricing_provider,
            account_provider=None, cache_repository=original.cache_repository, config=original.config, now_ms=now)

    def original(self, count=6):
        source = SyntheticMonthSource(count, 3, month_start_ms=START)
        source.snapshots = {sid: replace(snapshot, complete=True) for sid, snapshot in source.snapshots.items()}
        original = report_service(self, source)
        original.selection = replace(original.selection, warnings=())
        return original, source

    def test_cold_warm_incremental_removed_and_archived_roots(self):
        original, source = self.original()
        first = self.fresh(original).build(ReportRequest(ReportKind.AI_STATS))
        loads = source.load_count
        with patch.object(source, 'load_session_snapshot', side_effect=AssertionError('warm hydration')), \
             patch.object(PricingCatalog, 'reference_category_valuation', side_effect=AssertionError('warm repricing')):
            warm = self.fresh(original).build(ReportRequest(ReportKind.AI_STATS))
        self.assertEqual(first, warm)
        self.assertEqual(6, loads)
        del source.snapshots['root-0001']
        snapshot = source.snapshots['root-0002']
        root = replace(snapshot.root, archived_at_ms=NOW)
        source.snapshots['root-0002'] = replace(snapshot, root=root, sessions=(root,), source_revision='archived')
        self.fresh(original).build(ReportRequest(ReportKind.AI_STATS))
        self.assertEqual(loads + 1, source.load_count)

    def test_unknown_old_roots_are_verified_once_then_reused_across_periods(self):
        now = epoch('2026-10-31T22:00:00+00:00')
        start = epoch('2026-10-01T00:00:00+00:00')
        source = SyntheticMonthSource(2, 3, month_start_ms=start)
        late = make_root_snapshot(2, 3, month_start_ms=now - DAY_MS)
        source.snapshots[late.root.session_id] = late
        original = report_service(self, source, now_ms=now)
        initial = self.fresh(original, now=now).build(ReportRequest(ReportKind.AI_STATS))
        self.assertEqual({'today', '7-days', '30-days'}, {row.period for row in initial.ai_stats})
        self.assertEqual(3, source.load_count)
        extended = self.fresh(original, now=now).build(ReportRequest(ReportKind.AI_STATS, stats_scope='month'))
        self.assertIn('month', {row.period for row in extended.ai_stats})
        self.assertEqual(3, source.load_count)
        all_time = self.fresh(original, now=now).build(ReportRequest(ReportKind.AI_STATS, stats_scope='all'))
        self.assertEqual(5, len(all_time.ai_stats))
        self.assertEqual(3, source.load_count)

    def test_application_tokens_no_request_text_or_accounts_and_scope_validation(self):
        original, _source = self.original()
        app = ReportApplication(lambda now, progress: self.fresh(original, now=now), clock=lambda: NOW)
        result = app.execute(parse_report({'kind': 'ai-stats'})).to_json()
        self.assertIsNone(result['error'])
        self.assertEqual([], result['view']['request_identities'])
        metric = result['view']['ai_stats'][0]['metrics'][1]
        self.assertIn('CCost', metric['display']['value'])
        self.assertIn('$', metric['display_units']['usd']['value'])
        self.assertIn('trait', metric['display'])
        with self.assertRaises(ValueError):
            parse_report({'kind': 'token-mix', 'stats_scope': 'all'})
        with self.assertRaises(ValueError):
            parse_report({'kind': 'ai-stats', 'stats_scope': 'yesterday'})

    def test_host_shares_acquisition_and_updates_priority_across_scopes(self):
        jobs = ReportJobs()
        self.addCleanup(jobs.close)
        request_30 = ReportRequest(ReportKind.AI_STATS)
        first = jobs.submit(request_30)
        self.assertEqual(first, jobs.submit(request_30))
        self.assertEqual(first, jobs.submit(ReportRequest(ReportKind.AI_STATS, stats_scope='all')))
        self.assertEqual('all', jobs._jobs[first]['request'].stats_scope)
        jobs._jobs[first].update(status='complete', finished_at=time.monotonic(),
            result={'observed_at_ms': 123, 'view': {'ai_stats': [{'period': '30-days'}]}})
        self.assertEqual(first, jobs.submit(request_30))
        self.assertEqual(123, jobs.snapshot(first)['result']['observed_at_ms'])
        jobs._jobs[first]['finished_at'] -= 61
        self.assertNotEqual(first, jobs.submit(request_30))

    def test_reference_revision_changes_invalidate_values_then_reuse_new_evidence(self):
        original, source = self.original(3)
        first = self.fresh(original).build(ReportRequest(ReportKind.AI_STATS))
        loads = source.load_count
        catalog = original.pricing_provider.catalog
        original.pricing_provider.catalog = PricingCatalog(tuple(replace(model,
            tiers=tuple(replace(tier, per_million_output=Decimal(999)) for tier in model.tiers)) for model in catalog.models))
        second = self.fresh(original).build(ReportRequest(ReportKind.AI_STATS))
        self.assertNotEqual(first.ai_stats[2].metrics[1].value, second.ai_stats[2].metrics[1].value)
        self.assertEqual(loads + 3, source.load_count)
        with patch.object(source, 'load_session_snapshot', side_effect=AssertionError('unchanged revised pricing')):
            self.assertEqual(second, self.fresh(original).build(ReportRequest(ReportKind.AI_STATS)))

    def test_active_history_is_reobserved_and_unavailable_cache_does_not_invent_empty(self):
        source = SyntheticMonthSource(1, 3, month_start_ms=START, running_roots=1)
        source.snapshots = {sid: replace(snapshot, complete=True) for sid, snapshot in source.snapshots.items()}
        original = report_service(self, source)
        original.selection = replace(original.selection, warnings=())
        first = self.fresh(original).build(ReportRequest(ReportKind.AI_STATS))
        loads = source.load_count
        with patch.object(original.cache_repository, 'get_many', side_effect=OSError('optional cache read')), \
                patch.object(original.cache_repository, 'put_many', side_effect=OSError('optional cache write')):
            second = self.fresh(original).build(ReportRequest(ReportKind.AI_STATS))
        self.assertEqual(first, second)
        self.assertGreater(source.load_count, loads)
        self.assertEqual('provisional', second.ai_stats[2].metrics[2].status)


if __name__ == '__main__':
    unittest.main()
