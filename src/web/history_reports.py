"""Own background projection and atomically hand stable results to HTTP readers."""
from concurrent.futures import ThreadPoolExecutor
import logging
import sqlite3
import time
from types import SimpleNamespace
from uuid import uuid4

from src.analysis.ai_stats import ROLLING_DAYS
from src.analysis.cache import dependency_signature
from src.analysis.timezones import calendar_periods
from src.cache.web_archive import ArchiveFact, REPORT_CHECKPOINTS
from src.pricing.catalog import PricingCatalog
from src.reports import ReportKind
from src.reports.projection_cadence import cpu_cooldown
from src.reports.web_history_evidence import DOMAIN
from src.version import VERSION

from .history_projection import HistoryProjection


LOG = logging.getLogger(__name__)
KINDS = {ReportKind.AI_STATS, ReportKind.TOKEN_MIX}
VIEWS = 'report-view/1'
RENDER_INTERVAL = 1.0
PROGRESS_INTERVAL = 2.5
BACKGROUND_INTERVAL = 4.0
BACKGROUND_CPU_SHARE = 0.08
FOREGROUND_CPU_REST_LIMIT = 2.0
ROLLING_REFRESH_MS = 60_000


def checkpoint_stamp(config, zone, start, settings):
    return [zone, config.get('ccostDisplayUnit', 'credits'), config.get('workdayCalendar', 'SE'),
            start, settings]


def settings_signature(config):
    return dependency_signature({key: value for key, value in config.items() if key != 'webSettings'})


