"""Web-only nonblocking hydration adapter over the shared Watch cadence.

Catalog/hints, account requests, retry and cadence remain coordinator-owned.
Session captures and account-history aggregation have separate isolated services;
none of their full histories run on the presentation/live thread.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from src.pricing.base import PricingUnavailableError
from src.sources.errors import SourceError
from src.analysis.timezones import local_day_start_ms, local_month_start_ms
from src.reports.history import WatchHistoryAcquisition
from .card_workers import CardWorkers
from .cards import WatchCards
from .session_costs import SessionCosts
from .coordinator import WatchCoordinator, WatchCycle
from .today_ccost import WatchTodayCCost
from .running import running_prompts
from .source_status import SourceStatus, SOURCE_CONFIRM_SECONDS
from .source_reads import SourceReads, cancel_source


class WebWatchCoordinator(WatchCoordinator):
    def __init__(self, *, service_factory, **kwargs):
        super().__init__(**kwargs)
        self.card_workers = CardWorkers(service_factory)
        self.card_timing_observed = False
        self.session_costs = SessionCosts(service_factory)
        self.cards = WatchCards(self.card_workers, self.recent_seconds, self._record_card_duration, self._monotonic,
            costs=self.session_costs)
        self.history_factory = service_factory
        self.history_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cost-guard-account-history")
        self.history_job = None
        self.history_due_ms = 0
        self.history_quota = None
        self.daily_history = WatchHistoryAcquisition()
        self.daily_usage = None
        self.daily_status = SourceStatus(self._monotonic)
        self.history_revision = None
        self.detail_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cost-guard-detail")
        self.detail_job = None
        self.reads = SourceReads()

    def _record_refresh_duration(self, seconds):
        if not self.card_timing_observed:
            super()._record_refresh_duration(seconds)

    def _record_card_duration(self, seconds):
        self.card_timing_observed = True
        # The shared 0.60/0.20 EMA and 6× clamp must measure actual background
        # capture work, not just the now-nonblocking catalog admission call.
        super()._record_refresh_duration(seconds)

    def tick_details(self, details, *, unavailable=False):
        if self.detail_job is not None:
            if not self.detail_job.done():
                return
            self.detail_job.result()
            self.detail_job = None
        with details.lock:
            if not details.leases:
                return
        self.detail_job = self.detail_pool.submit(self._detail_capture, details, unavailable, int(self.clock_ms()))

    def _detail_capture(self, details, unavailable, now_ms):
        service = None
        try:
            service = self.history_factory(now_ms)
            with self.reads.using(service.source):
                details.tick(service, unavailable=unavailable)
        except (SourceError, PricingUnavailableError):
            details.tick(None, unavailable=True)
        finally:
            if service is not None:
                service.close_accounts()

    def _selected_roots(self, observation):
        roots = super()._selected_roots(observation)
        self.cards.catalog(observation)
        return roots

    def _hydrate(self, roots, *, now_ms, force_fresh_ids=()):
        # The card scheduler admits bounded work and publishes each session
        # independently. Existing CLI hydration is intentionally untouched.
        return ()

    def _hydrate_startup(self, roots, *, now_ms):
        return ()

    def _account_history(self, sessions, snapshots, now_ms, active_roots=()):
        service = None
        try:
            service = self.history_factory(now_ms)
            with self.reads.using(service.source):
                service.enable_watch_accounts(record_evidence=False, history=self.daily_history)
                service.project_watch_accounts(snapshots)  # Establish provider period requirements before admission.
                today = WatchTodayCCost(service.timezone_id)
                today.schedule_history(service, sessions, now_ms, active_root_ids=active_roots, live_root_ids=active_roots)
                while today.history_pending and not self._closed:
                    # Share authoritative V2 brackets across the existing bounded
                    # four-root slice instead of relisting all history per root.
                    today.advance_history(service, now_ms)
                if self._closed:
                    return None
                service.project_watch_accounts(snapshots)
                return service.watch_account_history(), service.project_watch_today()
        except (SourceError, PricingUnavailableError) as error:
            return error
        finally:
            if service is not None:
                service.close_accounts()

    def _refresh_quota(self, observation, *, now_ms, force=False, allow_history=True, fresh_root_ids=()):
        revision = tuple(sorted(observation.revisions.items()))
        if revision != self.history_revision:
            self.history_due_ms = 0
            self.history_revision = revision
        changed = self.accounts.refresh(now_ms=now_ms)
        self.report_service.record_account_display(self.accounts.diagnostics())
        if changed or self.quota is None:
            self.quota = self.report_service.project_watch_accounts(self.accounts.snapshots)[0]
        if self.history_job is not None and self.history_job.done():
            value = self.history_job.result()
            if isinstance(value, Exception):
                self.daily_status.fail(value)
                self.history_due_ms = min(self.history_due_ms, now_ms + int(SOURCE_CONFIRM_SECONDS * 1000))
            elif value is not None and value[1].day_start_ms == local_day_start_ms(self.report_service.timezone_id, now_ms=now_ms):
                self.history_quota, self.daily_usage = value
                self.daily_status.clear()
            elif value is not None:
                self.history_due_ms = 0
            self.history_job = None
        if not self._closed and self.history_job is None and now_ms >= self.history_due_ms:
            self.history_due_ms = now_ms + 60_000
            self.history_job = self.history_pool.submit(self._account_history,
                observation.sessions, tuple(self.accounts.snapshots), now_ms,
                observation.active_candidates | observation.live_candidates)

    def enrich_once(self):
        return WatchCycle(self.status_projection(), (), ())

    def _build_projection(self, *, now_ms, status="", status_active=False, scanned=False):
        self.cards.tick(now_ms)
        day = local_day_start_ms(self.report_service.timezone_id, now_ms=now_ms)
        if self.daily_usage is not None and self.daily_usage.day_start_ms != day:
            self.daily_usage = self.history_quota = None
            self.history_due_ms = 0
        active, history, state = self.cards.project(now_ms)
        frame = super()._build_projection(now_ms=now_ms, status=status,
            status_active=status_active, scanned=scanned)
        # Keep independently refreshed native quota observations. Canonical
        # historical cost scopes are indexed separately, never recomputed here.
        if self.history_quota is not None and frame.quota is not None:
            accounts = self.history_quota.project(tuple(item.account for item in frame.quota.accounts),
                now_ms=now_ms, today_start_ms=day,
                month_start_ms=local_month_start_ms(self.report_service.timezone_id, now_ms=now_ms),
                timezone_id=self.report_service.timezone_id,
                workday_calendar=str(self.config.get("workdayCalendar") or ""))
            frame = replace(frame, quota=replace(frame.quota, accounts=accounts))
        history_pending = any(entry.latest_ms is None for entry in self.cards.sessions.values())
        history_failed = any(entry.source_status.state(retained=entry.capture is not None) == "unavailable"
            for entry in self.cards.sessions.values())
        frame = replace(frame, active_cards=active, history_cards=history, cards_state=state,
            running=running_prompts(active, state),
            daily_usage=self.daily_usage,
            daily_state=self.daily_status.state(retained=self.daily_usage is not None) or ("loading" if self.daily_usage is None
                else "refreshing" if self.history_job is not None else "observed"),
            history_state="unavailable" if history_failed else "loading" if history_pending else "observed",
            active_count=sum(row.prompt.in_progress for card in active for row in card.rows if row.prompt.event_id == card.focal_id)
                + sum(not card.rows for card in active))
        self._last_projection = frame
        return frame

    def cancel(self):
        self._closed = True
        cancel_source(self.source)
        self.reads.cancel()
        self.card_workers.cancel()

    def close(self):
        self.cancel()
        super().close()
        try:
            self.card_workers.close()
        finally:
            self.session_costs.close()
            self.history_pool.shutdown(wait=True, cancel_futures=True)
            self.detail_pool.shutdown(wait=True, cancel_futures=True)
            for future in (self.history_job, self.detail_job):
                if future is not None and not future.cancelled():
                    future.result()
