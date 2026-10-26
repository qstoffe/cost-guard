"""Bounded read-only real-installation probe; no UI, inference or service stop."""
import http.client
import argparse
import json
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.web.composition import live_acquisition
from src.web.host import WebHost
from src.web.jobs import ReportJobs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--detail", action="store_true", help="Also probe complete session capture/pages/freeze.")
    parser.add_argument("--reports", action="store_true", help="Also capture finite reports beside Live and cancel deep history.")
    args = parser.parse_args()
    owners = []
    csrf = None

    def factory():
        driver = live_acquisition()
        owners.append(driver)
        return driver

    started = time.monotonic()
    host = WebHost(ROOT, jobs=ReportJobs(), live_factory=factory)
    streams = []
    try:
        host.start()
        shell_seconds = time.monotonic() - started
        server = host.server

        def get(path, *, value=None, cookie=None):
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
            headers = {'Host': server.host}
            if cookie:
                headers['Cookie'] = cookie
            if value is not None:
                headers.update(Origin=server.origin, **{'Content-Type': 'application/json'})
                if csrf:
                    headers['X-CG-CSRF'] = csrf
            connection.request('POST' if value is not None else 'GET', path,
                               json.dumps(value) if value is not None else None, headers)
            response = connection.getresponse()
            data = json.loads(response.read())
            connection.close()
            if response.status not in {200, 202}:
                raise RuntimeError('probe_http_failed')
            return data, response

        auth, response = get('/api/bootstrap', value={'credential': server.session.bootstrap()})
        csrf = auth['csrf']
        cookie = response.getheader('Set-Cookie').split(';')[0]
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            state, _ = get('/api/live', cookie=cookie)
            live = state['values'].get('live', {})
            if live.get('view'):
                break
            if live.get('state') in {'failed', 'internal_error'}:
                raise RuntimeError('probe_source_unavailable')
            time.sleep(0.25)
        else:
            raise RuntimeError('probe_live_timeout')
        start = live['view']['started_at_ms']
        source_seconds = time.monotonic() - started
        for _ in range(2):
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
            connection.request('GET', '/api/events', headers={'Cookie': cookie,
                'Last-Event-ID': f"{state['instance_id']}:{state['sequence']}"})
            response = connection.getresponse()
            if response.status != 200 or b'retry:' not in response.readline():
                raise RuntimeError('probe_stream_failed')
            streams.append((connection, response))
        time.sleep(2)
        latest, _ = get('/api/live', cookie=cookie)
        view = latest['values']['live']['view']
        if len(owners) != 1 or view['started_at_ms'] != start:
            raise RuntimeError('probe_duplicate_owner')
        print(json.dumps({'status': 'ok', 'source': view['source_label'], 'owners': len(owners),
            'streams': len(streams), 'rows': len(view['rows']),
            'accounts': len((view['accounts'] or {}).get('accounts', [])),
            'run_origin_preserved': True, 'sequence_advanced': latest['sequence'] > state['sequence'],
            'shell_seconds': round(shell_seconds, 3), 'source_view_seconds': round(source_seconds, 3)}))
        if args.detail:
            if not view['rows']:
                raise RuntimeError('probe_no_session_evidence')
            session_id = view['rows'][0]['session_id']

            def detail(value):
                return get('/api/detail', value=value, cookie=cookie)[0]

            token = detail(dict(action='open', session_id=session_id, mode='live'))['token']
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                page = detail(dict(action='page', token=token, offset=0))
                if page.get('result'):
                    break
                time.sleep(0.25)
            else:
                raise RuntimeError('probe_detail_timeout')
            last = detail(dict(action='page', token=token, offset=2**52))
            if last['total'] != page['total'] or len(last['result']['view']['prompt_blocks'][0]['rows']) > 50:
                raise RuntimeError('probe_detail_page_contract')
            detail(dict(action='freeze', token=token))
            frozen = detail(dict(action='page', token=token, offset=0))
            time.sleep(1)
            if detail(dict(action='page', token=token, offset=0)) != frozen:
                raise RuntimeError('probe_detail_freeze_changed')
            detail(dict(action='close', token=token))
            print(json.dumps(dict(detail='ok', available_rows=page['total'],
                page_rows=len(page['result']['view']['prompt_blocks'][0]['rows']),
                first_latest_access=True, frozen_consistent=True, account_owners=len(owners))))
        if args.reports:
            # Do not emit session IDs, account details, report content or bootstrap values.
            def submit(value):
                return get('/api/reports', value=value, cookie=cookie)[0]['id']

            def job(key):
                return get('/api/jobs/' + key, cookie=cookie)[0]

            for request in ({'kind': 'normal'}, {'kind': 'all-models'},
                            {'kind': 'sessions', 'session_limit': 1},
                            {'kind': 'date', 'date_text': '2026-10-25'}):
                report_started = time.monotonic()
                key = submit(request)
                deadline = time.monotonic() + 125
                while time.monotonic() < deadline:
                    value = job(key)
                    if value['status'] not in {'queued', 'running'}:
                        break
                    time.sleep(.25)
                if value['status'] != 'complete' or value['result']['error']:
                    print(json.dumps(dict(report=request['kind'], status=value['status'],
                                          error=value.get('error'), progress=value.get('progress'))))
                    raise RuntimeError('probe_finite_report_failed_' + str(value.get('error') or value['status']))
                current, _ = get('/api/live', cookie=cookie)
                if len(owners) != 1 or current['values']['live']['view']['started_at_ms'] != start:
                    raise RuntimeError('probe_report_changed_live_owner')
                print(json.dumps(dict(report=request['kind'], status='complete', live_owner_preserved=True,
                                      seconds=round(time.monotonic() - report_started, 3))))
            key = submit({'kind': 'token-mix'})
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                value = job(key)
                if value['status'] not in {'queued', 'running'} or value['progress']['phase'] == 'history':
                    break
                time.sleep(.05)
            get('/api/jobs/' + key + '/cancel', value={}, cookie=cookie)
            value = job(key)
            if value['status'] not in {'cancelled', 'complete'}:
                raise RuntimeError('probe_history_cancellation_failed')
            latest, _ = get('/api/live', cookie=cookie)
            if len(owners) != 1 or latest['values']['live']['view']['started_at_ms'] != start:
                raise RuntimeError('probe_cancel_changed_live_owner')
            print(json.dumps(dict(history=value['status'], live_owner_preserved=True)))
    finally:
        host.stop('menu')
        for connection, response in streams:
            response.close()
            connection.close()
        host.close()
        if host.failure:
            print(json.dumps({'runtime_error_type': type(host.failure).__name__, 'frames': [
                {'file': Path(frame.filename).name, 'function': frame.name, 'line': frame.lineno}
                for frame in traceback.extract_tb(host.failure.__traceback__)]}))
    if host.live.thread.is_alive() or host.thread.is_alive() or host.failure:
        raise RuntimeError('probe_shutdown_failed')
    print('PASS owned live and HTTP workers closed; shared OpenCode untouched')


if __name__ == '__main__':
    main()
