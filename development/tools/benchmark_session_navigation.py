"""Compare admitted navigation against a Git baseline with controlled scalar work.

No personal history or services. Wall/CPU are measured; the 10ms summary clock is
explicitly simulated, not a claim about workstation/source throughput.
"""
import argparse
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys
import time
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import src.application.session_catalog as current
from development.tests.fixtures.synthetic_month import SyntheticMonthSource, make_root_snapshot
from src.reports.models import SessionUsageRow
from src.watch.observers import observe_catalog


def measure(module, size, frozen):
    clock = [0.]
    source = SyntheticMonthSource(size, 1, month_start_ms=1000)
    catalog = module.SessionCatalog(clock=lambda: clock[0], clock_ms=lambda: 1_000_000_000)
    catalog.observe(observe_catalog(source, include_archived_revisions=True))
    service = SimpleNamespace(_dependencies=lambda _: (), _load_catalog=lambda: None,
        _load_comparison_catalog=lambda: SimpleNamespace(diagnostic_signature=()),
        source=source, timezone_id='UTC', config={})
    acquired, counts = [], {}
    active = 0.
    def summary(service, root, revision, *, metrics, on_activity=None, **kwargs):
        nonlocal active
        key = root.session_id
        acquired.append(key)
        counts[key] = counts.get(key, 0) + 1
        clock[0] += .01
        active += .01
        metrics['cache_hits'] += 1
        number = int(key.split('-')[1])
        if on_activity:
            on_activity((1000 + number * 60_000,), True)
        return SessionUsageRow(key, root.title, f'Model {number:05}', False, Decimal(number),
            number, duration_ms=number, context_tokens=number,
            last_activity_ms=1000 + number * 60_000), revision
    options = dict(sort='ccost', direction=1, period='all')
    first = catalog.page(**options, **({'navigation': 1} if frozen else {}))
    wall, cpu = time.perf_counter(), time.process_time()
    completed, previous, arrival_at = None, 0, None
    max_slices = (size + 3) // 4 + 20
    hot = f'root-{size - 1:04d}'
    with patch.object(module, 'session_summary', side_effect=summary):
        for batch in range(max_slices):
            catalog.tick(service)
            # Source evolves between the scalar slice and the HTTP observation.
            key = f'root-{size + batch:04d}'
            source.snapshots[key] = make_root_snapshot(size + batch, 1, month_start_ms=1000)
            source.snapshots[hot] = replace(source.snapshots[hot], source_revision=f'hot-{batch}')
            catalog.observe(observe_catalog(source, include_archived_revisions=True))
            page = catalog.page(token=first['token'], **options, **({'navigation': 1} if frozen else {}))
            if frozen:
                assert page['progress']['total'] == size
                assert page['progress']['completed'] >= previous
                previous = page['progress']['completed']
            if not page['pending_sort']:
                completed = dict(slices=batch + 1, simulated_seconds=round(clock[0], 3),
                    wall_seconds=round(time.perf_counter() - wall, 4))
                ids = tuple(row.session_id for row in
                            catalog.lease_pages.leases[first['token']]['epochs'][page['epoch']].rows)
                assert ids == tuple(f'root-{index:04d}' for index in range(size))
                assert not any(int(key.split('-')[1]) >= size for key in acquired)
                break
            clock[0] += 6  # Existing source retry cadence, not an agent wait.
        first_metrics = dict(catalog.metrics)
        first_reads = len(acquired)
        if frozen and completed:
            arrival_at = clock[0]
            catalog.page(token=first['token'], applied=1, **options)
            for batch in range(max_slices):
                clock[0] += 6
                catalog.tick(service)
                latest = catalog.page(token=first['token'], **options)
                if not latest['pending_sort']:
                    assert latest['total'] == len(source.snapshots)
                    arrival_at = round(clock[0] - arrival_at, 3)
                    break
            else:
                raise AssertionError('released arrivals were not reconciled')
    return dict(roots=size, contract='frozen' if frozen else 'baseline',
        applied=completed, observation_cap_slices=max_slices,
        first_view_summary_acquisitions=first_reads,
        duplicate_acquisitions=sum(value - 1 for value in counts.values()),
        first_view_metrics=first_metrics, total_summary_acquisitions=len(acquired),
        history_loads=source.load_count, modeled_summary_source_reads=0,
        simulated_worker_active_seconds=round(active, 3),
        simulated_worker_idle_seconds=round(clock[0] - active, 3),
        arrivals_reconciled_after_release_simulated_seconds=arrival_at,
        wall_seconds=round(time.perf_counter() - wall, 4),
        cpu_seconds=round(time.process_time() - cpu, 4))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = subprocess.run(['git', 'show', args.baseline + ':src/application/session_catalog.py'],
        cwd=ROOT, check=True, capture_output=True, encoding='utf-8')
    baseline = ModuleType('navigation_baseline')
    baseline.__package__ = 'src.application'
    exec(compile(result.stdout, '<git-navigation-baseline>', 'exec'), baseline.__dict__)
    evidence = [measure(module, size, frozen) for size in (324, 3217)
                for module, frozen in ((baseline, False), (current, True))]
    assert all(item['applied'] is not None for item in evidence if item['contract'] == 'frozen')
    output = dict(baseline=args.baseline, source='controlled scalar-cache fixture; no personal source',
        clock='10ms modeled summary; 6s modeled retry intervals; wall/CPU separately measured', results=evidence)
    Path(args.output).write_text(json.dumps(output, indent=2), encoding='utf-8')
    print(json.dumps(output))


if __name__ == '__main__':
    main()
