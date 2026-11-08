"""Compare isolated-reader lifetime and bracket size; acquisition microbenchmark only.

Default input is synthetic JSON with the current V2 wire contract, not network IO.
--live reads at most four inactive roots from the registered service, never writes
source data or calls models/providers. No raw IDs, payloads or registration data
are printed or persisted. This is NOT the global Earlier oracle or a Web benchmark.
"""
import argparse
from collections import Counter
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
from threading import Lock
import time
from unittest.mock import patch

PARSER = argparse.ArgumentParser(description=__doc__)
PARSER.add_argument('--product-root', type=Path, default=Path(__file__).resolve().parents[3])
PARSER.add_argument('--roots', type=int, default=2700)
PARSER.add_argument('--trials', type=int, default=3)
PARSER.add_argument('--live', action='store_true')
PARSER.add_argument('--capture', action='store_true', help='Fresh whole-card services: migration on/off, batch2/3')
PARSER.add_argument('--context-sampling', choices=('legacy', 'compact', 'compare'), default='compact',
    help='Compare freezes one cohort for legacy/compact sampling with single/batch-three acquisitions')
PARSER.add_argument('--seconds-per-strategy', type=float, default=90)
PARSER.add_argument('--output', type=Path, required=True)


class WireHistory:
    """Bounded current-wire history with independent deterministic finish times."""
    def __init__(self, count):
        self.sessions = [dict(id=f'ses_{index:05}', projectID='prj_fixture', title='Synthetic',
            location=dict(directory='/synthetic'), cost=1, tokens=dict(input=10, output=2),
            time=dict(created=1000, updated=9000)) for index in range(count)]
        self.calls = Counter()
        self.bytes = 0
        self.lock = Lock()

    def json(self, path, *, query=None, phase='unknown'):
        query = query or {}
        if path == '/api/info':
            value, stage = dict(version='2.1.0'), 'probe'
        elif path == '/api/session/active':
            value, stage = dict(data={}), 'active'
        elif path == '/api/session':
            offset = int(query.get('cursor', '0'))
            items = self.sessions[offset:offset + 500]
            following = offset + len(items)
            value = dict(data=items, cursor=dict(next=str(following)) if following < len(self.sessions) else {})
            stage = 'catalog'
        else:
            key = path.split('/')[3]
            index = int(key.removeprefix('ses_'))
            messages = [dict(id=f'msg_user_{index}', type='user', text='Synthetic',
                files=[], agents=[], time=dict(created=1000 + index * 10)),
                dict(id=f'msg_answer_{index}', type='assistant', agent='build',
                model=dict(providerID='github-copilot', id='gpt-5.6'),
                content=[dict(type='text', id=f'text_{index}', text='Synthetic')],
                finish='stop', cost=1, tokens=dict(input=10, output=2),
                time=dict(created=1001 + index * 10, completed=1002 + index * 10))]
            value = dict(data=messages, cursor={})
            stage = 'context' if path.endswith('/context') else 'messages'
        encoded = json.dumps(value, separators=(',', ':')).encode('utf-8')
        with self.lock:
            self.calls[stage] += 1
            self.bytes += len(encoded)
        return json.loads(encoded)


@contextmanager
def wire_observations(client_type):
    """Count bytes/categories without retaining request targets or response bodies."""
    original = client_type._get
    counts, seconds, lock = Counter(), Counter(), Lock()
    def read(client, target, **options):
        started = time.perf_counter()
        result = original(client, target, **options)
        path = target.split('?', 1)[0]
        stage = ('catalog' if path == '/api/session' else 'active' if path == '/api/session/active'
            else 'context' if path.endswith('/context') else 'messages' if path.endswith('/message') else 'other')
        with lock:
            counts[stage] += 1
            counts['bytes'] += len(result[1])
            seconds[stage] += time.perf_counter() - started
        return result
    with patch.object(client_type, '_get', read):
        yield counts, seconds


