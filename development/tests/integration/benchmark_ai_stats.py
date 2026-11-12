"""Fixed-history before/after AI Stats benchmark; no source, network or model work."""
import argparse
from dataclasses import asdict, replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import types

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.compact_reports import NOW
from development.tests.fixtures.report_runtime import FakePricingProvider
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from src.cache import CacheDatabase, CacheRepository
from src.domain.acquisition import AcquisitionMetrics
from src.reports import ReportService
from src.reports.ai_stats import build_ai_stats
from src.application.projection import project
from src.sources.selection import SourceSelection


def scenario(builder, size, scope, selected, sliced=False):
    source = SyntheticMonthSource(size, 20, month_start_ms=NOW - 3 * 86400000)
    source.snapshots = {sid: replace(s, complete=True) for sid, s in source.snapshots.items()}
    with tempfile.TemporaryDirectory(dir=os.environ['OPENCODE_TOOLKIT_SESSION_SCRATCH']) as directory:
        database = CacheDatabase(Path(directory))
        database.initialize()
        for attempt in ('cold', 'warm', 'changed'):
            source.metrics = AcquisitionMetrics(generation='synthetic')
            if attempt == 'changed':
                for sid in tuple(source.snapshots)[:max(1, size // 100)]:
                    source.snapshots[sid] = replace(source.snapshots[sid], source_revision='changed')
            def fresh():
                service = ReportService(selection=SourceSelection(source, 'v2', (), source.probe()),
                    pricing_provider=FakePricingProvider(), account_provider=None,
                    cache_repository=CacheRepository(database), config={'timezone': 'UTC'}, now_ms=NOW)
                if sliced:
                    service.stats_slice_roots, service.stats_scan = 256, 'fixed-benchmark-observation'
                return service

            before = source.load_count
            started, cpu = time.perf_counter(), time.process_time()
            slices = 0
            first_usable = None
            while True:
                service = fresh()
                report = builder(service, scope)
                slices += 1
                if first_usable is None and any(row.period == selected for row in report.ai_stats):
                    first_usable = time.perf_counter() - started
                work = report.ai_stats_work
                ready = work.get('scopes', {}).get(selected, {}).get('ready') if work else None
                if ready is None:
                    ready = any(row.period == selected for row in report.ai_stats)
                if ready:
                    break
                assert sliced and slices < size // 256 + 10, 'Bounded benchmark made no progress'
            elapsed, used_cpu = time.perf_counter() - started, time.process_time() - cpu
            row = next(row for row in report.ai_stats if row.period == selected)
            def comparable(row):
                value = asdict(row)
                value['metrics'] = [m for m in value['metrics'] if m['metric'] not in ('total-tokens', 'token-rate')]
                return value
            signature = hashlib.sha256(json.dumps(comparable(row), default=str, sort_keys=True).encode()).hexdigest()
            all_periods = hashlib.sha256(json.dumps([comparable(row) for row in report.ai_stats],
                default=str, sort_keys=True).encode()).hexdigest()
            result = dict(roots=size, requests=size * 20, scope=scope, attempt=attempt,
                seconds=round(elapsed, 4), cpu_seconds=round(used_cpu, 4), selected_sha256=signature,
                all_periods_sha256=all_periods, first_usable_seconds=round(first_usable, 4),
                hydrated=source.load_count - before, slices=slices, periods=len(report.ai_stats),
                view_bytes=len(json.dumps(project(report).to_json(), separators=(',', ':')).encode()),
                metrics=service.metrics.snapshot())
            yield result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', help='Exact Git revision whose AI Stats builder is measured without checkout')
    parser.add_argument('--large-roots', type=int, default=2700)
    parser.add_argument('--sliced', action='store_true', help='Both builders use fresh services and scan/256-root settings where supported; no process startup or IPC')
    args = parser.parse_args()
    builders = [('current', build_ai_stats)]
    if args.baseline:
        original = subprocess.check_output(['git', 'show', args.baseline + ':src/reports/ai_stats.py'], cwd=ROOT)
        module = types.ModuleType('src.reports.benchmark_baseline')
        module.__package__ = 'src.reports'
        exec(compile(original, '<baseline-ai-stats>', 'exec'), module.__dict__)
        # The old builder otherwise imports today's formula, making parity a
        # comparison of the new implementation with itself.
        analysis = types.ModuleType('src.analysis.benchmark_baseline')
        analysis.__package__ = 'src.analysis'
        sys.modules[analysis.__name__] = analysis
        formulas = subprocess.check_output(['git', 'show', args.baseline + ':src/analysis/ai_stats.py'], cwd=ROOT)
        exec(compile(formulas, '<baseline-stats-formulas>', 'exec'), analysis.__dict__)
        module.period_stats = analysis.period_stats
        module.StatsObservation = analysis.StatsObservation
        builders.insert(0, ('baseline', module.build_ai_stats))
    print(json.dumps(dict(environment=dict(python=sys.version.split()[0], platform=sys.platform),
                          source='fixed canonical synthetic history; no simulated I/O delay', baseline=args.baseline)))
    expected = {}
    for label, builder in builders:
        for size in (12, args.large_roots):
            for scope in ('7-days', '30-days', 'all'):
                # The historical baseline did not accept a narrower scope. It
                # acquired 30-days for a 7-day selection; measure that actual path.
                legacy_narrow = label == 'baseline' and scope == '7-days' and not hasattr(module, 'StatsAcquisition')
                actual = '30-days' if legacy_narrow else scope
                for result in scenario(builder, size, actual, scope, args.sliced):
                    identity = size, scope, result['attempt']
                    if label == 'baseline':
                        expected[identity] = result['selected_sha256']
                    elif identity in expected:
                        assert result['selected_sha256'] == expected[identity], 'Canonical selected-period mismatch'
                    print(json.dumps(dict(builder=label, selected=scope, **result)), flush=True)


if __name__ == '__main__':
    main()
