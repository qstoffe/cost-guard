"""Web-only nonblocking hydration adapter over the shared Watch cadence.

Catalog/hints, account requests, retry and cadence remain coordinator-owned.
Session captures and account-history aggregation have separate isolated services;
none of their full histories run on the presentation/live thread.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace

from src.pricing.base import PricingUnavailableError
from src.sources.errors import SourceError
from src.analysis.account_timeline import PERIODS
from src.analysis.daily_usage import DailyUsage
from src.analysis.timezones import local_day_start_ms, local_month_start_ms
from src.application.session_catalog import MINI_PREVIEW_LIMIT
from src.application.session_quota import source_scope
from src.reports.history import WatchHistoryAcquisition
from src.reports.accounts import AccountPeriodHistory
from .account_timeline import AccountTimeline, CardToday
from .card_workers import CardWorkers
from .cards import WatchCards
from .session_costs import SessionCosts
from .coordinator import WatchCoordinator, WatchCycle
from .today_ccost import WatchTodayCCost
from .running import running_prompts
from .source_status import SourceStatus, SOURCE_CONFIRM_SECONDS
from .source_reads import SourceReads, cancel_source
from .detail_capture import DetailWorkerStopError


@dataclass(frozen=True, slots=True)
class DailyAccountHistory:
    accounts: AccountPeriodHistory
    usage: DailyUsage
    source: tuple
    roots: dict


class WebWatchCoordinator(WatchCoordinator):
    def __init__(self, *, service_factory, session_cost_factory=None, guidance_binding=None,
                 card_readers=None, detail_capture=None, **kwargs):
        super().__init__(**kwargs)
        self.card_workers = CardWorkers(service_factory,
            batch_size=2 if callable(getattr(self.source, 'load_card_snapshots', None)) else 1,
            readers=card_readers)
        self.card_timing_observed = False
        self.session_costs = SessionCosts(service_factory, session_cost_factory)
        self.guidance = None
        if guidance_binding is not None:
            from .card_guidance import CardGuidance
            self.guidance = CardGuidance(self.card_workers, self.report_service,
                binding=guidance_binding, monotonic=self._monotonic)
        self.cards = WatchCards(self.card_workers, self.recent_seconds, self._record_card_duration, self._monotonic,
            costs=self.session_costs, guidance=self.guidance, started_at_ms=self.started_at_ms)
        self.history_factory = service_factory
        self.history_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cost-guard-account-history")
        self.history_job = None
        self.history_due_ms = 0
        self.history_quota = None
        self.daily_history = WatchHistoryAcquisition(share_roots=True)
        self.daily_history_source = None
        self.history_source, self.history_roots, self.card_today = None, None, None
        self.daily_usage = None
        self.daily_status = SourceStatus(self._monotonic)
        self.history_revision = None
        self.detail_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cost-guard-detail")
        self.detail_job = None
        self.detail_capture = detail_capture
        self.include_archived_revisions = True
        self.catalog_observation = None
        self.catalog_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cost-guard-session-index")
        self.catalog_job = None
        self.reads = SourceReads()
        self.account_timeline = AccountTimeline(service_factory, self.reads, self.report_service.cache_repository)

    def tick_account_timeline(self, frame, demand, *, available, terminal):
        service = self.report_service
        foreground = demand()
        source = source_scope(service.source)
        observation = self.catalog_observation
        available = available and observation is not None and observation.source_epoch == source[-1]
        identified = source[0] != 'opencode-v2' or source[-1] is not None
        return self.account_timeline.tick(source=source if identified else None, observation=observation,
            accounts=frame.quota.accounts if frame and frame.quota else (), periods=frozenset(PERIODS),
            zone=service.timezone_id, catalog=service.comparison_pricing_catalog,
            prices=getattr(service.comparison_pricing_provider, 'cached_catalog', lambda: None),
            migration_gap=service.selection.migration_gap, now_ms=int(self.clock_ms()),
            available=available, terminal=terminal, card_today=self.card_today,
            shared_roots=self.history_roots if self.history_source == source else None,
            foreground=foreground, require_background_prices=True)

    def _record_refresh_duration(self, seconds):
        if not self.card_timing_observed:
            super()._record_refresh_duration(seconds)

    def _record_card_duration(self, seconds):
        self.card_timing_observed = True
        # The shared 0.60/0.20 EMA and 6× clamp must measure actual background
        # capture work, not just the now-nonblocking catalog admission call.
        super()._record_refresh_duration(seconds)

    def tick_details(self, details, *, unavailable=False):
        details.observe_source(self.catalog_observation, self.cards.sessions, unavailable=unavailable)
        if self.detail_job is not None:
            if not self.detail_job.done():
                return
            try:
                self.detail_job.result()
            except DetailWorkerStopError:
                raise  # Unconfirmed owned-child exit is a host ownership failure.
            except Exception:
                details.failed('detail_worker_failed')
            self.detail_job = None
        with details.lock:
            if not details.leases:
                return
        self.detail_job = self.detail_pool.submit(self._detail_capture, details, unavailable, int(self.clock_ms()))

    def _detail_capture(self, details, unavailable, now_ms):
        if self.detail_capture is not None:
            return self.detail_capture.capture(details, self.source, self.config, now_ms, unavailable=unavailable)
        service = None
        try:
            service = self.history_factory(now_ms)
            with self.reads.using(service.source):
                details.tick(service, unavailable=unavailable)
        except (SourceError, PricingUnavailableError):
            details.tick(None, unavailable=True)
        except Exception:
            details.failed('detail_internal_error')
        finally:
            if service is not None:
                service.close_accounts()

    def _selected_roots(self, observation):
        self.catalog_observation = observation
        roots = super()._selected_roots(observation)
        self.cards.catalog(observation)
        return roots

    def tick_catalog(self, catalog, *, unavailable=False, source_interrupted=False):
        catalog.observe(self.catalog_observation, unavailable=unavailable,
                        source_interrupted=source_interrupted, timezone_id=self.report_service.timezone_id)
        evidence = []
        for entry in self.cards.sessions.values():
            if (entry.snapshot is None or entry.capture is None or not entry.capture.authoritative
                    or entry.capture.retained or entry.capture.catalog_prompt is None
                    or entry.source_status.failed_at is not None
                    or entry.verified_generation != entry.generation):
                continue
            prompt, start, running, ended = entry.capture.catalog_prompt
            evidence.append((entry.snapshot.root, entry.snapshot.source_revision, entry.capture.observed_at_ms,
                             prompt, start, running, None, ended))
        catalog.observe_prompts(evidence)
        if self.catalog_job is not None:
            if not self.catalog_job.done():
                return
            job, self.catalog_job = self.catalog_job, None
            try:
                job.result()
            except Exception:
                catalog.index_failed('scalar_worker_failed')
        if not self._closed and catalog.needed():
            self.catalog_job = self.catalog_pool.submit(self._catalog_capture, catalog, int(self.clock_ms()))

    def catalog_frame(self, catalog, frame):
        # Publication reads only the shared index. Never wait for catalog_job or
        # rich card workers; even the first metadata-only observation is useful.
        if frame is None:
            return None
        running = {card.session_id for card in frame.active_cards
            if any(row.prompt.in_progress or row.prompt.execution_unverified for row in card.rows)}
        previews = catalog.previews(running, limit=MINI_PREVIEW_LIMIT)
        self.cards.preview_ids = tuple(item.session_id for item in previews)
        published = []
        for item in previews:
            state, reason = self.cards.preview_status(item.session_id, frame.now_ms)
            published.append(replace(item, hydration_state=state, hydration_reason=reason,
                empty_history=catalog.state == "observed" and self.cards.preview_empty_history(item.session_id)))
        return replace(frame, earlier_previews=tuple(published),
            earlier_cards=self.cards.preview_cards(frame.now_ms))

    def _catalog_capture(self, catalog, now_ms):
        service = None
        try:
            service = self.history_factory(now_ms)
            with self.reads.using(service.source):
                catalog.tick(service)
        except SourceError as error:
            catalog.index_failed(str(error.code), terminal=error.terminal)
        except PricingUnavailableError:
            catalog.index_failed('pricing_unavailable')
        finally:
            if service is not None:
                service.close_accounts()

    def _hydrate(self, roots, *, now_ms, force_fresh_ids=()):
        # The card scheduler admits bounded work and publishes each session
        # independently. Existing CLI hydration is intentionally untouched.
        return ()

    def _hydrate_startup(self, roots, *, now_ms):
        return ()

    def _account_history(self, sessions, snapshots, now_ms, active_roots=(), *, expected_source=None):
        service = None
        try:
            service = self.history_factory(now_ms)
            with self.reads.using(service.source):
                source = source_scope(service.source)
                if expected_source is not None and source != expected_source:
                    return None
                if self.daily_history_source != source:
                    self.daily_history.reset()
                    self.daily_history_source = source
                service.enable_watch_accounts(record_evidence=False, history=self.daily_history)
                service.prepare_watch_account_history(snapshots)
                today = WatchTodayCCost(service.timezone_id)
                today.schedule_history(service, sessions, now_ms, active_root_ids=active_roots, live_root_ids=active_roots)
                while today.history_pending and not self._closed:
                    # Share authoritative V2 brackets across the existing bounded
                    # four-root slice instead of relisting all history per root.
                    today.advance_history(service, now_ms)
                if self._closed or source_scope(service.source) != source:
                    self.daily_history_source = None
                    return None
                service.project_watch_accounts(snapshots)
                history, daily = service.watch_account_history(), service.project_watch_today()
                return DailyAccountHistory(history, daily, source, dict(self.daily_history.chart_roots))
        except (SourceError, PricingUnavailableError) as error:
            return error
        finally:
            if service is not None:
                service.close_accounts()

    def _refresh_quota(self, observation, *, now_ms, force=False, allow_history=True, fresh_root_ids=()):
        source = source_scope(self.report_service.source)
        revision = source, tuple(sorted(observation.revisions.items()))
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
            elif (value is not None and value.source == source and
                  value.usage.day_start_ms == local_day_start_ms(self.report_service.timezone_id, now_ms=now_ms)):
                self.history_quota, self.daily_usage = value.accounts, value.usage
                self.history_source, self.history_roots = value.source, value.roots
                self.daily_status.clear()
            elif value is not None:
                self.history_due_ms = 0
            self.history_job = None
        if not self._closed and self.history_job is None and now_ms >= self.history_due_ms:
            self.history_due_ms = now_ms + 60_000
            self.history_job = self.history_pool.submit(self._account_history,
                observation.sessions, tuple(self.accounts.snapshots), now_ms,
                observation.active_candidates | observation.live_candidates, expected_source=source)

    def enrich_once(self):
        return WatchCycle(self.status_projection(), (), ())

    @property
    def work_ready(self):
        return self.card_workers.completed

    def service_completed(self):
        """Owner-thread refill only; no source polling, accounts or publication."""
        if not self._closed:
            self.cards.tick(int(self.clock_ms()), completed_only=True)

    def _build_projection(self, *, now_ms, status="", status_active=False, scanned=False):
        self.cards.tick(now_ms)
        day = local_day_start_ms(self.report_service.timezone_id, now_ms=now_ms)
        source = source_scope(self.report_service.source)
        if self.daily_usage is not None and (self.daily_usage.day_start_ms != day or self.history_source != source):
            self.daily_usage = self.history_quota = None
            self.history_source = self.history_roots = None
            self.history_due_ms = 0
        active, history, state = self.cards.project(now_ms)
        frame = super()._build_projection(now_ms=now_ms, status=status,
            status_active=status_active, scanned=scanned)
        # Keep independently refreshed native quota observations. Canonical
        # historical cost scopes are indexed separately, never recomputed here.
        self.card_today = None
        if self.history_quota is not None and frame.quota is not None:
            accounts = self.history_quota.project(tuple(item.account for item in frame.quota.accounts),
                now_ms=now_ms, today_start_ms=day,
                month_start_ms=local_month_start_ms(self.report_service.timezone_id, now_ms=now_ms),
                timezone_id=self.report_service.timezone_id,
                workday_calendar=str(self.config.get("workdayCalendar") or ""))
            frame = replace(frame, quota=replace(frame.quota, accounts=accounts))
            self.card_today = CardToday.from_accounts(accounts, source, self.report_service.timezone_id,
                day, self.daily_usage.observed_at_ms, self.history_quota)
        proof = self.cards.history
        frame = replace(frame, active_cards=active, history_cards=history, cards_state=state,
            recent_finished_cards=self.cards.recent.project(self.cards, now_ms),
            running=running_prompts(active, state),
            daily_usage=self.daily_usage,
            daily_state=self.daily_status.state(retained=self.daily_usage is not None) or ("loading" if self.daily_usage is None
                else "refreshing" if self.history_job is not None else "observed"),
            history_state=proof.state, history_scope=proof.scope, history_epoch=proof.epoch,
            history_catalog_revision=proof.catalog_revision, history_verified_at_ms=proof.verified_at_ms,
            history_checked=proof.checked, history_total=proof.total, history_cause=proof.cause,
            active_count=sum(row.prompt.in_progress for card in active for row in card.rows if row.prompt.event_id == card.focal_id)
                + sum(not card.rows for card in active))
        self._last_projection = frame
        return frame

    def cancel(self):
        self._closed = True
        if self.detail_capture is not None:
            self.detail_capture.cancel()
        cancel_source(self.source)
        self.reads.cancel()
        if self.guidance is not None:
            self.guidance.cancel()
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
            self.catalog_pool.shutdown(wait=True, cancel_futures=True)
            self.account_timeline.close()
            for future in (self.history_job, self.catalog_job):
                if future is not None and not future.cancelled():
                    future.result()
            if self.detail_job is not None and not self.detail_job.cancelled():
                try:
                    self.detail_job.result()
                except DetailWorkerStopError:
                    raise
                except Exception:
                    pass  # Ordinary detail faults cannot turn normal host close into failure.
