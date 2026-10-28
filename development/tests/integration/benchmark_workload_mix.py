"""Model-free before/after report timing; run from the candidate checkout.

Pass --source-tree to measure an extracted verified base using identical inputs.
No providers, model calls or live source. Reports are built via canonical owners.
"""
import argparse
import json
from pathlib import Path
import statistics
import sys
import tempfile
import time

parser = argparse.ArgumentParser()
parser.add_argument('--source-tree', default='.')
parser.add_argument('--roots', type=int, default=1000)
parser.add_argument('--prompts', type=int, default=20)
args = parser.parse_args()
sys.path.insert(0, str(Path(args.source_tree).resolve()))

from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from development.tests.fixtures.report_runtime import FakePricingProvider
from src.cache import CacheDatabase, CacheRepository
from src.reports import ReportService, ReportRequest, ReportKind
from src.sources.selection import SourceSelection

output = {}
for kind in (ReportKind.NORMAL, ReportKind.ALL_MODELS):
    source = SyntheticMonthSource(args.roots, args.prompts, month_start_ms=1_000_000)
    with tempfile.TemporaryDirectory() as directory:
        database = CacheDatabase(Path(directory)); database.initialize()
        repository = CacheRepository(database)
        def service():
            return ReportService(selection=SourceSelection(source, 'v2', (), source.probe()),
                pricing_provider=FakePricingProvider(), account_provider=None, cache_repository=repository,
                config={'timezone': 'UTC'}, now_ms=1_000_000_000)
        observations = []
        for _ in range(4):
            start = time.perf_counter()
            report = service().build(ReportRequest(kind))
            observations.append(time.perf_counter() - start)
        retained = service()
        retained.build(ReportRequest(kind))
        start = time.perf_counter()
        retained.build(ReportRequest(kind))
        refresh = time.perf_counter() - start
        output[kind.value] = dict(cold_seconds=observations[0],
            warm_median_seconds=statistics.median(observations[1:]), refresh_seconds=refresh,
            hydrated_roots=source.load_count, roots=args.roots, prompts=args.roots * args.prompts,
            global_sample=report.model_comparison_sample_size)
print(json.dumps(output, indent=2))
