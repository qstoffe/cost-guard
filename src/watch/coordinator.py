"""Coordinator-owned Watch lifecycle over abstract Session Sources."""
from __future__ import annotations

from dataclasses import dataclass, replace
import math
import time
from typing import Callable, Mapping, Sequence

from src.domain import NormalizedSession, SessionSnapshot
from src.domain.session_tree import root_activity
from src.reports import ReportService, SessionPromptBlock
from src.sources.errors import SourceError, SourceUnavailableError
from src.sources.selection import SourceSelection
from src.runtime_errors import check_pending

from src.sources.connectivity_events import record as record_source_recovery
from .observation_diagnostics import record_scan, record_source_error
from .model_discovery import WatchModelDiscovery
from .models import WatchProjection, WatchRow, WatchSessionSubtotal
from .observers import CatalogObservation, LiveEventPump, observe_catalog
from .redraw import needs_full_render, transient_signature, visible_signature
from .session_retention import select_earlier_sessions
from .skill_registry import active_skill_origins
from .tracker import WatchRowTracker
from .token_mix import WatchTokenMix
from .today_ccost import WatchTodayCCost
from .account_refresh import WatchAccountRefresh

ClockMs = Callable[[], int]
Sleep = Callable[[float], None]
RESUME_GAP_MS = 90_000
INITIAL_ROOT_SAMPLE = 20
SOURCE_RETRY_SECONDS = 5.0
# Unreadable (not merely unreachable) data gets about a minute to settle before
# Watch reports it as a terminal failure instead of retrying forever.
SOURCE_UNREADABLE_RETRIES = 12


class WatchedSessionEnded(ValueError):
    """The selected session/root disappeared or was archived, not a runtime bug."""


def _clock_ms() -> int:
    return int(time.time() * 1000)


def source_failure_kind(error: SourceError) -> str | None:
    """Normalized recovery category; None means the selected source contract is unsupported."""
    if error.terminal:
        return None
    if isinstance(error, SourceUnavailableError):
        return "unavailable" if error.watch_retryable or error.code.value == "unknown_source_failure" else None
    return "unreadable"


