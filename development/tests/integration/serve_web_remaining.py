"""Approval-only synthetic HTTP fixture for the shipped browser app; never a real host.

Fixed loopback resources, synthetic session/CSRF and finite fixture jobs only.
No provider, source, user configuration, browser process or persistent user data.
Exits after fifteen minutes or POST /fixture/stop. Not security/real-SSE proof.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from threading import Event, Thread, Timer
import unittest
from urllib.parse import urlsplit, parse_qs

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.remaining_views import remaining_reports, result, detail_page, NOW, ZONE
from development.tests.fixtures.warning_projections import warning_prompt, warning_watch_projection
from src.analysis.context import PriceWarningSeverity
from src.application.live_projection import project_live


def main():
    owner = unittest.TestCase()
    try:
        reports = {key: result(value) for key, value in remaining_reports(owner).items()}
    finally:
        owner.doCleanups()
    live_view = project_live(warning_watch_projection(warning_prompt(PriceWarningSeverity.EXCEEDED)), ZONE).to_json()
    live = dict(state="running", view=live_view, source_observed_at_ms=NOW)
    assets = ROOT / "src/web/assets"
    resources = {"/" + path.name: path.read_bytes() for path in assets.iterdir() if path.is_file()}
    jobs, leases, requests = {}, {}, []
    stopped = Event()

    class Handler(BaseHTTPRequestHandler):
        def send(self, value, content_type="application/json"):
            content = json.dumps(value).encode() if content_type == "application/json" else value
            self.send_response(200)
            self.send_header("Content-Type", content_type + "; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self):
            url = urlsplit(self.path)
            if url.path == "/api/session":
                return self.send(dict(csrf="synthetic-only"))
            if url.path == "/api/status":
                return self.send(dict(http="ready", analysis="ready", source="fixture", accounts="fixture", session_detail=True))
            if url.path == "/api/live":
                return self.send(dict(instance_id="fixture", sequence=1, values=dict(live=live)))
            if url.path == "/api/events":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                try:
                    while not stopped.is_set():
                        self.wfile.write(b": synthetic heartbeat\n\n")
                        self.wfile.flush()
                        if stopped.wait(2):
                            break
                except (ConnectionError, OSError):
                    pass
                return
            if url.path.startswith("/api/jobs/"):
                return self.send(jobs[url.path.split("/")[3]])
            if url.path == "/fixture/requests":
                return self.send(requests)
            if url.path == "/":
                width = 360 if parse_qs(url.query).get("width") == ["360"] else 1200
                return self.send(f'<!doctype html><html><title>Synthetic review only</title><iframe title="Cost Guard fixture" style="width:{width}px;height:1700px;border:0" src="/index.html"></iframe></html>'.encode(), "text/html")
            content = resources.get(url.path)
            if content is None:
                self.send_error(404)
                return
            kind = "text/javascript" if url.path.endswith(".js") else "text/css" if url.path.endswith(".css") else "text/html"
            self.send(content, kind)

        def do_POST(self):
            value = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            requests.append(dict(path=self.path, **value))
            if self.path == "/fixture/stop":
                self.send(dict(stopped=True)); stopped.set()
                Thread(target=self.server.shutdown).start()
            elif self.path == "/api/reports":
                key = str(len(jobs) + 1)
                kind = value["kind"]
                jobs[key] = dict(status="running", progress=dict(phase="history", completed=12, total=120)) if kind == "token-mix" else dict(status="complete", result=reports[kind])
                self.send(dict(id=key))
            elif self.path.startswith("/api/jobs/") and self.path.endswith("/cancel"):
                jobs[self.path.split("/")[3]] = dict(status="cancelled")
                self.send(dict(cancelled=True))
            elif self.path == "/fixture/finish-history":
                for key, job in jobs.items():
                    if job["status"] == "running":
                        jobs[key] = dict(status="complete", result=reports["token-mix"])
                self.send(dict(complete=True))
            elif self.path == "/fixture/stopped":
                live.update(state="stopped")
                self.send(dict(stopped=True))
            elif self.path == "/api/detail":
                action = value["action"]
                if action == "open":
                    token = str(len(leases) + 1); leases[token] = value["mode"]
                    self.send(dict(token=token))
                elif action == "page":
                    self.send(detail_page(reports["session"], value["offset"]))
                else:
                    self.send({})
            else:
                self.send_error(404)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 18751), Handler)
    timer = Timer(900, lambda: (stopped.set(), server.shutdown()))
    timer.start()
    try:
        print("Synthetic review ready: http://127.0.0.1:18751/index.html", flush=True)
        server.serve_forever()
    finally:
        stopped.set(); timer.cancel(); server.server_close()


if __name__ == "__main__":
    main()
