"""Deterministic global live parity, bounded transport and host ownership."""
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import http.client
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from threading import Event, Thread
import time
import unittest
from unittest.mock import Mock, patch

from development.tests.fixtures.session_snapshots import make_snapshot, make_uncompacted_snapshot
from development.tests.fixtures.watch_runtime import MutableSource, make_service
from src.application.live import LiveRuntime
from src.application.live_projection import project_live
from src.sources.errors import SourceUnavailableError, SourceSchemaError
from src.web.events import EventHub, MAX_REPLAY_BYTES
from src.web.host import WebHost
from src.web.jobs import ReportJobs
from src.watch.acquisition import LiveAcquisition
from src.watch.coordinator import WatchCoordinator
from src.watch.observers import LiveEventPump, PumpResult
from src.sources.base import SourceChange
from src.reports import ReportRequest

ROOT = Path(__file__).resolve().parents[2]


def slow_report(sender, request):
    sender.send(('progress', {'phase': 'acquiring', 'completed': 0, 'total': None}))
    time.sleep(10)  # Killable finite report, never source/model/network work.


class LiveTests(unittest.TestCase):
    def owner(self, root, snapshot=None, clock=None):
        source = MutableSource(snapshot or make_snapshot())
        config, selection, service, _ = make_service(root, source)
        owner = WatchCoordinator(selection=selection, report_service=service, config=config,
                                 clock_ms=clock or (lambda: 2200))
        self.addCleanup(owner.close)
        return source, owner

    def test_web_and_cli_share_canonical_values_through_terminal_transition(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            clock = [2200]
            source, owner = self.owner(a, clock=lambda: clock[0])
            cli_source, cli = self.owner(b, clock=lambda: clock[0])
            monotonic = [0]
            driver = LiveAcquisition(owner, monotonic=lambda: monotonic[0])
            web = driver.tick()
            expected = cli.initialize(defer_history=True).projection
            # Same canonical live/CLI values, including compaction/child/background fields.
            for field in ('rows', 'run_total', 'token_mix', 'today_total', 'session_subtotals'):
                self.assertEqual(getattr(expected, field), getattr(web, field), field)
            frozen = project_live(web)
            payload = frozen.to_json()
            self.assertEqual(str(web.rows[0].prompt.ccost), payload['rows'][0]['prompt']['ccost'])
            self.assertEqual(2200, payload['started_at_ms'])
            source.snapshot = cli_source.snapshot = replace(make_snapshot(running=False), source_revision='terminal')
            clock[0] = 8200
            monotonic[0] = 6
            web = driver.tick()
            expected = cli.poll_once().projection
            self.assertEqual(expected.rows, web.rows)
            self.assertEqual(expected.run_total, web.run_total)
            self.assertEqual(2200, web.watch_started_at_ms)
            self.assertEqual(payload, frozen.to_json(), 'published result is detached from subsequent cycles')

    def test_subscribers_replay_and_resync_do_not_acquire_or_reset_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, owner = self.owner(tmp)
            driver = LiveAcquisition(owner)
            frame = driver.tick()
            hub = EventHub('instance', capacity=2)
            hub.publish('live', {'state': 'running', 'view': project_live(frame).to_json()})
            reads = source.load_count
            first, second = hub.snapshot(), hub.snapshot()
            self.assertEqual(first, second)
            first['values'].clear()
            self.assertIn('live', hub.snapshot()['values'])
            for n in range(5):
                hub.publish('progress', {'n': n})
            _, frames = hub.read('instance:1', timeout=0)
            self.assertIn(b'event: resync', frames[0])
            _, frames = hub.read('old-instance:6', timeout=0)
            self.assertIn(b'event: resync', frames[0])
            number, frames = hub.read('instance:5', timeout=0)
            self.assertEqual(6, number)
            self.assertEqual(1, len(frames))
            self.assertEqual(reads, source.load_count)
            self.assertEqual(frame.watch_started_at_ms, hub.snapshot()['values']['live']['view']['started_at_ms'])
            self.assertLessEqual(hub.bytes, MAX_REPLAY_BYTES)
            hub.close('source_changed')
            self.assertIn('terminal', hub.snapshot()['values'])

    def test_source_outage_retains_active_frame_and_recovers_same_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, owner = self.owner(tmp)
            clock = [0]
            driver = LiveAcquisition(owner, monotonic=lambda: clock[0])
            initial = driver.tick()
            original = source.list_sessions
            source.list_sessions = Mock(side_effect=SourceUnavailableError('private transport details'))
            clock[0] = 31
            outage = driver.tick()
            self.assertEqual(initial.rows, outage.rows)
            self.assertFalse(driver.terminal)
            self.assertNotIn('private', project_live(outage).to_json()['status'])
            clock[0] = 32
            self.assertEqual(outage.rows, driver.tick().rows)
            self.assertEqual(1, source.list_sessions.call_count)
            source.list_sessions = original
            clock[0] = 37
            recovered = driver.tick()
            self.assertIsNone(driver.error)
            self.assertEqual(initial.watch_started_at_ms, recovered.watch_started_at_ms)
            source.list_sessions = Mock(side_effect=SourceSchemaError('unsupported'))
            clock[0] = 100
            driver.tick()
            self.assertTrue(driver.terminal)

    def test_hint_overflow_is_bounded_and_requires_authoritative_resync(self):
        pump = LiveEventPump(Mock())
        for _ in range(5000):
            pump._put(PumpResult())
        self.assertLessEqual(pump._queue.qsize(), 1024)
        self.assertTrue(pump.get(0).resync_required)

    def test_hints_request_fresh_authority_and_never_complete_a_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, owner = self.owner(tmp, make_uncompacted_snapshot(running=True))
            now = [0]
            driver = LiveAcquisition(owner, monotonic=lambda: now[0])
            first = driver.tick()
            pump = LiveEventPump(Mock())
            owner._event_pump = pump
            pump._put(PumpResult(resync_required=True))
            # A lost event stream is not prompt completion or invented usage.
            now[0] = 1
            waiting = driver.tick()
            self.assertEqual(first.active_count, waiting.active_count)
            now[0] = 7
            reads = source.load_count
            fresh = driver.tick()
            self.assertGreater(source.load_count, reads)
            self.assertEqual(first.active_count, fresh.active_count)
            self.assertEqual(first.run_total, fresh.run_total)

    def test_account_only_publication_does_not_read_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, owner = self.owner(tmp)
            now = [0]
            driver = LiveAcquisition(owner, monotonic=lambda: now[0])
            driver.tick()
            while owner.today_ccost.history_pending:
                driver.tick()
            reads, scans = source.load_count, source.batch_calls
            account = owner.accounts.snapshots[0]
            quotas = tuple(replace(q, remaining=Decimal('42')) for q in account.quotas)
            owner.accounts.snapshots = (replace(account, quotas=quotas),)
            now[0] = 1
            with patch.object(owner.accounts, 'refresh', return_value=True):
                frame = driver.tick()
            payload = project_live(frame).to_json()
            self.assertEqual('42', payload['accounts']['accounts'][0]['observation']['quotas'][0]['remaining'])
            self.assertEqual((reads, scans), (source.load_count, source.batch_calls))

    def test_midnight_dst_and_partial_pricing_preserve_canonical_scopes(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            clock = [int(datetime(2026, 10, 24, 21, 59, tzinfo=timezone.utc).timestamp() * 1000)]
            _, web = self.owner(a, clock=lambda: clock[0])
            _, cli = self.owner(b, clock=lambda: clock[0])
            for owner in (web, cli):
                owner.report_service.config['timezone'] = 'Europe/Stockholm'
                owner.today_ccost.timezone_id = 'Europe/Stockholm'
                pricing = owner.report_service.pricing_provider
                pricing.catalog = replace(pricing.catalog, models=())
            monotonic = [0]
            driver = LiveAcquisition(web, monotonic=lambda: monotonic[0])
            for hours in (0, 1, 3, 4, 27):
                clock[0] += hours * 3600000
                monotonic[0] += 3600
                actual = driver.tick()
                expected = cli.acquire_cycle().projection
                exported = project_live(actual).to_json()
                self.assertEqual(expected.today_label, exported['today_label'])
                self.assertEqual(expected.today_total, actual.today_total)
                self.assertEqual(expected.run_total, actual.run_total)
                self.assertEqual(expected.run_total.cost_complete, exported['run_total']['cost_complete'])
                self.assertNotIn('comparison_month', exported['accounts'])
                self.assertNotIn('billed_month', exported['accounts']['accounts'][0])

    def test_partial_pricing_exports_known_subtotal_without_priced_zero_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, owner = self.owner(tmp, make_uncompacted_snapshot(running=True))
            pricing = owner.report_service.pricing_provider
            pricing.catalog = replace(pricing.catalog, models=())
            frame = LiveAcquisition(owner).tick()
            payload = project_live(frame).to_json()
            self.assertGreater(payload['run_total']['request_count'], 0)
            self.assertFalse(payload['run_total']['cost_complete'])
            self.assertLess(payload['run_total']['priced_requests'], payload['run_total']['request_count'])

    def test_runtime_software_fault_stops_host_and_preserves_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            error = RuntimeError('private payload must not be serialized')
            driver = Mock()
            driver.tick.side_effect = error
            host = WebHost(Path(tmp), jobs=ReportJobs(), live_factory=lambda: driver)
            host.start()
            self.assertTrue(host.stopped.wait(3))
            host.close()
            self.assertIs(error, host.failure)
            self.assertEqual('runtime_fault', host.reason)
            self.assertNotIn('private payload', json.dumps(host.events.snapshot()))
            self.assertFalse(host.live.thread.is_alive())
            driver.close.assert_called_once()

    @unittest.skipUnless(shutil.which('node'), 'optional JavaScript VM unavailable')
    def test_client_ordering_offline_terminal_and_safe_live_presentation(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot = make_snapshot()
            snapshot = replace(snapshot, root=replace(snapshot.root, title='<img src=x> Å日本語'))
            _, owner = self.owner(tmp, snapshot)
            frame = owner.acquire_cycle().projection
            payload = {'state': 'running', 'view': project_live(frame).to_json()}
            result = subprocess.run([shutil.which('node'), 'development/tests/integration/web_live.cjs'],
                cwd=ROOT, input=json.dumps(payload), text=True, capture_output=True, timeout=15)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn('web live passed', result.stdout)

    def test_runtime_survives_zero_subscribers_and_closes_one_owner(self):
        ticked = Event()
        driver = Mock()
        driver.error = None
        driver.observed_at_ms = None
        driver.terminal = False
        driver.coordinator.today_ccost.history_pending = False
        driver.tick.side_effect = lambda: ticked.set()
        factory = Mock(return_value=driver)
        runtime = LiveRuntime(factory, Mock())
        runtime.start()
        self.assertTrue(ticked.wait(2))
        runtime.close()
        self.assertFalse(runtime.thread.is_alive())
        factory.assert_called_once()
        driver.close.assert_called_once()

    def test_authenticated_stream_and_stop_remain_responsive_beside_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            jobs = ReportJobs(target=slow_report)
            owner = WebHost(Path(tmp), jobs=jobs)
            owner.start()
            self.addCleanup(owner.close)
            server = owner.server
            key = jobs.submit(ReportRequest())
            until = time.monotonic() + 3
            while jobs.snapshot(key)['status'] != 'running' and time.monotonic() < until:
                time.sleep(0.01)
            self.assertEqual('running', jobs.snapshot(key)['status'])

            def request(path, *, method='GET', value=None, cookie=None):
                connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
                headers = {'Host': server.host}
                if cookie:
                    headers['Cookie'] = cookie
                if value is not None:
                    headers.update(Origin=server.origin, **{'Content-Type': 'application/json'})
                connection.request(method, path, json.dumps(value) if value is not None else None, headers)
                response = connection.getresponse()
                data = response.read()
                connection.close()
                return response, data

            response, _ = request('/api/events')
            self.assertEqual(401, response.status)
            response, _ = request('/api/bootstrap', method='POST', value={'credential': server.session.bootstrap()})
            cookie = response.getheader('Set-Cookie').split(';')[0]
            owner.events.publish('live', {'state': 'running', 'view': None})
            streams = []
            try:
                for _ in range(4):
                    connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
                    connection.request('GET', '/api/events', headers={'Cookie': cookie})
                    response = connection.getresponse()
                    self.assertEqual(200, response.status)
                    self.assertIn(b'retry:', response.readline())
                    streams.append((connection, response))
                response, data = request('/api/live', cookie=cookie)
                self.assertEqual(200, response.status)
                self.assertEqual(owner.nonce, json.loads(data)['instance_id'])
                response, _ = request('/api/events', cookie=cookie)
                self.assertEqual(429, response.status)
                start = time.monotonic()
                owner.stop('source_changed')
                terminal = b''.join(streams[0][1].readlines())
                self.assertIn(b'event: terminal', terminal)
                self.assertIn(b'source_changed', terminal)
            finally:
                for connection, _ in streams:
                    connection.close()
            owner.close()
            self.assertFalse(owner.thread.is_alive())
            self.assertLess(time.monotonic() - start, 3)
            self.assertIsNone(jobs._active)


if __name__ == '__main__':
    unittest.main()
