"""Measure same-host Accounts readiness using bounded, clock-driven turns."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from time import perf_counter, process_time, sleep

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from development.tests.fixtures.account_periods import subscription
from development.tests.fixtures.compact_reports import report_service
from development.tests.fixtures.report_runtime import FakePricingProvider
from development.tests.fixtures.synthetic_month import SyntheticMonthSource, make_root_snapshot
from development.tests.test_account_timeline import NOV_1, NOV_5, projected
from src.analysis.account_timeline import DAY_MS, PERIODS
from src.application.session_quota import source_scope
from src.cache import CacheDatabase, CacheRepository
from src.watch.account_timeline import AccountTimeline
from src.watch.observers import observe_catalog
from src.watch.source_reads import SourceReads


class History(SyntheticMonthSource):
    def __init__(self, roots, busy):
        super().__init__(0, 0, month_start_ms=NOV_1)
        self.busy = busy
        for index in range(roots):
            at = NOV_1 - (index % 29 - 3) * DAY_MS
            snapshot = make_root_snapshot(index, 3, month_start_ms=at)
            self.snapshots[snapshot.root.session_id] = replace(snapshot, complete=True)
        self.bursts = 0

    def load_session_snapshot(self, session_id):
        if self.busy:
            sleep(.001)  # A deterministic per-root source delay, not a native latency claim.
        return super().load_session_snapshot(session_id)

    def change_active(self, delta):
        self.bursts += 1
        for i in range(delta):
            key = f'root-{29 * i:04d}'
            snapshot = self.snapshots[key]
            root = replace(snapshot.root, active=True)
            self.snapshots[key] = replace(snapshot, root=root, sessions=(root,),
                                          source_revision=f'busy-{self.bursts}-{key}')


def run(folder, roots, warm):
    busy = roots >= 5000
    source = History(roots, busy)
    database = CacheDatabase(folder)
    database.initialize()
    repository = CacheRepository(database)
    pricing = FakePricingProvider()
    lane = AccountTimeline(lambda now: report_service(source, repository, now, pricing),
                           SourceReads(), repository)
    now = NOV_5 + 12 * 60 * 60_000
    options = dict(source=source_scope(source), accounts=projected(subscription('github-copilot')),
                   periods=frozenset(PERIODS), zone='UTC', catalog=pricing.catalog, prices=lambda: None,
                   migration_gap=None, require_background_prices=True,
                   observation=observe_catalog(source, include_archived_revisions=True))
    interest = frozenset() if warm else frozenset({'month'})
    first_ms = full_ms = None
    schedule_wait, worker_ms, prior_end, max_slice = 0, 0, now, 0
    started, cpu = perf_counter(), process_time()
    for turn in range(1000):
        if busy and turn in (25, 50, 75):
            source.change_active({25: 1, 50: 3, 75: 20}[turn])
            options['observation'] = observe_catalog(source, include_archived_revisions=True)
        lane.tick(**options, foreground=interest, now_ms=now)
        if lane.job is None:
            now += 1000
            continue
        schedule_wait += max(0, now - prior_end)
        before = perf_counter()
        lane.job.result(30)
        duration = round((perf_counter() - before) * 1000)
        worker_ms += duration
        max_slice = max(max_slice, duration)
        prior_end = now + duration
        lane.tick(**options, foreground=interest, now_ms=now + 1)
        views = {period: lane.lookup(period)['view'] for period in PERIODS}
        if first_ms is None and views['month'] and any(float(row['peak']) > 0 for row in views['month']['series']):
            first_ms = now + duration - NOV_5 - 12 * 60 * 60_000
        done = [view and not view['pending_buckets'] and not view['initial_pending_buckets'] for view in views.values()]
        if done[0] and all(done) or not warm and done[-1]:
            full_ms = now + duration - NOV_5 - 12 * 60 * 60_000
            break
        now = max(now + (1000 if warm else 200), lane.due, prior_end)

    if full_ms is None or first_ms is None:
        raise RuntimeError('fixture did not qualify the requested chart')
    before_open = source.load_count
    startup_wall = perf_counter() - started
    if warm:
        open_at = NOV_5 + 13 * 60 * 60_000
        assert now < open_at
        entered = perf_counter()
        lane.tick(**options, foreground=frozenset({'month'}), now_ms=open_at)
        chart = lane.lookup('month')['view']
        entry_ms = round((perf_counter() - entered) * 1000, 2)
        assert not chart['pending_buckets'] and not chart['initial_pending_buckets']
        if lane.job is not None:
            lane.job.result(30)
    else:
        entry_ms = first_ms
    cpu_ms = round((process_time() - cpu) * 1000)
    hits = sum(value.complete for value in lane.history.roots.values())
    lane.close()
    return dict(roots=roots, mode='off-page' if warm else 'foreground', first_fixture_ms=first_ms,
                full_fixture_ms=full_ms, observed_entry_ms=entry_ms, elapsed_harness_ms=round(startup_wall * 1000),
                worker_wall_ms=worker_ms, max_worker_slice_ms=max_slice, pacing_wait_fixture_ms=schedule_wait,
                process_cpu_ms=cpu_ms, new_source_reads_at_entry=source.load_count - before_open,
                source_reads_before_entry=before_open if warm else 0, source_reads=source.load_count,
                retained_complete_roots=hits, revised_root_bursts=source.bursts,
                sqlite_bytes=sum(path.stat().st_size for path in folder.rglob('*.sqlite3*')))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scratch', required=True, type=Path)
    parser.add_argument('--roots', nargs='+', type=int, default=(217, 2000, 5000))
    options = parser.parse_args()
    for roots in options.roots:
        for warm in (False, True):
            with TemporaryDirectory(prefix='background-accounts-', dir=options.scratch) as folder:
                print(json.dumps(run(Path(folder), roots, warm)), flush=True)


if __name__ == '__main__':
    main()
