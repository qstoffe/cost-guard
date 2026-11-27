"""Owned shipped Web host with synthetic native export and canonical detail data."""
from dataclasses import replace
from copy import deepcopy
import json
from pathlib import Path
import random
import shutil
import sys
from threading import Event, Thread
import time
from types import SimpleNamespace
import unittest
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from development.tests.fixtures.compact_reports import report_service
from development.tests.fixtures.session_export import export_source, SESSION, CHILD, SIBLING, GRANDCHILD, LEAF
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from development.tests.fixtures.web_help_reports import HelpAuditJobs
from development.tests.fixtures.watch_summary import summary_watch
from src.application.live_projection import project_live
from src.application.session_detail import SessionDetails
from src.application.session_catalog import SessionCatalog
from src.web.host import WebHost


class ExportRuntime:
    def __init__(self, service, publish):
        self.details = SessionDetails()
        self.catalog = SessionCatalog()
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


def extend_tree(state, names, expected):
    """A binary subtree below the original leaf, with distinct synthetic traces."""
    rng = random.Random(797)
    for i in range(31):
        member = f'ses_worker_{i}'
        parent = LEAF if not i else f'ses_worker_{(i - 1) // 2}'
        info = dict(id=member, parentID=parent, title=f'Nested worker {i}')
        messages = [dict(id=f'msg_{j}', sessionID=member, type='assistant', text=rng.randbytes(256).hex())
                    for j in range(128)]
        native = dict(info=info, messages=messages)
        state.tree[member] = expected[member] = native
        state.pages['page 2']['data'].append(info)
        names[member] = f'Nested worker {i}.json'


def main():
    config = Path(sys.argv[1])
    (config / 'config').mkdir(parents=True)
    shutil.copyfile(ROOT / 'config/default-config.jsonc', config / 'config/default-config.jsonc')
    test = unittest.TestCase()
    with export_source() as (native, state, _):
        source = SyntheticMonthSource(1, 3, month_start_ms=1000)
        snapshot = source.snapshots.pop('root-0000')
        root = replace(snapshot.root, session_id=SESSION, title='Synthetic: LIVE-style å 日本語 🚀?')
        source.snapshots[SESSION] = replace(snapshot, root=root, sessions=(root,), **{
            field: tuple(replace(item, session_id=SESSION) for item in getattr(snapshot, field))
            for field in ('messages', 'parts', 'events', 'invocations')})
        source.source_id, source.source_instance = native.source_id, native.source_instance
        source.observation_epoch, source.export_session_tree = native.observation_epoch, native.export_session_tree
        source.refresh_observation_epoch = native.refresh_observation_epoch
        state.tree[LEAF]['messages'] = [{'id': 'msg_error', 'type': 'assistant',
            'error': 'E_FIXTURE: password=synthetic-fixture-value; retry'}]
        expected = deepcopy(state.tree)
        expected[LEAF]['messages'][0]['error'] = 'E_FIXTURE: password=[REDACTED]; retry'
        names = {SESSION: 'Unicode å 日本語.json', CHILD: 'Unicode å 日本語 (1).json',
                 SIBLING: 'unicode å 日本語 (2).json', GRANDCHILD: 'session-ses_c.json', LEAF: 'Deep 🚀.json'}
        service = report_service(test, source)
        host = WebHost(config, jobs=HelpAuditJobs())
        host.live = ExportRuntime(service, host.events.publish)
        quota_ready = Event()
        page = host.live.details.page
        def quota_page(*args, **kwargs):
            result = page(*args, **kwargs)
            if kwargs.get('begin'):
                result['quota_state'] = 'ready' if quota_ready.is_set() else 'pending'
                result['quota_usage'] = {'scope': 'fixture', 'accounts': [{
                    'observation': {'id': 'test', 'label': 'Late subscription', 'provider_id': 'test'},
                    'quotas': [{'id': 'weekly', 'label': 'weekly', 'contribution': 'positive', 'percent': '17%'}]
                }]} if quota_ready.is_set() else None
            return result
        host.live.details.page = quota_page
        host.start(); host.publish_ready()
        print(json.dumps({'url': host.browser_url(), 'session': SESSION}), flush=True)
        try:
            for line in sys.stdin:
                command = json.loads(line)['command']
                if command == 'stop':
                    break
                if command == 'invalid':
                    del state.tree[LEAF]
                elif command == 'slow-tree':
                    extend_tree(state, names, expected)
                    # Each source response is healthy; their sum exceeds ordinary HTTP admission time.
                    state.before_export = lambda _: time.sleep(.16)
                elif command == 'remove-delay':
                    state.before_export = None
                elif command == 'publish-quota':
                    quota_ready.set()
                elif command == 'check-downloads':
                    files = sorted((config / 'downloads').glob('*.zip'))
                    for downloaded in files:
                        with ZipFile(downloaded) as archive:
                            test.assertCountEqual(names.values(), archive.namelist())
                            raw_bytes = sum(entry.file_size for entry in archive.infolist())
                            for member, name in names.items():
                                test.assertEqual(ZIP_DEFLATED, archive.getinfo(name).compress_type)
                                test.assertEqual(json.dumps(expected[member], ensure_ascii=False, indent=2) + '\n',
                                    archive.read(name).decode('utf-8'))
                    print(json.dumps({'checked': len(files), 'entries': len(names),
                                      'jsonBytes': raw_bytes if files else 0}), flush=True)
                    continue
                print(json.dumps({'requests': len(state.requests)}), flush=True)
        finally:
            host.close()
            test.doCleanups()


if __name__ == '__main__':
    main()