@dataclass(frozen=True, slots=True)
class WatchCycle:
    projection: WatchProjection
    changed_roots: tuple[str, ...]
    hydrated_roots: tuple[str, ...]
    resynced: bool = False
    recovered: bool = False


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
        started_at_ms: int | None = None,
        sleep: Sleep = time.sleep,
        monotonic: Callable[[], float] | None = None,
        record_observations: bool = True,
    ) -> None:
        self.selection = selection
        # Diagnostics' headless smoke must not appear as a user Watch observation.
        self.record_observations = record_observations
        self.source = selection.source
        if hasattr(self.source, "read_recovery"):
            self.source.read_recovery = None
        self.report_service = report_service
        self.config = config
        self.session_id = session_id
        self.clock_ms = clock_ms
        self.sleep = sleep
        self._monotonic_clock = monotonic
        self.started_at_ms = int(clock_ms() if started_at_ms is None else started_at_ms)
        self.token_mix = WatchTokenMix(self.started_at_ms)
        self.today_ccost = WatchTodayCCost(report_service.timezone_id)
        raw_interval = config.get("sessionWatchIntervalSeconds", "auto")
        self.auto_interval = isinstance(raw_interval, str) and raw_interval.strip().lower() == "auto"
        self.interval_seconds = 5 if self.auto_interval else max(5, int(raw_interval))
        self.idle_interval_seconds = self.interval_seconds if self.auto_interval else max(30, self.interval_seconds * 3)
        self._refresh_ema_seconds: float | None = None
        self.max_rows = max(1, int(config.get("watchDashboardMaxRows", 12)))
        self.earlier_sessions = max(0, int(config.get("watchStartupEarlierSessions", 2)))
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
        self._skill_origins_by_root: dict[str, dict[str, Mapping[str, str]]] = {}
        self.quota = None
        self.accounts = WatchAccountRefresh(report_service, clock_ms=clock_ms, monotonic=self._monotonic)
        self._last_cycle_end_ms: int | None = None
        self._event_pump: LiveEventPump | None = None
        self._last_quota_refresh_ms = 0
        self._last_projection: WatchProjection | None = None
        # What the dashboard last fully drew; _last_projection may already be newer.
        self._rendered_projection: WatchProjection | None = None
        # Ephemeral lifecycle evidence for this process only; never persisted.
        self.source_recoveries = 0
        self.last_source_recovery_kind = ""
        self._observer_error = ""
        self.model_discovery = WatchModelDiscovery(report_service)
        self._resume_pending = False
        self._resume_recovery_deadline_ms = 0
        self._closed = False
        self.startup_quiet_roots = 0

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
        self.accounts.resume()
        self._resume_pending = True
        self._resume_recovery_deadline_ms = now_ms + 180_000
        return True

    def _wait_delay_seconds(self, active_count: int) -> float:
        return self.accounts.wait_delay(float(self._delay_seconds(active_count)))

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
                raise WatchedSessionEnded(f"OpenCode session '{self.session_id}' was not found or is archived.")
            return observation.roots
        activity = root_activity(observation.sessions, observation.root_by_session)
        return tuple(sorted(
            observation.roots,
            key=lambda item: (activity.get(item.session_id, item.updated_at_ms), item.session_id),
            reverse=True,
        ))

    def _hydrate(
        self, roots: Sequence[NormalizedSession], *, now_ms: int, force_fresh_ids: Sequence[str] = ()
    ) -> tuple[str, ...]:
        pending = []
        force_fresh = set(force_fresh_ids)
        self.report_service.set_now_ms(now_ms)
        for root in roots:
            self.report_service.invalidate_roots((root.session_id,))
            block, snapshot, bundle = self.report_service.build_watch_root(
                root, force_fresh=root.session_id in force_fresh
            )
            pending.append((root.session_id, block, snapshot, bundle))
        for root_id, block, snapshot, bundle in pending:
            self.blocks[root_id] = block
            self.snapshots[root_id] = snapshot
            self._skill_origins_by_root[root_id] = active_skill_origins(self.source, snapshot, block)
            self.token_mix.observe(snapshot, bundle)
            self.today_ccost.observe(bundle.trace_entries, now_ms=now_ms)
        return tuple(root_id for root_id, *_ in pending)

    def _refresh_quota(self, observation: CatalogObservation, *, now_ms: int, force: bool = False) -> None:
        # Source changes/5m refresh local usage; account requests keep their cadence.
        account_changed = self.accounts.refresh(now_ms=now_ms)
        if not self.today_ccost.refresh_due(now_ms, self._last_quota_refresh_ms, force or account_changed):
            return
        self.quota = self.today_ccost.refresh_available_history(
            self.report_service, observation.sessions, self.accounts.snapshots, now_ms
        )
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

    _visible_signature = staticmethod(visible_signature)
    _transient_signature = staticmethod(transient_signature)

    @staticmethod
    def _needs_full_render(previous: WatchProjection, current: WatchProjection, cycle: WatchCycle) -> bool:
        return needs_full_render(previous, current,
                                 source_changed=bool(cycle.changed_roots or cycle.resynced or cycle.recovered))

    def _render(self, renderer, projection: WatchProjection) -> None:
        """Draw the full dashboard and remember exactly what is now on screen."""
        renderer.render(projection)
        self._rendered_projection = projection

    def _token_valuation(self):
        return self.report_service.token_category_valuation()

    def _projection(self, *, now_ms: int, status: str = "", status_active: bool = False,
                    scanned: bool = False) -> WatchProjection:
        check_pending()
        rows = self.tracker.project(
            self.blocks, self.snapshots, now_ms=now_ms, skill_origins_by_root=self._skill_origins_by_root
        )
        active = sum(1 for row in rows if row.prompt.in_progress)
        session_warnings: dict[str, str] = {}
        session_subtotals: dict[str, WatchSessionSubtotal] = {}
        for row in rows:
            # Sum the final retained/capped rows, not this Watch run's requests.
            previous = session_subtotals.get(row.session_id, WatchSessionSubtotal())
            session_subtotals[row.session_id] = WatchSessionSubtotal(
                ccost=previous.ccost + row.prompt.ccost,
                unresolved_cost=previous.unresolved_cost or row.prompt.unresolved_cost,
            )
            warning = row.next_context_warning
            if warning:
                session_warnings[row.session_id] = warning
        if not status:
            delay = int(math.ceil(self._wait_delay_seconds(active)))
            status = self._steady_status(active, delay, rows)
        recent_model_notice, recent_model_highlight_spans = self.model_discovery.notice_details(now_ms)
        projection = WatchProjection(
            title=(f"Cost Guard Watch - {self.session_id}" if self.session_id else "Cost Guard Watch"),
            source_label=self.selection.selected.upper(),
            rows=rows,
            source_warnings=tuple(self.selection.warnings),
            quota=self.quota,
            quota_stale=self.accounts.stale,
            quota_recovering_accounts=self.accounts.recovering_keys,
            active_count=active,
            status=self._observer_error or status,
            status_active=status_active,
            now_ms=now_ms,
            watch_started_at_ms=self.started_at_ms,
            session_warnings=session_warnings,
            recent_model_notice=recent_model_notice,
            recent_model_notice_highlight_spans=recent_model_highlight_spans,
            recent_promotion_notices=self.report_service.recent_promotion_notice_texts(),
            token_mix=self.token_mix.project(valuation := self._token_valuation()),
            run_total=self.token_mix.project_total(valuation),
            today_total=self.today_ccost.project_from_report(self.report_service, now_ms),
            today_label=self.today_ccost.label(now_ms),
            session_subtotals=session_subtotals,
        )
        self._last_projection = projection
        if scanned and self.observation is not None and self.record_observations:
            record_scan(self.selection.selected, self.observation, self.blocks, rows, self.started_at_ms,
                        startup_quiet_roots=self.startup_quiet_roots)
        return projection

    def initialize(self) -> WatchCycle:
        refresh_started = time.monotonic()
        now_ms = int(self.clock_ms())
        self.report_service.set_now_ms(now_ms)
        observation = observe_catalog(self.source, session_id=self.session_id)
        roots = self._selected_roots(observation)
        hydrated = (self._hydrate(roots, now_ms=now_ms) if self.session_id is not None
                    else self._hydrate_startup(roots, now_ms=now_ms))
        self.observation = observation
        self._record_refresh_duration(time.monotonic() - refresh_started)
        self.quota = self.today_ccost.refresh_available_history(
            self.report_service, observation.sessions, self.accounts.snapshots, now_ms
        )
        self.accounts.begin(now_ms)
        self.model_discovery.refresh(now_ms)
        self._refresh_quota(observation, now_ms=now_ms, force=True)
        if self.live:
            self._start_event_pump()
        completed_ms = int(self.clock_ms())
        self._last_cycle_end_ms = completed_ms
        return WatchCycle(
            self._projection(now_ms=completed_ms, scanned=True),
            tuple(root.session_id for root in roots),
            hydrated,
            resynced=True,
        )

    def _hydrate_startup(self, roots: Sequence[NormalizedSession], *, now_ms: int) -> tuple[str, ...]:
        """Bounded startup hydration plus the one-time Earlier baseline (actual prompt starts, never running).

        Metadata only bounds the sample; quiet cached roots hydrate only when chosen as Earlier.
        """
        sample = roots[:max(INITIAL_ROOT_SAMPLE, self.earlier_sessions)]
        quiet: dict[str, int] = {}
        for root in sample:
            latest = self.report_service.watch_root_latest_prompt_ms(root)
            if latest is not None and latest < self.started_at_ms:
                quiet[root.session_id] = latest
        hydrated = self._hydrate([root for root in sample if root.session_id not in quiet], now_ms=now_ms)
        latest_ms = dict(quiet)
        for root_id in hydrated:
            prompts = self.blocks[root_id].rows
            if prompts and all(not row.in_progress and row.at_ms < self.started_at_ms for row in prompts):
                latest_ms[root_id] = max(row.at_ms for row in prompts)
        earlier = select_earlier_sessions(latest_ms, self.earlier_sessions)
        hydrated += self._hydrate([root for root in sample if root.session_id in quiet and root.session_id in earlier],
                                  now_ms=now_ms)
        self.tracker.set_earlier_sessions(earlier)
        self.startup_quiet_roots = sum(1 for root_id in quiet if root_id not in earlier)
        return hydrated

    def initialize_with_recovery(self, renderer) -> WatchCycle:
        """Recover unfinished startup with the same selected-source lifecycle."""
        try:
            return self.initialize()
        except SourceError as error:
            self._discard_initialization()
            return self._recover_source(renderer, error, initializing=True)

    def _discard_initialization(self) -> None:
        self.observation = None
        self.blocks.clear()
        self.snapshots.clear()
        self._skill_origins_by_root.clear()
        self.token_mix = WatchTokenMix(self.started_at_ms)
        self.today_ccost.reset()
        self.report_service.invalidate_source_observations()

    def _start_event_pump(self) -> None:
        if not self.live:
            return
        if self._event_pump is not None:
            self._event_pump.stop()
        self._event_pump = LiveEventPump(self.source)  # type: ignore[arg-type]
        self._event_pump.start()

    def _changed_roots(self, old: CatalogObservation | None, observation: CatalogObservation, *,
                       force_resync: bool, hinted_session_ids: Sequence[str]) -> set[str]:
        """Roots to re-read: changed/removed revisions, hinted roots and, on resync, hydrated roots.

        A resync distrusts lost hints, so every already-hydrated root is re-read
        authoritatively. Never-hydrated roots stay gated by their fresh catalog
        revision exactly as at startup instead of hydrating the whole history.
        """
        old_revisions = {} if old is None else old.revisions
        changed = {root_id for root_id, revision in observation.revisions.items()
                   if old_revisions.get(root_id) != revision}
        changed.update(root_id for root_id in old_revisions if root_id not in observation.revisions)
        if force_resync:
            changed.update(root_id for root_id in self.blocks if root_id in observation.revisions)
        for session_id in hinted_session_ids:
            root_id = observation.root_by_session.get(session_id)
            if root_id:
                changed.add(root_id)
        return changed

    def poll_once(self, *, force_resync: bool = False, hinted_session_ids: Sequence[str] = ()) -> WatchCycle:
        refresh_started = time.monotonic()
        now_ms = int(self.clock_ms())
        self._detect_quota_resume(now_ms)
        self.model_discovery.refresh(now_ms, resumed=self._resume_pending)
        self._resume_pending = False
        old = self.observation
        observation = observe_catalog(self.source, session_id=self.session_id)
        roots = self._selected_roots(observation)
        changed = self._changed_roots(old, observation, force_resync=force_resync, hinted_session_ids=hinted_session_ids)
        current_roots = {item.session_id: item for item in roots}
        active_roots = {
            root_id for root_id, block in self.blocks.items()
            if any(row.in_progress for row in block.rows)
        }
        removed = set(self.blocks) - set(current_roots)

        hydrate_ids = changed | active_roots
        hydrate = [current_roots[root_id] for root_id in hydrate_ids if root_id in current_roots]
        hydrated = self._hydrate(
            hydrate, now_ms=now_ms, force_fresh_ids=active_roots
        ) if hydrate else ()
        for root_id in removed:
            self.blocks.pop(root_id, None)
            self.snapshots.pop(root_id, None)
            self._skill_origins_by_root.pop(root_id, None)
            self.report_service.invalidate_roots((root_id,))

        self.observation = observation
        self._record_refresh_duration(time.monotonic() - refresh_started)
        if changed:
            self._refresh_quota(observation, now_ms=now_ms, force=True)
        else:
            self._refresh_quota(observation, now_ms=now_ms, force=False)
        completed_ms = int(self.clock_ms())
        self._last_cycle_end_ms = completed_ms
        return WatchCycle(
            self._projection(now_ms=completed_ms, scanned=True),
            tuple(sorted(changed)),
            hydrated,
            resynced=force_resync,
        )

    def status_projection(self, *, seconds_until_check: int | None = None) -> WatchProjection:
        now_ms = int(self.clock_ms())
        self.report_service.set_now_ms(now_ms)
        # The cadence's one-second main-thread wake publishes individual provider
        # completions without waiting for source hydration or the entire batch.
        if not self._closed and self.observation is not None:
            self._refresh_quota(self.observation, now_ms=now_ms)
        active = 0 if self._last_projection is None else self._last_projection.active_count
        status = "Watching" if seconds_until_check is None else self._steady_status(active, seconds_until_check)
        return self._projection(now_ms=now_ms, status=status, status_active=active > 0)

    def activity_projection(self, status: str = "Refreshing...") -> WatchProjection:
        now_ms = int(self.clock_ms())
        self.report_service.set_now_ms(now_ms)
        return self._projection(now_ms=now_ms, status=status, status_active=True)

    def _v1_wait(self, renderer) -> None:
        projection = self._last_projection or self._projection(now_ms=self.clock_ms(), status="Watching")
        delay = self._wait_delay_seconds(projection.active_count)
        deadline = self._monotonic() + delay
        while True:
            if self._detect_quota_resume(int(self.clock_ms())):
                return
            remaining = deadline - self._monotonic()
            if remaining <= 0:
                return
            # Presentation-only wake: expire markers/notices and publish accepted
            # account results without touching OpenCode or waiting for a source poll.
            self._render_wake(renderer, self.status_projection(seconds_until_check=int(remaining + 0.999)), projection)
            self.sleep(min(1.0, remaining))

    def _render_wake(self, renderer, projection: WatchProjection, caller_frame: WatchProjection) -> None:
        """Redraw when on-screen content changed, else repaint the status (``caller_frame``: drawn by the caller)."""
        rendered = self._rendered_projection or caller_frame
        if self._transient_signature(projection) != self._transient_signature(rendered):
            self._render(renderer, projection)
        else:
            renderer.render_status(projection)

    def _v2_wait(self, renderer) -> tuple[bool, tuple[str, ...]]:
        """Wait one stable v77-style cadence while buffering V2 change hints."""
        projection = self._last_projection or self._projection(now_ms=self.clock_ms(), status="Watching")
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
            self._render_wake(renderer, self.status_projection(seconds_until_check=int(remaining + 0.999)), projection)
            pump = self._event_pump
            result = pump.get(min(1.0, remaining)) if pump is not None else None
            if result is None:
                continue
            if result.resync_required:
                if result.software_fault:
                    self._observer_error = result.error
                    renderer.render_status(self.activity_projection(result.error))
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
        try:
            cycle = self.initialize_with_recovery(renderer)
            if cycle.projection.active_count <= 0:
                return
            self._render(renderer, cycle.projection)
            while cycle.projection.active_count > 0:
                cycle = self._advance(renderer, cycle)
            renderer.finish("Prompt completed.")
        finally:
            self.close()

    def _advance(self, renderer, cycle: WatchCycle) -> WatchCycle:
        """Wait one cadence, poll the selected source and render the result."""
        if self.live:
            resync, hints = self._v2_wait(renderer)
        else:
            self._v1_wait(renderer)
            resync, hints = False, ()
        # Compare with what is actually on screen: wakes may already have
        # advanced _last_projection (for example with new account results).
        previous_projection = self._rendered_projection or cycle.projection
        renderer.render_status(self.activity_projection("Refreshing..."))
        try:
            cycle = self.poll_once(force_resync=resync, hinted_session_ids=hints)
        except SourceError as exc:
            cycle = self._recover_source(renderer, exc)
        else:
            if resync:
                self._observer_error = ""
                self._start_event_pump()
        if self._needs_full_render(previous_projection, cycle.projection, cycle):
            self._render(renderer, cycle.projection)
        else:
            renderer.render_status(cycle.projection)
        return cycle

    def _recover_source(self, renderer, error: SourceError, *, initializing: bool = False) -> WatchCycle:
        """Keep Watch alive across transient failures of the already-selected source.

        The last dashboard stays visible. Recovery retries only this selection
        (no generation switch, subprocess or account-quota refresh); V2 resumes
        only from a fresh authoritative snapshot. Unsupported schemas, and
        unreadable data that does not settle, still end Watch visibly.
        """
        if self._event_pump is not None:
            self._event_pump.stop()
            self._event_pump = None
        record_source_error(self.selection.selected, source_failure_kind(error) or "unsupported", self.source)
        attempts = unreadable = 0
        degraded_at = self._monotonic()
        while True:
            kind = source_failure_kind(error)
            unreadable = unreadable + 1 if kind == "unreadable" else 0
            if kind is None or unreadable > (SOURCE_UNREADABLE_RETRIES * 2 if self.live and int(self.clock_ms()) <= self._resume_recovery_deadline_ms else SOURCE_UNREADABLE_RETRIES):
                record_source_recovery(self.selection.selected, "failed", kind or "unsupported",
                                       **error.evidence(), attempts=attempts,
                                       duration_ms=int((self._monotonic() - degraded_at) * 1000))
                raise error
            if not attempts:
                self.source_recoveries += 1
                record_source_recovery(self.selection.selected, "retrying", kind, **error.evidence())
            attempts += 1
            self.last_source_recovery_kind = kind
            status = f"OpenCode {self.selection.selected.upper()} source {kind} · retrying every {SOURCE_RETRY_SECONDS:g}s"
            if initializing:
                renderer.render_startup_status(status, active=True)
            else:
                projection = self._last_projection or self.activity_projection(status)
                projection = replace(projection, status=status, status_active=True)
                if attempts == 1:
                    self._render(renderer, projection)
                else:
                    renderer.render_status(projection)
            self.sleep(SOURCE_RETRY_SECONDS)
            # Outage waits are observed time, not a suspend gap that would arm
            # account-quota resume retries.
            self._last_cycle_end_ms = int(self.clock_ms())
            try:
                refresh = getattr(self.source, "refresh_connection", None)
                if callable(refresh):
                    refresh()
                if initializing:
                    self.report_service.invalidate_source_observations()
                cycle = self.initialize() if initializing else self.poll_once(force_resync=self.live)
            except SourceError as exc:
                if initializing:
                    self._discard_initialization()
                error = exc
                continue
            if self.live and not initializing:
                self._start_event_pump()
            record_source_recovery(self.selection.selected, "recovered", kind, **error.evidence(),
                                   attempts=attempts, duration_ms=int((self._monotonic() - degraded_at) * 1000))
            return replace(cycle, recovered=True)

    def run_forever(self, renderer, *, initial_cycle: WatchCycle | None = None) -> None:
        try:
            cycle = initial_cycle or self.initialize_with_recovery(renderer)
            self._render(renderer, cycle.projection)
            while True:
                cycle = self._advance(renderer, cycle)
        except KeyboardInterrupt:
            check_pending()
            renderer.finish("Watch stopped.")
        except SourceError:
            # Bootstrap prints the normalized error and exits non-zero.
            renderer.finish(f"Watch stopped: OpenCode {self.selection.selected.upper()} source failed.")
            raise
        except WatchedSessionEnded as exc:
            # A session-scoped Watch may naturally disappear when its root is
            # archived.  Initial invalid selection still fails before this loop.
            if self.session_id is None:
                raise
            renderer.finish(str(exc))
        finally:
            self.close()

    def close(self) -> None:
        self._closed = True
        self.accounts.close()
        if self._event_pump is not None:
            self._event_pump.stop()
