"""Generate an offline, synthetic before/after owner-review gallery (no browser)."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.report_runtime import FakeAccountProvider, FakePricingProvider, FakeSource
from development.tests.fixtures.session_snapshots import make_snapshot
from development.tests.fixtures.watch_runtime import MutableSource, make_service
from src.application import ReportApplication
from src.application.live_projection import project_live
from src.cache import CacheDatabase, CacheRepository
from src.config import load_configuration
from src.reports import ReportKind, ReportRequest, ReportService
from src.sources.selection import SourceSelection
from src.watch.coordinator import WatchCoordinator


def synthetic_reports():
    """Use canonical report/Watch projections; never read installed user history."""
    with tempfile.TemporaryDirectory() as tmp:
        database = CacheDatabase(Path(tmp) / "reports")
        database.initialize()
        source = FakeSource(make_snapshot(running=True))

        def factory(now, progress):
            return ReportService(selection=SourceSelection(source, "v1", (), source.probe()),
                pricing_provider=FakePricingProvider(), account_provider=FakeAccountProvider(),
                cache_repository=CacheRepository(database), config=load_configuration(ROOT).values,
                now_ms=now, progress=progress)

        application = ReportApplication(factory, clock=lambda: 4000)
        normal = application.execute(ReportRequest()).to_json()
        sessions = application.execute(ReportRequest(ReportKind.SESSIONS, session_limit=None)).to_json()
        config, selection, service, _ = make_service(Path(tmp) / "watch", MutableSource(make_snapshot()))
        owner = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: 2200)
        try:
            live = {"state": "running", "view": project_live(owner.initialize().projection).to_json()}
        finally:
            owner.close()
        assert not normal["error"] and not sessions["error"]
        return {"normal": normal, "sessions": sessions, "watch": live}


def generate(output, baseline):
    output.mkdir(parents=True, exist_ok=True)
    assets = ROOT / "src/web/assets"
    for name, value in synthetic_reports().items():
        (output / f"{name}.js").write_text("const " + name.upper() + " = " + json.dumps(value, ensure_ascii=True) + ";\n", encoding="utf-8", newline="\n")
    for stage in ("before", "after"):
        def asset(name):
            if stage == "after":
                return (assets / name).read_text(encoding="utf-8")
            return subprocess.check_output(["git", "show", baseline + ":src/web/assets/" + name], cwd=ROOT).decode("utf-8")

        for name in ("app.css", "render.js"):
            (output / f"{stage}-{name}").write_text(asset(name), encoding="utf-8", newline="\n")
        watch_script = ''
        if stage == 'after':
            (output / 'after-watch.js').write_text(asset('watch.js'), encoding='utf-8', newline='\n')
            watch_script = '<script src="after-watch.js"></script>'
        shell = re.sub(r"<script.*?</script>", "", asset("index.html"))
        shell = shell.replace('/app.css', f'{stage}-app.css')
        scripts = ''.join(f'<script src="{name}.js"></script>' for name in ("normal", "sessions", "watch"))
        shell = shell.replace('</body>', f'<script src="{stage}-render.js"></script>{watch_script}{scripts}<script src="preview.js"></script></body>')
        (output / f"{stage}.html").write_text(shell, encoding="utf-8", newline="\n")
    (output / "preview.js").write_text(PREVIEW, encoding="utf-8", newline="\n")
    (output / "index.html").write_text(GALLERY.replace("BASELINE", baseline), encoding="utf-8", newline="\n")


PREVIEW = """'use strict';
const view = new URLSearchParams(location.search).get('view') || 'overview';
const state = {section: view, pages: {}};
const output = document.getElementById('result');
document.getElementById('heading').textContent = view[0].toUpperCase() + view.slice(1);
if (view === 'watch' && !document.querySelector('nav a[href="#/watch"]')) document.getElementById('heading').textContent = 'Live';
document.getElementById('status').textContent = 'Synthetic fixture · HTTP/source/account status not measured';
document.getElementById('notice').textContent = 'Visual review fixture only · no real accounts, source or acquisition';
output.setAttribute('aria-busy', 'false');
const draw = () => view === 'watch' ? ReportView.renderLive(output, WATCH, state) :
  ReportView.render(output, view === 'sessions' ? SESSIONS : NORMAL, state);
