"""Bounded synthetic Watch UI fixture for the integrated browser, not a UI driver.

The iframe supplies exact layout viewports. Styles select actual CSS media
branches; this is not OS-theme, native fullscreen, physical-input or AT proof.
No real account/source data, browser state or user configuration is acquired.
"""
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
from threading import Thread, Timer
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from development.tests.fixtures.watch_runtime import make_service
from src.application.live_projection import project_live
from src.watch.models import SkillObservation, ToolObservation, WatchCard, WatchProjection, WatchRow


def fixture():
    with tempfile.TemporaryDirectory() as tmp:
        source = SyntheticMonthSource(6, 12, month_start_ms=1000)
        _, _, service, _ = make_service(tmp, source, now_ms=100_000_000)
        cards = []
        for root in (snapshot.root for snapshot in source.snapshots.values()):
            block, _, _ = service.build_watch_root(root)
            cards.append(WatchCard(root.session_id, "Session " + root.session_id,
                "", tuple(WatchRow(root.session_id, root.title, row) for row in block.rows[-1:]), "observed"))
        active = cards[0]
        focal = active.rows[-1]
        tool = ToolObservation(tool_counts=tuple(("long-tool-name-" + str(index), 12 - index) for index in range(7)),
            failed_count=2, skills=tuple(SkillObservation("custom-skill-" + str(index), int(index == 0)) for index in range(7)),
            running_tool="shell-with-a-long-but-readable-name", running_ms=12000,
            background_kinds=("subagent",), background_ms=55000)
        focal = replace(focal, prompt=replace(focal.prompt, in_progress=True,
            watch_model="GPT model with a long readable name", watch_effort="XHigh",
            preview="Check completed behavior\nhttps://example.test/" + "unbroken" * 200), marker="▶", tool=tool)
        active = replace(active, title="Long running session · UTF-8 Å日本語 · live prompt cards",
            focal_id=focal.prompt.event_id, rows=(focal,))
        quota = service.build_watch_quota()
        return dict(state="running", view=project_live(WatchProjection("Watch", "fixture", (),
            now_ms=100_000_000, active_cards=(active,), history_cards=tuple(cards[1:]),
            cards_state="observed", history_state="observed", quota=quota)).to_json())


def main():
    payload = fixture()
    assets = ROOT / "src/web/assets"
    scripts = {"/" + name: (assets / name).read_bytes() for name in ("render.js", "watch.js")}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlsplit(self.path)
            query = parse_qs(url.query)
            theme = query.get("theme", ["classic"])[0]
            if url.path == "/stop":
                self.send_response(200); self.end_headers()
                Thread(target=self.server.shutdown).start()
                return
            if url.path == "/":
                width = query.get("width", ["1920"])[0]
                height = query.get("height", ["1080"])[0]
                if width not in {"1920", "1366", "360"} or height not in {"1080", "768", "800"}:
                    self.send_error(400); return
                content = (f'<!doctype html><title>Watch layout {width} {theme}</title><body style="margin:0">'
                    f'<iframe title="Watch fixture" style="border:0;width:{width}px;height:{height}px" '
                    f'src="/case.html?theme={theme}"></iframe>').encode()
            elif url.path == "/case.html":
                content = (f'<!doctype html><html lang="en" data-theme="{"classic" if theme == "classic" else "web"}">'
                    '<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                    f'<title>Watch synthetic fixture</title><link rel="stylesheet" href="/app.css?theme={theme}">'
                    '<body data-section="watch"><header><div class="brand"><div class="brand-mark">CG</div>'
                    '<h1>Cost Guard <small>Web Beta</small></h1></div></header><nav><a href="#/models">Models</a>'
                    '<a href="#/watch" aria-current="page">Watch</a><a href="#/accounts">Accounts</a><a href="#/sessions">Sessions</a></nav>'
                    '<main><div id="result"></div></main><script src="/render.js"></script><script src="/watch.js"></script>'
                    '<script>const INPUT=' + json.dumps(payload) + '; const state={connection:"Live connected."};'
                    'ReportView.renderLive(document.getElementById("result"),INPUT,state);'
                    'window.redraw=()=>ReportView.renderLive(document.getElementById("result"),INPUT,state);</script></body></html>').encode()
            elif url.path == "/app.css":
                content = (assets / "app.css").read_text().replace("@media (prefers-color-scheme: dark)",
                    "@media all" if theme == "dark" else "@media not all").encode()
            else:
                content = scripts.get(url.path)
            if content is None:
                self.send_error(404); return
            self.send_response(200)
            self.send_header("Content-Type", ("text/javascript" if url.path.endswith(".js") else
                "text/css" if url.path.endswith(".css") else "text/html") + "; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers(); self.wfile.write(content)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 18754), Handler)
    timer = Timer(900, server.shutdown); timer.start()
    try:
        print("Watch fixture ready: http://127.0.0.1:18754", flush=True)
        server.serve_forever()
    finally:
        timer.cancel(); server.server_close()


if __name__ == "__main__":
    main()
