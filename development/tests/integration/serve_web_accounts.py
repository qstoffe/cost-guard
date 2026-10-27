"""Bounded loopback-only synthetic Accounts page for explicitly approved browser checks.

No source/accounts/configuration, arbitrary files or product host. Exits after five
minutes or GET /stop; use before whole-tree package-copy tests.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from threading import Thread, Timer
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.account_views import account_report
from src.application.projection import project


def main():
    assets = ROOT / "src/web/assets"
    resources = {"/" + name: (assets / name).read_bytes() for name in ("app.css", "render.js")}
    resources["/data.js"] = ("const INPUT = " + json.dumps(project(account_report(), "Europe/Stockholm").to_json()) + ";").encode()
    resources["/case.html"] = b'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Synthetic Accounts acceptance</title><link rel="stylesheet" href="/app.css"><main><h1>Accounts</h1><p>Synthetic fixtures only</p><div id="result"></div></main><script src="/render.js"></script><script src="/data.js"></script><script>ReportView.render(document.getElementById('result'), {view: INPUT, observed_at_ms: 1793052000000, source: {status: 'acquired', atomicity: 'per_root_snapshot'}}, {section: 'accounts', pages: {}});</script></html>'''

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlsplit(self.path)
            if url.path == "/stop":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Stopping synthetic fixture server")
                Thread(target=self.server.shutdown).start()
                return
            if url.path == "/":
                width = 360 if parse_qs(url.query).get("width") == ["360"] else 1200
                content = f'<!doctype html><html><title>Accounts layout probe</title><iframe title="Synthetic Accounts" style="border:0;width:{width}px;height:1600px" src="/case.html"></iframe></html>'.encode()
            else:
                content = resources.get(url.path)
            if content is None:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", ("text/javascript" if url.path.endswith(".js") else "text/css" if url.path.endswith(".css") else "text/html") + "; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 18749), Handler)
    timer = Timer(300, server.shutdown)
    timer.start()
    try:
        print("Synthetic Accounts fixture ready on http://127.0.0.1:18749", flush=True)
        server.serve_forever()
    finally:
        timer.cancel()
        server.server_close()


if __name__ == "__main__":
    main()
