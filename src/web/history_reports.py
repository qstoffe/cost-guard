"""Own background projection and atomically hand stable results to HTTP readers."""
from concurrent.futures import ThreadPoolExecutor
import logging
import time
from types import SimpleNamespace

from src.analysis.ai_stats import ROLLING_DAYS
from src.analysis.cache import dependency_signature
from src.analysis.timezones import calendar_periods
from src.cache.web_archive import ArchiveFact, REPORT_CHECKPOINTS
from src.pricing.catalog import PricingCatalog
from src.reports import ReportKind
from src.reports.web_history_evidence import DOMAIN
from src.version import VERSION

from .history_projection import HistoryProjection


LOG = logging.getLogger(__name__)
KINDS = {ReportKind.AI_STATS, ReportKind.TOKEN_MIX}
VIEWS = 'report-view/1'
RENDER_INTERVAL = 1.0
PROGRESS_INTERVAL = 2.5
ROLLING_REFRESH_MS = 60_000


class HistoryReports:
    def __init__(self, usage, cached_prices):
        self.archive = usage.archive
        self.cached_prices = cached_prices
        self.projection = HistoryProjection(usage)
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='cost-guard-history-projection')
        self.publication = {}
        self.job = None
        self.job_key = None
        self.published_keys = {}
        self.last_render = {}
        self.restored = set()
        self.next_turn = 0

    def _load_checkpoint(self, period, stamp):
        _, checkpoints = self.archive.history_item(VIEWS, period, 0)
        for _, fact in checkpoints:
            saved = fact.value.get('stamp')
            if isinstance(saved, list) and saved[:4] == stamp[:4]:
                restored = self._restore(fact.value, period)
                if restored is not None:
                    return restored, False
        return {}, False

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
        if results and not more:
            try:
                self.archive.publish(REPORT_CHECKPOINTS, VIEWS, {period: ArchiveFact(str(inputs['now']), inputs['now'],
                    dict(stamp=[*format_stamp, snapshot[0]],
                         views={kind.value: results[kind.value, period] for kind in KINDS}))})
            except Exception:
                LOG.warning('history_projection_checkpoint_unavailable', exc_info=True)
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
                results, more = self.job.result()
            except Exception:
                LOG.warning('history_projection_unavailable', exc_info=True)
                self.next_turn = turn + 2
            else:
                if results:
                    self.publication = {**self.publication, **results}
                if render_key is None:
                    self.restored.add(period)
                elif not more:
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
        settings = dependency_signature({key: value for key, value in config.items() if key != 'webSettings'})

        def stamp(period):
            return [zone, config.get('ccostDisplayUnit', 'credits'), config.get('workdayCalendar', 'SE'),
                    scopes[period], settings]

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
            progress_key = catalog.generation, ready, catalog.legacy_done
            keys = {}
            for name, start in scopes.items():
                retained = self.published_keys.get(name)
                # An open rolling view ages out old data without causing idle
                # background rendering in unobserved periods.
                bucket = (now // ROLLING_REFRESH_MS if name in foreground and name in ROLLING_DAYS
                          else retained[0][-1] if retained else None)
                keys[name] = ((revision, price_signature, settings, start, bucket), progress_key)
            candidates = []
            for name, key in keys.items():
                saved = self.published_keys.get(name)
                interval = PROGRESS_INTERVAL if saved and saved[0] == key[0] else RENDER_INTERVAL
                if saved != key and turn - self.last_render.get(name, -interval) >= interval:
                    candidates.append(name)
            if not candidates:
                return
            period = min(candidates, key=lambda name: (self.last_render.get(name, 0) -
                         (2 if name in foreground else 0), name))
            unavailable = catalog.unavailable_history()
            pending = catalog.history_pending.keys() | unavailable
            revisions = {root: catalog.revisions.get(root) for root in pending}
            activity = {root: catalog.activity.get(root) for root in pending}
            live_roots = frozenset(catalog.history_live_roots())
        selected = SimpleNamespace(selected=selection.selected if selection else 'OpenCode',
                                    warnings=tuple(selection.warnings) if selection else (),
                                    migration_gap=selection.migration_gap if selection else None)
        self.job_key = period, keys[period]
        self.last_render[period] = turn
        self.job = self.pool.submit(self._render, dict(identity=REPORT_CHECKPOINTS, selection=selected,
              config=dict(config), now=now, revisions=revisions, activity=activity, available=ready,
              only=period, unavailable=unavailable, live_roots=live_roots),
              stamp(period), {key: value for key, value in self.publication.items() if key[1] == period})
        self.next_turn = turn + RENDER_INTERVAL

    def lookup(self, request, catalog):
        period = request.token_mix_scope if request.kind is ReportKind.TOKEN_MIX else request.stats_scope
        result = self.publication.get((request.kind.value, period))
        return dict(id=None, result_id=None, result=result, cache_first=True, refresh='scheduled',
                    terminal=False, stale=False, error=None,
                    source_identity=REPORT_CHECKPOINTS, projection_epoch=0)

    def close(self):
        self.pool.shutdown(wait=True, cancel_futures=True)
