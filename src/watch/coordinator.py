"""Coordinator-owned Watch lifecycle over abstract Session Sources."""
from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import Callable, Mapping, Sequence

from src.domain import NormalizedSession, SessionSnapshot
from src.reports import ReportService, SessionPromptBlock
from src.sources.base import LiveSessionSource
from src.sources.errors import SourceError
from src.sources.selection import SourceSelection

from .models import WatchProjection, WatchRow
from .observers import CatalogObservation, LiveEventPump, observe_catalog
from .tracker import WatchRowTracker
from .token_mix import WatchTokenMix
from .accounts import durable_quota_failure, reconcile_accounts, recovery_account_keys

ClockMs = Callable[[], int]
Sleep = Callable[[float], None]
QUOTA_REFRESH_MS = 60_000
RESUME_GAP_MS = 90_000
QUOTA_RECOVERY_SECONDS = 60.0
QUOTA_RETRY_SECONDS = (5.0, 10.0, 20.0)
INITIAL_ROOT_SAMPLE = 20


def _clock_ms() -> int:
    return int(time.time() * 1000)


def _root_activity(sessions: Sequence[NormalizedSession], root_by_session: Mapping[str, str]) -> dict[str, int]:
    activity: dict[str, int] = {}
    for item in sessions:
        root = root_by_session.get(item.session_id, item.session_id)
        observed = max(item.created_at_ms, item.updated_at_ms, item.archived_at_ms or 0)
        activity[root] = max(activity.get(root, 0), observed)
    return activity


@dataclass(frozen=True, slots=True)
class WatchCycle:
    projection: WatchProjection
    changed_roots: tuple[str, ...]
    hydrated_roots: tuple[str, ...]
    resynced: bool = False


