"""Explicit-browser synthetic Sessions acceptance; no accounts/models/installed source.

Run separately from package/layout suites: temporary browser profiles are not
product directories and must be gone before those suites inventory the tree.
"""
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
from development.tests.fixtures.report_runtime import FakePricingProvider
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from src.application import ReportApplication
from src.cache import CacheDatabase, CacheRepository
from src.config import load_configuration
from src.reports import ReportKind, ReportRequest, ReportService
from src.sources.selection import SourceSelection


def payload(directory):
    database = CacheDatabase(directory)
    database.initialize()
    source = SyntheticMonthSource(55, 1, month_start_ms=1000)
    def factory(now, progress):
        return ReportService(selection=SourceSelection(source, 'v1', (), source.probe()),
            pricing_provider=FakePricingProvider(), account_provider=None,
            cache_repository=CacheRepository(database), config=load_configuration(ROOT).values,
            now_ms=now, progress=progress)
    app = ReportApplication(factory, clock=lambda: 10_000_000)
    first = app.execute(ReportRequest(ReportKind.SESSIONS, session_page_size=50)).to_json()
    revision = first['view']['session_page']['catalog_revision']
    second = app.execute(ReportRequest(ReportKind.SESSIONS, session_page_size=50,
        session_offset=50, session_catalog_revision=revision)).to_json()
    detail = app.execute(ReportRequest(ReportKind.SESSION, session_id='root-0004')).to_json()
    return dict(first=first, second=second, detail=detail)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--keep-screenshots', action='store_true', help='Retain synthetic screenshots for review; remove before package validation')
    args = parser.parse_args()
    assert args.browser.is_file() and args.output.parent.is_dir()
    with tempfile.TemporaryDirectory(dir=args.output.parent, prefix='sessions-browser-') as tmp:
        data = payload(Path(tmp) / 'fixture')
        assets = ROOT / 'src/web/assets'
        resources = {'/' + p.name: p.read_bytes() for p in assets.iterdir() if p.is_file()}
        resources['/data.js'] = ('const INPUT = ' + json.dumps(data) + ';').encode()
        resources['/probe.js'] = Path(__file__).with_name('web_sessions_browser.js').read_bytes()
        page = (assets / 'index.html').read_text(encoding='utf-8')
        page = page.replace('<script src="/live.js" defer></script>', '').replace('<script src="/session.js" defer></script>', '')
        page = page.replace('<script src="/app.js" defer>', '<script src="/data.js" defer></script><script src="/probe.js" defer></script><script src="/app.js" defer>')
        resources['/'] = page.replace('</body>', '<pre id="probe">PENDING</pre></body>').encode()
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
            revision = data['first']['view']['session_page']['catalog_revision']
            for theme, width, fragment in (('light', 1200, '#/sessions'),
                    ('dark', 500, '#/sessions'), ('reload', 1200, '#/sessions?offset=50&revision=' + revision)):
                command = [str(args.browser), '--headless=new', '--disable-gpu', '--no-first-run',
                    '--no-default-browser-check', '--disable-extensions', '--disable-background-networking',
                    '--user-data-dir=' + str(Path(tmp) / theme), f'--window-size={width},1000',
                    '--virtual-time-budget=12000', '--dump-dom', '--screenshot=' + str(
                        (args.output.with_name(theme + '.png') if args.keep_screenshots else Path(tmp) / (theme + '.png')).resolve())]
                if theme == 'dark':
                    command.append('--force-dark-mode')
                command.append(f'http://127.0.0.1:{server.server_port}/' + fragment)
                result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=40)
                match = re.search(r'<pre id="probe">(.*?)</pre>', result.stdout, re.S)
                outcome = json.loads(html.unescape(match[1])) if match and match[1] != 'PENDING' else dict(outcome='FAIL', reason='no_browser_receipt')
                outcomes.append(dict(theme=theme, **outcome))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(5)
    evidence = dict(outcome='PASS' if all(o['outcome'] == 'PASS' for o in outcomes) else 'FAIL', cases=outcomes,
        limitations=['Synthetic canonical DTO transport; real browser app/DOM/history/layout, not installed-source click, physical input or screen reader.'])
    args.output.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(evidence))
    return int(evidence['outcome'] != 'PASS')


if __name__ == '__main__':
    raise SystemExit(main())
