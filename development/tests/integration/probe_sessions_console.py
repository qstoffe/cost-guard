"""Bounded Windows detached-host/report console reproduction; no source/model/browser.

Explicitly run only for approved native console investigation. Starts/joins only
owned children, measuring GetConsoleWindow in the real ReportJobs spawn path.
"""
import ctypes
import http.client
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.reports import ReportKind, ReportRequest
from src.web.jobs import ReportJobs


def managed_route_probe():
    """Actual Windows managed tray/launcher and authenticated Sessions request path.

    No external browser handoff. The tray is legitimate UI; only this checkout's
    newly created host is stopped, never OpenCode or an existing instance.
    """
    from src.web.instance_state import InstanceStore
    from src.web.lifecycle import launch, stop_existing
    store = InstanceStore(ROOT)
    assert store.read() is None, 'existing_instance_not_owned'
    csrf = None
    cookie = None
    try:
        launch(ROOT, 'src.web.native_windows', opener=lambda _: False)
        state = store.read()
        assert Path(state['process']['image']).name.lower() == 'pythonw.exe'
        def request(path, value):
            connection = http.client.HTTPConnection('127.0.0.1', state['port'], timeout=5)
            headers = {'Origin': f"http://127.0.0.1:{state['port']}", 'Content-Type': 'application/json'}
            if csrf:
                headers['X-CG-CSRF'] = csrf
            if cookie:
                headers['Cookie'] = cookie
            connection.request('POST' if value is not None else 'GET', path,
                json.dumps(value) if value is not None else None, headers)
            response = connection.getresponse()
            body = json.loads(response.read())
            cookies = response.getheader('Set-Cookie')
            connection.close()
            assert response.status in (200, 202), body
            return body, cookies
        # A control Open gives a one-use link without opening any external app.
        from src.web.lifecycle import control
        from urllib.parse import urlsplit, parse_qs
        opened = control(state, 'open')
        credential = parse_qs(urlsplit(opened['url']).fragment)['bootstrap'][0]
        auth, cookies = request('/api/bootstrap', {'credential': credential})
        csrf, cookie = auth['csrf'], cookies.split(';')[0]
        job, _ = request('/api/reports', dict(kind='sessions', session_page_size=50))
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            snapshot, _ = request('/api/jobs/' + job['id'], None)
            if snapshot['status'] not in ('queued', 'running'):
                break
            time.sleep(.1)
        assert snapshot['status'] == 'complete', snapshot.get('error')
        result = snapshot['result']
        assert result['error'] is None, result['error']
        return dict(managed_interpreter='pythonw.exe', authenticated_sessions='complete',
            rows=len(result['view']['session_usage']), total=result['view']['session_page']['total'],
            limitation='Production managed tray/HTTP Sessions route; no physical mouse click or external browser handoff.')
    finally:
        current = store.read()
        if current:
            stop_existing(store, current)


def report(sender, request):
    kernel = ctypes.WinDLL('kernel32')
    kernel.GetConsoleWindow.restype = ctypes.c_void_p
    sender.send(('result', json.dumps(dict(error=None, source=dict(status='acquired'),
        console_window=bool(kernel.GetConsoleWindow())))))
    sender.close()


def host(output):
    owner = ReportJobs(target=report)
    try:
        key = owner.submit(ReportRequest(ReportKind.SESSIONS, session_page_size=50))
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            owner.tick()
            result = owner.snapshot(key)
            if result['status'] not in ('queued', 'running'):
                output.write_text(json.dumps(result), encoding='utf-8')
                return
            time.sleep(.02)
        raise RuntimeError('console_probe_timeout')
    finally:
        owner.close()


def main():
    output = Path(sys.argv[1]).resolve()
    if len(sys.argv) == 3 and sys.argv[2] == '--host':
        host(output)
        return
    outcomes = {}
    for name in ('python.exe', 'pythonw.exe'):
        target = output.with_name(output.stem + '-' + name + '.json')
        child = subprocess.Popen([str(Path(sys.executable).with_name(name)), str(Path(__file__).resolve()),
            str(target), '--host'], cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
        try:
            if child.wait(timeout=20) != 0:
                raise RuntimeError('owned_host_failed')
            result = json.loads(target.read_text(encoding='utf-8'))
            assert result['status'] == 'complete', result
            outcomes[name] = result['result']['console_window']
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5)
    assert outcomes == {'python.exe': True, 'pythonw.exe': False}, outcomes
    evidence = dict(outcome='PASS', detached_report_console=outcomes,
        limitation='Real ReportJobs from detached hosts; not physical Sessions click or tray visual acceptance.')
    if '--managed' in sys.argv:
        evidence['managed_route'] = managed_route_probe()
    output.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(evidence))


if __name__ == '__main__':
    main()
