"""Fixed 2,700-root capture/admission benchmark; no real source or provider calls.

Measures CPU/memory and logical source IO, not disk/network latency or native UI.
Baseline code is read from the explicitly supplied Git revision, never checked out.
"""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import tracemalloc
import types

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from development.tests.fixtures.watch_runtime import make_service
from src.reports.watch_capture import capture_rows
from src.watch.card_workers import CardResult
from src.watch.cards import WatchCards
from src.watch.observers import observe_catalog
from src.application.session_catalog import SessionCatalog
from src.reports.models import SessionUsageRow
from decimal import Decimal

NOW = 1_000_000_000


class SliceWorkers:
    limit = 4

    def __init__(self, service):
        self.service, self.jobs, self.fetches = service, {}, {}
        self.capture_seconds = 0

    def submit(self, root, generation, now, previous, focal_ids):
        self.jobs[root.session_id] = (root, generation, previous, focal_ids)
        return True

    def drain(self):
        pending, self.jobs = self.jobs, {}
        results = []
        for key, (root, generation, previous, focal_ids) in pending.items():
            started = time.perf_counter()
            capture, item = capture_rows(self.service, root, previous, focal_ids)
            self.capture_seconds += time.perf_counter() - started
            self.fetches[key] = self.fetches.get(key, 0) + 1
            results.append(CardResult(key, generation, 'rows', (capture, (), item.snapshot)))
        return results


