"""Input/location adapters for version-pinned historical Web execution, including spawn.

No report, Watch, scheduling, source-normalization or browser implementation is
substituted. This module deliberately imports only the selected version's src.
"""
import atexit
from datetime import datetime
from decimal import Decimal
import functools
import inspect
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
import traceback
from urllib.parse import urlsplit


def verify_origins(root):
    names = []
    for name, module in tuple(sys.modules.items()):
        if name != 'src' and not name.startswith('src.'):
            continue
        filename = getattr(module, '__file__', None)
        if filename is not None:
            Path(filename).resolve().relative_to(root)
            names.append(name)
    return sorted(names)


def fixed_prices(url, _timeout):
    if url.startswith('https://docs.github.com/api/article/body?pathname='):
        return ('## OpenAI\nModel | Release status | Tier | Threshold (input tokens) | Input | Cached input | Cache write | Output\n'
            '--- | --- | --- | --- | --- | --- | --- | ---\n' + ''.join(
            f'GPT-Test-{index} | GA | Standard | Not applicable | ${index} | $0.1 | ${index} | ${index * 2}\n'
            for index in range(1, 6)))
    if url == 'https://models.dev/models.json':
        return json.dumps(dict(openai=dict(models={f'gpt-test-{index}': dict(
            id=f'gpt-test-{index}', name=f'GPT-Test-{index}', release_date='2026-01-01') for index in range(1, 6)})))
    if url == 'https://github.blog/changelog/feed/':
        return '<rss version="2.0"><channel><title>Synthetic metadata</title></channel></rss>'
    raise RuntimeError('unexpected_fixture_pricing_request')


def quota_input(asof_ms):
    """Raw provider window shared by all arms; no computed usage/completeness."""
    return dict(reset_at_ms=asof_ms + 9_000_000, duration_seconds=18_000, remaining_fraction='0.75')


def validate_input_time(asof_ms, timezone, *, now_ms=None):
    """Censor expired benchmark inputs, never time out product computation."""
    from src.analysis.timezones import resolve_timezone
    now = int(time.time() * 1000) if now_ms is None else now_ms
    if not asof_ms - 9_000_000 <= now < asof_ms + 9_000_000:
        raise RuntimeError('fixture_input_window_expired')
    zone = resolve_timezone(timezone)
    if datetime.fromtimestamp(asof_ms / 1000, zone).date() != datetime.fromtimestamp(now / 1000, zone).date():
        raise RuntimeError('fixture_input_calendar_changed')


def failure_facts(error, root=None):
    frames = []
    if root is not None:
        for frame in traceback.extract_tb(error.__traceback__):
            try:
                source = Path(frame.filename).resolve().relative_to(root).as_posix()
            except ValueError:
                continue
            frames.append(dict(source=source, line=frame.lineno, function=frame.name))
    return dict(error_class=type(error).__name__, errno=getattr(error, 'errno', None),
        winerror=getattr(error, 'winerror', None), sqlite_code=getattr(error, 'sqlite_errorcode', None),
        sqlite_name=getattr(error, 'sqlite_errorname', None), cache_phase=getattr(error, 'cache_phase', None),
        frames=frames[-5:])


def observe_cache_writes(original, failures, *, root, lock_once=None):
    """Opt-in diagnostic only; preserve native writes and their real exceptions."""
    @functools.wraps(original)
    def measured(self, entries, **kwargs):
        locked, failed = None, None
        try:
            stats_batch = lock_once is not None and any(frame.name == '_batch' and
                Path(frame.filename).resolve() == root / 'src/reports/ai_stats.py'
                for frame in traceback.extract_stack())
            if stats_batch:
                try:
                    with lock_once.open('x', encoding='utf-8') as marker:
                        marker.write('owned one-shot write-lock diagnostic')
                except FileExistsError:
                    pass
                else:
                    locked = sqlite3.connect(self.database.paths.database, timeout=.5)
                    locked.execute('BEGIN IMMEDIATE')
            return original(self, entries, **kwargs)
        except BaseException as error:
            if len(failures) < 20:
                failed = dict(failure_facts(error, root), busy_timeout_ms=kwargs.get('busy_timeout_ms'),
                    controlled_write_lock=locked is not None, failed_wall_ms=int(time.time() * 1000),
                    stats_batch=any(frame.name == '_batch' and Path(frame.filename).resolve() == root / 'src/reports/ai_stats.py'
                        for frame in traceback.extract_stack()))
                failures.append(failed)
            raise
        finally:
            if locked is not None:
                locked.rollback()
                locked.close()
                if failed is not None:
                    failed['lock_released_wall_ms'] = int(time.time() * 1000)
    return measured


