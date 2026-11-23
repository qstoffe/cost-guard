"""Cross-service reuse and cold parity; process/DOM evidence lives in the benchmark."""
from dataclasses import replace
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from development.tests.fixtures.account_periods import subscription
from development.tests.fixtures.report_runtime import FakePricingProvider
from development.tests.fixtures.synthetic_month import SyntheticMonthSource, make_root_snapshot
from development.tests.test_account_timeline import NOV_5, projected
from src.analysis.account_timeline import DAY_MS
from src.application.account_timeline import account_roster
from src.application.detail_archive import load_detail
from src.application.session_archive import DOMAIN as SESSIONS, SessionArchive
from src.application.session_catalog import SessionCatalog
from src.application.session_quota import source_scope
from src.cache import CacheDatabase, CacheRepository
from src.cache.web_archive import ArchiveFact, WebArchive
from src.reports import ReportKind, ReportRequest, ReportService
from src.reports import ai_stats_warm
from src.reports.archived_usage import ArchivedUsage
from src.sources.selection import SourceSelection
from src.watch.account_timeline import TimelineHistory
from src.watch.observers import observe_catalog
from src.watch.source_reads import SourceReads
from src.web.composition import open_cache
from src.web.history_projection import HistoryProjection


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
        for now, zone, calendar in ((NOV_5 + DAY_MS, 'UTC', 'SE'), (NOV_5, 'Europe/Stockholm', 'SE'),
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


class DisplayHistoryTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.directory = Path(folder.name)
        self.now = NOV_5
        self.pricing = FakePricingProvider()
        self.cache = open_cache(self.directory)

    def restore(self, epoch):
        archive = WebArchive(self.directory)
        catalog = SessionCatalog(archive=archive, clock=lambda: (self.now - NOV_5) / 1000,
                                 clock_ms=lambda: self.now)
        self.addCleanup(catalog.close)
        catalog.bind_archive('v2', 'synthetic-month', epoch)
        catalog.archive_maintenance()
        # A queued barrier on this catalog's single worker runs after the
        # restore callback, even if the callback has already cleared archive_job.
        catalog.archive_pool.submit(lambda: None).result(timeout=10)
        return archive, catalog

    def source(self, roots, requests, **kwargs):
        source = SyntheticMonthSource(roots, requests, month_start_ms=NOV_5 - 5 * DAY_MS, **kwargs)
        source.source_id = 'opencode-v2'
        source.source_instance = 'synthetic-month'
        source.observation_epoch = 'one'
        source.snapshots = {k: replace(s, complete=True) for k, s in source.snapshots.items()}
        return source

    def tick(self, catalog, source):
        self.now += 1000
        catalog.tick(report_service(source, self.cache, self.now, self.pricing))

    def request_count(self, archive, source):
        service = report_service(source, self.cache, self.now, self.pricing)
        views, _ = HistoryProjection(ArchivedUsage(archive)).render(identity='shared-history',
            selection=service.selection, config=service.config, reference=self.pricing.catalog, now=self.now,
            revisions={}, activity={}, available=False, only='all')
        return views['token-mix', 'all']['view']['token_mix']['request_count']

    def test_reports_details_and_rows_survive_an_empty_new_epoch_then_merge_a_correction(self):
        source = self.source(2, 3)
        archive, first = self.restore('one')
        first.observe(observe_catalog(source, include_archived_revisions=True))
        for _ in range(4):
            self.tick(first, source)
        self.assertEqual(6, self.request_count(archive, source))

        replacement = self.source(0, 0)
        replacement.observation_epoch = 'two'
        reopened, second = self.restore('two')
        second.observe(observe_catalog(replacement, include_archived_revisions=True))
        page = second.page(period='all')
        self.assertEqual(2, page['total'])
        self.assertEqual(6, self.request_count(reopened, replacement))
        self.assertEqual(3, len(load_detail(reopened, 'root-0000').value['view']['prompt_blocks'][0]['rows']))
        self.assertEqual(0, replacement.load_count)

        changed = make_root_snapshot(0, 4, month_start_ms=NOV_5 - DAY_MS)
        replacement.snapshots['root-0000'] = replace(changed, complete=True, source_revision='corrected')
        second.observe(observe_catalog(replacement, include_archived_revisions=True))
        self.tick(second, replacement)
        self.assertEqual(2, second.page(period='all')['total'])
        self.assertEqual(7, self.request_count(reopened, replacement))

    def test_unrecognized_summary_shape_keeps_readable_fields_without_reviving_running(self):
        archive = WebArchive(self.directory)
        archive.initialize()
        archive.publish('old-store', SESSIONS, {'old': ArchiveFact('old-codec', 1, {
            'title': 'Retained session', 'prompt_count': 8, 'running': True, 'duration_ms': 'unknown'})})

        _, catalog = self.restore('other')
        page = catalog.page(period='all')
        row, = page['view']['session_usage']
        self.assertEqual(('Retained session', 8), (row['title'], row['prompt_count']))
        self.assertFalse(row['running'])
        self.assertIsNone(row['duration_ms'])

    def test_upgrade_keeps_inputs_after_failed_write_then_reopens_both_histories(self):
        cache_dir = self.directory / 'cache'
        old_web = WebArchive(self.directory / 'instance')
        old_web.initialize()
        old_web.publish('old-epoch', SESSIONS, {'from-appdata': ArchiveFact('r1', 100, {
            'title': 'Earlier history', 'prompt_count': 3, 'running': True})})
        display = cache_dir / 'cost-guard-display-v1.sqlite3'
        with sqlite3.connect(display) as db:
            db.executescript('''PRAGMA application_id=0x43474448; PRAGMA user_version=1;
                CREATE TABLE sessions(source, session_id, title, revision, prompts);
                INSERT INTO sessions VALUES ('old','from-display','Display history','r2',7);''')
        db.close()
        disposable = CacheDatabase(self.directory, generation=2)
        disposable.initialize()
        unrelated = cache_dir / 'unrelated.sqlite3'
        unrelated.write_bytes(b'not a migration input')

        destination = WebArchive(cache_dir)
        upgrade = SessionArchive(destination, display, upgrade=(self.directory, old_web.path))
        # The destination does not exist yet; no successful transfer is possible.
        with self.assertLogs('src.application.session_archive', level='WARNING'):
            _, retry = upgrade.load_legacy(lambda: False)
        self.assertTrue(retry)
        self.assertTrue(all(path.exists() for path in (old_web.path, display, disposable.paths.database)))

        destination.initialize()
        _, retry = upgrade.load_legacy(lambda: False)
        self.assertFalse(retry)
        rows, _ = SessionArchive(WebArchive(cache_dir)).load()
        self.assertEqual({'from-appdata': 3, 'from-display': 7},
                         {key: row.prompt_count for key, row in rows.items()})
        self.assertFalse(rows['from-appdata'].running)
        for path in (old_web.path, display, disposable.paths.database):
            for suffix in ('', '-wal', '-shm'):
                self.assertFalse(path.with_name(path.name + suffix).exists())
        self.assertEqual(b'not a migration input', unrelated.read_bytes())

    def test_running_and_today_precede_old_all_time_work_without_starvation(self):
        source = self.source(20, 1, today_roots=2, now_ms=NOV_5, running_roots=1)
        _, catalog = self.restore('one')
        catalog.observe(observe_catalog(source, include_archived_revisions=True))
        with patch.object(source, 'load_session_snapshot', wraps=source.load_session_snapshot) as read:
            catalog.page(period='all', sort='name')
            self.tick(catalog, source)
            catalog.page(period='today')
            for _ in range(10):
                self.tick(catalog, source)
        order = list(dict.fromkeys(call.args[0] for call in read.call_args_list))
        self.assertEqual('root-0000', order[0])
        self.assertEqual({'root-0019', 'root-0018'}, set(order[1:3]))
        self.assertEqual(20, len(order))

    def test_cold_week_admits_second_today_page_before_bulk_discovered_older_history(self):
        source = self.source(74, 1, today_roots=30, now_ms=NOV_5 + 54 * 60_000)
        older = {key: source.snapshots.pop(key) for key in list(source.snapshots)[:44]}
        today_ids = set(source.snapshots)
        _, catalog = self.restore('one')
        catalog.observe(observe_catalog(source, include_archived_revisions=True))
        week = catalog.page(period='7-days', sort='name', direction=1)
        token = week['token']
        self.assertEqual(0, week['total'])
        for _ in range(6):
            self.tick(catalog, source)
        today = catalog.page(token=token, period='today')
        self.assertEqual(24, today['total'])
        self.assertTrue(today['membership_pending'], 'the live tail is not proof of complete Today coverage')

        source.snapshots.update(older)
        catalog.observe(observe_catalog(source, include_archived_revisions=True))
        catalog.page(token=token, period='7-days', sort='name', direction=1)
        with patch.object(source, 'load_session_snapshot', wraps=source.load_session_snapshot) as read:
            self.tick(catalog, source)
            self.tick(catalog, source)
        self.assertTrue(all(call.args[0] in today_ids for call in read.call_args_list[:6]))
        first = catalog.page(token=token, period='today')
        second = catalog.page(token=token, period='today', offset=25)
        self.assertEqual((30, 25), (first['total'], second['offset']))
        shown = first['view']['session_usage'] + second['view']['session_usage']
        self.assertEqual(today_ids, {row['session_id'] for row in shown})
        self.assertTrue(all(row['has_summary'] and row['prompt_count'] == 1 for row in shown))
        self.assertFalse(first['membership_pending'])
        self.assertTrue(catalog.page(token=token, period='all')['membership_pending'])
        for _ in range(11):
            self.tick(catalog, source)
        settled = catalog.page(token=token, period='all')
        self.assertEqual(74, settled['total'])
        self.assertFalse(settled['membership_pending'])

    def test_short_prompt_discovered_and_finished_before_history_catches_up(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        from types import SimpleNamespace
        from unittest.mock import Mock
        from src.reports.session_summary import session_summary
        from src.reports.watch_capture import capture_rows
        from src.watch.web_coordinator import WebWatchCoordinator

        source = self.source(2, 1, today_roots=2, now_ms=self.now)
        _, catalog = self.restore('one')
        catalog.observe(observe_catalog(source, include_archived_revisions=True))
        self.tick(catalog, source)
        def rows():
            return catalog.page(period='today', sort='name', direction=1)['view']['session_usage']
        peer, key = [row['session_id'] for row in rows()]
        previous = source.snapshots[key]
        source.snapshots[key] = replace(previous, source_revision='historical-refresh')
        self.now += 6000
        catalog.observe(observe_catalog(source, include_archived_revisions=True))
        started, release = Event(), Event()
        def delayed(*args, **kwargs):
            result = session_summary(*args, **kwargs)
            started.set()
            if not release.wait(10):
                raise TimeoutError('history not released')
            return result

        live = self.source(2, 2, today_roots=2, now_ms=self.now + 3_590_000, running_roots=2)
        snapshot = replace(live.snapshots[key], source_revision='new-prompt')
        cards = SimpleNamespace(sessions={}, tick=Mock())
        coordinator = SimpleNamespace(cards=cards, session_catalog=catalog, _closed=False, clock_ms=lambda: self.now)
        def publish(snapshot):
            service = report_service(source, self.cache, self.now, self.pricing)
            capture, _ = capture_rows(service, snapshot.root, fresh=snapshot)
            cards.sessions[key] = SimpleNamespace(snapshot=snapshot, capture=capture,
                generation=1, verified_generation=1, source_status=SimpleNamespace(failed_at=None))
            WebWatchCoordinator.service_completed(coordinator)

        with ThreadPoolExecutor(max_workers=1) as pool, patch(
                'src.application.session_catalog.session_summary', side_effect=delayed):
            job = pool.submit(catalog.tick, report_service(source, self.cache, self.now, self.pricing))
            try:
                self.assertTrue(started.wait(10))
                self.now += 500
                publish(snapshot)  # Authoritative Watch is ahead of the source catalog revision.
                self.assertEqual([(key, True), (peer, False)], [(r['session_id'], r['running']) for r in rows()])
            finally:
                release.set()
            job.result(timeout=10)
        self.assertEqual((key, True), (rows()[0]['session_id'], rows()[0]['running']))

        self.now += 500
        end = self.now - 150
        root = replace(snapshot.root, active=False)
        final = replace(snapshot, root=root, sessions=(root,), source_revision='terminal',
            messages=(*snapshot.messages[:-1], replace(snapshot.messages[-1], completed_at_ms=end, finish_reason='stop')),
            invocations=(*snapshot.invocations[:-1], replace(snapshot.invocations[-1], completed_at_ms=end, finish_reason='stop')))
        source.snapshots[key] = final
        catalog.observe(observe_catalog(source, include_archived_revisions=True))
        publish(final)
        pending, older = rows()
        self.assertEqual((key, False, None, snapshot.events[-1].created_at_ms),
            (pending['session_id'], pending['running'], pending['last_activity_ms'], pending['prompt_started_ms']))
        self.assertEqual(peer, older['session_id'])
        self.now += 6000
        self.tick(catalog, source)
        older, verified = rows()
        self.assertEqual((peer, key, end), (older['session_id'], verified['session_id'], verified['last_activity_ms']))


if __name__ == '__main__':
    unittest.main()
