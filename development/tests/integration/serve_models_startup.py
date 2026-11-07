"""Controlled first-Live handshake through the real authenticated Web host."""
from pathlib import Path
import json
import shutil
import sys
import time
from threading import Event
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.report_loading import LoadingJobs
from development.tests.fixtures.web_reports import SyntheticSessionsRuntime
from development.tests.fixtures.watch_summary import summary_watch
from src.application.live import LiveRuntime
from src.web.dispatch import DataDispatcher
from src.web.host import WebHost
from src.web.source_startup import SourceStartup


class StartupJobs(LoadingJobs):
    def __init__(self):
        super().__init__()
        self.mode = 'complete'
        self.submissions = []

    def submit(self, request):
        key = super().submit(request)
        result = self.jobs[key]['result']
        result['source'] = dict(status='acquired', observed_at_ms=int(time.time() * 1000))
        self.submissions.append(dict(id=key, kind=request.kind.value, at=time.monotonic()))
        return key

    def prioritize(self, priorities):
        self.priorities = priorities


class GatedDriver:
    def __init__(self, service):
        self.coordinator = SimpleNamespace(report_service=service,
            today_ccost=SimpleNamespace(history_pending=False))
        self.error = None
        self.terminal = False
        self.source_state = 'running'
        self.observed_at_ms = None
        self.release = Event()

    def tick(self):
        self.release.wait()
        self.observed_at_ms = int(time.time() * 1000)
        return summary_watch()

    def cancel(self):
        self.release.set()

    def close(self):
        pass


def main():
    root = Path(sys.argv[1])
    (root / 'config').mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / 'config/default-config.jsonc', root / 'config/default-config.jsonc')
    jobs = StartupJobs()
    host = WebHost(root, jobs=jobs)
    synthetic = SyntheticSessionsRuntime(root)
    driver = GatedDriver(synthetic.service)
    startup = SourceStartup(root, host.events.publish, host.stopping)

    def acquire():
        startup._selected(synthetic.service.selection)
        startup.finished.set()
        return driver

    host.source_startup = startup
    times = {}
    started = time.monotonic()

    def publish(kind, value):
        if kind == 'live' and value.to_json().get('view'):
            times.setdefault('first_live', round(time.monotonic() - started, 4))
        host.events.publish(kind, value)

    host.live = LiveRuntime(acquire, publish, host.runtime_failed)
    host.dispatcher = DataDispatcher(jobs)
    tick = host.dispatcher.tick

    def measured_tick(**kwargs):
        tick(**kwargs)
        if host.dispatcher.ready:
            times.setdefault('dispatcher_ready', round(time.monotonic() - started, 4))

    host.dispatcher.tick = measured_tick
    try:
        host.start()
        host.publish_ready()
        print(json.dumps({'url': host.browser_url()}), flush=True)
        for line in sys.stdin:
            action = json.loads(line)['command']
            if action == 'stop':
                break
            if action == 'release':
                driver.release.set()
            elif action == 'status':
                with host.dispatcher.lock:
                    print(json.dumps(dict(startup=startup.report_status(),
                        observed=host.live.observed.is_set(), identity=bool(host.dispatcher.identity),
                        ready=host.dispatcher.ready, error=host.dispatcher.source_error,
                        terminal=host.dispatcher.source_terminal, jobs=jobs.submissions,
                        seconds=times,
                        failure=type(host.failure).__name__ if host.failure else None)), flush=True)
                continue
            print('{"ok":true}', flush=True)
    finally:
        host.close()


if __name__ == '__main__':
    main()
