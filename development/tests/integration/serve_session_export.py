"""Owned shipped Web host with synthetic native export and canonical detail data."""
from dataclasses import replace
import json
from pathlib import Path
import shutil
import sys
from threading import Event, Thread
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from development.tests.fixtures.compact_reports import report_service
from development.tests.fixtures.session_export import export_source, SESSION
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from development.tests.fixtures.web_help_reports import HelpAuditJobs
from development.tests.fixtures.watch_summary import summary_watch
from src.application.live_projection import project_live
from src.application.session_detail import SessionDetails
from src.web.host import WebHost


class ExportRuntime:
    def __init__(self, service, publish):
        self.details = SessionDetails()
        self.driver = SimpleNamespace(coordinator=SimpleNamespace(report_service=service))
        self.stopping = Event()
        self.service, self.publish = service, publish
        self.thread = Thread(target=self.run)

    def start(self):
        self.thread.start()

    def run(self):
        while not self.stopping.is_set():
            self.details.tick(self.service)
            self.publish('live', dict(state='running', source_observed_at_ms=self.service.now_ms,
                view=project_live(summary_watch(), 'UTC').to_json()))
            self.stopping.wait(.1)

    def close(self):
        self.stopping.set()
        self.thread.join(3)
        if self.thread.is_alive():
            raise RuntimeError('fixture_shutdown_timeout')


def main():
    config = Path(sys.argv[1])
    (config / 'config').mkdir(parents=True)
    shutil.copyfile(ROOT / 'config/default-config.jsonc', config / 'config/default-config.jsonc')
    test = unittest.TestCase()
    with export_source() as (native, state, _):
        source = SyntheticMonthSource(1, 3, month_start_ms=1000)
        snapshot = source.snapshots.pop('root-0000')
        root = replace(snapshot.root, session_id=SESSION, title='Synthetic LIVE-style å 日本語')
        source.snapshots[SESSION] = replace(snapshot, root=root, sessions=(root,), **{
            field: tuple(replace(item, session_id=SESSION) for item in getattr(snapshot, field))
            for field in ('messages', 'parts', 'events', 'invocations')})
        source.source_id, source.source_instance = native.source_id, native.source_instance
        source.observation_epoch, source.export_session = native.observation_epoch, native.export_session
        service = report_service(test, source)
        host = WebHost(config, jobs=HelpAuditJobs())
        host.live = ExportRuntime(service, host.events.publish)
        host.start(); host.publish_ready()
        print(json.dumps({'url': host.browser_url(), 'session': SESSION}), flush=True)
        try:
            for line in sys.stdin:
                command = json.loads(line)['command']
                if command == 'stop':
                    break
                if command == 'invalid':
                    state.body = b'{"data":null}'
                elif command == 'recover':
                    state.body = None
                print(json.dumps({'requests': len(state.requests)}), flush=True)
        finally:
            host.close()
            test.doCleanups()


if __name__ == '__main__':
    main()
