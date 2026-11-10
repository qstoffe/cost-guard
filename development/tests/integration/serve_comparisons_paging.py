"""Offline 321-group browser host: real jobs/dispatcher/index and private bootstrap.

The separate loopback entry redirects to the normal one-use fixture link without
printing it. Controls affect only this synthetic host. No installed browser,
accounts, source history, inference or ordinary checkout is accessed.
"""
from dataclasses import replace
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import sys
import subprocess
import tempfile
from threading import Thread, Timer
import time
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.matched_inputs import source
from development.tests.fixtures.model_views import model_report
from development.tests.fixtures.report_runtime import FakePricingProvider
from development.tests.fixtures.watch_summary import summary_watch
from development.tests.fixtures.benchmark import payload
from development.tests.fixtures.web_reports import SyntheticSessionsRuntime
from development.tests.fixtures.token_mix_views import token_mix_report
from src.application import ReportApplication
from src.application.projection import project
from src.application.live_projection import project_live
from src.benchmarks import parse_pages
from src.cache import CacheDatabase, CacheRepository
from src.reports import ReportKind, ReportService
from src.sources.errors import SourceConcurrentChangeError
from src.sources.selection import SourceSelection
from src.web.dispatch import DataDispatcher
from src.analysis.cache import dependency_signature
from src.web.host import WebHost
from src.web.jobs import ReportJobs, run_report


def application(request, *, read_admission=None, history_checkpoint=None):
    root = Path(os.environ['COST_GUARD_PAGING_FIXTURE'])
    mode = (root / 'mode').read_text()
    history = source(int((root / 'groups').read_text()), start=int((root / 'start').read_text()))
    if mode == 'preview-error':
        def unavailable_preview(sid):
            raise SourceConcurrentChangeError('Synthetic unavailable preview')
        history.load_session_snapshot = unavailable_preview
    if mode == 'changed':
        snapshot = history.snapshots['root-0000']
        history.snapshots['root-0000'] = replace(snapshot, source_revision='changed-fixture-root')
    database = CacheDatabase(root)
    database.initialize()

    def factory(now, progress):
        def observe(event):
            progress(event)
            if mode == 'slow' and getattr(event, 'stage', None) == 'comparison-previews':
                time.sleep(.15)
            if mode in {'slow', 'stalled', 'source-error'} and getattr(event, 'stage', None) == 'comparison-groups':
                if mode == 'source-error':
                    raise SourceConcurrentChangeError('Synthetic source retry')
                if mode == 'stalled':
                    until = time.monotonic() + 60
                    while (root / 'mode').read_text() == 'stalled' and time.monotonic() < until:
                        time.sleep(.05)
                else:
                    time.sleep(2)
        service = ReportService(selection=SourceSelection(history, 'v2', (), history.probe()),
            pricing_provider=FakePricingProvider(), account_provider=None, cache_repository=CacheRepository(database),
            config={'timezone': 'UTC'}, now_ms=now, progress=observe)
        service.shared_web_evidence = True
        service.allow_partial_history = True
        service.history_checkpoint = history_checkpoint
        service.history_slice_roots = 256
        return service
    return ReportApplication(factory)


def finite(sender, request):
    if request.kind is ReportKind.COMPARISONS:
        with patch('src.web.composition.application', application):
            run_report(sender, request)
        return
    if request.kind is ReportKind.TOKEN_MIX:
        report = token_mix_report()
    else:
        report = tall_models()
        delay = float((Path(os.environ['COST_GUARD_PAGING_FIXTURE']) / 'models-delay').read_text())
        if delay:
            time.sleep(delay)
    sender.send(('result', json.dumps(dict(error=None, view=project(report).to_json(),
        source=dict(status='acquired', observed_at_ms=int(time.time() * 1000),
                    identity=dependency_signature(('v2', None))))).encode()))
    sender.close()


def tall_models():
    # Canonical, deliberately tall Models fixture; navigation/acquire remain shipped.
    report = model_report(include_model_catalog=True)
    catalog = report.model_catalog
    base = next(row for row in catalog.rows if row.model == 'Z')
    extra = tuple(replace(base, model=f'Synthetic model {i:02d}') for i in range(35))
    report = replace(report, model_catalog=replace(catalog, rows=catalog.rows + extra,
        selectable=catalog.selectable + tuple((row.publisher, row.model) for row in extra)))
    return report