def observe_build(original, reports, *, kind=None, catalogs=False, root=None):
    """Observe the original entrypoint, including continuation exits and parking."""
    @functools.wraps(original)
    def measured(self, *args, **kwargs):
        started, cpu = time.monotonic(), time.process_time()
        started_wall_ms = int(time.time() * 1000)
        outcome, failure = 'returned', None
        try:
            return original(self, *args, **kwargs)
        except BaseException as error:
            failure = failure_facts(error, root)
            outcome = type(error).__name__ if type(error).__name__ in {
                'HistoryContinuation', 'HistoryCheckpointError', 'SourceError'} else 'other_exception'
            raise
        finally:
            observation = dict(kind=kind or (args[0] if args else kwargs['request']).kind.value,
                wall_seconds=time.monotonic() - started,
                cpu_seconds=time.process_time() - cpu, acquisition=self.metrics.snapshot(),
                 started_monotonic=started, started_wall_ms=started_wall_ms, outcome=outcome, failure=failure,
                limitation='Original report entrypoint only; wall includes cooperative parking, excludes application export/IPC and process startup.')
            if catalogs:
                counts = self.metrics.counts
                preparation = counts.get('observed_sampling_preparation_catalogs', 0)
                consumption = counts.get('observed_analysis_consumption_catalogs', 0)
                observation['catalog_attribution'] = dict(sampling_preparation=preparation,
                    analysis_consumption=consumption,
                    outside_sampling_and_analysis=counts.get('full_catalog_fetches', 0) - preparation - consumption)
            reports.append(observation)
    return measured


class FixtureAccounts:
    provider_id = 'openai'
    included_usage = False

    def __init__(self, quota):
        self.quota = dict(quota)

    def probe(self):
        from src.domain import IntegrationHealth
        return IntegrationHealth(True, True)

    def get_account_snapshots(self):
        from src.domain import AccountRef, AccountSnapshot, QuotaComponent
        now = int(time.time() * 1000)
        return (AccountSnapshot(AccountRef('fixture', 'openai', 'synthetic', account_label='Synthetic account'),
            now, 'OpenAI', 'Plus', quotas=(QuotaComponent('5-hour', 'rolling',
                remaining_fraction=Decimal(self.quota['remaining_fraction']),
                duration_seconds=self.quota['duration_seconds'], reset_at_ms=self.quota['reset_at_ms']),)),)


def withhold_history_pacing(dispatcher_class):
    """Historical-replay control: the dispatcher never learns that visible history is pending.

    Leases, permits, quanta, checkpoints and warming stay native; only the
    history-pending demotion of hidden requested finite work is withheld.
    Current production removed that demotion, so it fails explicitly.
    """
    original_tick = dispatcher_class.tick
    if 'history_pending' not in inspect.signature(original_tick).parameters:
        raise RuntimeError('fixture_pacing_control_unsupported')

    @functools.wraps(original_tick)
    def unpaced_tick(self, **kwargs):
        kwargs['history_pending'] = False
        return original_tick(self, **kwargs)

    dispatcher_class.tick = unpaced_tick
    return original_tick