class WatchCoordinator:
    """Own scheduling, invalidation and rendering inputs for one Watch process.

    Source-specific mechanics remain inside Session Sources / observers.  Watch
    never treats event hints as history and never runs a subprocess to decide
    whether a root needs hydration.
    """

    def __init__(
        self,
        *,
        selection: SourceSelection,
        report_service: ReportService,
        config: Mapping[str, object],
        session_id: str | None = None,
        clock_ms: ClockMs = _clock_ms,
        sleep: Sleep = time.sleep,
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        self.selection = selection
        self.source = selection.source
        self.report_service = report_service
        self.config = config
        self.session_id = session_id
        self.clock_ms = clock_ms
        self.sleep = sleep
        self._monotonic_clock = monotonic
        self.started_at_ms = int(clock_ms())
        self.token_mix = WatchTokenMix(self.started_at_ms)
        raw_interval = config.get("sessionWatchIntervalSeconds", "auto")
        self.auto_interval = isinstance(raw_interval, str) and raw_interval.strip().lower() == "auto"
        self.interval_seconds = 5 if self.auto_interval else max(5, int(raw_interval))
        self.idle_interval_seconds = self.interval_seconds if self.auto_interval else max(30, self.interval_seconds * 3)
        self._refresh_ema_seconds: float | None = None
        self.max_rows = max(1, int(config.get("watchDashboardMaxRows", 14)))
        self.recent_seconds = max(0.0, float(config.get("watchRecentEventSeconds", 30)))
        self.tracker = WatchRowTracker(
            started_at_ms=self.started_at_ms,
            recent_seconds=self.recent_seconds,
            max_rows=self.max_rows,
            session_scope=session_id is not None,
        )
        self.observation: CatalogObservation | None = None
        self.blocks: dict[str, SessionPromptBlock] = {}
        self.snapshots: dict[str, SessionSnapshot] = {}
        self.quota = None
        self._account_quotas = ()
        self._account_quota_seen_ms = {}
        self._quota_stale = False
        self._last_account_fresh = ()
        self._quota_recovery_until: float | None = None
        self._quota_retry_at: float | None = None
        self._quota_retry_index = 0
        self._quota_recovering_accounts = ()
        self._quota_first_retried: set[tuple[str, str, str]] = set()
        self._last_cycle_end_ms: int | None = None
        self._event_pump: LiveEventPump | None = None
        self._last_account_refresh_ms = 0
        self._last_quota_refresh_ms = 0
        self._last_projection: WatchProjection | None = None

    def _record_refresh_duration(self, seconds: float) -> None:
        value = max(0.001, float(seconds))
        if self._refresh_ema_seconds is None:
            self._refresh_ema_seconds = value
            return
        alpha = 0.60 if value > self._refresh_ema_seconds else 0.20
        self._refresh_ema_seconds = alpha * value + (1.0 - alpha) * self._refresh_ema_seconds

    def _monotonic(self) -> float:
        return self._monotonic_clock() if self._monotonic_clock else time.monotonic()

    def _detect_quota_resume(self, now_ms: int) -> bool:
        if self._last_cycle_end_ms is None:
            return False
        active = self._last_projection.active_count if self._last_projection else 0
        # Measure unobserved waiting, never time spent hydrating/fetching quotas.
        # Explicitly long configured waits also need at least 60s of overshoot.
        threshold = max(RESUME_GAP_MS, self._delay_seconds(active) * 1000 + 60_000)
        if now_ms - self._last_cycle_end_ms <= threshold:
            return False
        self._last_cycle_end_ms = now_ms  # the next poll must not re-arm this gap
        self._quota_recovery_until = self._monotonic() + QUOTA_RECOVERY_SECONDS
        self._quota_retry_at = self._monotonic()
        self._quota_retry_index = 0
        return True

    def _end_quota_recovery(self) -> None:
        self._quota_recovery_until = self._quota_retry_at = None
        self._quota_recovering_accounts = ()

    def _wait_delay_seconds(self, active_count: int) -> float:
        delay = float(self._delay_seconds(active_count))
        for target in (self._quota_retry_at, self._quota_recovery_until):
            if target is not None:
                delay = min(delay, max(0.0, target - self._monotonic()))
        return delay

    def _delay_seconds(self, active_count: int) -> int:
        if not self.auto_interval:
            return self.interval_seconds if active_count else self.idle_interval_seconds
        ema = self._refresh_ema_seconds or (5.0 / 6.0)
        return max(5, min(30, int(math.ceil(6.0 * ema))))

    @property
    def live(self) -> bool:
        return bool(self.source.capabilities.live_changes and hasattr(self.source, "iter_changes"))

    def _selected_roots(self, observation: CatalogObservation) -> tuple[NormalizedSession, ...]:
        if self.session_id is not None:
            if not observation.roots:
                raise ValueError(f"OpenCode session '{self.session_id}' was not found or is archived.")
            return observation.roots
        activity = _root_activity(observation.sessions, observation.root_by_session)
        return tuple(sorted(
            observation.roots,
            key=lambda item: (activity.get(item.session_id, item.updated_at_ms), item.session_id),
            reverse=True,
        ))

    def _hydrate(
        self, roots: Sequence[NormalizedSession], *, now_ms: int, force_fresh_ids: Sequence[str] = ()
    ) -> tuple[str, ...]:
        hydrated: list[str] = []
        force_fresh = set(force_fresh_ids)
        self.report_service.set_now_ms(now_ms)
        for root in roots:
            self.report_service.invalidate_roots((root.session_id,))
            block, snapshot, bundle = self.report_service.build_watch_root(
                root, force_fresh=root.session_id in force_fresh
            )
            self.blocks[root.session_id] = block
            self.snapshots[root.session_id] = snapshot
            self.token_mix.observe(snapshot, bundle)
            hydrated.append(root.session_id)
        return tuple(hydrated)

    def _refresh_account_quota(self, *, now_ms: int, force: bool = False) -> bool:
        """Refresh once per minute, except for bounded post-idle recovery retries.

        Source changes are deliberately not account-refresh triggers.  This keeps
        OpenCode Watch activity from multiplying external account requests.
        """
        expired = self._quota_recovery_until is not None and self._monotonic() >= self._quota_recovery_until
        if expired:
            self._end_quota_recovery()
            self._account_quotas, self._account_quota_seen_ms, self._quota_stale = reconcile_accounts(
                self._account_quotas, self._last_account_fresh, self._account_quota_seen_ms, now_ms=now_ms,
                update_seen=False,  # deadline expiry is not a new provider observation
            )
        retry_due = self._quota_retry_at is not None and self._monotonic() >= self._quota_retry_at
        if not force and not retry_due and self._last_account_refresh_ms and now_ms - self._last_account_refresh_ms < QUOTA_REFRESH_MS:
            return expired
        self.report_service.set_now_ms(now_ms)
        try:
            fresh = self.report_service.account_quota_snapshots()
        except Exception:
            fresh = ()
        completed_ms = int(self.clock_ms())
        recovering = self._quota_recovery_until is not None and self._monotonic() < self._quota_recovery_until
        previous = self._account_quotas
        # The report service fails soft per provider. A missing snapshot means
        # this refresh could not supply that provider, not that its last known
        # balance suddenly became zero. Keep it briefly and label it as stale;
        # an explicit unavailable snapshot replaces it immediately.
        self._account_quotas, self._account_quota_seen_ms, self._quota_stale = reconcile_accounts(
            previous, fresh, self._account_quota_seen_ms, now_ms=completed_ms, recovering=recovering,
        )
        self._last_account_fresh = fresh
        self._last_account_refresh_ms = completed_ms
        # An account that has never delivered capacity in this Watch (typically
        # a cold provider at startup) gets the same bounded retry schedule once,
        # instead of showing a bare error until the next minute refresh.
        unseen = {item.key for item in fresh if item.availability == "error" and not durable_quota_failure(item)
                  and item.key not in self._account_quota_seen_ms and item.key not in self._quota_first_retried}
        if unseen and not recovering:
            self._quota_first_retried |= unseen
            self._quota_recovery_until = self._monotonic() + QUOTA_RECOVERY_SECONDS
            self._quota_retry_index = 0
            recovering = True
        if recovering:
            self._quota_recovering_accounts = recovery_account_keys(previous, fresh, self._account_quotas)
            if self._quota_recovering_accounts:
                self._quota_retry_at = None
                if self._quota_retry_index < len(QUOTA_RETRY_SECONDS):
                    self._quota_retry_at = self._monotonic() + QUOTA_RETRY_SECONDS[self._quota_retry_index]
                    self._quota_retry_index += 1
            else:
                self._end_quota_recovery()
        else:
            self._end_quota_recovery()
        return True

    def _refresh_quota(self, observation: CatalogObservation, *, now_ms: int, force: bool = False) -> None:
        # Local usage refreshes on meaningful source changes (or at most every
        # five minutes while unchanged).  Account quota has its own one-minute
        # cadence and is reused here instead of being fetched for every change.
        account_changed = self._refresh_account_quota(now_ms=now_ms, force=self._last_account_refresh_ms == 0)
        if (
            not force
            and not account_changed
            and self._last_quota_refresh_ms
            and now_ms - self._last_quota_refresh_ms < 300_000
        ):
            return
        self.report_service.set_now_ms(now_ms)
        try:
            self.quota = self.report_service.build_watch_quota(
                observation.sessions, quota_snapshots=self._account_quotas, query_account=False
            )
        except Exception:
            # Local Watch rows remain useful even when quota projection is unavailable.
            if self.quota is None:
                self.quota = None
        self._last_quota_refresh_ms = now_ms

    @staticmethod
    def _countdown_text(seconds_until_check: int) -> str:
        seconds = max(0, int(seconds_until_check))
        minutes, seconds = divmod(seconds, 60)
        return f"{minutes:02d}:{seconds:02d}"

    def _steady_status(self, active_count: int, seconds_until_check: int, rows: Sequence[WatchRow] | None = None) -> str:
        countdown = self._countdown_text(seconds_until_check)
        if active_count:
            visible = rows if rows is not None else (self._last_projection.rows if self._last_projection else ())
            active_rows = [row for row in visible if row.prompt.in_progress]
            only_compactions = len(active_rows) == active_count and all(row.prompt.is_compaction for row in active_rows)
            noun = ("compaction" if active_count == 1 else "compactions") if only_compactions else ("prompt" if active_count == 1 else "prompts")
            # Rows waiting only on background work keep the footer active and say why.
            waiting = [kind for row in active_rows if row.prompt.background_only for kind in row.prompt.background_kinds]
            background = ""
            if waiting:
                background = f" · background {waiting[0]}" if len(waiting) == 1 else f" · {len(waiting)} background jobs"
            return f"{active_count} {noun} running{background} · Next refresh: {countdown}"
        return f"Idle · Next prompt check: {countdown}"

    @staticmethod
    def _visible_signature(projection: WatchProjection) -> tuple[object, ...]:
        """Stable dashboard content excluding the overwrite-only status/countdown.

        A Watch poll can change transient presentation state without a source
        revision (notably the 30-second recent-completion marker and provider
        quota refresh).  Those changes still require a full dashboard repaint.
        """
        rows = tuple(
            (
                row.session_id, row.prompt.event_id, row.marker, row.prompt.in_progress,
                row.prompt.aborted, row.prompt.duration_ms,
                row.prompt.watch_delta_context_tokens, row.prompt.watch_next_context_tokens,
                row.is_latest_session_event, row.next_context_warning, row.next_context_warning_severity,
                row.prompt.watch_next_context_cached_ccost, row.prompt.watch_next_context_fresh_ccost,
                row.tool,
            )
            for row in projection.rows
        )
        warnings = tuple((projection.session_warnings or {}).items())
        return (rows, projection.quota, projection.quota_stale, projection.quota_recovering_accounts,
                projection.source_warnings, warnings, projection.recent_model_notice,
                projection.recent_promotion_notices, projection.token_mix, tuple(projection.session_mix.items()))

    @staticmethod
    def _transient_signature(projection: WatchProjection) -> tuple[object, ...]:
        return (tuple((row.session_id, row.prompt.event_id, row.marker) for row in projection.rows),
                projection.recent_model_notice, projection.recent_promotion_notices)

    @classmethod
    def _needs_full_render(cls, previous: WatchProjection, current: WatchProjection, cycle: WatchCycle) -> bool:
        if cycle.changed_roots or cycle.resynced or current.active_count > 0:
            return True
        return cls._visible_signature(previous) != cls._visible_signature(current)

    def _token_valuation(self):
        try:
            return self.report_service.token_category_valuation()
        except Exception:
            # Without a reference catalog the mix still renders its shares.
            return None

    def _projection(self, *, now_ms: int, status: str = "", status_active: bool = False) -> WatchProjection:
        rows = self.tracker.project(self.blocks, self.snapshots, now_ms=now_ms)
        active = sum(1 for row in rows if row.prompt.in_progress)
        session_warnings: dict[str, str] = {}
        for row in rows:
            warning = row.next_context_warning
            if warning:
                session_warnings[row.session_id] = warning
        if not status:
            delay = int(math.ceil(self._wait_delay_seconds(active)))
            status = self._steady_status(active, delay, rows)
        projection = WatchProjection(
            title=(f"Cost Guard Watch - {self.session_id}" if self.session_id else "Cost Guard Watch"),
            source_label=self.selection.selected.upper(),
            rows=rows,
            source_warnings=tuple(self.selection.warnings),
            quota=self.quota,
            quota_stale=self._quota_stale,
            quota_recovering_accounts=self._quota_recovering_accounts,
            active_count=active,
            status=status,
            status_active=status_active,
            now_ms=now_ms,
            session_warnings=session_warnings,
            recent_model_notice=self.report_service.recent_model_notice_text(),
            recent_promotion_notices=self.report_service.recent_promotion_notice_texts(),
            token_mix=self.token_mix.project(self._token_valuation()),
            session_mix=dict(self.token_mix.project_sessions(self._token_valuation())),
        )
        self._last_projection = projection
        return projection

    def initialize(self) -> WatchCycle:
        refresh_started = time.monotonic()
        now_ms = int(self.clock_ms())
        observation = observe_catalog(self.source, session_id=self.session_id)
        roots = self._selected_roots(observation)
        # Initial global hydration is deliberately bounded.  Every root revision
        # is already known, so later changes still enter immediately; we hydrate
        # only the newest roots likely to contain active/recent work.
        # Preserve the historical default discovery scope independently of the
        # display cap, so row configuration cannot change Watch-run mix inputs.
        initial_roots = roots if self.session_id is not None else roots[:INITIAL_ROOT_SAMPLE]
        hydrated = self._hydrate(initial_roots, now_ms=now_ms)
        self.observation = observation
        self._record_refresh_duration(time.monotonic() - refresh_started)
        self._refresh_quota(observation, now_ms=now_ms, force=True)
        if self.live:
            self._start_event_pump()
        completed_ms = int(self.clock_ms())
        self._last_cycle_end_ms = completed_ms
        return WatchCycle(
            self._projection(now_ms=completed_ms),
            tuple(root.session_id for root in roots),
            hydrated,
            resynced=True,
        )

    def _start_event_pump(self) -> None:
        if not self.live:
            return
        if self._event_pump is not None:
            self._event_pump.stop()
        self._event_pump = LiveEventPump(self.source)  # type: ignore[arg-type]
        self._event_pump.start()

    def poll_once(self, *, force_resync: bool = False, hinted_session_ids: Sequence[str] = ()) -> WatchCycle:
        refresh_started = time.monotonic()
        now_ms = int(self.clock_ms())
        self._detect_quota_resume(now_ms)
        old = self.observation
        observation = observe_catalog(self.source, session_id=self.session_id)
        roots = self._selected_roots(observation)
        old_revisions = {} if old is None else old.revisions
        changed = {
            root_id for root_id, revision in observation.revisions.items()
            if force_resync or old_revisions.get(root_id) != revision
        }
        if old is not None:
            changed.update(root_id for root_id in old.revisions if root_id not in observation.revisions)
        for session_id in hinted_session_ids:
            root_id = observation.root_by_session.get(session_id)
            if root_id:
                changed.add(root_id)

        current_roots = {item.session_id: item for item in roots}
        active_roots = {
            root_id for root_id, block in self.blocks.items()
            if any(row.in_progress for row in block.rows)
        }
        removed = set(self.blocks) - set(current_roots)
        for root_id in removed:
            self.blocks.pop(root_id, None)
            self.snapshots.pop(root_id, None)
            self.report_service.invalidate_roots((root_id,))

        hydrate_ids = changed | active_roots
        hydrate = [current_roots[root_id] for root_id in hydrate_ids if root_id in current_roots]
        hydrated = self._hydrate(
            hydrate, now_ms=now_ms, force_fresh_ids=active_roots
        ) if hydrate else ()
        self.observation = observation
        self._record_refresh_duration(time.monotonic() - refresh_started)
        if changed:
            self._refresh_quota(observation, now_ms=now_ms, force=True)
        else:
            self._refresh_quota(observation, now_ms=now_ms, force=False)
        completed_ms = int(self.clock_ms())
        self._last_cycle_end_ms = completed_ms
        return WatchCycle(
            self._projection(now_ms=completed_ms),
            tuple(sorted(changed)),
            hydrated,
            resynced=force_resync,
        )

    def status_projection(self, *, seconds_until_check: int | None = None) -> WatchProjection:
        now_ms = int(self.clock_ms())
        self.report_service.set_now_ms(now_ms)
        active = 0 if self._last_projection is None else self._last_projection.active_count
        status = "Watching" if seconds_until_check is None else self._steady_status(active, seconds_until_check)
        return self._projection(now_ms=now_ms, status=status, status_active=active > 0)

    def activity_projection(self, status: str = "Refreshing...") -> WatchProjection:
        now_ms = int(self.clock_ms())
        self.report_service.set_now_ms(now_ms)
        return self._projection(now_ms=now_ms, status=status, status_active=True)

    def _v1_wait(self, renderer) -> None:
        projection = self._last_projection or self._projection(now_ms=self.clock_ms(), status="Watching")
        visible_projection = projection
        delay = self._wait_delay_seconds(projection.active_count)
        deadline = self._monotonic() + delay
        while True:
            if self._detect_quota_resume(int(self.clock_ms())):
                return
            remaining = deadline - self._monotonic()
            if remaining <= 0:
                return
            status_projection = self.status_projection(seconds_until_check=int(remaining + 0.999))
            if self._transient_signature(status_projection) != self._transient_signature(visible_projection):
                # Presentation-only wake: expire markers and pricing notices
                # without touching OpenCode or waiting for the next source poll.
                renderer.render(status_projection)
                visible_projection = status_projection
            else:
                renderer.render_status(status_projection)
            self.sleep(min(1.0, remaining))

    def _v2_wait(self, renderer) -> tuple[bool, tuple[str, ...]]:
        """Wait one stable v77-style cadence while buffering V2 change hints."""
        projection = self._last_projection or self._projection(now_ms=self.clock_ms(), status="Watching")
        visible_projection = projection
        delay = self._wait_delay_seconds(projection.active_count)
        started = self._monotonic()
        deadline = started + delay
        hinted_deadline: float | None = None
        hints: set[str] = set()
        resync_required = False
        while True:
            if self._detect_quota_resume(int(self.clock_ms())):
                return resync_required, tuple(sorted(hints))
            effective_deadline = min(deadline, hinted_deadline) if hinted_deadline is not None else deadline
            remaining = effective_deadline - self._monotonic()
            if remaining <= 0:
                return resync_required, tuple(sorted(hints))
            status_projection = self.status_projection(seconds_until_check=int(remaining + 0.999))
            if self._transient_signature(status_projection) != self._transient_signature(visible_projection):
                renderer.render(status_projection)
                visible_projection = status_projection
            else:
                renderer.render_status(status_projection)
            pump = self._event_pump
            result = pump.get(min(1.0, remaining)) if pump is not None else None
            if result is None:
                continue
            if result.resync_required:
                resync_required = True
                hinted_deadline = min(deadline, started + 5.0)
                continue
            if result.change is not None and result.change.session_id:
                hints.add(result.change.session_id)
                hinted_deadline = min(deadline, started + 5.0)

    def run_until_inactive(self, renderer) -> None:
        """Follow an already-running session and stop when no prompt remains active.

        This preserves v77's one-shot session behavior without turning a completed
        session report into an indefinite Watch.  The caller decides whether the
        initial one-shot projection contained running work before invoking it.
        """
        cycle = self.initialize()
        if cycle.projection.active_count <= 0:
            return
        renderer.render(cycle.projection)
        try:
            while cycle.projection.active_count > 0:
                if self.live:
                    resync, hints = self._v2_wait(renderer)
                    previous_projection = self._last_projection or cycle.projection
                    renderer.render_status(self.activity_projection("Refreshing..."))
                    cycle = self.poll_once(force_resync=resync, hinted_session_ids=hints)
                    if resync:
                        self._start_event_pump()
                else:
                    self._v1_wait(renderer)
                    previous_projection = self._last_projection or cycle.projection
                    renderer.render_status(self.activity_projection("Refreshing..."))
                    cycle = self.poll_once()
                if self._needs_full_render(previous_projection, cycle.projection, cycle):
                    renderer.render(cycle.projection)
                else:
                    renderer.render_status(cycle.projection)
            renderer.finish("Prompt completed.")
        finally:
            if self._event_pump is not None:
                self._event_pump.stop()

    def run_forever(self, renderer, *, initial_cycle: WatchCycle | None = None) -> None:
        cycle = initial_cycle or self.initialize()
        renderer.render(cycle.projection)
        try:
            while True:
                if self.live:
                    resync, hints = self._v2_wait(renderer)
                    previous_projection = self._last_projection or cycle.projection
                    renderer.render_status(self.activity_projection("Refreshing..."))
                    cycle = self.poll_once(force_resync=resync, hinted_session_ids=hints)
                    if resync:
                        self._start_event_pump()
                else:
                    self._v1_wait(renderer)
                    previous_projection = self._last_projection or cycle.projection
                    renderer.render_status(self.activity_projection("Refreshing..."))
                    cycle = self.poll_once()
                if self._needs_full_render(previous_projection, cycle.projection, cycle):
                    renderer.render(cycle.projection)
                else:
                    renderer.render_status(cycle.projection)
        except KeyboardInterrupt:
            renderer.finish("Watch stopped.")
        except ValueError as exc:
            # A session-scoped Watch may naturally disappear when its root is
            # archived.  Initial invalid selection still fails before this loop.
            renderer.finish(str(exc))
        finally:
            if self._event_pump is not None:
                self._event_pump.stop()
