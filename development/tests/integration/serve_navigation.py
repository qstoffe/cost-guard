"""Offline browser host for navigation, scroll and zoom: real jobs/dispatcher.

Only owned synthetic data; no installed browser, accounts, source history,
inference or ordinary checkout is accessed.
"""
from dataclasses import replace
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.repeated_inputs import source
from development.tests.fixtures.model_views import model_report
from development.tests.fixtures.watch_summary import summary_watch
from development.tests.fixtures.benchmark import payload
from development.tests.fixtures.web_reports import SyntheticSessionsRuntime
from development.tests.fixtures.token_mix_views import token_mix_report
from development.tests.fixtures.synthetic_month import make_root_snapshot
from src.application.projection import project
from src.application.live_projection import project_live
from src.benchmarks import parse_pages
from src.reports import ReportKind
from src.analysis.cache import dependency_signature
from src.web.dispatch import DataDispatcher
from src.web.host import WebHost
from src.web.jobs import ReportJobs


def finite(sender, request):
    if request.kind is ReportKind.TOKEN_MIX:
        report = token_mix_report()
    else:
        report = tall_models()
        root = Path(os.environ['COST_GUARD_NAVIGATION_FIXTURE'])
        delay = (root / 'models-delay').read_text()
        if delay == 'gated':
            until = time.monotonic() + 30
            while not (root / 'models-release').exists() and time.monotonic() < until:
                time.sleep(.05)
            if not (root / 'models-release').exists():
                raise TimeoutError('synthetic_models_release_timeout')
            time.sleep(2)
        elif float(delay):
            time.sleep(float(delay))
    sender.send(('result', json.dumps(dict(error=None, observed_at_ms=int(time.time() * 1000), view=project(report).to_json(),
        source=dict(status='acquired', observed_at_ms=int(time.time() * 1000),
                    identity=dependency_signature(('v2', None))))).encode()))
    sender.close()


def tall_models():
    # Canonical, deliberately tall Models fixture; navigation/acquire remain shipped.
    report = model_report(include_model_catalog=True)
    catalog = report.model_catalog
    base = next(row for row in catalog.rows if row.model == 'Z')
    extra = (replace(base, publisher='Anthropic', model='Claude Opus 5.5'),
        *(replace(base, model=f'Synthetic model {i:02d}') for i in range(35)))
    report = replace(report, model_catalog=replace(catalog, rows=catalog.rows + extra,
        selectable=catalog.selectable + tuple((row.publisher, row.model) for row in extra)))
    return report


class FixtureDispatcher(DataDispatcher):
    def tick(self, **_kwargs):
        super().tick(identity=dependency_signature(('v2', None)), ready=True)


@contextmanager
def fixture():
    """Shared actual HTTP/job fixture, also used by normally triggered hosted CI."""
    previous = os.environ.get('COST_GUARD_NAVIGATION_FIXTURE')
    with tempfile.TemporaryDirectory(dir=os.environ.get('OPENCODE_TOOLKIT_SESSION_SCRATCH'), prefix='navigation-') as tmp:
        root = Path(tmp)
        (root / 'config').mkdir()
        shutil.copyfile(ROOT / 'config/default-config.jsonc', root / 'config/default-config.jsonc')
        for name, value in {'models-delay': '0',
                            'start': str(int(time.time() * 1000) - 86400000)}.items():
            (root / name).write_text(value)
        os.environ['COST_GUARD_NAVIGATION_FIXTURE'] = str(root)
        jobs = ReportJobs(target=finite)
        host = WebHost(root, jobs=jobs)
        host.dispatcher = FixtureDispatcher(jobs)
        session_source = source(321, start=int((root / 'start').read_text()))
        session_source.snapshots['root-0000'] = make_root_snapshot(0, 70,
            month_start_ms=int((root / 'start').read_text()))
        host.live = SyntheticSessionsRuntime(root, clock_ms=lambda: int(time.time() * 1000), source=session_source)
        host.live.driver = None
        host.live.source_failure = None
        board = payload()['pages']
        for row, score in zip(board[0]['rows'], (9, 80, 100, 80, 0)):
            row['metrics']['accuracy'] = score
        host.benchmark.snapshot = parse_pages(board, int(time.time() * 1000))
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
            if host.live.failure:
                raise RuntimeError('synthetic_live_acquisition_failed') from host.live.failure
        finally:
            host.stop()
            host.close()
            if previous is None:
                os.environ.pop('COST_GUARD_NAVIGATION_FIXTURE', None)
            else:
                os.environ['COST_GUARD_NAVIGATION_FIXTURE'] = previous