class HistoryReports:
    def __init__(self, usage, cached_prices, *, notify=None):
        self.archive = usage.archive
        self.cached_prices = cached_prices
        self.notify = notify
        self.projection = HistoryProjection(usage)
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='cost-guard-history-projection')
        self.publication = {}
        self._committed = {}
        self.job = None
        self.job_key = None
        self.published_keys = {}
        self.last_render = {}
        self.rendered_scope = {}
        self.restored = set()
        self.next_turn = 0
        self.next_background = 0
        self.foreground_due = {}
        self.foreground = frozenset()
        self.run = uuid4().hex

    def _read_checkpoint(self, period, stamp):
        _, checkpoints = self.archive.history_item(VIEWS, period, 0)
        for _, fact in checkpoints:
            saved = fact.value.get('stamp')
            if isinstance(saved, list) and saved[:len(stamp)] == stamp:
                value = fact.value
                views = value.get('views')
                if value.get('run') == self.run:
                    if isinstance(views, dict):
                        return {(kind.value, period): views[kind.value]
                                for kind in KINDS if kind.value in views}
                elif (restored := self._restore(value, period)) is not None:
                    return restored
        return {}

    def _load_checkpoint(self, period, stamp):
        return self._read_checkpoint(period, stamp), False, 0.0

    def _measure_render(self, inputs, stamp, previous):
        started = time.thread_time()
        results, more = self._render(inputs, stamp, previous)
        return results, more, time.thread_time() - started

    def _render(self, inputs, stamp, previous):
        period = inputs['only']
        reference = self.cached_prices() or PricingCatalog(())
        format_stamp = [*stamp, VERSION, reference.diagnostic_signature]
        snapshot = self.projection.usage.snapshot()
        results, more = self.projection.render(reference=reference, snapshot=snapshot,
                                                defer_while_loading=previous, **inputs)
        if results and previous:
            # An older writer may have left usable report fields even when the
            # corresponding analysis codec no longer decodes. Do not replace
            # those values with an empty publication solely because of a rebuild.
            for kind in KINDS:
                key = kind.value, period
                current, retained = results[key], previous.get(key)
                if retained is not None:
                    results[key] = self._retain_readable(kind, period, current, retained)
        if results:
            now = inputs['now']
            fact = ArchiveFact(str(now), now, dict(stamp=[*format_stamp, snapshot[0]], run=self.run,
                views={kind.value: results[kind.value, period] for kind in KINDS}))
            try:
                committed = self.archive.publish_checkpoint(VIEWS, {period: fact})
                if period not in committed:
                    return {}, True
            except (OSError, sqlite3.Error, ValueError):
                LOG.warning('history_projection_checkpoint_unavailable', exc_info=True)
                return {}, True
            # Event consumers must see the committed frame even before the host
            # tick collects this job. Do not share mutable projection results.
            self._committed = {**self._committed, period: committed[period].value}
            if self.notify is not None:
                self.notify(('ai-stats', 'token-mix'), (period,))
        return results, more

    @staticmethod
    def _retain_readable(kind, period, current, old):
        fresh, saved = current['view'], old['view']
        if kind is ReportKind.TOKEN_MIX:
            if fresh['token_mix_period']['start_ms'] != saved['token_mix_period']['start_ms'] and period != 'all':
                return current
            if not fresh['model_token_mix'] and saved['model_token_mix']:
                # Retain values, not the old job's loading state or identity.
                for key in ('token_mix', 'model_token_mix', 'publisher_token_mix'):
                    fresh[key] = saved[key]
                fresh['token_mix_period']['coverage'] = 'partial'
                current['source']['status'] = 'partial'
        else:
            row, = fresh['ai_stats']
            previous = next((item for item in saved['ai_stats'] if item['period'] == period
                             and (period in ROLLING_DAYS or item['start_ms'] == row['start_ms'])), None)
            if previous:
                known = {metric['metric']: metric for metric in previous['metrics'] if metric.get('value') is not None}
                row['metrics'] = [known.get(metric['metric'], metric)
                                  if metric.get('value') is None and metric['metric'] != 'hourly-rate'
                                  else metric for metric in row['metrics']]
                if row.get('matched') is None:
                    row['matched'] = previous.get('matched')
        return current

    @staticmethod
    def _restore(value, period):
        try:
            stats, mix = (value['views'][kind.value] for kind in (ReportKind.AI_STATS, ReportKind.TOKEN_MIX))
            for result in (stats, mix):
                result['source']['status'] = 'partial'
                result['source']['identity'] = REPORT_CHECKPOINTS
            stats['view']['history_progress'][period].update(complete=False, restored=True)
            mix['view']['history_progress'].update(complete=False, restored=True)
            mix['view']['token_mix_period']['coverage'] = 'partial'
        except (AttributeError, KeyError, TypeError):
            return None
        return {(ReportKind.AI_STATS.value, period): stats, (ReportKind.TOKEN_MIX.value, period): mix}

    def tick(self, *, selection, config, catalog, ready, price_signature, foreground=()):
        turn = time.monotonic()
        if self.job is not None and self.job.done():
            period, render_key = self.job_key
            try:
                results, more, cpu = self.job.result()
            except Exception:
                LOG.warning('history_projection_unavailable', exc_info=True)
                self.next_turn = turn + 2
            else:
                if results:
                    self.publication = {**self.publication, **results}
                if render_key is None:
                    self.restored.add(period)
                else:
                    # A long render consumes its budget even if more facts
                    # arrived in the meantime. No budget state is read by HTTP.
                    self.next_background = max(self.next_background,
                        turn + cpu_cooldown(cpu, BACKGROUND_CPU_SHARE))
                    self.foreground_due[period] = turn + min(cpu, FOREGROUND_CPU_REST_LIMIT)
                    if not more:
                        self.published_keys[period] = render_key
                    else:
                        self.published_keys.pop(period, None)
            self.job = None
        if self.job is not None or turn < self.next_turn:
            return
        if not catalog.archive.storage_ready:
            return
        now = int(time.time() * 1000)
        zone = str(config.get('timezone') or 'Europe/Stockholm')
        scopes = dict(calendar_periods(zone, now))
        settings = settings_signature(config)

        def stamp(period):
            return checkpoint_stamp(config, zone, scopes[period], settings)

        # Frozen results are an independent, cheap warm path. Prioritize an
        # open period and do not wait for the Sessions index or pricing.
        refresh = tuple(name for name in scopes if name in foreground)
        restore = next((name for name in (*refresh, *scopes) if name not in self.restored), None)
        if restore is not None:
            self.job_key = restore, None
            self.job = self.pool.submit(self._load_checkpoint, restore, stamp(restore))
            return

        revision = self.archive.generation(DOMAIN)
        with catalog.lock:
            if not catalog.archive.loaded:
                return
            promoted = frozenset(refresh) - self.foreground
            self.foreground = frozenset(refresh)
            backfill = bool(catalog.history_pending)
            progress_key = catalog.generation, ready
            keys, scope_keys = {}, {}
            for name, start in scopes.items():
                retained = self.published_keys.get(name)
                # An open rolling view ages out old data without causing idle
                # background rendering in unobserved periods.
                bucket = (now // ROLLING_REFRESH_MS if name in foreground and name in ROLLING_DAYS
                          else retained[0][-1] if retained else None)
                keys[name] = ((revision, price_signature, settings, start, bucket), progress_key)
                scope_keys[name] = (price_signature, settings, start, ready, backfill, catalog.index_terminal)
            candidates = []
            for name, key in keys.items():
                saved = self.published_keys.get(name)
                scope_changed = self.rendered_scope.get(name) != scope_keys[name]
                outstanding = key != saved or scope_changed
                urgent = scope_changed or name in promoted
                if backfill and not urgent:
                    due = self.foreground_due.get(name, 0) if name in foreground else self.next_background
                    if turn < due:
                        continue
                interval = PROGRESS_INTERVAL if saved and saved[0] == key[0] else RENDER_INTERVAL
                if outstanding and (urgent or turn - self.last_render.get(name, -interval) >= interval):
                    candidates.append((urgent, name))
            if not candidates:
                return
            _, period = min(candidates, key=lambda item: (item[1] not in promoted,
                self.last_render.get(item[1], 0) - (2 if item[1] in foreground else 0) - int(item[0]), item[1]))
            unavailable = catalog.unavailable_history()
            pending = catalog.history_pending.keys() | unavailable
            revisions = {root: catalog.revisions.get(root) for root in pending}
            activity = {root: catalog.activity.get(root) for root in pending}
            live_roots = frozenset(catalog.history_progress_live_roots())
            refresh_roots = frozenset(catalog.history_refresh_roots())
        selected = SimpleNamespace(selected=selection.selected if selection else 'OpenCode',
                                    warnings=tuple(selection.warnings) if selection else (),
                                    migration_gap=selection.migration_gap if selection else None)
        self.job_key = period, keys[period]
        self.last_render[period] = turn
        self.rendered_scope[period] = scope_keys[period]
        if backfill and period not in foreground:
            self.next_background = turn + BACKGROUND_INTERVAL
        self.job = self.pool.submit(self._measure_render, dict(identity=REPORT_CHECKPOINTS, selection=selected,
              config=dict(config), now=now, revisions=revisions, activity=activity, available=ready,
               only=period, unavailable=unavailable, live_roots=live_roots, refresh_roots=refresh_roots),
              stamp(period), {key: value for key, value in self.publication.items() if key[1] == period})
        self.next_turn = turn + RENDER_INTERVAL

    def lookup(self, request, config, *, terminal_error=None):
        period = request.token_mix_scope if request.kind is ReportKind.TOKEN_MIX else request.stats_scope
        zone = str(config.get('timezone') or 'Europe/Stockholm')
        start = dict(calendar_periods(zone, int(time.time() * 1000)))[period]
        stamp = checkpoint_stamp(config, zone, start, settings_signature(config))
        frame = self._committed.get(period)
        if frame is not None and frame['stamp'][:len(stamp)] == stamp:
            result = frame['views'].get(request.kind.value)
        else:
            result = None
            try:
                result = self._read_checkpoint(period, stamp).get((request.kind.value, period))
            except (sqlite3.Error, OSError):
                pass  # The next publication or reconnect can recover the read.
        return dict(id=None, result_id=None, result=result, cache_first=True,
                    refresh='failed' if terminal_error else 'scheduled',
                    terminal=terminal_error is not None, stale=False, error=terminal_error,
                    source_identity=REPORT_CHECKPOINTS, projection_epoch=0)

    def close(self):
        self.pool.shutdown(wait=True, cancel_futures=True)
        self._committed = {}
