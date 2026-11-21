"""Cross-service reuse and cold parity; process/DOM evidence lives in the benchmark."""
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from development.tests.fixtures.account_periods import subscription
from development.tests.fixtures.report_runtime import FakePricingProvider
from development.tests.fixtures.synthetic_month import SyntheticMonthSource, make_root_snapshot
from development.tests.test_account_timeline import NOV_5, projected
from src.analysis.account_timeline import DAY_MS
from src.application.account_timeline import account_roster
from src.application.session_quota import source_scope
from src.cache import CacheDatabase, CacheRepository
from src.reports import ReportKind, ReportRequest, ReportService
from src.reports import ai_stats_warm
from src.sources.selection import SourceSelection
from src.watch.account_timeline import TimelineHistory
from src.watch.observers import observe_catalog
from src.watch.source_reads import SourceReads
from src.web.composition import open_cache


def report_service(source, cache, now, pricing, *, zone='UTC', calendar='SE'):
    return ReportService(selection=SourceSelection(source, 'v2', (), source.probe()),
        pricing_provider=pricing, account_provider=None, cache_repository=cache, now_ms=now,
        config={'timezone': zone, 'workdayCalendar': calendar})


class WarmRestartTests(unittest.TestCase):
    def cache(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        db = CacheDatabase(Path(folder.name))
        db.initialize()
        return CacheRepository(db)

    def history(self, size, *, linked=False):
        source = SyntheticMonthSource(size, 2, month_start_ms=NOV_5 - 3 * DAY_MS,
                                      children_per_root=int(linked))
        source.snapshots = {sid: replace(snapshot, complete=True) for sid, snapshot in source.snapshots.items()}
        return source

    def stats(self, source, cache, now=NOV_5, *, zone='UTC', calendar='SE', scan='report', limit=256):
        service = report_service(source, cache, now, FakePricingProvider(), zone=zone, calendar=calendar)
        service.stats_scan, service.stats_slice_roots, service.shared_web_evidence = scan, limit, True
        report = service.build(ReportRequest(ReportKind.AI_STATS, stats_scope='all'))
        return report, service.metrics.counts.get('ai_stats_warm_projection_hits', 0)

    def timeline(self, source, cache, now=NOV_5, *, zone='UTC', accounts=None, pricing=None):
        pricing = pricing or FakePricingProvider()
        roster = account_roster(projected(*(accounts or (subscription('github-copilot'),))))
        worker = TimelineHistory(lambda at: report_service(source, cache, at, pricing), SourceReads(), cache)
        observation = observe_catalog(source, include_archived_revisions=True)
        while True:
            periods = ('today', '7-days', '30-days', 'month')
            views, more, _ = worker.step(source_scope(source), observation, periods, roster, zone,
                pricing.catalog, lambda: None, None, now, foreground=True)
            if not more:
                return {period: view.to_json() for period, view in views.items()}

    def test_accounts_reuses_exact_index_and_never_reads_unchanged_history(self):
        source, cache = self.history(40, linked=True), self.cache()
        initial = self.timeline(source, cache)
        before = source.load_count

        with patch('src.watch.account_timeline.PeriodCCostIndex', side_effect=AssertionError('repriced history')):
            warm = self.timeline(source, CacheRepository(cache.database))

        self.assertEqual(40, before)
        self.assertEqual(before, source.load_count)
        self.assertEqual(initial, warm)
        self.assertIsNotNone(cache.get('account-timeline-warm-index', 'last-complete'))

    def test_stats_reuses_all_ready_periods_but_reads_current_titles_and_clock(self):
        source, cache = self.history(15, linked=True), self.cache()
        initial, hit = self.stats(source, cache, scan='first')
        before = source.load_count
        root = source.snapshots['root-0000']
        renamed = replace(root.root, title='Changed title with same tree revision')
        source.snapshots['root-0000'] = replace(root, root=renamed, sessions=(renamed, *root.sessions[1:]))

        with patch('src.reports.ai_stats.StatsObservation', side_effect=AssertionError('reprojected history')):
            warm, warm_hit = self.stats(source, CacheRepository(cache.database), NOV_5 + 1000, scan='second')
        canonical, _ = self.stats(source, self.cache(), NOV_5 + 1000, scan='canonical')

        self.assertEqual((0, 1), (hit, warm_hit))
        self.assertEqual(15, before)
        self.assertEqual(30, source.load_count)
        self.assertEqual(canonical.ai_stats, warm.ai_stats)
        self.assertEqual(initial.ai_stats_work['scopes'], warm.ai_stats_work['scopes'])
        raw = str(cache.get(ai_stats_warm.NAMESPACE, ai_stats_warm.KEY).payload)
        self.assertNotIn('Synthetic 0000', raw)
        self.assertNotIn('prompt 0-', raw)

    def test_small_delta_rehydrates_only_changed_and_new_trees_and_matches_cold(self):
        for delta in (1, 3, 10):
            with self.subTest(delta=delta):
                source, cache = self.history(48, linked=True), self.cache()
                self.timeline(source, cache)
                self.stats(source, cache, scan='before')
                for index in range(delta):
                    sid = f'root-{index:04d}'
                    snapshot = source.snapshots[sid]
                    if index % 3 == 1:
                        del source.snapshots[sid]
                    elif index % 3 == 2:
                        added = make_root_snapshot(index + 100, 3, month_start_ms=NOV_5 - DAY_MS)
                        source.snapshots[added.root.session_id] = replace(added, complete=True)
                    else:
                        usage = replace(snapshot.invocations[-1].tokens, output=12345)
                        invocations = (*snapshot.invocations[:-1], replace(snapshot.invocations[-1], tokens=usage))
                        source.snapshots[sid] = replace(snapshot, invocations=invocations, source_revision='child-updated')
                source.snapshots = dict(reversed(tuple(source.snapshots.items())))
                expected_reads = sum(index % 3 != 1 for index in range(delta))
                now = NOV_5 + 1000

                before = source.load_count
                warm_chart = self.timeline(source, CacheRepository(cache.database), now)
                self.assertEqual(expected_reads, source.load_count - before)
                before = source.load_count
                warm_stats, hit = self.stats(source, CacheRepository(cache.database), now, scan='after')
                self.assertEqual(expected_reads, source.load_count - before)
                self.assertEqual(0, hit)
                fresh_chart = self.timeline(source, self.cache(), now)
                fresh_stats, _ = self.stats(source, self.cache(), now, scan='fresh')

                self.assertEqual(fresh_chart, warm_chart)
                self.assertEqual(fresh_stats.ai_stats, warm_stats.ai_stats)

    def test_stats_rollover_calendar_timezone_and_corruption_do_not_relabel_projection(self):
        source, cache = self.history(8), self.cache()
        self.stats(source, cache, scan='warm')
        for now, zone, calendar in ((NOV_5 + DAY_MS, 'UTC', 'SE'), (NOV_5, 'America/New_York', 'SE'),
                                    (NOV_5, 'UTC', 'US'), (NOV_5 + 28 * DAY_MS, 'UTC', 'SE')):
            with self.subTest(now=now, zone=zone, calendar=calendar):
                candidate, hit = self.stats(source, cache, now, zone=zone, calendar=calendar, scan=str(now) + zone + calendar)
                fresh, _ = self.stats(source, self.cache(), now, zone=zone, calendar=calendar, scan='canonical')
                self.assertEqual(0, hit)
                self.assertEqual(fresh.ai_stats, candidate.ai_stats)
        self.stats(source, cache, scan='back-to-initial')
        row = cache.get(ai_stats_warm.NAMESPACE, ai_stats_warm.KEY)
        cache.put(row.namespace, row.key, ['wrong-seal', row.payload[1]], source_revision=row.source_revision,
                  algorithm_version=row.algorithm_version)
        recovered, hit = self.stats(source, cache, scan='corrupt')
        self.assertEqual(0, hit)
        self.assertTrue(recovered.ai_stats_work['scopes']['all']['ready'])

    def test_locked_stats_cache_can_finish_without_a_durable_continuation(self):
        source, cache = self.history(8), self.cache()
        self.stats(source, cache, scan='previous')
        # An independent writer prevents SQLite writes but does not rewrite the
        # existing entries. Change cohort to force a cold fallback.
        snapshot = source.snapshots['root-0000']
        source.snapshots['root-0000'] = replace(snapshot, source_revision='changed')
        with cache.database.connect(busy_timeout_ms=0) as writer:
            writer.execute('BEGIN IMMEDIATE')
            result, hit = self.stats(source, cache, scan='locked', limit=1)

        self.assertEqual(0, hit)
        self.assertTrue(result.ai_stats_work['scopes']['all']['ready'])
        self.assertEqual(8, result.ai_stats_work['scopes']['all']['completed'])

    def test_corrupt_database_is_left_in_place_and_both_views_fall_back(self):
        source, ready = self.history(14), self.cache()
        fresh_stats, _ = self.stats(source, ready)
        fresh_chart = self.timeline(source, ready)
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        package = Path(folder.name)
        path = CacheDatabase(package).paths.database
        path.parent.mkdir()
        corrupt = b'not a Cost Guard SQLite file'
        path.write_bytes(corrupt)

        cache = open_cache(package)
        stats, hit = self.stats(source, cache)
        chart = self.timeline(source, cache)

        self.assertEqual(corrupt, path.read_bytes())
        self.assertEqual(0, hit)
        self.assertEqual(fresh_stats.ai_stats, stats.ai_stats)
        self.assertEqual(fresh_chart, chart)

    def test_active_tree_never_admits_previous_stats_or_accounts_facts(self):
        source, cache = self.history(14), self.cache()
        self.stats(source, cache, scan='previous')
        self.timeline(source, cache)
        snapshot = source.snapshots['root-0000']
        root = replace(snapshot.root, active=True)
        source.snapshots[root.session_id] = replace(snapshot, root=root, sessions=(root,), complete=False)

        before = source.load_count
        result, hit = self.stats(source, cache, scan='active')
        stats_reads = source.load_count - before
        before = source.load_count
        chart = self.timeline(source, cache)

        self.assertEqual(0, hit)
        self.assertEqual(1, stats_reads)
        self.assertEqual(1, source.load_count - before)
        self.assertEqual(self.timeline(source, self.cache()), chart)
        self.assertEqual(self.stats(source, self.cache(), scan='canonical')[0].ai_stats, result.ai_stats)


if __name__ == '__main__':
    unittest.main()
