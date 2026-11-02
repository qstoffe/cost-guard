"""Loopback synthetic Watch fixture for integrated-browser layout checks only.

No real source, credentials, settings or inference; stops after ten minutes.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from threading import Thread, Timer
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.watch_summary import summary_watch
from src.application.live_projection import project_live


def main():
    assets = ROOT / 'src/web/assets'
    resources = {'/' + name: (assets / name).read_bytes() for name in ('app.css', 'render.js', 'watch.js')}
    resources['/data.js'] = ('const INPUT = ' + json.dumps(dict(state='running', view=project_live(summary_watch()).to_json())) + ';').encode()

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
                width = width if width in {'360', '768', '1366', '1920'} else '1366'
                theme = 'classic' if query.get('theme') == ['classic'] else 'web'
                scheme = 'dark' if query.get('scheme') == ['dark'] else 'light'
                content = f'''<!doctype html><html style="color-scheme:{scheme}"><title>Watch summary layout</title>
                    <iframe title="Synthetic Watch" style="border:0;width:{width}px;height:1600px" src="/case.html?theme={theme}"></iframe></html>'''.encode()
            elif url.path == '/case.html':
                theme = 'classic' if query.get('theme') == ['classic'] else 'web'
                content = f'''<!doctype html><html lang="en" data-theme="{theme}"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
                    <title>Synthetic Watch</title><link rel="stylesheet" href="/app.css"><main><h1>Watch</h1><div id="result"></div></main>
                    <script src="/render.js"></script><script src="/watch.js"></script><script src="/data.js"></script>
                    <script>const state = {{connection:'Live connected.'}}; ReportView.renderLive(document.getElementById('result'), INPUT, state);</script></html>'''.encode()
            else:
                content = resources.get(url.path)
            if content is None:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', ('text/javascript' if url.path.endswith('.js') else 'text/css' if url.path.endswith('.css') else 'text/html') + '; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers(); self.wfile.write(content)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 18753), Handler)
    timer = Timer(600, server.shutdown); timer.start()
    try:
        print('Synthetic Watch fixture ready on http://127.0.0.1:18753', flush=True)
        server.serve_forever()
    finally:
        timer.cancel(); server.server_close()


if __name__ == '__main__':
    main()