class FixtureDispatcher(DataDispatcher):
    def tick(self, **_kwargs):
        super().tick(identity=dependency_signature(('v2', None)), ready=True)


class FixtureJobs(ReportJobs):
    def submit(self, request):
        root = Path(os.environ['COST_GUARD_PAGING_FIXTURE'])
        if request.kind is ReportKind.COMPARISONS and (root / 'mode').read_text() == 'busy':
            raise RuntimeError('busy')
        return super().submit(request)


@contextmanager
def fixture():
    """Shared actual HTTP/job fixture, also used by normally triggered hosted CI."""
    previous = os.environ.get('COST_GUARD_PAGING_FIXTURE')
    with tempfile.TemporaryDirectory(dir=os.environ.get('OPENCODE_TOOLKIT_SESSION_SCRATCH'), prefix='paging-') as tmp:
        root = Path(tmp)
        (root / 'config').mkdir()
        shutil.copyfile(ROOT / 'config/default-config.jsonc', root / 'config/default-config.jsonc')
        for name, value in {'mode': 'stable', 'groups': '321', 'models-delay': '0',
                            'start': str(int(time.time() * 1000) - 86400000)}.items():
            (root / name).write_text(value)
        os.environ['COST_GUARD_PAGING_FIXTURE'] = str(root)
        jobs = FixtureJobs(target=finite)
        host = WebHost(root, jobs=jobs)
        host.dispatcher = FixtureDispatcher(jobs)
        host.live = SyntheticSessionsRuntime(root)
        host.live.service.source = source(321, start=int((root / 'start').read_text()))
        host.live.driver = None
        host.live.source_failure = None
        host.benchmark.snapshot = parse_pages(payload()['pages'], int(time.time() * 1000))
        host.benchmark.next_due = float('inf')
        host.start()
        host.publish_ready()
        frame = summary_watch()
        card = frame.active_cards[0]
        frame = replace(frame, active_cards=tuple(replace(card, session_id=f'watch-{i}', title=f'Synthetic active {i}') for i in range(8)))
        host.events.publish('live', dict(state='running', source_observed_at_ms=frame.now_ms,
            view=project_live(frame).to_json()))
        try:
            yield host, root
        finally:
            host.stop()
            host.close()
            if previous is None:
                os.environ.pop('COST_GUARD_PAGING_FIXTURE', None)
            else:
                os.environ['COST_GUARD_PAGING_FIXTURE'] = previous


def main():
    with fixture() as (host, root):
        current_script = host.server.assets['app.js']
        baseline_script = subprocess.run(['git', 'show', '288b08358ad3b543d86447c68f40677ecb92fe25:src/web/assets/app.js'], cwd=ROOT,
            capture_output=True, check=True).stdout

        class Entry(BaseHTTPRequestHandler):
            def do_GET(self):
                query = parse_qs(urlsplit(self.path).query)
                mode = query.get('mode', [None])[0]
                script = query.get('script', [None])[0]
                if script in {'baseline', 'current'}:
                    host.server.assets['app.js'] = (baseline_script, current_script[1]) if script == 'baseline' else current_script
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'Fixture script selected')
                elif mode in {'stable', 'changed', 'slow', 'stalled', 'source-error', 'preview-error', 'busy'}:
                    (root / 'mode').write_text(mode)
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'Fixture mode set')
                elif query.get('groups', [None])[0] in {'0', '1', '321'}:
                    (root / 'groups').write_text(query['groups'][0])
                    host.dispatcher.invalidate()
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'Fixture group count set')
                elif self.path == '/stop':
                    self.send_response(200)
                    self.end_headers()
                    Thread(target=self.server.shutdown).start()
                else:
                    self.send_response(302)
                    self.send_header('Location', host.browser_url())
                    self.end_headers()

            def log_message(self, *_):
                pass

        entry = ThreadingHTTPServer(('127.0.0.1', 18754), Entry)
        timer = Timer(1200, entry.shutdown)
        timer.start()
        try:
            print('Offline paging fixture ready: http://127.0.0.1:18754/', flush=True)
            entry.serve_forever()
        finally:
            timer.cancel()
            entry.server_close()


if __name__ == '__main__':
    main()
