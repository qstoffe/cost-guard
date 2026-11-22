"""Private-stdio canonical synthetic dispatcher host; no real source/providers/UI."""
from pathlib import Path
from dataclasses import replace
import json
import shutil
import sys
import time
from threading import Event
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.report_loading import LoadingJobs
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from development.tests.fixtures.web_reports import SyntheticSessionsRuntime
from development.tests.fixtures.watch_summary import summary_watch
from src.application.live_projection import project_live
from src.web.dispatch import DataDispatcher
from src.web.host import WebHost
from src.reports import ReportService


class DispatchJobs(LoadingJobs):
    def __init__(self):
        super().__init__()
        self.mode = 'complete'

    def submit(self, request):
        key = super().submit(request)
        result = self.jobs[key]['result']
        observed = int(time.time() * 1000)
        result['observed_at_ms'] = observed
        result['source'] = dict(status='acquired', observed_at_ms=observed)
        if request.kind.value in {'ai-stats', 'comparisons', 'token-mix'}:
            result['source'].update(status='partial', omitted_roots=3)
            if request.kind.value == 'comparisons':
                result['view']['comparisons']['complete'] = False
        return key

    def prioritize(self, priorities):
        self.priorities = priorities


def main():
    root = Path(sys.argv[1])
    (root / 'config').mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / 'config/default-config.jsonc', root / 'config/default-config.jsonc')
    jobs = DispatchJobs()
    host = WebHost(root, jobs=jobs)
    runtime = SyntheticSessionsRuntime(root)
    original = runtime.service
    source = SyntheticMonthSource(510, 1, month_start_ms=int(time.time() * 1000) - 86400000)
    runtime.service = ReportService(selection=replace(original.selection, source=source),
        pricing_provider=original.pricing_provider, account_provider=None,
        cache_repository=original.cache_repository, config=original.config, now_ms=int(time.time() * 1000))
    runtime.driver = SimpleNamespace(error=None, terminal=False, coordinator=SimpleNamespace(report_service=runtime.service))
    runtime.observed = Event()
    host.live = runtime
    host.dispatcher = DataDispatcher(jobs)
    try:
        host.start()
        host.publish_ready()
        host.events.publish('live', dict(state='running', view=project_live(summary_watch()).to_json(),
                                       source_observed_at_ms=int(time.time() * 1000)))
        runtime.observed.set()
        print(json.dumps({'url': host.browser_url()}), flush=True)
        for line in sys.stdin:
            action = json.loads(line)['command']
            if action == 'stop':
                break
            if action in {'hold', 'complete'}:
                jobs.mode = action
            if action == 'invalidate':
                jobs.mode = 'hold'
                with host.dispatcher.lock:
                    for entry in host.dispatcher.entries.values():
                        entry.update(result=None, due=0)
            if action == 'age':
                jobs.mode = 'hold'
                with host.dispatcher.lock:
                    for entry in host.dispatcher.entries.values():
                        if entry['result']:
                            entry['result']['source']['observed_at_ms'] = int(time.time() * 1000) - 61 * 60000
                            entry['due'] = 0
            if action == 'failed':
                jobs.mode = 'failed'
            if action == 'status':
                with host.dispatcher.lock:
                    print(json.dumps(dict(failure=type(host.failure).__name__ if host.failure else None,
                        reason=host.reason, jobs=len(jobs.jobs), ready=[request.kind.value for request, entry
                        in host.dispatcher.entries.items() if entry['result']])), flush=True)
            else:
                print('{"ok":true}', flush=True)
    finally:
        host.close()


if __name__ == '__main__':
    main()
