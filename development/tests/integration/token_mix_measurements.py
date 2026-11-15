"""Numeric-only 520-root cross-period measurements over the maintained fixture."""
from dataclasses import replace
from contextlib import ExitStack
import json
import time
import unittest
from unittest.mock import patch

from development.tests.fixtures.compact_reports import report_service, START
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from src.pricing.catalog import PricingCatalog
from src.reports import ReportService
from src.reports.token_mix_cache import NAMESPACE


def measure():
    results = []
    for reuse in (False, True):
        case = unittest.TestCase()
        try:
            source = SyntheticMonthSource(520, 4, month_start_ms=START)
            source.snapshots = {sid: replace(snapshot, complete=True) for sid, snapshot in source.snapshots.items()}
            original = report_service(case, source)
            evidence = None
            for index, scope in enumerate(('all', '7-days', '30-days', 'all')):
                service = ReportService(selection=original.selection, pricing_provider=original.pricing_provider,
                    account_provider=None, cache_repository=original.cache_repository, config=original.config,
                    now_ms=original.now_ms, model_availability_source=original.model_availability_source,
                    cache_token_mix_history=True)
                service.shared_web_evidence = True
                service.token_mix_reuse = json.loads(evidence) if evidence else None
                measured = dict(cache_get_many=0, cached_fact_reads=0, pricing=0, cache_progress=0)
                before = dict(source.metrics.counts)
                get_many = service.cache_repository.get_many
                price = PricingCatalog.reference_category_valuation

                def read(namespace, keys, **kwargs):
                    keys = tuple(keys)
                    if namespace == NAMESPACE:
                        measured['cache_get_many'] += 1
                        measured['cached_fact_reads'] += len(keys)
                    return get_many(namespace, keys, **kwargs)

                def value(catalog, *args):
                    measured['pricing'] += 1
                    return price(catalog, *args)

                def progress(label, _percent):
                    if getattr(label, 'stage', None) == 'history-cache':
                        measured['cache_progress'] += 1

                wall, cpu = time.perf_counter(), time.process_time()
                with ExitStack() as stack:
                    stack.enter_context(patch.object(service.cache_repository, 'get_many', read))
                    stack.enter_context(patch.object(PricingCatalog, 'reference_category_valuation', value))
                    report = service.build_token_mix_history(progress, scope=scope)
                    # Include the actual compact IPC serialization/parse costs.
                    evidence = json.dumps(service.token_mix_reuse).encode() if reuse else None
                measured.update(wall_seconds=round(time.perf_counter() - wall, 6),
                    cpu_seconds=round(time.process_time() - cpu, 6))
                for metric, name in [('full_catalog_fetches', 'history_scans'), ('revision_checks', 'root_revision_checks'),
                                     ('hydrated_roots', 'raw_snapshot_loads')]:
                    measured[name] = source.metrics.counts.get(metric, 0) - before.get(metric, 0)
                measured.update(reuse=reuse, cold=index == 0, period=scope, calls=report.token_mix.request_count)
                if reuse and index:
                    assert measured['cache_get_many'] == measured['cached_fact_reads'] == 0
                    assert measured['raw_snapshot_loads'] == measured['pricing'] == measured['cache_progress'] == 0
                results.append(measured)
        finally:
            case.doCleanups()
    assert [row['calls'] for row in results[:4]] == [row['calls'] for row in results[4:]]
    return dict(outcome='PASS', roots=520, prompts_per_root=4, observations=results,
        limitations=['Synthetic compact source facts, not personal history or OS-input evidence.',
                      'Two live catalog/revision brackets remain intentional; no stale source-verification shortcut.'])
