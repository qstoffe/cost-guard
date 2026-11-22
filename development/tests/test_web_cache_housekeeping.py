"""Demand delivery and real SQLite work behind virtual host uptime/idle evidence."""
from dataclasses import replace
from pathlib import Path
from threading import Event
from types import SimpleNamespace
import tempfile
import shutil
import subprocess
import unittest
from unittest.mock import Mock, patch

from development.tests.fixtures.session_snapshots import make_snapshot
from src.application.session_catalog import SessionCatalog
from src.application.session_detail import SessionDetails
from src.cache import CacheDatabase, CacheRepository
from src.cache.lifecycle import CacheLifecycle
from src.cache.session_scope import SessionScope, root_key
from src.reports import ReportRequest
from src.watch.observers import CatalogObservation
from src.web.cache_housekeeping import CacheHousekeeping
from src.web.dispatch import DataDispatcher
from src.web.dispatch_http import handle
from src.web.host import WebHost

NOW = 1_800_000_000_000
OLD = NOW - 40 * 86_400_000


class WebCacheHousekeepingTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'node unavailable')
    def test_shipped_browser_api_marks_only_selected_visible_demand_including_hidden_opener_pip(self):
        result = subprocess.run([shutil.which('node'), 'development/tests/integration/cache_demand.cjs'],
            cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=10)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        database = CacheDatabase(Path(temporary.name))
        database.initialize()
        self.repository = CacheRepository(database)
        self.now = 0
        self.wall = OLD / 1000
        self.lifecycle = CacheLifecycle(database, wall_clock=lambda: self.wall)
        self.work = CacheHousekeeping(database.package_root, clock=lambda: self.now, lifecycle=self.lifecycle)
        root = replace(make_snapshot().root, active=False)
        self.root = root
        self.digest = root_key(root.provenance, root.session_id)
        self.repository.put('derived-analysis', 'key', 42, source_revision='r', session_scope=SessionScope(self.digest, OLD))
        self.lifecycle.note_use([self.digest])
        self.lifecycle.flush()
        self.wall = NOW / 1000
        catalog = SessionCatalog(clock=lambda: self.now)
        self.coordinator = SimpleNamespace(card_workers=SimpleNamespace(jobs={}),
            session_costs=SimpleNamespace(job=None), history_job=None, detail_job=None, catalog_job=None,
            report_service=SimpleNamespace(accounts_pending=False), _last_projection=None, catalog_observation=None)
        driver = SimpleNamespace(coordinator=self.coordinator, error=None, resync=False, hints=set(),
            monotonic=lambda: self.now, deadline=1_000_000, frame=None)
        live = SimpleNamespace(driver=driver, catalog=catalog, details=SessionDetails(clock=lambda: self.now),
            observed=Event(), working=Event())
        live.observed.set()
        jobs = Mock()
        jobs.updates.return_value = {'jobs': []}
        dispatcher = DataDispatcher(jobs, clock=lambda: self.now)
        dispatcher.identity = 'source'
        self.host = SimpleNamespace(live=live, dispatcher=dispatcher, jobs=jobs, stopping=Event(), cache_housekeeping=self.work)
        self.fresh()
        self.work.start()

    def fresh(self, *, revision='r', active=False):
        observation = CatalogObservation((self.root,), (self.root,), {self.root.session_id: self.root.session_id},
            {self.root.session_id: revision}, frozenset({self.root.session_id}) if active else frozenset())
        self.coordinator.catalog_observation = observation
        self.host.live.catalog.observe(observation)

    def cached(self):
        return self.repository.get('derived-analysis', 'key')

    def result(self):
        return {'result': {'view': {'kind': 'normal'}, 'source': {'identity': 'source',
            'revisions': [{'session_id': self.root.session_id, 'revision': 'exported-hash-not-native-r'}]}}}

    def test_first_job_delivery_warm_data_and_retained_interest_are_meaningful_not_passive_warming(self):
        # Mere dispatcher collection/probe work has no demand callback.
        self.host.dispatcher._entry(ReportRequest()).update(result=self.result()['result'], finished=0, due=100)
        self.assertFalse(self.lifecycle.pending)
        self.work.delivered(self.host, '/api/jobs/' + 'a' * 32, self.result())
        self.assertIn(self.digest, self.lifecycle.pending)
        self.lifecycle.flush()
        self.wall += 3601
        self.work.delivered(self.host, '/api/data', self.result())
        self.assertIn(self.digest, self.lifecycle.pending)
        self.lifecycle.flush()
        self.wall += 3601
        handler = SimpleNamespace(path='/api/interest', server=SimpleNamespace(lifecycle=self.host),
            headers={'X-CG-Viewed': '1'}, reply=Mock())
        handle(handler, {'tab': 'a' * 32, 'section': 'models', 'visible': True, 'request': {'kind': 'normal'}})
        self.assertIn(self.digest, self.lifecycle.pending)
        self.lifecycle.flush()
        self.wall += 3601
        changed = self.result()
        changed['result']['source']['identity'] = 'another-source'
        self.work.delivered(self.host, '/api/data', changed)
        handler.headers = {}
        handle(handler, {'tab': 'a' * 32, 'section': 'models', 'visible': True, 'request': {'kind': 'normal'}})
        self.assertFalse(self.lifecycle.pending, 'source restart and headerless probes cannot renew unrelated cache')

    def test_prune_waits_for_continuous_host_uptime_and_does_not_repeat_daily_attempt(self):
        self.now = 3599
        self.fresh()
        self.work.tick(self.host)
        self.assertIsNotNone(self.cached())
        self.now = 3600
        self.fresh()
        self.work.tick(self.host)
        self.assertIsNone(self.cached())
        self.assertEqual(90000, self.work.due)
        with patch.object(self.lifecycle, 'prune') as prune:
            self.now += 1
            self.work.tick(self.host)
        prune.assert_not_called()

    def test_idle_defers_for_real_requests_live_foreground_acquisition_provider_pressure_and_stale_source(self):
        self.now = 3600
        self.fresh()
        with self.work.request('/api/data'):
            self.work.tick(self.host)
        self.assertIsNotNone(self.cached())
        pressures = [(self.host.live, 'working', Event()), (self.coordinator, 'history_job', object()),
            (self.coordinator, 'detail_job', object()), (self.coordinator, 'catalog_job', object()),
            (self.coordinator.report_service, 'accounts_pending', True),
            (self.coordinator.card_workers, 'jobs', {'pending': object()}),
            (self.coordinator.session_costs, 'job', object()), (self.host.live.driver, 'resync', True)]
        pressures[0][2].set()
        for target, name, value in pressures:
            with self.subTest(pressure=name), patch.object(target, name, value):
                self.work.tick(self.host)
                self.assertIsNotNone(self.cached())
        self.host.jobs.updates.return_value = {'jobs': [{'status': 'running'}]}
        self.work.tick(self.host)
        self.assertIsNotNone(self.cached())
        self.host.jobs.updates.return_value = {'jobs': []}
        self.host.dispatcher.tabs['tab'] = {'visible': True, 'request': ReportRequest(), 'section': 'models'}
        self.work.tick(self.host)
        self.assertIsNotNone(self.cached())
        self.host.dispatcher.tabs.clear()
        self.now += 16
        self.work.tick(self.host)
        self.assertIsNotNone(self.cached(), 'repeated publication must not refresh the source observation age')
        self.fresh()
        with self.work.request('/api/events'):
            self.work.tick(self.host)
        self.assertIsNone(self.cached(), 'a permanent SSE stream is not foreground pressure')

    def test_current_active_child_or_changed_revision_prevents_stale_eviction(self):
        self.now = 3600
        self.fresh(active=True)
        self.work.tick(self.host)
        self.assertIsNotNone(self.cached())
        self.now = self.work.due
        self.fresh(revision='changed-child')
        self.work.tick(self.host)
        self.assertIsNotNone(self.cached())

    def test_shutdown_source_change_and_new_request_cancel_before_mutation(self):
        self.now = 3600
        self.fresh()
        original = self.lifecycle.prune
        for effect in (lambda: self.host.stopping.set(), lambda: self.fresh(revision='new'),
                lambda: setattr(self.work, 'epoch', self.work.epoch + 1)):
            self.work.due = self.now
            self.host.stopping.clear()
            self.fresh()
            def interrupted(revisions, *, allowed):
                effect()
                return original(revisions, allowed=allowed)
            with patch.object(self.lifecycle, 'prune', side_effect=interrupted):
                self.work.tick(self.host)
            self.assertIsNotNone(self.cached())

    def test_normal_close_drains_queued_meaningful_use_without_waiting_for_next_host_tick(self):
        host = WebHost(self.repository.database.package_root, jobs=Mock())
        host.cache_housekeeping.lifecycle = self.lifecycle
        self.wall = NOW / 1000
        self.lifecycle.note_use([self.digest])

        host.close()

        self.assertFalse(self.lifecycle.pending)
        with self.repository.database.connect() as connection:
            self.assertEqual(NOW, connection.execute('SELECT used_ms FROM cache_entry_lifecycle').fetchone()[0])


if __name__ == '__main__':
    unittest.main()