def measure(factory, ids, *, retained, size):
    source = factory()
    totals, diagnostics = Counter(), Counter()
    started, cpu = time.perf_counter(), time.process_time()
    checked = failures = 0
    try:
        for offset in range(0, len(ids), size):
            if offset and not retained:
                source.close_reads()
                source = factory()
            group = ids[offset:offset + size]
            try:
                snapshots = (source.load_session_snapshots_available(group, lambda *_: None) if size > 1
                    else {group[0]: source.load_session_snapshot(group[0])})
                checked += sum(snapshot.complete for snapshot in snapshots.values())
            except SourceError:
                failures += 1
            # Counters are cumulative for each isolated reader, not per call.
            if not retained or offset + size >= len(ids):
                totals.update(source.metrics.counts)
                diagnostics.update(source.diagnostic_metadata().get('transport', {}))
    finally:
        source.close_reads()
    return dict(retained=retained, batch_size=size, checked=checked, requested=len(ids),
        failed_batches=failures, seconds=time.perf_counter()-started,
        cpu_seconds=time.process_time()-cpu, acquisition=dict(totals), transport=dict(diagnostics))


class BenchmarkBudgetExceeded(RuntimeError):
    """An experiment limit is not a claim about source health."""


def legacy_context_sample(service, roots, activity):
    """Pre-compaction control, using the original canonical sampling functions."""
    from types import SimpleNamespace
    from src.pricing.catalog import normalized_average_token_mix
    from src.reports.sampling import latest_prompts, recent_sample_roots
    priceable = service._priceable()
    analyzed = recent_sample_roots(roots, activity, service._analyze, priceable)
    service.metrics.add('context_warning_sample_roots', len(analyzed))
    return SimpleNamespace(mix=normalized_average_token_mix(service._relative_usage(latest_prompts(analyzed, priceable))))


def measure_capture(factory, ids, roots, args, *, migration, size, catalog, context_sampling):
    from src.cache import CacheDatabase, CacheRepository
    from src.config import load_configuration
    from src.domain import IntegrationHealth
    from src.reports import ReportService
    from src.reports.watch_capture import capture_rows
    from src.sources.selection import SourceSelector
    from src.watch.skill_registry import active_skill_origins
    from src.watch.tools import observe_tools, RUNNING_VISIBLE_AFTER_MS
    class EmptyLegacy:
        def probe(self):
            return IntegrationHealth(True, True, 'synthetic empty legacy')
        def list_sessions(self):
            return ()
    class PinnedPricing:
        def get_catalog(self):
            return catalog
    config = load_configuration(args.product_root).values
    selector_options = {} if args.live else dict(v1_factory=EmptyLegacy)
    totals, stages = Counter(), Counter()
    failure_codes = Counter()
    started, cpu = time.perf_counter(), time.process_time()
    checked = failures = maximum_analyzed = 0
    maximum_diagnostic_entries = 0
    budget_exceeded = False
    def admission():
        if time.perf_counter() - started >= args.seconds_per_strategy:
            raise BenchmarkBudgetExceeded()
    from src.reports.context_sample import collect_context_sample
    sampler = legacy_context_sample if context_sampling == 'legacy' else collect_context_sample
    with tempfile.TemporaryDirectory(prefix='cost-guard-card-benchmark-') as tmp, \
            patch('src.reports.context_sample.collect_context_sample', sampler):
        database = CacheDatabase(Path(tmp))
        database.initialize()
        try:
            for offset in range(0, len(ids), size):
                service = source = None
                try:
                    admission()
                    selection_started = time.perf_counter()
                    source = factory()
                    source.read_admission = admission
                    selection = SourceSelector(v2_factory=lambda: source, inspect_migration_gap=migration,
                        **selector_options).select('v2')
                    stages['selection'] += time.perf_counter() - selection_started
                    source = selection.source
                    source.read_admission = admission
                    service = ReportService(selection=selection, pricing_provider=PinnedPricing(),
                        account_provider=None, cache_repository=CacheRepository(database), config=config,
                        now_ms=int(time.time() * 1000))
                    group = ids[offset:offset + size]
                    hydration_started = time.perf_counter()
                    snapshots, errors = (source.load_card_snapshots(group) if size > 1 else
                        ({group[0]: source.load_session_snapshot(group[0])}, {}))
                    stages['card_acquisition'] += time.perf_counter() - hydration_started
                    failures += len(errors)
                    failure_codes.update(str(error.code) for error in errors.values())
                    for key, snapshot in snapshots.items():
                        projection_started = time.perf_counter()
                        capture, item = capture_rows(service, roots[key], fresh=snapshot)
                        origins = active_skill_origins(source, item.snapshot, capture)
                        for row in capture.rows:
                            observe_tools(item.snapshot, row.event_id, is_compaction=False,
                                now_ms=service.now_ms + RUNNING_VISIBLE_AFTER_MS,
                                skill_origins_by_session=origins)
                        stages['capture_analysis_projection_tools'] += time.perf_counter() - projection_started
                        checked += capture.authoritative and item.snapshot.complete
                    maximum_analyzed = max(maximum_analyzed, len(service._analyzed))
                    maximum_diagnostic_entries = max(maximum_diagnostic_entries, sum(
                        len(value) for value in source._diagnostics.values() if isinstance(value, dict)))
                except SourceError as error:
                    failures += 1
                    failure_codes[str(error.code)] += 1
                finally:
                    if source is not None:
                        totals.update(source.metrics.counts)
                        for stage, milliseconds in source.metrics.milliseconds.items():
                            stages['measured_' + stage] += milliseconds / 1000
                        source.close_reads()
                    if service is not None:
                        service.close_accounts()
        except BenchmarkBudgetExceeded:
            budget_exceeded = True
    return dict(migration=migration, context_sampling=context_sampling,
        batch_size=size, checked=checked, requested=len(ids),
        failures=failures, budget_exceeded=budget_exceeded, seconds=time.perf_counter()-started,
        failure_codes=dict(failure_codes),
        cpu_seconds=time.process_time()-cpu, acquisition=dict(totals), stages_seconds=dict(stages),
        maximum_retained_analysis_roots=maximum_analyzed, maximum_diagnostic_entries=maximum_diagnostic_entries)


