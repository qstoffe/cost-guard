"""Owned archive at scale, with source corrections admitted only by fixture commands."""
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import shutil
import sys
from threading import Event
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.report_runtime import FakePricingProvider
from development.tests.fixtures.synthetic_month import SyntheticMonthSource, make_root_snapshot
from development.tests.fixtures.watch_summary import summary_watch
from development.tests.integration.serve_web_sessions import CaptureJobs
from development.tests.test_warm_restart import NOV_5, report_service
from src.analysis.session_cost import SessionCostGroup
from src.application.live_projection import project_live
from src.application.session_archive import DOMAIN
from src.application.session_catalog import SessionCatalog
from src.application.session_epoch_page import sort_value
from src.cache.session_projection import SORT_COLUMNS
from src.cache.web_archive import ArchiveFact, WebArchive, source_partition
from src.reports.models import SessionUsageRow
from src.reports.session_models import SessionModel
from src.reports.session_summary import encode_summary
from src.watch.observers import observe_catalog
from src.web.composition import open_cache
from src.web.host import WebHost


def seed(directory):
    store = WebArchive(directory, retain_writer=True)
    store.initialize()
    partition = source_partition('v2', 'synthetic-month', 'registered')
    try:
        for i in range(10_000):
            key = f'root-{i:04d}'
            cost = Decimal(i)
            model = f'Model {9999-i:04d}'
            group = SessionCostGroup(0, 'fixture', model, (), (), cost, i, True)
            at = NOV_5 - (10000-i)*60_000
            row = SessionUsageRow(key, f'Name {i:04d}', model, False, cost, 10000-i,
                                  duration_ms=i+1, last_activity_ms=at, context_tokens=10000-i,
                                  contributor_models=(f'fixture/{model}',), main_models=(SessionModel('fixture', model),),
                                  cost_groups=(group,), main_ccost=cost)
            fact = ArchiveFact('original', NOV_5-60_000, dict(row=encode_summary(row),
                                                               dependencies='fixture', models=[]))
            assert store.publish_session(partition, {DOMAIN: {key: fact}}, key,
                {sort: sort_value(row, sort) for sort in SORT_COLUMNS}, at, row.activity_latest_ms)
    finally:
        store.close_writer()


def main():
    directory = Path(sys.argv[1])
    (directory / 'config').mkdir()
    shutil.copyfile(ROOT / 'config/default-config.jsonc', directory / 'config/default-config.jsonc')
    seed(directory)
    now = [NOV_5]
    source = SyntheticMonthSource(0, 1, month_start_ms=NOV_5)
    source.source_id, source.source_instance, source.observation_epoch = 'opencode-v2', 'synthetic-month', 'registered'
    args = ('v2', source.source_instance, source.observation_epoch)
    catalog = SessionCatalog(archive=WebArchive(directory), clock_ms=lambda: now[0])
    catalog.bind_archive(*args)
    catalog.archive_maintenance()
    catalog.archive_pool.submit(lambda: None).result(timeout=30)
    catalog.observe(observe_catalog(source, include_archived_revisions=True))
    assert len(catalog.archive.rows) == 10_000
    cache, pricing = open_cache(directory), FakePricingProvider()
    host = WebHost(directory, jobs=CaptureJobs())
    host.live = SimpleNamespace(catalog=catalog, stopping=Event(), start=lambda: None, close=catalog.close)

    def publish():
        host.events.publish('live', dict(state='running', view=project_live(summary_watch(), 'UTC').to_json(),
                                        source_observed_at_ms=now[0], catalog_hint=catalog.live_hint()))

    try:
        host.start()
        host.publish_ready()
        publish()
        print(json.dumps(dict(url=host.browser_url())), flush=True)
        for line in sys.stdin:
            command = json.loads(line)['command']
            if command in ('correct', 'correct-offline'):
                # Different roots require no synthetic advancement of the retry scheduler.
                index = 25 if command == 'correct' else 26
                now[0] += 1000
                snapshot = make_root_snapshot(index, 3, month_start_ms=now[0]-(index+1)*60000)
                root = replace(snapshot.root, title=f'Name {index:04d} corrected')
                source.snapshots[root.session_id] = replace(snapshot, complete=True, root=root, sessions=(root,))
                catalog.observe(observe_catalog(source, include_archived_revisions=True))
                catalog.tick(report_service(source, cache, now[0], pricing))
                assert catalog.archive.rows[root.session_id].title == root.title
                publish()
            elif command != 'stats':
                raise ValueError(command)
            print(json.dumps(dict(reads=source.load_count)), flush=True)
    finally:
        host.close()


if __name__ == '__main__':
    main()
