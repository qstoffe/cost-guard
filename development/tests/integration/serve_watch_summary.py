"""Loopback synthetic Watch fixture for integrated-browser layout checks only.

No real source, credentials, settings or inference; stops after ten minutes.
"""
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import time
from threading import Thread, Timer
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.watch_summary import summary_watch
from src.application.live_projection import project_live
from src.analysis.timezones import local_day_start_ms


def main():
    assets = ROOT / 'src/web/assets'
    frames = None
    if '--stopped-parent' in sys.argv:
        from development.tests.fixtures.stopped_parent_watch import stopped_parent_frames
        frames = stopped_parent_frames()
        frame = summary_watch()
    elif '--tool-outcomes' in sys.argv:
        from development.tests.fixtures.watch_tool_outcomes import outcome_watch
        frame = outcome_watch()
    else:
        frame = summary_watch()
    now = int(time.time() * 1000)
    frame = replace(frame, now_ms=now, daily_usage=replace(frame.daily_usage,
        day_start_ms=local_day_start_ms('UTC', now_ms=now), observed_at_ms=now))
    resources = {'/' + name: (assets / name).read_bytes() for name in ('app.css', 'mini.css', 'mini.js', 'help.js', 'render.js', 'account-cards.js', 'watch.js')}
    resources['/data.js'] = ('const INPUT = ' + json.dumps(dict(state='running', view=project_live(frame).to_json())) + ';').encode()
    if frames is not None:
        resources['/data.js'] = ('const FRAMES = ' + json.dumps(frames) +
            '; const INPUT = {state:"running", view:FRAMES[0]}; let syntheticNow=FRAMES[0].now_ms; Date.now=()=>syntheticNow;').encode()
    if '--tool-outcomes' in sys.argv:
        from development.tests.fixtures.watch_tool_outcomes import revision_observations
        from src.application.live_projection import card_row
        sequences = {f'{mode}-{count}': [card_row(replace(frame.active_cards[0].rows[0], tool=tool), now).to_json()['tool']
                     for tool in revision_observations(mode, count)]
                     for mode in ('foreground', 'background') for count in (1, 2)}
        resources['/data.js'] += ('const REVISIONS = ' + json.dumps(sequences) + ';').encode()

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
                    <iframe title="Synthetic Watch" style="border:0;width:{width}px;height:1600px" src="/case.html?theme={theme}&scheme={scheme}"></iframe></html>'''.encode()
            elif url.path == '/case.html':
                theme = 'classic' if query.get('theme') == ['classic'] else 'web'
                scheme = 'dark' if query.get('scheme') == ['dark'] else 'light'
                mini = '''<button id="mini">Mini</button><p id="feedback"></p><script src="/mini.js"></script>
                    <script>const mini = new MiniWatch.Controller(window, document.getElementById('mini'), document.getElementById('feedback'), ()=>{});
                    mini.settings({miniWatchPlacement:'standard',miniWatchSize:'fit-on-open'},'synthetic');
                    mini.health({kind:'connected',writable:true}); mini.update(INPUT);</script>''' if frames else ''
                content = f'''<!doctype html><html lang="en" data-theme="{theme}"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
                    <title>Synthetic Watch</title><link rel="stylesheet" href="/app.css?scheme={scheme}"><main><h1>Watch</h1><div id="result"></div></main>
                    <script src="/help.js"></script><script src="/render.js"></script><script src="/account-cards.js"></script><script src="/watch.js"></script><script src="/data.js"></script>
                    <script>const state = {{connection:'Live connected.'}}; ReportView.renderLive(document.getElementById('result'), INPUT, state);</script>{mini}</html>'''.encode()
            else:
                content = resources.get(url.path)
                if content is not None and url.path == '/app.css':
                    # Emulate the requested media preference only in this synthetic fixture.
                    media = b'@media all' if query.get('scheme') == ['dark'] else b'@media not all'
                    content = content.replace(b'@media (prefers-color-scheme: dark)', media)
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
