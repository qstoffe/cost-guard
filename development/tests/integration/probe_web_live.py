"""Bounded read-only real-installation probe; no UI, inference or service stop."""
import http.client
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
    owners = []

    def factory():
        driver = live_acquisition()
        owners.append(driver)
        return driver

    host = WebHost(ROOT, jobs=ReportJobs(), live_factory=factory)
    streams = []
    try:
        host.start()
        server = host.server

        def get(path, *, value=None, cookie=None):
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
            headers = {'Host': server.host}
            if cookie:
                headers['Cookie'] = cookie
            if value is not None:
                headers.update(Origin=server.origin, **{'Content-Type': 'application/json'})
            connection.request('POST' if value is not None else 'GET', path,
                               json.dumps(value) if value is not None else None, headers)
            response = connection.getresponse()
            data = json.loads(response.read())
            connection.close()
            if response.status != 200:
                raise RuntimeError('probe_http_failed')
            return data, response

        _, response = get('/api/bootstrap', value={'credential': server.session.bootstrap()})
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
            'run_origin_preserved': True, 'sequence_advanced': latest['sequence'] > state['sequence']}))
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
