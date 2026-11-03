"""Causal cancellation at the Web owner's real source-read boundary."""
import http.client
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import sys
from threading import Event, Thread
import threading
import time
import traceback
import unittest

from development.tests.fixtures.watch_runtime import MutableSource, make_service
from src.sources.opencode_v2_transport import V2Endpoint, V2HttpClient
from src.watch.acquisition import LiveAcquisition
from src.watch.web_coordinator import WebWatchCoordinator
from src.web.host import WebHost
from src.web.jobs import ReportJobs
from src.reports import ReportRequest


def pending_report(sender, request):
    sender.send(('progress', {'phase': 'history', 'completed': 0, 'total': None}))
    Event().wait(60)


class PendingSource(MutableSource):
    def __init__(self, client):
        super().__init__()
        self.client = client

    def load_session_snapshot(self, session_id):
        self.client.json('/snapshot', phase='snapshot')
        return super().load_session_snapshot(session_id)

    def cancel_reads(self):
        self.client.cancel()


class WebShutdownTests(unittest.TestCase):
    def test_stop_interrupts_pending_history_and_card_http_reads_before_join(self):
        self.pending_reads('headers', 1)

    def test_stop_interrupts_detached_body_detail_and_report_with_two_streams(self):
        self.pending_reads('body', 2)

    def pending_reads(self, phase, stream_count):
        entered, release, closed = Event(), Event(), Event()

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if phase == 'body':
                    self.send_response(200)
                    self.send_header('Content-Length', '2')
                    self.end_headers()
                    self.wfile.write(b'{')
                    self.wfile.flush()
                entered.set()
                release.wait(15)
                try:
                    if phase == 'headers':
                        self.send_response(200)
                        self.send_header('Content-Length', '2')
                        self.end_headers()
                        self.wfile.write(b'{}')
                    else:
                        self.wfile.write(b'}')
                except OSError:
                    pass

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        serving = Thread(target=server.serve_forever)
        serving.start()
        clients, errors = [], []
        with tempfile.TemporaryDirectory() as tmp:
            source = MutableSource()
            config, selection, service, _ = make_service(tmp, source)

            def factory(now):
                endpoint = V2Endpoint(f'http://127.0.0.1:{server.server_port}', '2.0', 0, '', None, Path(tmp))
                client = V2HttpClient(endpoint)
                clients.append(client)
                return make_service(tmp, PendingSource(client), now_ms=now)[2]

            coordinator = WebWatchCoordinator(selection=selection, report_service=service,
                config=config, service_factory=factory, clock_ms=lambda: 2200)
            host = WebHost(Path(tmp), jobs=ReportJobs(target=pending_report), live_factory=lambda: LiveAcquisition(coordinator))
            streams = []

            def request(path, value=None, cookie=None, csrf=None):
                connection = http.client.HTTPConnection('127.0.0.1', host.server.server_port, timeout=3)
                headers = dict(Host=host.server.host)
                if cookie:
                    headers['Cookie'] = cookie
                if value is not None:
                    headers.update(Origin=host.server.origin, **{'Content-Type': 'application/json'})
                if csrf:
                    headers['X-CG-CSRF'] = csrf
                try:
                    connection.request('GET' if value is None else 'POST', path,
                        None if value is None else json.dumps(value), headers)
                    response = connection.getresponse()
                    return response, json.loads(response.read())
                finally:
                    connection.close()

            def close():
                try:
                    host.close()
                except BaseException as error:
                    errors.append(error)
                finally:
                    closed.set()

            closing = Thread(target=close)
            try:
                host.start()
                self.assertTrue(entered.wait(3), 'source request reached the real socket read')
                response, auth = request('/api/bootstrap', {'credential': host.server.session.bootstrap()})
                cookie = response.getheader('Set-Cookie').split(';')[0]
                for _ in range(stream_count):
                    connection = http.client.HTTPConnection('127.0.0.1', host.server.server_port, timeout=3)
                    connection.request('GET', '/api/events', headers={'Cookie': cookie})
                    response = connection.getresponse()
                    self.assertIn(b'retry:', response.readline())
                    streams.append((connection, response))
                if phase == 'body':
                    _, detail = request('/api/detail', dict(action='open', session_id=source.snapshot.root.session_id,
                        mode='live'), cookie, auth['csrf'])
                    key = host.jobs.submit(ReportRequest())
                    until = time.monotonic() + 3
                    while time.monotonic() < until and (len(clients) < 3 or host.jobs.snapshot(key)['progress']['phase'] != 'history'):
                        time.sleep(.01)
                    self.assertGreaterEqual(len(clients), 3, 'history, card and detail lanes entered')
                    self.assertEqual('running', host.jobs.snapshot(key)['status'])
                    self.assertEqual('history', host.jobs.snapshot(key)['progress']['phase'])
                started = time.monotonic()
                closing.start()
                completed = closed.wait(2)
                stacks = {t.name: [(Path(f.filename).name, f.name, f.lineno)
                    for f in traceback.extract_stack(sys._current_frames()[t.ident])[-7:]]
                    for t in threading.enumerate() if t.ident in sys._current_frames()} if not completed else {}
                self.assertTrue(completed, f'stop must cancel owned reads, not join their source timeout: {stacks}')
                self.assertLess(time.monotonic() - started, 2)
                self.assertEqual([], errors)
                self.assertFalse(host.live.thread.is_alive())
                self.assertFalse(host.thread.is_alive())
                self.assertTrue(all(f.done() for f in coordinator.card_workers.jobs.values()))
                self.assertIsNone(host.jobs._active)
                self.assertTrue(coordinator.history_job.done())
                if phase == 'body':
                    self.assertTrue(coordinator.detail_job.done())
                host.close()
            finally:
                release.set()
                if closing.ident is not None:
                    closing.join(12)
                host.close()
                for connection, response in streams:
                    response.close()
                    connection.close()
                for client in clients:
                    client.close()
                server.shutdown()
                server.server_close()
                serving.join(2)


if __name__ == '__main__':
    unittest.main()
