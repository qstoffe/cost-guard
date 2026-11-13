"""Bounded source-neutral integrated-browser fixture for all Watch-derived tables."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from threading import Thread, Timer
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.compact_reports import report_service
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from development.tests.fixtures.watch_summary import summary_watch
from development.tests.fixtures.web_help_reports import HelpAuditJobs
from src.application.live_projection import project_live
from src.application.session_catalog import SessionCatalog
from src.application.session_detail import SessionDetails
from src.reports import ReportKind, ReportRequest
from src.watch.observers import observe_catalog


def main():
    owner = unittest.TestCase()
    service = report_service(owner, SyntheticMonthSource(120, 8, month_start_ms=1000, running_roots=1))
    catalog = SessionCatalog()
    catalog.observe(observe_catalog(service.source, include_archived_revisions=True))
    cold = catalog.page(period="all")
    catalog.tick(service)
    warm = catalog.page(token=cold["token"], period="all")
    details = SessionDetails()
    token = details.open("root-0000", "live")
    details.tick(service)
    detail = details.page(token, 0, begin=True)
    jobs = HelpAuditJobs()
    normal = jobs.snapshot(jobs.submit(ReportRequest(ReportKind.NORMAL)))["result"]
    mix = jobs.snapshot(jobs.submit(ReportRequest(ReportKind.TOKEN_MIX)))["result"]
    data = dict(cold=cold, warm=warm, detail=detail, normal=normal, mix=mix,
                watch=project_live(summary_watch()).to_json())
    html = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Web table parity — synthetic evidence</title><link rel="stylesheet" href="/app.css"><body><main><div id="result"></div></main>
<script src="/help.js"></script><script src="/render.js"></script><script src="/account-cards.js"></script><script src="/watch.js"></script>
<script src="/session.js"></script><script src="/sessions.js"></script><script src="/token-mix.js"></script><script src="/data.js"></script>
<script>
const root=document.getElementById('result'); let view;
function show(route) {
  root.replaceChildren(); document.body.dataset.section=route==='detail'?'sessions':route;
  if(route==='sessions') {view=new SessionsCatalog.View(async()=>DATA.warm);view.configure(new URLSearchParams());root.append(view.root);view.update(DATA.warm);}
  if(route==='detail') {view=new SessionDetail.View(async()=>DATA.detail,'root-0000');root.append(view.root);view.update(DATA.detail);view.sourceStatus(DATA.detail);}
  if(route==='models') ReportView.render(root,DATA.normal,{section:'models',pages:{}});
  if(route==='token-mix') {view=new TokenMixView.View();root.append(view.root);view.update(DATA.mix);}
  if(route==='watch') {view=new WatchView.View({connection:'Live connected.'});view.attach(root);view.update({view:DATA.watch,state:'running'});}
}
show(new URLSearchParams(location.search).get('route')||'sessions');
</script></body></html>'''.encode()
    resources = {"/" + name: (ROOT / "src/web/assets" / name).read_bytes() for name in
                 ("app.css", "help.js", "render.js", "account-cards.js", "watch.js", "session.js", "sessions.js", "token-mix.js")}
    resources["/data.js"] = ("const DATA=" + json.dumps(data) + ";").encode()
    resources["/"] = html

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/stop":
                self.send_response(200)
                self.end_headers()
                Thread(target=self.server.shutdown).start()
                return
            content = resources.get(path)
            if content is None:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/css" if path.endswith(".css") else "text/javascript" if path.endswith(".js") else "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    timer = Timer(600, server.shutdown)
    timer.start()
    try:
        print(f"Synthetic table fixture: http://127.0.0.1:{server.server_port}", flush=True)
        server.serve_forever()
    finally:
        timer.cancel()
        server.server_close()
        owner.doCleanups()


if __name__ == "__main__":
    main()
