"""Fixed 2700-root/54000-request compatible-evidence benchmark; no remote access."""
from dataclasses import replace
import argparse
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.compact_reports import NOW
from development.tests.fixtures.report_runtime import FakePricingProvider
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from development.tests.integration.historical_report_observations import peak_memory
from src.cache import CacheDatabase, CacheRepository
from src.config import load_configuration
from src.reports import ReportKind, ReportRequest, ReportService
from src.sources.selection import SourceSelection


def run(shared, roots=2700):
    source = SyntheticMonthSource(roots, 20, month_start_ms=NOW - 30 * 86400000)
    source.snapshots = {key: replace(value, complete=True) for key, value in source.snapshots.items()}
    pricing = FakePricingProvider()
    config = dict(load_configuration(ROOT).values, timezone='UTC')
    outcomes = []
    with tempfile.TemporaryDirectory() as temporary:
        database = CacheDatabase(Path(temporary))
        database.initialize()
        cache = CacheRepository(database)
        for cycle in ('cold', 'warm'):
            for kind in (ReportKind.NORMAL, ReportKind.TOKEN_MIX, ReportKind.AI_STATS, ReportKind.COMPARISONS):
                service = ReportService(selection=SourceSelection(source, 'v1', (), source.probe()),
                    pricing_provider=pricing, account_provider=None, cache_repository=cache,
                    config=config, now_ms=NOW, cache_token_mix_history=True)
                service.shared_web_evidence = shared
                previous = source.load_count
                started, cpu = time.perf_counter(), time.process_time()
                report = service.build_token_mix_history() if kind is ReportKind.TOKEN_MIX else service.build(ReportRequest(kind))
                outcomes.append(dict(cycle=cycle, kind=kind.value, roots_read=source.load_count - previous,
                    seconds=round(time.perf_counter() - started, 4), cpu_seconds=round(time.process_time() - cpu, 4),
                    stats_periods=len(report.ai_stats), sample=report.model_comparison_sample_size))
                service.close_accounts()
    return dict(shared=shared, roots=roots, requests=roots * 20, total_root_reads=source.load_count,
                peak_memory=peak_memory(), outcomes=outcomes)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--roots', type=int, default=2700)
    parser.add_argument('--shared-only', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.roots <= 10000:
        parser.error('roots must be 1..10000')
    for shared in (True,) if args.shared_only else (False, True):
        print(json.dumps(run(shared, args.roots)), flush=True)
