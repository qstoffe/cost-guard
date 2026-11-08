"""Bounded cohort comparison of actual card scheduling and shared numeric guidance.

Synthetic by default. --live reads at most twelve inactive roots plus the normal
canonical guidance sample, with pinned cached prices and no account/model calls.
This is NOT global Earlier, full Web, Live cadence, browser paint or final B2 proof.
"""
import argparse
from collections import Counter
import ctypes
from dataclasses import replace
import json
from pathlib import Path
import statistics
import sys
import tempfile
from threading import Lock
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.integration.benchmark_v2_acquisition import WireHistory, product_identity, wire_observations
from src.cache import CacheDatabase, CacheRepository
from src.config import load_configuration
from src.domain import ModelRef
from src.reports import ReportService
from src.reports.context_guidance import cached_guidance_binding
from src.sources.opencode_v2 import OpenCodeV2Source
from src.sources.opencode_v2_transport import V2HttpClient
from src.sources.selection import SourceSelector
from src.watch.card_guidance import CardGuidance
from src.watch.card_workers import CardWorkers
from src.watch.cards import WatchCards
from src.watch.observers import observe_catalog


class RunBudgetExpired(RuntimeError):
    """Experiment limit, not a source-health classification."""


def own_working_set():
    """Sample this process only; sampled peaks are not an absolute allocation bound."""
    if sys.platform != 'win32':
        return None
    from ctypes import wintypes
    class Memory(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD),
            *[(name, ctypes.c_size_t) for name in ('peak', 'working', 'quota_peak_paged',
                'quota_paged', 'quota_peak_nonpaged', 'quota_nonpaged', 'pagefile', 'peak_pagefile')]]
    value = Memory()
    value.cb = ctypes.sizeof(value)
    call = ctypes.windll.psapi.GetProcessMemoryInfo
    call.argtypes = (wintypes.HANDLE, ctypes.POINTER(Memory), wintypes.DWORD)
    call.restype = wintypes.BOOL
    return value.working if call(wintypes.HANDLE(-1), ctypes.byref(value), value.cb) else None


