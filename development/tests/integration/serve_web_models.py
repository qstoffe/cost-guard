"""Loopback-only canonical Models fixture for the integrated browser; no UI driver.

Serves bounded resources only and stops on /stop or after ten minutes. The iframe
provides real 360/laptop/wide layout viewports; theme CSS selects the same tokens
without claiming OS-theme emulation. No accounts/history/configuration is read.
"""
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from threading import Thread, Timer
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.model_views import model_report
from src.application.projection import project


def main():
    report = model_report(include_model_catalog=True)
    catalog = report.model_catalog
    base = next(row for row in catalog.rows if row.model == 'Z')
    extra = tuple(replace(base, model=f'Long comparison model variant {index:02d}',
                          recent=False) for index in range(35))
    catalog = replace(catalog, rows=catalog.rows + extra,
        selectable=catalog.selectable + tuple((row.publisher, row.model) for row in extra),
         promotion_notes=report.model_comparison_promotion_notes)
    view = project(replace(report, model_catalog=catalog)).to_json()
    assets = ROOT / 'src/web/assets'
    resources = {'/' + name: (assets / name).read_bytes() for name in ('app.css', 'help.js', 'render.js', 'reports.js')}
    resources['/browser.js'] = Path(__file__).with_name('web_models_browser.js').read_bytes()
    resources['/data.js'] = ('const INPUT = ' + json.dumps(view) + ';').encode()
    resources['/case.html'] = b'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Unified Models fixture</title><link rel="stylesheet" href="/app.css"><body data-section="models"><header><h1>Cost Guard Web Beta</h1><p>Synthetic Models acceptance fixture</p></header><nav><a href="#/models" aria-current="page">Models</a><a href="#/accounts">Accounts</a></nav><main><div id="result"></div></main><script src="/render.js"></script><script src="/data.js"></script><script>const state = {section:'models',pages:{}}; ReportView.render(document.getElementById('result'), {view:INPUT,source:{status:'acquired'}},state); if(new URLSearchParams(location.search).get('theme')==='light'){const style=document.createElement('style');style.textContent=':root {color-scheme:light;--bg:#eef2f8;--panel:#fff;--surface:#f6f8fc;--hover:#edf3ff;--ink:#17253b;--muted:#51627b;--line:#d3ddea;--control-line:#7b8da6;--accent:#2457c5;--accent-ink:#fff;--accent-soft:#e8efff;--warn:#815000;--warn-bg:#fff6df;--error:#b1263b;--success:#14674e;}';document.head.append(style);}else{const style=document.createElement('style');style.textContent=':root {color-scheme:dark;--bg:#0c1422;--panel:#141f31;--surface:#19263b;--hover:#20324b;--ink:#e6edf8;--muted:#a6b5cc;--line:#31415b;--control-line:#7387a5;--accent:#9cbfff;--accent-ink:#0d2045;--accent-soft:#23385a;--warn:#ffcf7b;--warn-bg:#352b1a;--error:#ff9aad;--success:#7bd9b3;}';document.head.append(style);}</script></body></html>'''

    resources['/case.html'] = resources['/case.html'].replace(b'<script src="/render.js">', b'<script src="/help.js"></script><script src="/render.js">')

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlsplit(self.path)
            query = parse_qs(url.query)
            if url.path == '/stop':
                self.send_response(200); self.end_headers()
                Thread(target=self.server.shutdown).start()
                return
            if url.path == '/':
                width = query.get('width', ['1366'])[0]
                width = width if width in {'360', '1366', '1920'} else '1366'
                theme = 'dark' if query.get('theme') == ['dark'] else 'light'
                content = (f'<!doctype html><html><title>Models layout {width} {theme}</title>'
                    f'<iframe title="Models fixture" style="border:0;width:{width}px;height:900px" src="/case.html?theme={theme}"></iframe></html>').encode()
            else:
                content = resources.get(url.path)
            if content is None:
                self.send_error(404); return
            self.send_response(200)
            self.send_header('Content-Type', ('text/javascript' if url.path.endswith('.js') else
                'text/css' if url.path.endswith('.css') else 'text/html') + '; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers(); self.wfile.write(content)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 18753), Handler)
    timer = Timer(600, server.shutdown); timer.start()
    try:
        print('Models fixture ready: http://127.0.0.1:18753', flush=True)
        server.serve_forever()
    finally:
        timer.cancel(); server.server_close()


if __name__ == '__main__':
    main()
