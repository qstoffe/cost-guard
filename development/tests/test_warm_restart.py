"""Cross-service reuse and cold parity; process/DOM evidence lives in the benchmark."""
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
from threading import Event
from time import perf_counter
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from development.tests.fixtures.account_periods import subscription
from development.tests.fixtures.catalog_prompt_activity import publish_verified_capture
from development.tests.fixtures.report_runtime import FakePricingProvider
from development.tests.fixtures.synthetic_month import SyntheticMonthSource, make_root_snapshot
from development.tests.test_account_timeline import NOV_5, projected
from development.tests.fixtures.session_snapshots import DAY as DAY_MS
from src.application.account_timeline import account_roster
from src.application.detail_archive import DOMAIN as DETAILS, load_detail
from src.application.session_archive import DOMAIN as SESSIONS, SessionArchive
from src.application.session_catalog import SessionCatalog
from src.application.session_quota import source_scope
from src.cache import CacheDatabase, CacheRepository
from src.cache import session_projection
from src.cache.web_archive import ArchiveFact, PREVIOUS_ARCHIVE_FILENAME, WebArchive
from src.domain import TerminalEvidence, TerminalOutcome
from src.reports.models import SessionUsageRow
from src.reports import ReportKind, ReportRequest, ReportService
from src.reports import ai_stats_warm
from src.reports.watch_capture import capture_rows
from src.reports.archived_usage import ArchivedUsage
from src.sources.selection import SourceSelection
from src.watch.account_timeline import TimelineHistory
from src.watch.observers import observe_catalog
from src.watch.source_reads import SourceReads
from src.web.composition import open_cache
from src.web.history_process import ArchivedHistoryProcess
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

    def test_stored_detail_help_replays_child_cost_and_calls_without_old_timing_labels(self):
        model = 'github-copilot/claude-test — Low'
        decorated = model + ' (Linked by prompt timing)'
        def cost(label, amount):
            return f'Sub Agents:\n• {label} — ({amount})'

        row = dict(event_id='p1', ccost='102', calls=1,
                   model_display_help='Subagent 1 (Linked by prompt timing) — ' + model,
                   watch_calls_help=model + ': 1 calls\nSubagent 1 — Linked by prompt timing',
                   display=dict(cost_detail_help=cost(decorated, '102 Credits'),
                                mini_cost_models=[['Sub Agents', decorated]]),
                   display_units={'usd': dict(cost_detail_help=cost(decorated, '$1.02'))})
        fact = ArchiveFact('old', self.now, {'view': {'prompt_blocks': [{'session_id': 'root', 'rows': [row]}]}})
        archive, _ = self.restore('old')
        archive.publish('original', DETAILS, {'root': fact})

        replay = load_detail(WebArchive(self.directory), 'root')

        current, = replay.value['view']['prompt_blocks'][0]['rows']
        self.assertEqual(('102', 1), (current['ccost'], current['calls']))
        self.assertEqual('Subagent 1 — ' + model, current['model_display_help'])
        self.assertEqual(model + ': 1 calls', current['watch_calls_help'])
        self.assertEqual([['Sub Agents', model]], current['display']['mini_cost_models'])
        self.assertEqual(cost(model, '102 Credits'), current['display']['cost_detail_help'])
        self.assertEqual(cost(model, '$1.02'), current['display_units']['usd']['cost_detail_help'])

    def test_unrecognized_summary_shape_keeps_readable_fields_without_reviving_running(self):
        source = self.source(1, 8)
        archive, first = self.restore('one')
        first.observe(observe_catalog(source, include_archived_revisions=True))
        self.tick(first, source)
        # Drift the payload codec on an actual ready projection, not an orphan
        # generic fact which never qualified as a Sessions row.
        with closing(sqlite3.connect(archive.path)) as db, db:
            db.execute("""UPDATE facts SET value=json_set(value, '$.row.title', 'Retained session',
                '$.row.new_field', 1, '$.row.running', json('true'), '$.row.duration_ms', 'unknown')
                WHERE domain=?""", (SESSIONS,))

        _, catalog = self.restore('other')
        page = catalog.page(period='all')
        row, = page['view']['session_usage']
        self.assertEqual(('Retained session', 8), (row['title'], row['prompt_count']))
        self.assertFalse(row['running'])
        self.assertIsNone(row['duration_ms'])

    def test_legacy_capped_model_choices_restore_only_from_matching_trace(self):
        import json
        from src.reports.web_history_evidence import DOMAIN as usage_domain

        choices = ('low', 'medium', 'high', 'extra-high', 'max')
        source = self.source(2, len(choices))
        for key, snapshot in source.snapshots.items():
            source.snapshots[key] = replace(snapshot, events=tuple(
                replace(event, metadata={**event.metadata, 'variant': choice})
                for event, choice in zip(snapshot.events, choices, strict=True)))
        archive, catalog = self.restore('one')
        catalog.observe(observe_catalog(source, include_archived_revisions=True))
        for _ in range(2):
            self.tick(catalog, source)
        with closing(sqlite3.connect(archive.path)) as db, db:
            for key, raw in db.execute('SELECT item, value FROM facts WHERE domain=?', (SESSIONS,)).fetchall():
                fact = json.loads(raw)
                efforts = fact['row']['main_models'][0]['efforts']
                self.assertEqual(set(choices), {entry['selected'] for entry in efforts})
                efforts[:] = [entry for entry in efforts if entry['selected'] != 'max']
                fact.pop('model_effort_evidence')
                fact['row']['contributor_models_complete'] = False
                db.execute('UPDATE facts SET value=? WHERE domain=? AND item=?',
                           (json.dumps(fact, separators=(',', ':')), SESSIONS, key))
            db.execute('UPDATE facts SET revision=? WHERE domain=? AND item=?', ('different', usage_domain, 'root-0001'))

        _, reopened = self.restore('one')
        reopened.archive_maintenance()
        reopened.archive_pool.submit(lambda: None).result(timeout=10)
        rows = reopened.page(period='all')['view']['session_usage']
        help_by_id = {row['session_id']: row['model_display_help'] for row in rows}
        self.assertEqual(1, help_by_id['root-0000'].count(' — max'))
        self.assertNotIn(' — max', help_by_id['root-0001'])
        self.assertIn('may be incomplete', help_by_id['root-0001'])

    def test_cutover_retires_only_owned_legacy_files_without_import_and_preserves_next_start(self):
        cache_dir = self.directory / 'cache'
        instance = self.directory / 'instance'
        instance.mkdir()
        old_web = instance / PREVIOUS_ARCHIVE_FILENAME
        with closing(sqlite3.connect(old_web)) as db, db:
            db.executescript('''PRAGMA application_id=0x43475732; PRAGMA user_version=2;
                CREATE TABLE facts(value); INSERT INTO facts VALUES ('old history');''')
        display = cache_dir / 'cost-guard-display-v1.sqlite3'
        display.write_bytes(b'unknown identity')
        disposable = CacheDatabase(self.directory, generation=2)
        disposable.initialize()
        unrelated = cache_dir / 'unrelated.sqlite3'
        unrelated.write_bytes(b'not a migration input')
        destination = WebArchive(cache_dir, previous_directory=instance, retire_previous=True)
        with self.assertLogs('src.cache.web_archive', level='WARNING'):
            destination.initialize()
        self.assertEqual(b'unknown identity', display.read_bytes())
        self.assertFalse(old_web.exists())
        self.assertFalse(disposable.paths.database.exists())
        self.assertEqual([], list(destination.history_rows(SESSIONS)))
        display.unlink()
        with closing(sqlite3.connect(display)) as db:
            db.executescript('''PRAGMA application_id=0x43474448; PRAGMA user_version=1;
                CREATE TABLE sessions(title); INSERT INTO sessions VALUES ('Old display');''')
        orphan = (cache_dir / PREVIOUS_ARCHIVE_FILENAME).with_suffix('.sqlite3-shm')
        orphan.write_bytes(b'old shared memory')
        destination.initialize()
        self.assertFalse(orphan.exists())
        self.assertFalse(display.exists())
        self.assertEqual([], list(destination.history_rows(SESSIONS)))
        display.write_bytes(b'created after transition')
        WebArchive(cache_dir, retire_previous=True).initialize()
        self.assertEqual(b'created after transition', display.read_bytes())
        self.assertEqual(b'not a migration input', unrelated.read_bytes())

    def test_page_reads_prior_commit_under_live_writer_and_catalog_locks_then_sees_publication(self):
        notices = []
        archive = WebArchive(self.directory, retain_writer=True, retain_session_readers=True,
                             notify_sessions=notices.append)
        archive.initialize()
        self.addCleanup(archive.close_writer)
        self.addCleanup(archive.close_session_readers)
        catalog = SessionCatalog(archive=archive, clock_ms=lambda: self.now)
        self.addCleanup(catalog.close)
        def publish(live, *, pending):
            return catalog.archive.update_runtime(state='observed', terminal=False, reset_pending=True,
                pending=pending, live=live)

        live_row = SessionUsageRow('busy', 'New running session', 'N/A', False, None, 2, running=True)
        older = replace(live_row, prompt_count=1)
        self.assertTrue(publish({'busy': (older, self.now - 10, None)}, pending={'waiting': (self.now - 10, False)}))
        notices.clear()
        uncommitted, release = Event(), Event()
        apply = session_projection.update_runtime

        def hold_after_update(*args, **kwargs):
            apply(*args, **kwargs)
            uncommitted.set()
            if not release.wait(5):
                raise TimeoutError('reader did not release fixture writer')

        with ThreadPoolExecutor(max_workers=2) as pool, patch.object(session_projection, 'update_runtime', hold_after_update):
            with catalog.lock, archive._lock:
                writer = pool.submit(publish, {'busy': (live_row, self.now - 10, None)}, pending={})
                try:
                    self.assertTrue(uncommitted.wait(2))
                    start = perf_counter()
                    prior = pool.submit(catalog.page, period='all').result(timeout=1)
                    print(f'Sessions logical read with writer and catalog held: {(perf_counter()-start)*1000:.1f} ms')
                    prior_row, = prior['view']['session_usage']
                    self.assertEqual((1, 'busy', True, 1), (prior['total'], prior_row['session_id'],
                                                            prior_row['running'], prior_row['prompt_count']))
                    self.assertFalse(prior['history_progress']['complete'])
                    self.assertEqual([], notices)
                finally:
                    release.set()
            self.assertTrue(writer.result(timeout=2))
        self.assertEqual(1, len(notices))
        current = catalog.page(period='all')
        catalog.interest(current['token'], True)
        self.assertFalse(catalog.has_browsing_leases(), 'committed pages do not create source browsing demand')
        row, = current['view']['session_usage']
        self.assertTrue(current['history_progress']['complete'])
        self.assertEqual((1, 'busy', True, 2), (current['total'], row['session_id'], row['running'], row['prompt_count']))

    def test_committed_accounts_frame_is_detached_and_restores_only_for_its_zone_and_day(self):
        from src.analysis.account_timeline import period_start
        from src.watch.account_timeline_snapshots import AccountTimelineSnapshots

        archive = WebArchive(self.directory)
        archive.initialize()
        frames = AccountTimelineSnapshots(archive, None)
        old_week = ArchiveFact('old', self.now, dict(zone='UTC', day=period_start('today', self.now, 'UTC'),
            scope='old', view={'period': '7-days', 'series': []}, series=[], ready=True, active_until=0))
        archive.publish_checkpoint('account-timeline-view/1', {'7-days': old_week})
        self.assertIsNone(frames.lookup('7-days', None, zone='UTC', now=self.now)['view'],
                          'a rolling-week frame is incompatible even on the same local day')
        view = {'period': 'today', 'series': [{'id': 'A', 'amount': '27'}]}
        frames.publish(zone='UTC', day=period_start('today', self.now, 'UTC'), marker='A-scope',
                       now=self.now, periods=('today',), results={'today': view}, roster=(),
                       ready=True, active=(), active_until=0)
        view['series'][0]['amount'] = '99'  # Not committed.

        with patch.object(archive, 'history_item', side_effect=AssertionError('warm view read SQLite')):
            first = frames.lookup('today', None, zone='UTC', now=self.now)
            self.assertEqual(('27', 'A-scope'), (first['view']['series'][0]['amount'], first['scope']))
            self.assertTrue(frames.lookup('today', first['revision'], zone='UTC', now=self.now)['unchanged'])

        reopened = AccountTimelineSnapshots(WebArchive(self.directory), None)
        self.assertEqual(dict(first, restored=True, acquiring=False),
                         reopened.lookup('today', None, zone='UTC', now=self.now))
        for period, zone, now in (('month', 'UTC', self.now), ('today', 'UTC', self.now + DAY_MS),
                                  ('today', 'Europe/Stockholm', self.now)):
            with self.subTest(period=period, zone=zone, now=now):
                missing = reopened.lookup(period, None, zone=zone, now=now)
                self.assertIsNone(missing['view'])
                self.assertFalse(missing['ready'])

    def test_report_pointer_reads_a_committed_pair_and_restarts_with_qualified_history(self):
        from src.web.history_reports import HistoryReports, checkpoint_stamp, settings_signature

        source = self.source(1, 2)
        archive, catalog = self.restore('one')
        catalog.observe(observe_catalog(source, include_archived_revisions=True))
        self.tick(catalog, source)
        service = report_service(source, self.cache, self.now, self.pricing)
        projector = ArchivedHistoryProcess(archive)
        self.addCleanup(projector.close)
        reports = HistoryReports(archive, lambda: self.pricing.catalog, projector)
        self.addCleanup(reports.close)
        config = service.config
        stamp = checkpoint_stamp(config, 'UTC', None, settings_signature(config))
        inputs = dict(identity='test', selection=service.selection, config=config, now=self.now,
                      revisions={}, activity={}, available=True, only='all')
        reports._render(inputs, stamp, {})
        mix = ReportRequest(ReportKind.TOKEN_MIX, token_mix_scope='all')
        stats = ReportRequest(ReportKind.AI_STATS, stats_scope='all')
        with patch.object(archive, 'history_item', side_effect=AssertionError('warm report read SQLite')):
            view = reports.lookup(mix, config)['result']['view']
            self.assertEqual(2, view['token_mix']['request_count'])
            self.assertTrue(view['history_progress']['complete'])
            self.assertTrue(reports.lookup(stats, config)['result']['view']['history_progress']['all']['complete'])

        # A restart can serve qualified committed history before a projector is available.
        reopened = HistoryReports(WebArchive(self.directory), lambda: self.pricing.catalog, projector=None)
        self.addCleanup(reopened.close)
        restored = reopened.lookup(mix, config)['result']['view']
        self.assertEqual(2, restored['token_mix']['request_count'])
        self.assertTrue(restored['history_progress']['restored'])
        self.assertFalse(restored['history_progress']['complete'])
        self.assertIsNone(reopened.lookup(mix, dict(config, ccostDisplayUnit='usd'))['result'])

    def test_watch_projection_picks_up_committed_usage_without_claiming_a_complete_day(self):
        from src.reports.web_history_evidence import DOMAIN

        archive, catalog = self.restore('one')
        projector = ArchivedHistoryProcess(archive)
        self.addCleanup(projector.close)
        day = self.now // DAY_MS * DAY_MS
        source = self.source(2, 3, now_ms=self.now, today_roots=1)

        (empty, _), _ = projector.watch(day, self.now, self.pricing.catalog, archive.generation(DOMAIN))
        self.assertIsNone(empty)
        catalog.observe(observe_catalog(source, include_archived_revisions=True))
        self.tick(catalog, source)
        self.tick(catalog, source)

        (daily, more), _ = projector.watch(day, self.now, self.pricing.catalog, archive.generation(DOMAIN))
        self.assertFalse(more)
        self.assertEqual((3, 3), (daily.total.observed_requests, daily.prompt_count))
        self.assertFalse(daily.total.source_complete)
        self.assertFalse(daily.prompt_count_complete)

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

    def test_slow_running_reads_cannot_spend_every_scalar_slice_while_today_is_cold(self):
        source = self.source(6, 1, today_roots=6, now_ms=self.now, running_roots=2)
        archive, catalog = self.restore('one')
        catalog.observe(observe_catalog(source, include_archived_revisions=True))
        active = source.watch_candidate_session_ids()
        remaining = set(source.snapshots) - active
        reads = []
        load = source.load_session_snapshot

        def slow_read(key):
            reads.append(key)
            self.now += 6000  # One transport read exceeds the slice; Running is due again next turn.
            return load(key)

        with patch.object(source, 'load_session_snapshot', side_effect=slow_read):
            self.tick(catalog, source)
            self.assertIn(reads[0], active)
            for _ in range(7):
                self.tick(catalog, source)

        persisted, _ = SessionArchive(archive).load()
        self.assertEqual(remaining, set(persisted))
        self.assertTrue(all(row.prompt_count == 1 for row in persisted.values()))
        self.assertGreater(len([key for key in reads if key in active]), 1)

    def test_old_pending_root_is_taken_over_finalized_once_and_not_replayed_after_deletion(self):
        source = self.source(18, 1)
        archive, catalog = self.restore('one')
        def observe():
            catalog.observe(observe_catalog(source, include_archived_revisions=True))

        observe()
        self.tick(catalog, source)
        key, deleted = 'root-0000', 'root-0001'
        ready = catalog.page(period='all')['view']['session_usage']
        self.assertTrue(catalog.page(period='today')['history_progress']['complete'])
        self.assertTrue(ready)
        self.assertNotIn(key, {row['session_id'] for row in ready})
        self.assertNotIn(deleted, {row['session_id'] for row in ready})
        del source.snapshots[deleted]  # Discovered, never enriched.
        active = self.source(1, 2, today_roots=1, now_ms=self.now, running_roots=1).snapshots[key]
        root = replace(active.root, created_at_ms=source.snapshots[key].root.created_at_ms)
        active = replace(active, root=root, sessions=(root,), source_revision='takeover')
        source.snapshots[key] = active
        observe()
        with patch.object(source, 'load_session_snapshot', wraps=source.load_session_snapshot) as reads:
            self.tick(catalog, source)
        self.assertEqual(key, reads.call_args_list[0].args[0])
        first = catalog.page(period='all', sort='name', direction=-1)['view']['session_usage'][0]
        self.assertEqual((key, True, 2), (first['session_id'], first['running'], first['prompt_count']))
        self.assertNotIn(key, {item for item, _ in archive.history_rows(SESSIONS)})

        self.now += 6000
        aborted_at = self.now - 170
        root = replace(active.root, active=False, updated_at_ms=self.now)
        final = replace(active, root=root, sessions=(root,), source_revision='settled',
            messages=(*active.messages[:-1], replace(active.messages[-1], completed_at_ms=aborted_at,
                termination=TerminalEvidence(aborted_at, TerminalOutcome.CANCELLATION))),
            invocations=(*active.invocations[:-1], replace(active.invocations[-1], completed_at_ms=aborted_at)))
        source.snapshots[key] = final
        observe()
        capture, _ = capture_rows(report_service(source, self.cache, self.now, self.pricing), root, fresh=final)
        publish_verified_capture(catalog, final, capture)
        def pending_row():
            page = catalog.page(period='all', sort='name', direction=-1)
            self.assertTrue(catalog.page(period='today')['history_progress']['complete'])
            rows = page['view']['session_usage']
            self.assertEqual(page['total'], len({row['session_id'] for row in rows}))
            self.assertEqual((key, False, False), (rows[0]['session_id'], rows[0]['running'], rows[0]['indexed']))
            return rows[0]

        self.assertEqual('aborted', pending_row().get('terminal_status'))
        # No archive fact exists. The status expires, but not the row or its priority.
        self.now += 180_000
        observe()
        late = pending_row()
        self.assertNotIn('terminal_status', late)
        self.assertEqual(('pending', 'retained', 2),
                         (late.get('finalization_status'), late['metric_states']['prompts'], late['prompt_count']))
        self.assertNotIn(key, {item for item, _ in archive.history_rows(SESSIONS)})
        # One Live read may establish the end before a distinct qualified
        # finalization. The forbidden duplicate is a replay *after* publication.
        for _ in range(2):
            self.tick(catalog, source)
            if key in {item for item, _ in archive.history_rows(SESSIONS)}:
                break
        self.assertIn(key, {item for item, _ in archive.history_rows(SESSIONS)})
        last = catalog.page(period='all', sort='name', direction=-1)['view']['session_usage'][-1]
        self.assertEqual((key, True, aborted_at), (last['session_id'], last['indexed'], last['last_activity_ms']))
        self.assertNotIn('finalization_status', last)
        with patch.object(source, 'load_session_snapshot', wraps=source.load_session_snapshot) as reads:
            for _ in range(12):
                self.tick(catalog, source)
        self.assertNotIn(key, [call.args[0] for call in reads.call_args_list])
        self.assertEqual(17, len(list(archive.history_rows(SESSIONS))))
        self.assertTrue(catalog.page(period='all')['history_progress']['complete'])
        del source.snapshots[key]  # Settled history survives even when source membership does not.
        _, reopened = self.restore('one')
        reopened.observe(observe_catalog(source, include_archived_revisions=True))
        rows = {r['session_id']: r for r in reopened.page(period='all')['view']['session_usage']}
        self.assertNotIn(deleted, rows)
        self.assertEqual((False, 2), (rows[key]['running'], rows[key]['prompt_count']))

    def test_active_scalar_uses_only_current_watch_capture_once_and_never_archives_it(self):
        from src.reports.watch_capture import capture_rows
        from src.watch.web_coordinator import publish_catalog_prompts

        source = self.source(1, 2, today_roots=1, now_ms=self.now, running_roots=1)
        source.refresh_observation_epoch = lambda: None  # The synthetic registration stays available.
        archive, catalog = self.restore('one')
        catalog.observe(observe_catalog(source, include_archived_revisions=True))
        key, = source.snapshots
        snapshot = source.snapshots[key]
        service = report_service(source, self.cache, self.now, self.pricing)
        capture, _ = capture_rows(service, snapshot.root, fresh=snapshot)
        entry = SimpleNamespace(snapshot=snapshot, capture=capture, generation=1, verified_generation=1,
            source_status=SimpleNamespace(failed_at=None), cost=SimpleNamespace(evidence=snapshot))
        cards = SimpleNamespace(sessions={key: entry}, source_epoch='one')
        self.assertIsNotNone(capture.catalog_prompt)

        for case in ('current', 'replay', 'wrong-provenance', 'wrong-revision', 'old-epoch', 'incomplete', 'expired'):
            with self.subTest(offer=case):
                if case != 'current':
                    self.now += 5000
                observed_at = self.now
                if case == 'replay':
                    observed_at = capture.observed_at_ms
                elif case == 'expired':
                    observed_at -= 5001
                entry.capture = replace(capture, observed_at_ms=observed_at,
                    source_epoch='previous' if case == 'old-epoch' else 'one')
                if case == 'wrong-provenance':
                    foreign = replace(snapshot.root.provenance, source_instance='foreign')
                    entry.cost.evidence = replace(snapshot, root=replace(snapshot.root, provenance=foreign))
                elif case == 'wrong-revision':
                    entry.cost.evidence = replace(snapshot, source_revision='previous')
                else:
                    entry.cost.evidence = replace(snapshot, complete=case != 'incomplete')
                before = source.load_count
                publish_catalog_prompts(catalog, cards, offer_snapshots=True)
                catalog.tick(report_service(source, self.cache, self.now, self.pricing), fresh_snapshots=True)

                self.assertEqual(0 if case == 'current' else 1, source.load_count - before)
                row, = catalog.page(period='today')['view']['session_usage']
                self.assertEqual((True, 2), (row['running'], row['prompt_count']))
        persisted, _ = SessionArchive(archive).load()
        self.assertNotIn(key, persisted)

    def test_unsaved_running_row_qualifies_each_watch_cost_against_its_source_and_valuation(self):
        from decimal import Decimal
        from src.analysis.session_cost import SessionCost, session_cost_source_key
        from src.analysis.valuation import ComparisonCost
        from src.domain.reference_cost import ReferenceCostIssue
        from src.reports.watch_capture import capture_rows
        from src.watch.session_costs import SessionCostState
        from src.watch.web_coordinator import publish_catalog_prompts

        source = self.source(1, 2, today_roots=1, now_ms=self.now, running_roots=1, children_per_root=1)
        _, catalog = self.restore('one')
        catalog.observe(observe_catalog(source, include_archived_revisions=True))
        snapshot, = source.snapshots.values()
        capture, _ = capture_rows(report_service(source, self.cache, self.now, self.pricing), snapshot.root, fresh=snapshot)
        key = session_cost_source_key(snapshot)
        cost = SessionCost(ComparisonCost(Decimal('18'), 2, 2), True, True, source_revision=snapshot.source_revision,
                           valuation_revision='prices', main_ccost=Decimal('11'), subagent_ccost=Decimal('7'))
        state = SessionCostState(value=cost, source_key=key, validated_key=key, valuation_revision='prices')
        entry = SimpleNamespace(snapshot=snapshot, capture=capture, cost=state, generation=1, verified_generation=1,
                                source_status=SimpleNamespace(failed_at=None))
        cards = SimpleNamespace(sessions={snapshot.root.session_id: entry}, source_epoch='one')

        def observed():
            self.now += 1
            entry.capture = replace(capture, source_epoch='one', observed_at_ms=self.now)
            publish_catalog_prompts(catalog, cards)
            row, = catalog.page(period='today')['view']['session_usage']
            self.assertTrue(row['running'])
            self.assertFalse(row['indexed'])
            return row['ccost'], row['metric_states']['ccost']

        self.assertEqual(('18', 'ready'), observed())
        state.failed = True
        self.assertEqual(('18', 'retained'), observed())
        state.failed = False
        state.value = replace(cost, total=ComparisonCost(Decimal(0), 2, 2))
        self.assertEqual(('0', 'ready'), observed())
        state.value = replace(cost, total=ComparisonCost(observed_requests=2, unavailable=(ReferenceCostIssue('rate'),)))
        self.assertEqual((None, 'unavailable'), observed())
        state.value = cost
        state.validated_key = (*key[:2], 'other-source', *key[3:])
        self.assertEqual((None, 'pending'), observed())
        state.validated_key = key
        state.valuation_revision = 'changed-prices'
        self.assertEqual((None, 'pending'), observed())

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

    def test_today_progress_distinguishes_unread_history_from_refresh_and_live_arrivals(self):
        source = self.source(0, 0)
        _, catalog = self.restore('one')
        def add(index, created):
            snapshot = make_root_snapshot(index, 1, month_start_ms=created - index * 60_000)
            source.snapshots[snapshot.root.session_id] = replace(snapshot, complete=True)
            return snapshot.root.session_id

        def observe():
            catalog.observe(observe_catalog(source, include_archived_revisions=True))

        recent = add(1, self.now - 60_000)
        observe()
        self.assertFalse(catalog.page(period='today')['history_progress']['complete'])
        self.tick(catalog, source)
        settled = catalog.page(period='today')
        self.assertTrue(settled['history_progress']['complete'])
        self.assertEqual([recent], [r['session_id'] for r in settled['view']['session_usage']])

        # Same-source refresh, genuinely new work, and late discovery of a
        # week-only root arrive together. Do not run an archive tick to hide a restart.
        source.snapshots[recent] = replace(source.snapshots[recent], source_revision='new-prompt')
        created = self.now + 1000
        self.now += 2000
        observe()  # This tick misses the Live addition.
        arrival = add(2, created)
        add(3, self.now - 2 * DAY_MS)
        self.now += 3000
        observe()
        for advance in (0, 180_000):
            self.now += advance
            observe()
            self.assertFalse(catalog.page(period='7-days')['history_progress']['complete'])
            self.assertTrue(catalog.page(period='today')['history_progress']['complete'])

        for confirmed in (False, True):
            catalog.observe(None, source_interrupted=confirmed)
            page = catalog.page(period='today')
            self.assertEqual(not confirmed, page['history_progress']['complete'])
            self.assertEqual(confirmed, page['history_progress']['recovering'])
            self.assertEqual([recent], [r['session_id'] for r in page['view']['session_usage']])

        gap = add(4, self.now + 1000)
        self.now += 3000
        observe()
        self.assertFalse(catalog.page(period='today')['history_progress']['complete'])
        for _ in range(3):
            self.tick(catalog, source)
        recovered = catalog.page(period='today')
        self.assertTrue(recovered['history_progress']['complete'])
        self.assertEqual({recent, arrival, gap}, {r['session_id'] for r in recovered['view']['session_usage']})

    def test_short_prompt_discovered_and_finished_before_history_catches_up(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        from unittest.mock import Mock
        from src.reports.session_summary import session_summary
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
        self.assertEqual('completed', pending.get('terminal_status'))
        transitioned = self.now
        self.now += 6000
        self.tick(catalog, source)
        verified, older = rows()
        self.assertEqual((key, 'completed', end, 2, 'ready'),
            (verified['session_id'], verified.get('terminal_status'), verified['last_activity_ms'],
             verified['prompt_count'], verified['metric_states']['prompts']))
        self.assertNotIn('finalization_status', verified)
        # Re-observing the end while already final does not renew the display interval.
        self.now = transitioned + 29_999
        publish(final)
        self.assertEqual('completed', rows()[0].get('terminal_status'))
        self.now += 1
        older, verified = rows()
        self.assertEqual((peer, key, end), (older['session_id'], verified['session_id'], verified['last_activity_ms']))
        self.assertNotIn('terminal_status', verified)

    def test_next_running_prompt_supersedes_abort_and_failure_does_not_inherit_it(self):
        _, catalog = self.restore('one')
        source = self.source(0, 0)
        def publish(snapshot):
            source.snapshots[snapshot.root.session_id] = snapshot
            catalog.observe(observe_catalog(source, include_archived_revisions=True))
            service = report_service(source, self.cache, self.now, self.pricing)
            capture, _ = capture_rows(service, snapshot.root, fresh=snapshot)
            publish_verified_capture(catalog, snapshot, capture)
            row, = catalog.page(period='all')['view']['session_usage']
            return row

        start = self.now
        for prompts, outcome, label in ((1, TerminalOutcome.CANCELLATION, 'aborted'),
                                        (2, TerminalOutcome.FAILURE, None)):
            self.now += 1_000
            snapshot = self.source(1, prompts, today_roots=1, running_roots=1,
                                   now_ms=start + 3_600_000).snapshots['root-0000']
            running = publish(replace(snapshot, source_revision=f'run-{prompts}'))
            self.assertEqual((True, snapshot.events[-1].created_at_ms, None),
                             (running['running'], running['prompt_started_ms'], running.get('terminal_status')))
            self.now += 100
            root = replace(snapshot.root, active=False)
            ended = publish(replace(snapshot, root=root, sessions=(root,), source_revision=f'end-{prompts}',
                messages=(*snapshot.messages[:-1], replace(snapshot.messages[-1], completed_at_ms=self.now,
                    termination=TerminalEvidence(self.now, outcome)))))
            self.assertEqual((False, snapshot.events[-1].created_at_ms, label),
                             (ended['running'], ended['prompt_started_ms'], ended.get('terminal_status')))


if __name__ == '__main__':
    unittest.main()