draw();
for (const a of document.querySelectorAll('nav a')) {
  if (a.hash === '#/' + view || view === 'watch' && a.hash === '#/live') a.setAttribute('aria-current', 'page');
  a.addEventListener('click', event => event.preventDefault());
}
document.getElementById('search').addEventListener('input', event => {state.search = event.target.value; state.pages = {}; draw();});
document.getElementById('skip').addEventListener('click', () => document.getElementById('content').focus());
"""

GALLERY = """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>FR 000440 visual review</title>
<style>
body {font:15px/1.5 system-ui; margin:1rem; background:#edf1f7; color:#182536}
h1 {font-size:1.4rem} label {display:inline-block; margin:.4rem} select,button {font:inherit; padding:.4rem}
.pair {display:flex; gap:1rem; flex-wrap:wrap} iframe {border:1px solid #7387a5; height:1000px; width:100%; background:white}
article {min-width:0; flex:1} h2 {font-size:1rem} code {overflow-wrap:anywhere}
</style>
<h1>Web Beta · before / after</h1>
<p>FR 000440 owner-review artifact · synthetic canonical DTOs only. Baseline <code>BASELINE</code>.
No live history, credentials or account identifiers. These frozen previews are not runtime or screen-reader proof.</p>
<label>View <select id="view"><option>overview</option><option>watch</option><option>sessions</option><option>models</option><option>accounts</option></select></label>
<label>Width <select id="width"><option value="100%">Side by side</option><option value="1440px">Desktop 1440px</option><option value="360px">Narrow 360px</option></select></label>
<label>Theme <select id="theme"><option>light</option><option>dark</option></select></label>
<p>Scroll each preview independently; table filters, sorting and pagination work locally. Navigation and acquisition are disabled. No fields or rows are removed between versions. Use browser Find/select/copy inside a preview.</p>
<div class="pair"><article><h2>Before · legacy Live navigation</h2><iframe title="Before design" id="before"></iframe></article>
<article><h2>After · Watch navigation</h2><iframe title="After design" id="after"></iframe></article></div>
<details><summary>Browser-rendered fixture facts (not visual proof)</summary><pre id="audit">Loading previews</pre></details>
<script>
const query = new URLSearchParams(location.search);
for (const id of ['view','width','theme']) if(query.has(id)) document.getElementById(id).value = query.get(id);
function update() {
  for (const id of ['before','after']) {
    const frame = document.getElementById(id);
    frame.style.width = document.getElementById('width').value;
    frame.style.colorScheme = document.getElementById('theme').value;
    const target = id + '.html?view=' + document.getElementById('view').value;
    if (!frame.src.endsWith(target)) frame.src = target;
  }
}
for (const id of ['view','width','theme']) document.getElementById(id).addEventListener('change', update);
function audit() {
  const frames = ['before','after'].map(id => document.getElementById(id));
  if (frames.some(frame => !frame.contentDocument?.querySelector('#result table'))) return;
  const tables = frames.map(frame => [...frame.contentDocument.querySelectorAll('#result table')].map(t => t.textContent));
  const facts = frames.map(frame => {
    const doc = frame.contentDocument, root = doc.documentElement;
    const input = doc.getElementById('search'); input.focus();
    const focusVisible = frame.contentWindow.getComputedStyle(input).outlineStyle !== 'none';
    input.blur();
    return {width: root.clientWidth, scrollWidth: root.scrollWidth, tables: doc.querySelectorAll('table').length,
      rows: doc.querySelectorAll('tbody tr').length, focusVisible,
      reducedMotion: frame.contentWindow.matchMedia('(prefers-reduced-motion: reduce)').matches,
      transition: frame.contentWindow.getComputedStyle(input).transitionDuration,
      stickyHeading: frame.contentWindow.getComputedStyle(doc.querySelector('th')).position,
      background: frame.contentWindow.getComputedStyle(root).getPropertyValue('--bg').trim()};
  });
  document.getElementById('audit').textContent = JSON.stringify({tableParity: JSON.stringify(tables[0]) === JSON.stringify(tables[1]), facts});
}
for (const id of ['before','after']) document.getElementById(id).addEventListener('load', audit);
update();
</script></html>
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", required=True)
    args = parser.parse_args()
    generate(args.output, args.baseline)