def measure(owner_type, count):
    with tempfile.TemporaryDirectory() as tmp:
        source = SyntheticMonthSource(count, 1, month_start_ms=1000)
        source.snapshots = {key: replace(value, complete=True) for key, value in source.snapshots.items()}
        service = make_service(tmp, source, now_ms=NOW)[2]
        workers = SliceWorkers(service)
        owner = owner_type(workers)
        tracemalloc.start()
        started, cpu = time.perf_counter(), time.process_time()
        first_visible = first_verified = None
        max_tick = 0
        max_admission_projection = 0
        changes = 0
        previous = ()
        owner.catalog(observe_catalog(source))
        for _ in range(count * 2):
            tick = time.perf_counter()
            capture_before = workers.capture_seconds
            owner.tick(NOW)
            history = owner.project(NOW)[1]
            max_tick = max(max_tick, time.perf_counter() - tick)
            max_admission_projection = max(max_admission_projection,
                time.perf_counter() - tick - (workers.capture_seconds - capture_before))
            ids = tuple(card.session_id for card in history)
            if ids and first_visible is None:
                first_visible = time.perf_counter() - started
            if previous and ids != previous:
                changes += 1
            previous = ids
            covered = all(entry.latest_ms is not None for entry in owner.sessions.values())
            if covered and len(history) == 5 and all(card.rows for card in history):
                first_verified = time.perf_counter() - started
                break
        assert first_verified is not None
        assert ids == tuple(f'root-{index:04}' for index in range(count-5, count)), 'independent fixed-source winners'
        if hasattr(owner, 'history'):
            assert owner.history.state == 'observed'
            assert (owner.history.checked, owner.history.total) == (count, count)
        cold_fetches = source.load_count
        # Unchanged source revisions reuse scalar coverage and retained finalists.
        owner.catalog(observe_catalog(source))
        for _ in range(10):
            owner.tick(NOW)
            owner.project(NOW)
        warm_fetches = source.load_count - cold_fetches
        root = source.snapshots['root-0000']
        source.snapshots['root-0000'] = replace(root, source_revision='changed')
        owner.catalog(observe_catalog(source))
        for _ in range(4):
            owner.tick(NOW)
            owner.project(NOW)
        changed_fetches = source.load_count - cold_fetches - warm_fetches
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        return dict(roots=count, first_visible_seconds=round(first_visible, 4),
            complete_capture_seconds=round(first_verified, 4), replacements_without_new_activity=changes,
            product_verified=hasattr(owner, 'history'), independently_expected_winners=True,
            cold_source_reads=cold_fetches, warm_source_reads=warm_fetches,
            changed_source_reads=changed_fetches, revision_checks=source.metrics.to_dict()['revision_checks']
                if hasattr(source.metrics, 'to_dict') else source.revision_count + count * source.batch_count,
            max_fetches_per_root=max(workers.fetches.values()), max_slice_seconds=round(max_tick, 4),
            capture_seconds=round(workers.capture_seconds, 4),
            max_admission_projection_seconds=round(max_admission_projection, 4),
            cpu_seconds=round(time.process_time()-cpu, 4), peak_traced_bytes=peak,
            retained_captures=sum(entry.capture is not None for entry in owner.sessions.values()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--roots', type=int, default=2700)
    parser.add_argument('--previews-only', action='store_true',
        help='Blocked-rich-worker first-useful-row matrix; no hydration or full proof benchmark.')
    args = parser.parse_args()
    code = subprocess.check_output(['git', 'show', f'{args.baseline}:src/watch/cards.py'], cwd=ROOT, text=True)
    baseline = types.ModuleType('src.watch.history_baseline')
    baseline.__package__ = 'src.watch'
    sys.modules[baseline.__name__] = baseline
    exec(compile(code, 'baseline/cards.py', 'exec'), baseline.__dict__)
    if args.previews_only:
        evidence = dict(baseline_revision=args.baseline, scenarios=[
            preview_measure(baseline.WatchCards, count, running, warm)
            for count in (25, 324, 2793, 3217) for running in (0, 1, 2, 5) for warm in (False, True)],
            limitations=['Synthetic shared scalar facts and metadata, not disk/network or installed-source timing.',
                'Rich workers remain blocked for a logical ten-minute interval; no ten-minute sleep or private scan.',
                'Preview eligibility is not certified global latest-five coverage.'])
        args.output.write_text(json.dumps(evidence, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(evidence))
        return
    evidence = dict(baseline_revision=args.baseline, baseline=measure(baseline.WatchCards, args.roots),
        candidate=measure(WatchCards, args.roots), limitations=[
            'Synthetic single-prompt roots; four-capture slices executed serially for reproducible logical IO.',
            'No disk/network latency, browser scheduling, provider latency or private desktop chronology proof.',
            'No safe metadata-only finish bound exists; cold proof still requires complete root coverage.'])
    assert evidence['candidate']['warm_source_reads'] == 0
    assert evidence['candidate']['replacements_without_new_activity'] == 0
    args.output.write_text(json.dumps(evidence, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(evidence))


def preview_measure(baseline_type, count, running, warm):
    source = SyntheticMonthSource(count, 0, month_start_ms=1000)
    source.snapshots = {key: replace(value, root=replace(value.root, active=False))
        for key, value in source.snapshots.items()}
    observation = observe_catalog(source)
    catalog = SessionCatalog(clock_ms=lambda: NOW)
    catalog.observe(observation)
    if warm:
        # Synthetic already-qualified Sessions scalar observations; no model or
        # source history is acquired by either measured publication.
        for key in list(catalog.roots)[-25:]:
            catalog.rows[key] = SessionUsageRow(key, catalog.roots[key].title, 'N/A', False,
                Decimal(12), 1, last_activity_ms=catalog.activity[key])
            catalog.valid[key] = catalog.revisions[key], catalog.clock()
            catalog.activity_valid[key] = catalog.revisions[key]
    baseline = baseline_type(type('BlockedWorkers', (), {'drain': lambda self: (), 'jobs': {}, 'limit': 4})())
    baseline.catalog(observation)
    before = source.load_count, source.catalog_count, source.batch_count
    started = time.perf_counter()
    history = baseline.project(NOW)[1]
    baseline_seconds = time.perf_counter() - started
    excluded = tuple(list(catalog.roots)[-(running):]) if running else ()
    started = time.perf_counter()
    previews = catalog.previews(excluded, limit=5-running)
    candidate_seconds = time.perf_counter() - started
    assert not history
    assert len(previews) == 5-running
    assert before == (source.load_count, source.catalog_count, source.batch_count)
    assert not catalog.leases
    return dict(roots=count, running=running, warm=warm, baseline_named_earlier_rows=len(history),
        candidate_named_earlier_rows=len(previews), blocked_worker_interval_seconds=600,
        baseline_publication_ms=round(baseline_seconds * 1000, 3),
        catalog_to_preview_ms=round(candidate_seconds * 1000, 3),
        qualified_totals=sum(value.total_ccost is not None for value in previews),
        extra_source_reads=0, browser_leases=0, global_proof_claimed=False)


if __name__ == '__main__':
    main()
