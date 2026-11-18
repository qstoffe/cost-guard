"""Measure cold Today → 7 days with real analysis, SQLite and the catalog HTTP handler.

Uses owned normalized fixtures and in-process source reads. The handler is
called after each worker slice, with configurable worker cadence. The rendered
browser probe separately measures ordinary browser polling and acknowledgement.
Run this same script in a clean baseline checkout and the candidate checkout.
No installed source, accounts, models or provider network are accessed.
"""
import argparse
from collections import Counter
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.report_runtime import FakePricingProvider
from development.tests.fixtures.synthetic_month import SyntheticMonthSource, make_root_snapshot
from src.application.session_catalog import SessionCatalog
from src.cache import CacheDatabase, CacheRepository
from src.reports import ReportService
from src.sources.selection import SourceSelection
from src.watch.observers import observe_catalog
from src.web.session_catalog import catalog_page

DAY = 86_400_000
NOW = int(datetime(2026, 11, 13, 12, tzinfo=timezone.utc).timestamp() * 1000)


def fixture(size):
    source = SyntheticMonthSource(302, 8, month_start_ms=NOW - 4 * DAY,
                                  today_roots=30, now_ms=NOW, children_per_root=1, running_roots=1)
    for index, (key, snapshot) in enumerate(source.snapshots.items()):
        changes = dict(complete=True)
        if index == 2:
            changes.update(events=(), invocations=(), messages=(), parts=())
        elif index == 3:
            # A catalog touch admits an old prompt, but does not make it a member.
            old = make_root_snapshot(index, 8, month_start_ms=NOW - 14 * DAY)
            snapshot = replace(old, root=snapshot.root, sessions=(snapshot.root,))
        elif index % 11 == 0:
            # A complete bracket may still contain unpriced source telemetry.
            changes['invocations'] = tuple(replace(request, cost=None, model=replace(
                request.model, model="unpriced-fixture")) for request in snapshot.invocations)
        source.snapshots[key] = replace(snapshot, **changes)
    if size > 302:
        old = SyntheticMonthSource(size, 0, month_start_ms=NOW - 90 * DAY)
        source.snapshots.update(list(old.snapshots.items())[302:])
    return source


class MeasuredCache(CacheRepository):
    def __init__(self, database):
        super().__init__(database)
        self.operations = Counter()
        self.seconds = Counter()

    def get(self, namespace, *args, **kwargs):
        started = time.perf_counter()
        try:
            return super().get(namespace, *args, **kwargs)
        finally:
            self.operations['read:' + namespace] += 1
            self.seconds['read:' + namespace] += time.perf_counter() - started

    def put(self, namespace, *args, **kwargs):
        started = time.perf_counter()
        try:
            return super().put(namespace, *args, **kwargs)
        finally:
            self.operations['write:' + namespace] += 1
            self.seconds['write:' + namespace] += time.perf_counter() - started


class MeasuredService(ReportService):
    def _session_rows(self, *args, **kwargs):
        with self.metrics.measure('scalar_projection'):
            return super()._session_rows(*args, **kwargs)


