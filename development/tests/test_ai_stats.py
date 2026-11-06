"""Independent AI Stats accounting, calendar boundaries and incremental acquisition."""
from dataclasses import replace
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
from src.domain import ModelRef, TokenUsage
from src.pricing.catalog import PricingCatalog
from src.reports import ReportKind, ReportRequest, ReportService
from src.web.jobs import parse_report, ReportJobs


def request(sid, at, amount):
    return TraceEntry(sid, 'prompt', 'message-' + str(at), None, at, 0,
                     ModelRef('provider', 'model'), None, TokenUsage(input=amount))


def metrics(roots, *, start=None, now=None, zone='UTC', valuation=None, complete=True):
    result = period_stats(roots, valuation or (lambda _model, tokens: Decimal(tokens.input)),
        period='all', start=start, now=now or epoch('2026-11-05T12:00:00+00:00'), zone=zone, source_complete=complete)
    return {item.metric: item for item in result.metrics}


class AIStatsAnalysisTests(unittest.TestCase):
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
    def test_actual_finite_process_returns_coherent_ai_stats(self):
        jobs = ReportJobs(target=stats_report, deadline=10)
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

    def test_31_day_month_extension_and_all_history_are_lazy_reusing_roots(self):
        now = epoch('2026-10-31T22:00:00+00:00')
        start = epoch('2026-10-01T00:00:00+00:00')
        source = SyntheticMonthSource(2, 3, month_start_ms=start)
        late = make_root_snapshot(2, 3, month_start_ms=now - DAY_MS)
        source.snapshots[late.root.session_id] = late
        original = report_service(self, source, now_ms=now)
        initial = self.fresh(original, now=now).build(ReportRequest(ReportKind.AI_STATS))
        self.assertEqual({'today', '7-days', '30-days'}, {row.period for row in initial.ai_stats})
        self.assertEqual(1, source.load_count)
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

    def test_host_coalesces_ai_stats_but_not_distinct_scopes(self):
        jobs = ReportJobs()
        self.addCleanup(jobs.close)
        request_30 = ReportRequest(ReportKind.AI_STATS)
        first = jobs.submit(request_30)
        self.assertEqual(first, jobs.submit(request_30))
        self.assertNotEqual(first, jobs.submit(ReportRequest(ReportKind.AI_STATS, stats_scope='all')))
        jobs._jobs[first].update(status='complete', finished_at=time.monotonic(), result={'observed_at_ms': 123})
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
