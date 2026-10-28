"""Approval-only built-in-browser fixture: real WebHost/HTTP/SSE, synthetic data.

No browser launch, model calls, installed history, private control record or remote effects.
Local command-file actions affect this process only. Hard lifetime: ten minutes.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.session_snapshots import make_snapshot
from development.tests.fixtures.watch_runtime import MutableSource, make_service
from src.application.live_projection import project_live
from src.application import ReportApplication
from src.reports import ReportRequest
from src.watch.coordinator import WatchCoordinator
from src.web.host import WebHost
from src.web.http import ASSETS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    workspace.mkdir(exist_ok=True)
    config, selection, service, _ = make_service(workspace / 'fixture', MutableSource(make_snapshot()))
    result = ReportApplication(lambda clock, progress: service, clock=lambda: 2200).execute(ReportRequest()).to_json()
    config, selection, service, _ = make_service(workspace / 'watch', MutableSource(make_snapshot()))
    owner = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: 2200)
    try:
        view = project_live(owner.initialize().projection).to_json()
    finally:
        owner.close()

    class Jobs:
        def readiness(self):
            return dict(http='ready', source='fixture', accounts='fixture', analysis='ready')

        def submit(self, request):
            return '1' * 32

        def snapshot(self, key):
            return dict(id=key, status='complete', result=result, progress={})

        def tick(self):
            pass

        def close(self):
            pass

    host = WebHost(ROOT, jobs=Jobs())
    read = host.events.read
    interruption = [0]

    def read_with_owned_fault(*args, **kwargs):
        if time.monotonic() < interruption[0]:
            raise ConnectionResetError('owned_fixture_stream_interruption')
        return read(*args, **kwargs)

    host.events.read = read_with_owned_fault
    host.start()
    # A fixture-only asset bootstraps the test browser without printing a token.
    # Production routing/assets remain unchanged on disk.
    ASSETS['/probe-entry.js'] = ('probe-entry.js', 'text/javascript; charset=utf-8')
    host.server.assets['probe-entry.js'] = (
        ('location.hash = "bootstrap=" + ' + json.dumps(host.server.session.bootstrap()) + ';').encode(),
        'text/javascript; charset=utf-8')
    shell, content_type = host.server.assets['index.html']
    entry = shell.replace(b'<script src="/render.js"', b'<script src="/probe-entry.js"></script><script src="/render.js"')
    ASSETS['/probe-entry'] = ('probe-entry.html', 'text/html; charset=utf-8')
    host.server.assets['probe-entry.html'] = entry, content_type
    host.events.publish('live', dict(state='running', source_observed_at_ms=2200, view=view))
    (workspace / 'ready.json').write_text(json.dumps(dict(origin=host.server.origin, pid=os.getpid())), encoding='utf-8')
    print('Browser fixture ready; owned host only.', flush=True)
    deadline = time.monotonic() + 600
    command = workspace / 'command.json'
    try:
        while time.monotonic() < deadline and not host.stopped.is_set():
            if command.is_file():
                action = json.loads(command.read_text(encoding='utf-8-sig'))['action']
                command.unlink()
                if action in {'menu', 'source_changed'}:
                    host.stop(action)
                elif action == 'crash':
                    os._exit(0)  # Deliberately abrupt, test process only; no child jobs.
                elif action == 'expire':
                    with host.server.session._lock:
                        host.server.session._until = 0
                elif action in {'running', 'recovering'}:
                    host.events.publish('live', dict(state=action, source_observed_at_ms=2200, view=view))
                elif action == 'new_identity':
                    host.nonce = 'replacement-fixture'
                elif action == 'interrupt':
                    interruption[0] = time.monotonic() + 1
                else:
                    raise ValueError('unknown_fixture_action')
            time.sleep(.1)
    finally:
        host.close()
    print('Browser fixture stopped and joined.', flush=True)


if __name__ == '__main__':
    main()
