"""Supply the same authenticated, read-only Watch history to Full and Mini."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal
import logging
from time import monotonic, thread_time

from src.analysis.daily_usage import daily_usage, request_identity
from src.analysis.timezones import local_day_start_ms
from src.analysis.valuation import unique_usage
from src.application.detail_archive import DOMAIN as DETAIL, load_detail
from src.application.live_projection import project_live
from src.application.session_archive import DOMAIN as SESSIONS
from src.pricing.catalog import PricingCatalog
from src.reports.projection_cadence import cpu_cooldown
from src.reports.web_history_evidence import DOMAIN as USAGE
from src.watch.models import WatchProjection


LOG = logging.getLogger(__name__)
VISIBLE_INTERVAL = 1.0
BACKGROUND_INTERVAL = 5.0
BACKGROUND_CPU_SHARE = 0.02


class WatchHistory:
    def __init__(self, usage, prices, publish):
        self.usage = usage
        self.archive = usage.archive
        self.prices = prices
        self.publish = publish
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='cost-guard-watch-history')
        self.job = None
        self.key = None
        self.last_started = -BACKGROUND_INTERVAL
        self.retry_after = 0
        self.background_resume = 0
        self.foreground = False
        self.more = False

    def tick(self, catalog, zone, unit, now, *, foreground=True, price_signature=None):
        with catalog.lock:
            ready = catalog.archive.loaded
            index = catalog.archive_revision
            backfill = bool(catalog.history_pending)
            available = not catalog.index_unavailable
        day = local_day_start_ms(zone, now_ms=now)
        turn = monotonic()
        if self.job is not None:
            if not self.job.done():
                return
            try:
                result, self.more, cpu = self.job.result()
                self.background_resume = turn + cpu_cooldown(cpu, BACKGROUND_CPU_SHARE)
                if self.key[0][:3] == (day, zone, unit):
                    self.publish('watch_history', result)
            except Exception:
                LOG.warning('watch_archive_projection_unavailable', exc_info=True)
                self.key = None
                self.retry_after = turn + 2
            self.job = None
        if not ready or turn < self.retry_after:
            return
        scope = (day, zone, unit, index, backfill, available, price_signature)
        key = (scope, self.archive.generation(USAGE), self.archive.generation(DETAIL),
               self.archive.generation(SESSIONS))
        scope_changed = self.key is None or self.key[0] != scope
        promoted = foreground and not self.foreground
        self.foreground = foreground
        interval = BACKGROUND_INTERVAL if backfill and not foreground else VISIBLE_INTERVAL
        due = self.last_started + interval
        if backfill and not foreground:
            due = max(due, self.background_resume)
        if (key != self.key or self.more) and (scope_changed or promoted or turn >= due):
            self.key = key
            self.last_started = turn
            self.job = self.pool.submit(self._measure_render, catalog, zone, unit, day, now)

    def _measure_render(self, *args):
        started = thread_time()
        result, more = self._render(*args)
        return result, more, thread_time() - started

    def _render(self, catalog, zone, unit, day, now):
        _, facts, more = self.usage.snapshot()
        reference = self.prices() or PricingCatalog(())
        entries, prompts, category = [], {}, {}
        for root, fact in facts.items():
            if not fact.report or fact.last_request_ms < day:
                continue
            _, usage, _ = fact.report
            causal = fact.causal_prompts or {}
            for entry, _, costs in usage:
                if not day <= entry.completed_at_ms <= now:
                    continue
                entries.append(entry)
                key = request_identity(entry)
                if entry.invocation_id in causal:
                    value = causal[entry.invocation_id]
                    prompts[key] = (root, *value) if value else None
                if costs is not None:
                    category[entry.model, entry.tokens] = costs
        def valuation(model, tokens):
            return category.get((model, tokens)) or reference.reference_category_valuation(model, tokens)
        def total_cost(model, tokens):
            amounts = valuation(model, tokens)
            return sum(amounts, Decimal(0)) if amounts is not None else None
        daily = None
        if entries:
            daily = daily_usage(unique_usage(entries, shared_history=True), prompts,
                                day_start_ms=day, now_ms=now, valuation=total_cost, category_valuation=valuation)
            daily = replace(daily, total=replace(daily.total, source_complete=False), prompt_count_complete=False)
        previews = catalog.archived_previews()
        projection = WatchProjection('Watch', 'OpenCode', (), earlier_previews=previews, now_ms=now,
                                    daily_usage=daily, daily_state='retained' if daily else 'loading')
        view = project_live(projection, zone, unit).to_json()
        cards = []
        for preview in previews:
            saved = load_detail(self.archive, preview.session_id)
            if saved is None:
                continue
            block = saved.value['view']['prompt_blocks'][0]
            prompts = [row for row in block['rows'] if row.get('completed_at_ms') and
                       not row.get('execution_unverified') and not row.get('in_progress')]
            if not prompts:
                continue
            prompt = max(prompts, key=lambda item: item['completed_at_ms'])
            row = dict(prompt=prompt, model=prompt.get('watch_model') or prompt.get('model_effort', 'N/A'),
                       effort=prompt.get('watch_effort') or 'N/A', marker='', tool=None,
                       live_context={}, watch_duration_ms=prompt.get('duration_ms'))
            cards.append(dict(session_id=preview.session_id, title=preview.title, focal_id=prompt['event_id'],
                              rows=[row], state='retained', invocation_verified=False,
                              observed_at_ms=saved.observed_ms, session_summary=None))
        return dict(day=day, view={**view, 'history_cards': cards[-10:], 'history_epoch': 1}), more

    def close(self):
        self.pool.shutdown(wait=True, cancel_futures=True)
