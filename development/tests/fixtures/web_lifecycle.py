"""Finite synthetic end-to-end Web cycle, real acquisition/HTTP/SSE/job owners."""
from decimal import Decimal
import http.client
import json
import multiprocessing
from pathlib import Path
import tempfile
import threading
import time

from .synthetic_month import SyntheticMonthSource
from .watch_runtime import make_service
from src.reports import ReportKind, ReportRequest
from src.sources.errors import transport_failure
from src.watch.acquisition import LiveAcquisition
from src.watch.web_coordinator import WebWatchCoordinator
from src.web.host import WebHost
from src.web.jobs import ReportJobs


def competing_work(stop):
    value = [dict(count=n, words='synthetic' * 20) for n in range(2000)]
    while not stop.is_set():
        json.loads(json.dumps(value))


def pending_report(sender, request):
    sender.send(('progress', dict(phase='history', completed=0, total=None)))
    threading.Event().wait(60)  # The real job owner must terminate this pending capture.


def run_cycle(*, competing=False, failed_daily=False, http_timeout=False, deep_date=False):
    before_threads = set(threading.enumerate())
    before_children = {child.pid for child in multiprocessing.active_children()}
    started = time.monotonic()
    with tempfile.TemporaryDirectory() as tmp:
        source = SyntheticMonthSource(3, 2, month_start_ms=1000)
        config, selection, service, _ = make_service(tmp, source, now_ms=80_000_000)

        def factory(now):
            if failed_daily:
                raise transport_failure(TimeoutError(), phase='snapshot')
            return make_service(tmp, SyntheticMonthSource(3, 2, month_start_ms=1000), now_ms=now)[2]

        coordinator = WebWatchCoordinator(selection=selection, report_service=service,
            config=config, service_factory=factory, clock_ms=lambda: 80_000_000)
        from .historical_reports import blocked_date_report
        host = WebHost(Path(tmp), jobs=ReportJobs(target=blocked_date_report if deep_date else pending_report),
            live_factory=lambda: LiveAcquisition(coordinator))
        streams, cookie, csrf = [], None, None
        requests = []

        def get(path, value=None):
            request_started = time.monotonic()
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
                result = json.loads(response.read())
                assert response.status in (200, 202), response.status
                return response, result
            finally:
                requests.append(time.monotonic() - request_started)
                connection.close()

        try:
            host.start()
            response, auth = get('/api/bootstrap', dict(credential=host.server.session.bootstrap()))
            cookie = response.getheader('Set-Cookie').split(';')[0]
            csrf = auth['csrf']
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                _, state = get('/api/live')
                view = (state['values'].get('live') or {}).get('view') or {}
                if failed_daily and view.get('daily_state') == 'unavailable':
                    assert view.get('daily_usage') is None
                    break
                if not failed_daily and view.get('daily_usage') and view.get('history_cards'):
                    break
                time.sleep(.01)
            else:
                raise AssertionError('synthetic publication deadline')
            daily_seconds = time.monotonic() - started
            if not failed_daily:
                daily = view['daily_usage']
                assert daily['mix']['request_count'] == daily['total']['observed_requests'] == 6
                assert daily['prompt_count'] == 6
                assert sum(Decimal(value) for value in daily['mix']['costs']) == Decimal(daily['total']['known_ccost'])
                assert all(len(card['rows']) == 1 for card in view['history_cards'])
            for _ in range(2 if competing else 1):
                connection = http.client.HTTPConnection('127.0.0.1', host.server.server_port, timeout=3)
                connection.request('GET', '/api/events', headers=dict(Cookie=cookie,
                    **{'Last-Event-ID': f'{state["instance_id"]}:{state["sequence"]}'}))
                response = connection.getresponse()
                assert response.status == 200 and b'retry:' in response.readline()
                streams.append((connection, response))
            host.events.publish('cycle', {'value': 1})
            for _, response in streams:
                frame = []
                while not any(line.startswith(b'event: cycle') for line in frame):
                    line = response.readline()
                    assert line, 'stream ended before publication'
                    frame.append(line)
                identity = next(line for line in reversed(frame) if line.startswith(b'id: '))
                instance, sequence = identity.decode().strip()[4:].rsplit(':', 1)
                assert instance == state['instance_id'] and int(sequence) > state['sequence']
            if competing or deep_date:
                request = ReportRequest(ReportKind.DATE, date_text='2026-10-25') if deep_date else ReportRequest()
                key = host.jobs.submit(request)
                until = time.monotonic() + 5
                def ready():
                    progress = host.jobs.snapshot(key)['progress']
                    return (progress.get('stage') == 'date-messages' and progress['completed'] >= 4
                            if deep_date else progress['phase'] == 'history')
                while time.monotonic() < until and not ready():
                    time.sleep(.01)
                assert host.jobs.snapshot(key)['status'] == 'running'
                assert ready()
                host.jobs.cancel(key)
                assert host.jobs.snapshot(key)['status'] == 'cancelled'
            if http_timeout:
                # A genuinely blocked authenticated snapshot request must time
                # out, never be recorded as an empty/successful Daily result.
                with host.events.condition:
                    try:
                        get('/api/live')
                    except TimeoutError:
                        pass
                    else:
                        raise AssertionError('expected real HTTP timeout')
            close_started = time.monotonic()
        finally:
            host.stop()
            host.close()
            for connection, response in streams:
                response.close()
                connection.close()
        close_seconds = time.monotonic() - close_started
        host.close()
        assert not host.failure and not host.thread.is_alive() and not host.live.thread.is_alive()
        assert close_seconds < 10
        assert all(future.done() for future in coordinator.card_workers.jobs.values())
        assert coordinator.history_job is None or coordinator.history_job.done()
        assert not ({child.pid for child in multiprocessing.active_children()} - before_children)
        assert not [thread.name for thread in threading.enumerate() if thread not in before_threads]
        return dict(daily_seconds=round(daily_seconds, 4), close_seconds=round(close_seconds, 4),
            max_http_seconds=round(max(requests), 4), failed_daily=failed_daily,
            streams=len(streams), competing=competing, owned_threads=0, owned_processes=0)