def product_identity(root):
    digest = hashlib.sha256()
    for path in sorted((root / 'src').rglob('*.py')):
        digest.update(path.relative_to(root).as_posix().encode('utf-8'))
        digest.update(b'\0')
        digest.update(path.read_bytes())
    return dict(product_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
        product_dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True).strip()),
        product_source_sha256=digest.hexdigest(), harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())


def main(args):
    global SourceError
    sys.path.insert(0, str(args.product_root.resolve()))
    from src.sources.errors import SourceError
    from src.sources.opencode_v2 import OpenCodeV2Source
    from src.sources.opencode_v2_transport import V2HttpClient
    from src.watch.observers import observe_catalog
    maximum_live = 12 if args.capture else 4
    if (not 1 <= args.trials <= 10 or not 4 <= args.roots <= 3000 or
            args.live and args.roots > maximum_live or not 1 <= args.seconds_per_strategy <= 300):
        PARSER.error('trials 1..10; synthetic roots 4..3000; live roots 4 (capture 4..12); budget 1..300s')
    identity = product_identity(args.product_root)
    catalog = None
    if args.capture:
        if args.live:
            from src.cache import CacheDatabase, CacheRepository
            from src.pricing.github_copilot import GitHubCopilotPricingProvider
            catalog = GitHubCopilotPricingProvider(cache=CacheRepository(CacheDatabase(args.product_root))).cached_catalog()
            if catalog is None:
                raise RuntimeError('cached_pricing_unavailable; benchmark never fetches prices')
        else:
            from development.tests.fixtures.report_runtime import FakePricingProvider
            catalog = FakePricingProvider().get_catalog()
    wire = WireHistory(args.roots)
    class SyntheticSource(OpenCodeV2Source):
        @property
        def source_instance(self):
            return 'synthetic'
        def _client(self):
            return wire
        def _current_endpoint(self):
            return None  # Synthetic epoch is stable; never discover a real registration.
    factory = ((lambda: OpenCodeV2Source(timeout_seconds=1)) if args.live else
        lambda: SyntheticSource(registration_path=args.product_root / 'synthetic-not-read.json'))
    reference = factory()
    try:
        health = reference.probe()
        if not health.healthy:
            raise RuntimeError('supported_source_not_healthy')
        observation = observe_catalog(reference)
        roots = {root.session_id: root for root in observation.roots}
        ids = tuple(root.session_id for root in observation.roots
            if root.session_id not in observation.active_candidates)[:args.roots]
    finally:
        reference.close_reads()
    if len(ids) != args.roots:
        raise RuntimeError('insufficient_inactive_roots')
    outcomes = []
    compare_sampling = args.capture and args.context_sampling == 'compare'
    strategies = ([('legacy', 1), ('compact', 1), ('legacy', 3), ('compact', 3)] if compare_sampling else
        [(True, 1), (False, 1), (False, 2), (False, 3)] if args.capture else
        [(False, 1), (True, 1), (False, 4), (True, 4)])
    for trial in range(args.trials):
        # Rotate order to avoid always assigning transient conditions to one design.
        ordered = strategies[trial % 4:] + strategies[:trial % 4]
        for retained, size in ordered:
            wire.calls.clear()
            wire.bytes = 0
            with wire_observations(V2HttpClient) as (counts, durations):
                result = (measure_capture(factory, ids, roots, args,
                    migration=False if compare_sampling else retained, size=size, catalog=catalog,
                    context_sampling=retained if compare_sampling else args.context_sampling)
                    if args.capture else measure(factory, ids, retained=retained, size=size))
            result.update(trial=trial + 1, calls=dict(counts) if args.live else dict(wire.calls),
                bytes=counts['bytes'] if args.live else wire.bytes, http_seconds=dict(durations))
            outcomes.append(result)
            print(json.dumps(result), flush=True)
    summaries = []
    for retained, size in strategies:
        dimension = 'context_sampling' if compare_sampling else 'migration' if args.capture else 'retained'
        rows = [row for row in outcomes if (row[dimension], row['batch_size']) == (retained, size)]
        valid_rows = [row for row in rows if row['checked'] == row['requested'] and
            not row.get('failures', row.get('failed_batches', 0)) and not row.get('budget_exceeded', False)]
        times = sorted(row['seconds'] for row in valid_rows)
        if not times:
            summaries.append(dict(**{dimension: retained}, batch_size=size, valid_trials=0,
                trials=len(rows), p50=None, p95=None, min=None, max=None))
            continue
        summaries.append(dict(**{dimension: retained}, batch_size=size, p50=statistics.median(times),
            p95=times[min(len(times)-1, int(.95 * len(times)))], min=min(times), max=max(times),
            valid_trials=len(valid_rows), trials=len(rows)))
    evidence = dict(**identity, mode='whole-card' if args.capture else 'acquisition-only',
        source='real-v2' if args.live else 'synthetic-current-wire',
        roots=args.roots, trials=args.trials, summaries=summaries, outcomes=outcomes,
        limitations=['No Watch scheduling, independent global oracle, Live protection, browser or RSS proof.',
            'Whole-card mode pins cached pricing, uses fresh disposable derived cache per strategy; no provider calls.',
            'Whole-card services are sequential groups, not production four-root concurrency or foreground promotion.',
            'Live cohorts freeze root membership, not source contents; real source activity can change between trials.',
            'Synthetic timings include JSON copying/normalization but no network/disk/server contention.',
            'Small trial count: empirical nearest-rank p95 is the maximum, not a reliable population tail.',
            'Retained means same reader, not a warm derived cache; each root is still hydrated and bracketed.'])
    args.output.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(summaries=summaries)), flush=True)


if __name__ == '__main__':
    main(PARSER.parse_args())
