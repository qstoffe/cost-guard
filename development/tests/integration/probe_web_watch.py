"""Explicit-browser, bounded synthetic Watch rendering probe; no installed history/login."""
import argparse
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import html
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from threading import Thread

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.session_snapshots import make_snapshot
from development.tests.fixtures.watch_runtime import MutableSource, make_service
from src.application.live_projection import project_live
from src.watch.coordinator import WatchCoordinator


def payload(root):
    config, selection, service, _ = make_service(root, MutableSource(make_snapshot()))
    owner = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: 2200)
    try:
        view = project_live(owner.initialize().projection).to_json()
    finally:
        owner.close()
    other = deepcopy(view['rows'][0])
    other.update(session_id='second-session', session_title='Second synthetic session')
    view['rows'].append(other)
    view['session_subtotals'].append(dict(view['session_subtotals'][0], session_id='second-session'))
    return dict(state='running', source_observed_at_ms=2200, view=view)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='Owned scratch JSON evidence path')
    args = parser.parse_args()
    if not args.browser.is_file() or not args.output.parent.is_dir():
        raise SystemExit('Explicit browser and existing owned output directory required')
    assets = ROOT / 'src/web/assets'
    with tempfile.TemporaryDirectory(dir=args.output.parent, prefix='watch-browser-') as tmp:
        data = payload(Path(tmp) / 'fixture')
        resources = {f'/{name}': (assets / name).read_bytes() for name in ('app.css', 'render.js', 'watch.js', 'live.js')}
        resources['/data.js'] = ('const INPUT = ' + json.dumps(data) + ';').encode()
        resources['/browser.js'] = (Path(__file__).with_name('web_watch_browser.js')).read_bytes()
        resources['/case.html'] = b'''<!doctype html><html><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/app.css"><main><div id="result"></div></main><script src="/render.js"></script><script src="/watch.js"></script><script src="/live.js"></script><script src="/data.js"></script><script src="/browser.js"></script></html>'''

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                content = resources.get(self.path)
                if content is None:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header('Content-Type', 'text/javascript' if self.path.endswith('.js') else 'text/css' if self.path.endswith('.css') else 'text/html')
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)

            def log_message(self, *_):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = Thread(target=server.serve_forever)
        thread.start()
        outcomes = []
        try:
            for theme, width in (('light', 1200), ('dark', 360)):
                resources['/'] = (f'<!doctype html><html><iframe style="width:{width}px;height:900px" src="/case.html"></iframe><pre id="probe">PENDING</pre></html>').encode()
                command = [str(args.browser), '--headless=new', '--disable-gpu', '--no-first-run',
                    '--no-default-browser-check', '--disable-extensions', '--disable-background-networking',
                    '--user-data-dir=' + str(Path(tmp) / theme), '--window-size=1400,1100',
                    '--virtual-time-budget=5000', '--dump-dom']
                if theme == 'dark':
                    command.append('--force-dark-mode')
                command.append(f'http://127.0.0.1:{server.server_port}/')
                result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=40)
                match = re.search(r'<pre id="probe">(.*?)</pre>', result.stdout, re.S)
                outcome = json.loads(html.unescape(match[1])) if match and match[1] != 'PENDING' else dict(outcome='FAIL', reason='no_browser_receipt')
                outcomes.append(dict(theme=theme, requested_width=width, **outcome))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(5)
        evidence = dict(outcome='PASS' if all(o['outcome'] == 'PASS' for o in outcomes) else 'FAIL', cases=outcomes,
            limitations=['Synthetic canonical projections and fixture transport, not live-source/browser SSE integration.',
                'Headless Edge; no physical input, screen-reader, native macOS or desktop-pane proof.'])
        args.output.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(evidence))
        return int(evidence['outcome'] != 'PASS')


if __name__ == '__main__':
    raise SystemExit(main())