def install(spec):
    root, data = Path(spec['product_root']).resolve(), Path(spec['data_root']).resolve()
    evidence_root = Path(spec.get('evidence_root', data)).resolve()
    stack_output = None
    if spec.get('diagnostic_stacks'):
        import faulthandler
        stack_output = (evidence_root / f'owned-stacks-{os.getpid()}.txt').open('w', encoding='utf-8')
        faulthandler.dump_traceback_later(15, repeat=True, file=stack_output)
    endpoint = urlsplit(spec['source_url'])
    allowed_ports = {endpoint.port}

    def audit(event, values):
        if event == 'socket.connect':
            address = values[1]
            if not isinstance(address, tuple) or address[0] != '127.0.0.1' or address[1] not in allowed_ports:
                raise RuntimeError('unexpected_fixture_network_access')
        if event == 'subprocess.Popen':
            raise RuntimeError('unexpected_fixture_cli_access')

    sys.addaudithook(audit)
    import src.config as config
    original_load = config.load_configuration
    config.load_configuration = lambda _root: original_load(data)

    import src.cache.database as database
    original_paths = database.cache_paths
    database.cache_paths = lambda _root, generation=database.CACHE_SCHEMA_GENERATION: original_paths(data, generation)

    import src.pricing.github_copilot as pricing
    from src.pricing.metadata_health import MetadataHealthStore
    original_pricing = pricing.GitHubCopilotPricingProvider.__init__

    @functools.wraps(original_pricing)
    def pricing_input(self, *args, **kwargs):
        kwargs.update(fetch_text=fixed_prices, metadata_store=MetadataHealthStore(data))
        original_pricing(self, *args, **kwargs)

    pricing.GitHubCopilotPricingProvider.__init__ = pricing_input

    import src.sources.connectivity_events as connectivity
    connectivity.FILE = data / 'logs/recovery/watch-recovery.json'
    import src.opencode_service as opencode_service

    def no_wake(*_args, **_kwargs):
        raise RuntimeError('fixture_source_must_not_wake_service')

    opencode_service.wake_cli_service = no_wake
    import src.bootstrap as bootstrap
    bootstrap._account_providers = lambda *_args: (FixtureAccounts(spec['quota']),)
    from src.reports.acquisition import RootAcquisition
    window = spec.get('sample_window')
    if window is not None:
        if not hasattr(RootAcquisition, 'sample_window_size') or window not in (1, 2, 4, 8):
            raise RuntimeError('fixture_sampling_control_unsupported')
        RootAcquisition.sample_window_size = window

    if spec.get('sampling_catalog_observer'):
        def observe_catalogs(original, phase):
            @functools.wraps(original)
            def observed(self, *args, **kwargs):
                before = self.metrics.counts.get('full_catalog_fetches', 0)
                try:
                    return original(self, *args, **kwargs)
                finally:
                    self.metrics.add('observed_' + phase + '_catalogs',
                        self.metrics.counts.get('full_catalog_fetches', 0) - before)
            return observed

        RootAcquisition.prepare_sample = observe_catalogs(RootAcquisition.prepare_sample, 'sampling_preparation')
        RootAcquisition.analyze = observe_catalogs(RootAcquisition.analyze, 'analysis_consumption')

    if spec.get('card_readers') == 'off':
        from src.watch.card_workers import CardWorkers
        original_workers = CardWorkers.__init__

        @functools.wraps(original_workers)
        def fresh_card_workers(self, *args, **kwargs):
            # Only the new ownership seam is disabled; all original captures,
            # health probes, logical permits and after-brackets still execute.
            kwargs['readers'] = None
            original_workers(self, *args, **kwargs)

        CardWorkers.__init__ = fresh_card_workers

    if spec.get('card_brackets') == 'global':
        from src.sources.opencode_v2 import OpenCodeV2Source
        original_begin = OpenCodeV2Source.begin_card_read

        @functools.wraps(original_begin)
        def global_card_brackets(self, origin):
            original_begin(self, origin)
            # Only the scoped bracket seam changes. Retained readers, per-job
            # health probes, services, permits and all other lanes stay native.
            self._card_trees = None

        OpenCodeV2Source.begin_card_read = global_card_brackets

    refill = spec.get('completion_refill')
    if refill is not None:
        from src.watch.web_coordinator import WebWatchCoordinator
        if not hasattr(WebWatchCoordinator, 'work_ready'):
            raise RuntimeError('fixture_completion_control_unsupported')
        if refill == 'off':
            # Disable only the new readiness notification seam. The default
            # runtime still executes all original cadence ticks and card work.
            del WebWatchCoordinator.work_ready

    if spec.get('history_pacing') == 'off':
        from src.web.dispatch import DataDispatcher
        withhold_history_pacing(DataDispatcher)

    # Observe the original report path, not a replacement worker target. Store
    # numeric stage evidence only, without snapshots, roots or provider payloads.
    from src.reports import ReportService
    reports = []
    ReportService.build = observe_build(ReportService.build, reports,
        catalogs=bool(spec.get('sampling_catalog_observer')), root=root)
    cache_failures = []
    if spec.get('observe_cache_failures'):
        from src.cache.repository import CacheRepository
        CacheRepository.put_many = observe_cache_writes(CacheRepository.put_many, cache_failures, root=root,
            lock_once=evidence_root / 'stats-cache-lock.claim' if spec.get('stats_cache_lock_once') else None)
    cooperative_waits = []
    if spec.get('report_timeline'):
        ReportService.build_token_mix_history = observe_build(ReportService.build_token_mix_history, reports, kind='token-mix')
        from src.web.report_control import Quantum
        original_checkpoint = Quantum.checkpoint

        @functools.wraps(original_checkpoint)
        def checkpoint(self):
            before, started = self.started, time.monotonic()
            result = original_checkpoint(self)
            if self.started != before and len(cooperative_waits) < 2500:
                cooperative_waits.append(dict(started_monotonic=started, wall_seconds=time.monotonic() - started))
            return result

        Quantum.checkpoint = checkpoint
    verify_origins(root)

    def evidence():
        try:
            names = verify_origins(root)
            value = dict(pid=os.getpid(), module_count=len(names), foreign_src_modules=False,
                 process_cpu_seconds=time.process_time(), reports=reports, cooperative_waits=cooperative_waits,
                 cache_write_failures=cache_failures)
        except ValueError:
            value = dict(pid=os.getpid(), foreign_src_modules=True)
        (evidence_root / f'imports-{os.getpid()}.json').write_text(json.dumps(value), encoding='utf-8')

    def close_stacks():
        if stack_output is not None:
            faulthandler.cancel_dump_traceback_later()
            stack_output.close()

    atexit.register(close_stacks)
    atexit.register(evidence)
    # multiprocessing's normal owned-child teardown bypasses ordinary atexit.
    from multiprocessing.util import Finalize
    Finalize(None, evidence, exitpriority=0)
    return allowed_ports
