"""Real Web and native V1 reads over an owned SQLite fixture, with one delayed scalar."""
from collections import Counter
from contextlib import closing
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
from threading import Event, Thread
import time
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.compact_reports import report_service
from development.tests.fixtures.watch_summary import summary_watch
from development.tests.integration.serve_web_sessions import CaptureJobs
from development.tools.benchmark_session_period_change import DAY, NOW
from src.application.live_projection import project_live
from src.application.session_catalog import SessionCatalog
from src.sources.opencode_v1 import OpenCodeV1Source
from src.watch.observers import observe_catalog
from src.web.host import WebHost


class WarmPages:
    def __init__(self, root, owner):
        self.path = root / 'native.db'
        self.reads = Counter()
        self.worker = None
        self.delayed_read = Event()
        self.serial = 0
        self.delay = False
        self.clock = 0
        size = int(os.environ.get('COST_GUARD_WARM_PAGE_ROOTS', '43'))
        with closing(sqlite3.connect(self.path)) as db, db:
            db.executescript((ROOT / 'development/tests/fixtures/opencode_v1/schema.sql').read_text())
            for index in range(size):
                key = f'root-{index:04d}'
                start = NOW - 3_600_000 + index * 1000 - (0 if index < 43 else 10 * DAY)
                user = {'role': 'user', 'time': {'created': start}, 'agent': 'build'}
                assistant = {'role': 'assistant', 'parentID': key + '-user',
                    'time': {'created': start + 100}, 'providerID': 'github-copilot',
                    'modelID': 'gpt-test', 'tokens': {'input': 100, 'output': 10}}
                if index not in (40, 41, 42):
                    assistant['time']['completed'] = start + 200
                    assistant['finish'] = 'stop'
                db.execute('INSERT INTO session VALUES(?,NULL,?,?,?,?,?,NULL)',
                           (key, 'fixture', 'test', key, start, start + 200))
                db.executemany('INSERT INTO message VALUES(?,?,?,?,?)', [
                    (key + '-user', key, start, start, json.dumps(user)),
                    (key + '-assistant', key, start + 100, start + 200, json.dumps(assistant))])
                db.execute('INSERT INTO part VALUES(?,?,?,?,?,?)',
                           (key + '-text', key + '-user', key, start, start,
                            json.dumps({'type': 'text', 'text': 'Owned fixture'})))
                if index in (40, 41, 42):
                    tool = {'type': 'tool', 'tool': 'synthetic', 'callID': key,
                            'state': {'status': 'running', 'time': {'start': start + 100}}}
                    db.execute('INSERT INTO part VALUES(?,?,?,?,?,?)',
                               (key + '-tool', key + '-assistant', key, start + 100, start + 200, json.dumps(tool)))
        source = OpenCodeV1Source(self.path)
        original_load = source.load_session_snapshot

        def measured_load(key):
            self.reads[key] += 1
            if self.delay and key == 'root-0000':
                self.delayed_read.set()
                time.sleep(.65)
            return original_load(key)

        source.load_session_snapshot = measured_load
        self.service = report_service(owner, source, now_ms=NOW)
        self.catalog = SessionCatalog(clock=lambda: self.clock, clock_ms=lambda: NOW)
        self.observe()
        self.catalog.tick(self.service)

    def observe(self):
        self.catalog.observe(observe_catalog(self.service.source, include_archived_revisions=True))

    def tick(self):
        self.catalog.tick(self.service)

    def churn(self, finish=False):
        self.join()
        self.serial += 1
        self.clock += 1
        with closing(sqlite3.connect(self.path)) as db, db:
            for key in ('root-0042', 'root-0000'):
                identifier = key + '-assistant'
                data, updated = db.execute('SELECT data,time_updated FROM message WHERE id=?',
                                           (identifier,)).fetchone()
                assistant = json.loads(data)
                assistant['tokens']['input'] += self.serial
                if finish and key == 'root-0042':
                    assistant['time']['completed'] = NOW - 1000
                    assistant['finish'] = 'stop'
                    tool = json.loads(db.execute('SELECT data FROM part WHERE id=?', (key + '-tool',)).fetchone()[0])
                    tool['state']['status'] = 'completed'
                    tool['state']['time']['end'] = NOW - 1000
                    db.execute('UPDATE part SET data=?,time_updated=? WHERE id=?',
                               (json.dumps(tool), NOW - 1000, key + '-tool'))
                db.execute('UPDATE message SET data=?,time_updated=? WHERE id=?',
                           (json.dumps(assistant), updated + 1, identifier))
                db.execute('UPDATE session SET time_updated=? WHERE id=?', (updated + 1, key))
        self.observe()
        # Make the two revised roots due without fast-forwarding unrelated
        # running evidence or doing another read outside the shared lane.
        with self.catalog.lock:
            for key in ('root-0042', 'root-0000'):
                self.catalog.attempted.pop(key, None)
        self.delay = not finish
        self.delayed_read.clear()
        self.worker = Thread(target=self.tick)
        self.worker.start()
        if self.delay and not self.delayed_read.wait(5):
            raise RuntimeError('offscreen_scalar_was_not_admitted')

    def join(self):
        if self.worker is not None:
            self.worker.join()
            self.worker = None

    def start(self):
        pass  # The fixture explicitly admits worker slices through stdin.

    def close(self):
        self.join()

    def stats(self):
        with self.catalog.lock:
            return dict(reads=dict(self.reads), metrics=dict(self.catalog.metrics),
                        work=self.catalog.work, generation=self.catalog.generation,
                        stale=sum(not self.catalog._current(key) for key in ('root-0042', 'root-0000')))


def main():
    root = Path(sys.argv[1])
    (root / 'config').mkdir()
    shutil.copyfile(ROOT / 'config/default-config.jsonc', root / 'config/default-config.jsonc')
    owner = unittest.TestCase()
    live = WarmPages(root, owner)
    host = WebHost(root, jobs=CaptureJobs())
    host.live = live
    host.start()
    host.publish_ready()
    host.events.publish('live', dict(state='running', view=project_live(summary_watch(), 'UTC').to_json(),
                                    source_observed_at_ms=NOW, catalog_hint=live.catalog.live_hint()))
    print(json.dumps(dict(url=host.browser_url())), flush=True)
    try:
        for line in sys.stdin:
            command = json.loads(line)['command']
            if command == 'stop':
                break
            if command == 'warm':
                for _ in range(11):
                    live.tick()
            elif command == 'refresh':
                live.join()
                live.tick()
            elif command in ('churn', 'finish'):
                live.churn(finish=command == 'finish')
            elif command == 'join':
                live.join()
            elif command != 'stats':
                raise ValueError('unsupported_fixture_command')
            print(json.dumps(live.stats()), flush=True)
    finally:
        live.join()
        host.close()
        owner.doCleanups()


if __name__ == '__main__':
    main()