def measure(factory, observation, catalog, args, *, shared):
    config = load_configuration(ROOT).values
    metrics, diagnostics, lock = [], [], Lock()
    started, cpu = time.perf_counter(), time.process_time()
    first_rows = certified = complete_guidance = None
    maximum_jobs = maximum_history_jobs = peak_rss = 0
    producer_seen = budget_exceeded = False
    final_state, checked, total, failures = 'loading', 0, len(observation.roots), 0
    sample_required = 0
    def admission():
        if time.perf_counter() - started >= args.seconds:
            raise RunBudgetExpired()
    class Pricing:
        def get_catalog(self):
            return catalog
        def cached_catalog(self):
            return catalog
    with tempfile.TemporaryDirectory(prefix='cost-guard-guidance-benchmark-') as tmp:
        CacheDatabase(Path(tmp)).initialize()  # Match the host's schema-before-worker startup.
        def service_factory(now_ms):
            admission()
            source = factory()
            source.read_admission = admission
            selection = SourceSelector(v2_factory=lambda: source, inspect_migration_gap=False).select('v2')
            database = CacheDatabase(Path(tmp))
            database.initialize()
            service = ReportService(selection=selection, pricing_provider=Pricing(), account_provider=None,
                cache_repository=CacheRepository(database), config=config, now_ms=now_ms)
            close = source.close_reads
            def close_reads():
                with lock:
                    diagnostics.append(sum(len(value) for value in source._diagnostics.values()
                        if isinstance(value, dict)))
                close()
            source.close_reads = close_reads
            with lock:
                metrics.append(service.metrics)
            return service
        workers = CardWorkers(service_factory, batch_size=args.batch_size)
        owner_service = service_factory(int(time.time() * 1000)) if shared else None
        guidance = CardGuidance(workers, owner_service, binding=cached_guidance_binding) if shared else None
        cards = WatchCards(workers, guidance=guidance)
        cards.catalog(observation)
        try:
            while True:
                admission()
                now_ms = int(time.time() * 1000)
                cards.tick(now_ms)
                maximum_jobs = max(maximum_jobs, len(workers.jobs))
                maximum_history_jobs = max(maximum_history_jobs, len(workers.history_jobs))
                if maximum_jobs > 4 or maximum_history_jobs > 3:
                    raise AssertionError('combined_root_occupancy_exceeded')
                if guidance is not None:
                    producer_seen |= guidance.attempt is not None
                active, history, _state = cards.project(now_ms)
                elapsed = time.perf_counter() - started
                if first_rows is None and any(entry.capture is not None for entry in cards.sessions.values()):
                    first_rows = elapsed
                if cards.history.state == 'observed':
                    if certified is None:
                        certified = elapsed
                    contexts = [card.session_context for card in (*active, *history) if card.session_context is not None]
                    sample_required = sum(bool(context.price_threshold) for context in contexts)
                    if all(context.guidance_state == 'ready' for context in contexts):
                        complete_guidance = elapsed
                        break
                rss = own_working_set()
                if rss is not None:
                    peak_rss = max(peak_rss, rss)
                time.sleep(.02)  # Probe sampling, not a product owner or scheduling clock.
        except RunBudgetExpired:
            budget_exceeded = True
        finally:
            final_state, checked, total = cards.history.state, cards.history.checked, cards.history.total
            failures = sum(bool(entry.failure_code) for entry in cards.sessions.values())
            if guidance is not None:
                guidance.cancel()
            try:
                workers.close()
            except RunBudgetExpired:
                budget_exceeded = True
            if owner_service is not None:
                owner_service.source.close_reads()
                owner_service.close_accounts()
    counts, milliseconds = Counter(), Counter()
    for metric in metrics:
        counts.update(metric.counts)
        milliseconds.update(metric.milliseconds)
    return dict(shared=shared, batch_size=args.batch_size, requested=len(observation.roots),
        checked=checked, total=total, state=final_state, failures=failures, budget_exceeded=budget_exceeded,
        first_rows_seconds=first_rows, certified_cohort_seconds=certified,
        complete_guidance_seconds=complete_guidance, warning_finalists=sample_required,
        producer_seen=producer_seen, maximum_occupied_roots=maximum_jobs,
        maximum_historical_roots=maximum_history_jobs, cpu_seconds=time.process_time()-cpu,
        total_seconds=time.perf_counter()-started, sampled_peak_working_set_bytes=peak_rss or None,
        maximum_completed_source_diagnostic_entries=max(diagnostics, default=0),
        acquisition=dict(counts), measured_stage_seconds={key: value / 1000 for key, value in milliseconds.items()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--roots', type=int, default=12)
    parser.add_argument('--trials', type=int, default=3)
    parser.add_argument('--batch-size', type=int, choices=(1, 2, 3), default=2)
    parser.add_argument('--seconds', type=float, default=180)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 4 <= args.roots <= 12 or not 1 <= args.trials <= 10 or not 1 <= args.seconds <= 300:
        parser.error('roots 4..12, trials 1..10, strategy budget 1..300 seconds')
    identity = product_identity(ROOT)
    import hashlib
    identity['harness_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if args.live:
        from src.pricing.github_copilot import GitHubCopilotPricingProvider
        catalog = GitHubCopilotPricingProvider(cache=CacheRepository(CacheDatabase(ROOT))).cached_catalog()
        if catalog is None:
            raise RuntimeError('cached_pricing_unavailable; no upstream fetch permitted')
        factory = lambda: OpenCodeV2Source(timeout_seconds=2)
    else:
        from development.tests.fixtures.pricing_catalog import threshold_catalog
        from src.pricing.catalog import PricingCatalog
        model = threshold_catalog().models[0]
        catalog = PricingCatalog((replace(model, model=ModelRef('github-copilot', 'gpt-5.6'), tiers=(
            replace(model.tiers[0], max_input_tokens=10), replace(model.tiers[1], min_input_tokens=11))),))
        wire = WireHistory(args.roots)
        class SyntheticSource(OpenCodeV2Source):
            @property
            def source_instance(self):
                return 'synthetic'
            @property
            def observation_epoch(self):
                return 'synthetic-epoch'
            def refresh_observation_epoch(self):
                pass
            def _client(self):
                return wire
            def _current_endpoint(self):
                return None
        factory = lambda: SyntheticSource(ROOT / 'synthetic-not-read.json')
    source = factory()
    try:
        if not source.probe().healthy:
            raise RuntimeError('supported_source_not_healthy')
        observation = observe_catalog(source)
        roots = tuple(root for root in observation.roots
            if root.session_id not in observation.active_candidates)[:args.roots]
        if len(roots) != args.roots:
            raise RuntimeError('insufficient_inactive_roots')
        ids = {root.session_id for root in roots}
        observation = replace(observation, roots=roots, active_candidates=frozenset(), live_candidates=frozenset(),
            revisions={key: value for key, value in observation.revisions.items() if key in ids})
    finally:
        source.close_reads()
    outcomes = []
    for trial in range(args.trials):
        for shared in ((False, True) if trial % 2 == 0 else (True, False)):
            with wire_observations(V2HttpClient) as (counts, durations):
                result = measure(factory, observation, catalog, args, shared=shared)
            result.update(trial=trial+1, calls=dict(counts), bytes=counts['bytes'], http_seconds=dict(durations))
            outcomes.append(result)
            print(json.dumps(result), flush=True)
    summaries = []
    for shared in (False, True):
        rows = [row for row in outcomes if row['shared'] == shared]
        valid = [row for row in rows if row['state'] == 'observed' and row['checked'] == row['requested']
            and not row['failures'] and not row['budget_exceeded'] and row['complete_guidance_seconds'] is not None]
        summary = dict(shared=shared, valid_trials=len(valid), trials=len(rows))
        for metric in ('first_rows_seconds', 'certified_cohort_seconds', 'complete_guidance_seconds'):
            values = sorted(row[metric] for row in valid)
            summary[metric] = dict(p50=statistics.median(values), p95=values[-1]) if values else None
        summaries.append(summary)
    args.output.write_text(json.dumps(dict(**identity, source='real-v2' if args.live else 'synthetic-current-wire',
        roots=args.roots, trials=args.trials, outcomes=outcomes, summaries=summaries, limitations=[
            'Subset cohort proof, not an independent global Earlier oracle or full Web/B0/B1/B2 acceptance.',
            'Actual CardWorkers/WatchCards/CardGuidance; no real Live/account cadence or browser paint measurement.',
            'One fixed inactive cohort; evolving real source and OS contention are not frozen.',
            'Fresh disposable derived cache per strategy; cached prices pinned; no providers/models invoked.',
            'Windows own-process RSS sampled every probe tick; not absolute memory or individual root byte bounds.',
            'Empirical p95 is the maximum for small n, not a reliable population tail.']), indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
