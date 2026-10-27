"""Explicit-browser, bounded Models layout probe using canonical synthetic reports only."""
import argparse
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

from development.tests.fixtures.model_views import model_report
from src.application.projection import project


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.browser.is_file() or not args.output.parent.is_dir():
        raise SystemExit('Explicit browser and existing owned output directory required')
    assets = ROOT / 'src/web/assets'
    resources = {'/' + name: (assets / name).read_bytes() for name in ('app.css', 'render.js', 'reports.js')}
    resources['/data.js'] = ('const INPUT = ' + json.dumps([
        project(model_report(all_models=all_models, fallback=fallback)).to_json()
        for all_models in (False, True) for fallback in (False, True)]) + ';').encode()
    resources['/browser.js'] = Path(__file__).with_name('web_models_browser.js').read_bytes()
    resources['/case.html'] = b'''<!doctype html><html><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/app.css"><main><div id="scope-controls"></div><div id="result"></div></main><script src="/render.js"></script><script src="/reports.js"></script><script src="/data.js"></script><script src="/browser.js"></script></html>'''

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            content = resources.get(self.path)
            if content is None:
                self.send_error(404)
                return
            self.send_response(200)
            content_type = 'text/javascript' if self.path.endswith('.js') else 'text/css' if self.path.endswith('.css') else 'text/html'
            self.send_header('Content-Type', content_type + '; charset=utf-8')
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
        with tempfile.TemporaryDirectory(dir=args.output.parent, prefix='models-browser-') as tmp:
            for theme, width in (('light', 1200), ('light', 360), ('dark', 1200), ('dark', 360)):
                resources['/'] = (f'<!doctype html><html><iframe style="width:{width}px;height:1100px" src="/case.html"></iframe><pre id="probe">PENDING</pre></html>').encode()
                command = [str(args.browser), '--headless=new', '--disable-gpu', '--no-first-run',
                    '--no-default-browser-check', '--disable-extensions', '--disable-background-networking',
                    '--user-data-dir=' + str(Path(tmp) / f'{theme}-{width}'), '--window-size=1400,1400',
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
    evidence = dict(outcome='PASS' if all(case['outcome'] == 'PASS' for case in outcomes) else 'FAIL', cases=outcomes,
        limitations=['Synthetic canonical reports in headless Chromium, not installed-history browser integration.',
            'No physical input, screen-reader or native macOS acceptance.'])
    args.output.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(evidence))
    return int(evidence['outcome'] != 'PASS')


if __name__ == '__main__':
    raise SystemExit(main())