def measure(size, sort, cadence, warm_cache, cache_dir):
    source = fixture(size)
    load = source.load_session_snapshot

    def measured_read(key):
        with source.metrics.measure('in_process_snapshot'):
            return load(key)

    source.load_session_snapshot = measured_read
    database = CacheDatabase(cache_dir)
    database.initialize()
    cache = MeasuredCache(database)
    pricing = FakePricingProvider()

    def service():
        return MeasuredService(selection=SourceSelection(source, 'v1', (), source.probe()),
            pricing_provider=pricing, account_provider=None, cache_repository=cache,
            config={'timezone': 'UTC'}, now_ms=NOW)

    discovery = time.perf_counter()
    observation = observe_catalog(source, include_archived_revisions=True)
    discovery = time.perf_counter() - discovery
    if warm_cache:
        from src.reports.session_summary import session_summary
        for root in observation.roots:
            if root.updated_at_ms >= NOW - 5 * DAY:
                session_summary(service(), root, observation.revisions[root.session_id])
    catalog = SessionCatalog(clock_ms=lambda: NOW)
    catalog.observe(observation)
    today = catalog_page(catalog, dict(sort=sort, navigation=1))
    for _ in range(10):
        catalog.tick(service())
    token = today['token']
    assert not catalog_page(catalog, dict(token=token, sort=sort, navigation=1))['pending_sort']
    catalog_page(catalog, dict(token=token, sort=sort, applied=1))
    assert not any(key in catalog.rows for key in ('root-0002', 'root-0003', 'root-0100'))
    before = dict(catalog.metrics)
    stages = source.metrics.milliseconds.copy()
    cache.operations.clear()
    cache.seconds.clear()
    reads, revisions = source.load_count, source.revision_count
    options = dict(token=token, sort=sort, period='7-days')
    wall, cpu = time.perf_counter(), time.process_time()
    first = catalog_page(catalog, dict(options, navigation=2))
    assert first['pending_sort']
    prior = first['progress']['completed']
    batches, polls, active, worker_cpu = [], 1, 0., 0.
    next_tick = wall + cadence
    while True:
        if len(batches) >= 110:
            raise AssertionError('fixture did not reach a verified page')
        time.sleep(max(0, next_tick - time.perf_counter()))
        started, started_cpu = time.perf_counter(), time.process_time()
        attempted = catalog.metrics['attempts']
        if catalog.needed():
            catalog.tick(service())
        active += time.perf_counter() - started
        worker_cpu += time.process_time() - started_cpu
        batches.append(catalog.metrics['attempts'] - attempted)
        polls += 1
        result = catalog_page(catalog, dict(options, navigation=2))
        assert result['progress']['completed'] >= prior
        prior = result['progress']['completed']
        if not result['pending_sort']:
            break
        next_tick = started + cadence
    final_epoch = catalog.leases[token]['epochs'][result['epoch']]
    assert result['total'] == 300 and result['size'] == 25
    assert result['progress']['completed'] == result['progress']['total'] == 302
    ids = [row.session_id for row in final_epoch.rows]
    assert ids[0] == 'root-0000' and set(ids) == set(source.snapshots).intersection(
        f'root-{index:04d}' for index in range(302) if index not in (2, 3))
    acknowledged = catalog_page(catalog, dict(options, applied=2, passive=True))
    assert acknowledged['total'] == result['total'] and not acknowledged['pending_sort']
    elapsed = time.perf_counter() - wall
    cold = dict(wall_s=round(elapsed, 3), newly_qualified_per_s=round((302 - first['indexed']) / elapsed, 2),
        worker_s=round(active, 3), idle_and_http_s=round(elapsed - active, 3),
        process_cpu_s=round(time.process_time() - cpu, 3), worker_cpu_s=round(worker_cpu, 3),
        first_indexed=first['indexed'], candidates=302, members=300, attempts_per_slice=batches, http_calls=polls + 1,
        reads=source.load_count - reads, revisions=source.revision_count - revisions,
        summary={key: value - before[key] for key, value in catalog.metrics.items()},
        measured_stage_ms={key: round(value - stages.get(key, 0), 3)
            for key, value in source.metrics.milliseconds.items()},
        cache_operations=dict(cache.operations),
        cache_ms={key: round(value * 1000, 3) for key, value in cache.seconds.items()})
    reads = source.load_count
    warm_start = time.perf_counter()
    back = catalog_page(catalog, dict(token=token, sort=sort, navigation=3))
    revisit = catalog_page(catalog, dict(options, navigation=4, applied=3))
    assert not back['pending_sort'] and not revisit['pending_sort'] and revisit['total'] == result['total']
    assert source.load_count == reads
    assert ids == [row.session_id for row in catalog.leases[token]['epochs'][revisit['epoch']].rows]
    digest = hashlib.sha256(json.dumps([asdict(row) for row in final_epoch.rows],
        ensure_ascii=True, sort_keys=True, default=str).encode()).hexdigest()
    return dict(size=size, sort=sort, cadence_s=cadence, disk_cache_preseeded=warm_cache,
        discovery_s=round(discovery, 3), transition=cold,
        revisit=dict(wall_s=round(time.perf_counter() - warm_start, 3), reads=0),
        qualified_digest=digest, order=ids)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--roots', type=int, choices=(302, 3000), default=302)
    parser.add_argument('--sort', choices=('activity', 'name', 'ccost', 'duration'), default='activity')
    parser.add_argument('--cadence', type=float, default=1.0)
    parser.add_argument('--warm-cache', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='catalog-period-', dir=args.output.parent) as path:
        result = measure(args.roots, args.sort, args.cadence, args.warm_cache, Path(path))
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in result.items() if key != 'order'}))


if __name__ == '__main__':
    main()
