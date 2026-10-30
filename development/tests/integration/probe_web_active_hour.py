"""Approval-only headless browser probe: shipped app, synthetic loopback data only."""
import argparse
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from threading import Event, Thread
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.test_active_hour import clean_service, history, hourly_result
from development.tests.fixtures.warning_projections import warning_prompt, warning_watch_projection
from src.analysis.context import PriceWarningSeverity
from src.application.live_projection import project_live
from src.application.projection import project
from src.reports import ReportKind, ReportRequest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not args.browser.is_file() or not args.output.parent.is_dir():
        raise SystemExit("Explicit browser and existing owned output directory required")
    owner = unittest.TestCase()
    try:
        hourly = hourly_result(owner)
        details = []
        for now in (4000, 8000):
            # One-shot ReportService observations are immutable per instance;
            # use a fresh service exactly as finite application captures do.
            service = clean_service(owner, history(((1000, None),)), now=now)
            report = service.build(ReportRequest(ReportKind.SESSION, session_id="root"))
            details.append(dict(state="observed", revision=str(now), offset=0, total=1, pending=False,
                result=dict(observed_at_ms=now, view=project(report).to_json(), source=dict(status="acquired"))))
        early = details[0]["result"]["view"]["prompt_blocks"][0]["active_hour"]
        late = details[1]["result"]["view"]["prompt_blocks"][0]["active_hour"]
        assert (early["duration_ms"], late["duration_ms"]) == (3000, 7000)
        assert early["rate"] != late["rate"]
        live = dict(state="running", source_observed_at_ms=4000,
            view=project_live(warning_watch_projection(warning_prompt(PriceWarningSeverity.EXCEEDED))).to_json())
    finally:
        owner.doCleanups()
    assets = ROOT / "src/web/assets"
    resources = {"/" + p.name: p.read_bytes() for p in assets.iterdir() if p.is_file()}
    # Scripted transport keeps --dump-dom finite; real SSE is covered by the
    # separate HTTP/Live tests, not this synthetic presentation probe.
    resources["/index.html"] = resources["/index.html"].replace(b"<head>", b'''<head><script>
window.EventSource = class {
  constructor() { setTimeout(() => this.onopen?.(), 0); }
  addEventListener() {}
  close() {}
};
</script>''')
    resources["/index.html"] = resources["/index.html"].replace(b"</body>", b'<script src="/probe.js"></script></body>')
    resources["/probe.js"] = Path(__file__).with_name("web_active_hour_browser.js").read_bytes()
    jobs, leases, requests, state = {}, {}, [], {}
    stopped = Event()

    class Handler(BaseHTTPRequestHandler):
        def send(self, value, kind="application/json"):
            content = json.dumps(value).encode() if kind == "application/json" else value
            self.send_response(200)
            self.send_header("Content-Type", kind + "; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self):
            if self.path == "/":
                jobs.clear(); leases.clear(); requests.clear(); state.clear()
                state.update(fail=False, advanced=False, unavailable=False, slow=False)
                return self.send(f'<!doctype html><html><iframe style="width:{self.server.case_width}px;height:1700px;border:0" src="/index.html#/cost-per-hour"></iframe><pre id="probe">PENDING</pre></html>'.encode(), "text/html")
            if self.path == "/api/session":
                return self.send(dict(csrf="synthetic-only"))
            if self.path == "/api/status":
                return self.send(dict(http="ready", session_detail=True))
            if self.path == "/api/live":
                return self.send(dict(instance_id="fixture", sequence=1, values=dict(live=live)))
            if self.path == "/api/events":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                try:
                    self.wfile.write(b": synthetic fixture\n\n"); self.wfile.flush()
                    stopped.wait(35)
                except (ConnectionError, OSError):
                    pass
                return
            if self.path.startswith("/api/jobs/"):
                return self.send(jobs[self.path.split("/")[3]])
            if self.path == "/fixture/requests":
                return self.send(requests)
            content = resources.get(self.path)
            if content is None:
                return self.send_error(404)
            kind = "text/javascript" if self.path.endswith(".js") else "text/css" if self.path.endswith(".css") else "text/html"
            self.send(content, kind)

        def do_POST(self):
            value = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            requests.append(dict(path=self.path, **value))
            if self.path == "/fixture/state":
                state.update(value); return self.send(dict(ok=True))
            if self.path == "/api/reports":
                key = str(len(jobs) + 1)
                jobs[key] = (dict(status="failed", error="pricing_unavailable") if state["fail"] else
                             dict(status="running", progress=dict(phase="history", completed=1, total=10)) if state["slow"] else
                             dict(status="complete", result=hourly))
                return self.send(dict(id=key))
            if self.path.startswith("/api/jobs/") and self.path.endswith("/cancel"):
                jobs[self.path.split("/")[3]] = dict(status="cancelled")
                return self.send(dict(cancelled=True))
            if self.path == "/api/detail":
                action = value["action"]
                if action == "open":
                    token = str(len(leases) + 1)
                    leases[token] = dict(mode=value["mode"], frozen=None)
                    return self.send(dict(token=token))
                lease = leases[value["token"]]
                if action == "freeze":
                    lease["frozen"] = details[int(state["advanced"])]; lease["mode"] = "snapshot"
                if action == "page":
                    page = lease["frozen"] or details[int(state["advanced"])]
                    return self.send(dict(page, mode=lease["mode"], state="source_unavailable" if state["unavailable"] else "observed"))
                return self.send(dict(ok=True))
            self.send_error(404)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = Thread(target=server.serve_forever)
    thread.start()
    outcomes = []
    try:
        with tempfile.TemporaryDirectory(dir=args.output.parent, prefix="hourly-browser-") as tmp:
            for theme, width in (("light", 1200), ("light", 360), ("dark", 1200), ("dark", 360)):
                server.case_width = width
                command = [str(args.browser), "--headless=new", "--disable-gpu", "--no-first-run",
                    "--no-default-browser-check", "--disable-extensions", "--disable-background-networking",
                    "--user-data-dir=" + str(Path(tmp) / f"{theme}-{width}"), "--window-size=1400,1900",
                    "--virtual-time-budget=20000", "--dump-dom"]
                if theme == "dark":
                    command.append("--force-dark-mode")
                command.append(f"http://127.0.0.1:{server.server_port}/")
                try:
                    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=40)
                    match = re.search(r'<pre id="probe">(.*?)</pre>', result.stdout, re.S)
                    outcome = json.loads(html.unescape(match[1])) if match and match[1] != "PENDING" else dict(outcome="FAIL", reason="no_browser_result")
                except subprocess.TimeoutExpired:
                    outcome = dict(outcome="TIMEOUT", reason="no_assertion_result")
                outcomes.append(dict(theme=theme, requested_width=width, **outcome))
                if outcome["outcome"] != "PASS":
                    break  # No known-failing browser repetition; consult first.
    finally:
        stopped.set(); server.shutdown(); server.server_close(); thread.join(5)
    evidence = dict(outcome="PASS" if len(outcomes) == 4 and all(case["outcome"] == "PASS" for case in outcomes) else "FAIL", cases=outcomes,
        limitations=["Synthetic HTTP data and scripted EventSource with shipped app in isolated headless Chromium; not real SSE or installed-history/source integration.",
                      "Programmatic focus/clicks are not physical keyboard, assistive-technology or macOS/native proof."])
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence))
    return int(evidence["outcome"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())
