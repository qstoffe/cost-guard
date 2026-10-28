"""Bounded owned real-V2 browser soak host; no UI launch, inference or shared stop.

The fixture-only entry exchanges a one-use credential without emitting it. Browser
instrumentation retains only transport timing/status, never payloads or identities.
"""
import argparse
import faulthandler
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.web.composition import live_acquisition
from src.web.host import WebHost
from src.web.http import ASSETS
from src.web.jobs import ReportJobs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--seconds', type=int, default=1800, choices=range(60, 3601))
    parser.add_argument('--stack-after', type=int, default=0, help='Optional local-only stalled-startup thread evidence.')
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    workspace.mkdir(exist_ok=False)
    stack_file = (workspace / 'threads.log').open('w', encoding='utf-8') if args.stack_after else None
    if stack_file:
        faulthandler.dump_traceback_later(args.stack_after, file=stack_file)
    owners = []

    def factory():
        driver = live_acquisition()
        owners.append(driver)
        return driver

    host = WebHost(ROOT, jobs=ReportJobs(), live_factory=factory)
    try:
        host.start()
        instrument = """
        window.connectionProbe = {started: Date.now(), events: [], streams: 0};
        const record = (kind, detail) => {
          const p = window.connectionProbe;
          if (p.events.length < 4096) p.events.push({at: Date.now(), kind, detail});
        };
        const NativeStream = window.EventSource;
        window.EventSource = class extends NativeStream {
          constructor(url) {
            super(url); window.connectionProbe.streams++;
            record('stream-created', null);
            for (const kind of ['open', 'error', 'resync', 'live', 'terminal'])
              this.addEventListener(kind, () => record(kind, this.readyState));
          }
          close() { record('stream-close', this.readyState); super.close(); }
        };
        const nativeFetch = window.fetch;
        window.fetch = async (...args) => {
          const path = args[0], start = performance.now();
          try {
            const response = await nativeFetch(...args);
            if (['/api/live', '/health'].includes(path))
              record(path, {status: response.status, ms: Math.round(performance.now()-start)});
            return response;
          } catch (e) { record('fetch-error', {path, name: e.name}); throw e; }
        };
        document.addEventListener('visibilitychange', () => record('visibility', document.visibilityState));
        window.addEventListener('DOMContentLoaded', () => {
          const banner = document.getElementById('host-state');
          new MutationObserver(() => {
            const kind = banner.dataset.kind;
            if (window.connectionProbe.last !== kind) {
              record('state', kind); window.connectionProbe.last = kind;
            }
          }).observe(banner, {attributes: true, childList: true, subtree: true});
        });
        """
        entry = ('location.hash = "bootstrap=" + ' +
                 json.dumps(host.server.session.bootstrap()) + ';\n' + instrument)
        ASSETS['/soak-entry.js'] = ('soak-entry.js', 'text/javascript; charset=utf-8')
        host.server.assets['soak-entry.js'] = entry.encode(), 'text/javascript; charset=utf-8'
        shell, content_type = host.server.assets['index.html']
        ASSETS['/soak-entry'] = ('soak-entry.html', content_type)
        host.server.assets['soak-entry.html'] = (
            shell.replace(b'<script src="/render.js"',
                          b'<script src="/soak-entry.js"></script><script src="/render.js"'), content_type)
        (workspace / 'ready.json').write_text(json.dumps(dict(origin=host.server.origin, pid=os.getpid())), encoding='utf-8')
        print('Owned real-source soak host ready; no credential output.', flush=True)
        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline and not host.stopped.is_set():
            if (workspace / 'stop').exists():
                break
            time.sleep(.1)
    finally:
        host.stop('menu')
        host.close()
        if stack_file:
            faulthandler.cancel_dump_traceback_later()
            stack_file.close()
    summary = dict(owners=len(owners), http_joined=not host.thread.is_alive(),
                   live_joined=not host.live.thread.is_alive(), failure=type(host.failure).__name__ if host.failure else None)
    (workspace / 'closed.json').write_text(json.dumps(summary), encoding='utf-8')
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
