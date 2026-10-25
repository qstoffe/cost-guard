"""Process-local retention for the current local day's deduplicated CCost."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Iterable, Sequence

from src.analysis.models import TraceEntry
from src.analysis.timezones import local_day_start_ms, resolve_timezone
from src.analysis.period_ccost import reconcile_usage
from src.analysis.valuation import ComparisonCost, comparison_cost, unique_usage
from src.domain.ccost import ReferenceValuation

if TYPE_CHECKING:
    from src.domain import AccountSnapshot, NormalizedSession
    from src.reports.models import AccountsQuotasProjection
    from src.reports.service import ReportService

BaseIdentity = tuple[str | None, str, str]
RequestIdentity = tuple[str | None, str, str, str | None]
NIGHT_DATE_LABEL_END_HOUR = 3


class WatchTodayCCost:
    """Retain only current-local-day requests; absent source rows never erase them."""

    def __init__(self, timezone_id: str) -> None:
        self.timezone_id = timezone_id
        self.reset()

    def reset(self) -> None:
        """Start a fresh process observation after an abandoned initialization."""
        self._day_start_ms: int | None = None
        self._history_day_start_ms: int | None = None
        self._entries: dict[RequestIdentity, TraceEntry] = {}
        self._stepped: set[BaseIdentity] = set()
        self._total = ComparisonCost()
        self._published: ComparisonCost | None = None
        self._valuation: ReferenceValuation | None = None
        self._dirty = True
        self._pending_history: tuple[NormalizedSession, ...] = ()
        self._scheduled_day_start_ms: int | None = None
        self._pending_catalog: tuple[NormalizedSession, ...] | None = None
        self._active_history_roots: tuple[str, ...] = ()
        self._fresh_history_roots: tuple[str, ...] = ()
        self._live_history_roots: tuple[str, ...] = ()

    def needs_history_refresh(self, now_ms: int) -> bool:
        """Refresh historical candidates once for a new local date, not per status wake."""
        return self._history_day_start_ms != local_day_start_ms(self.timezone_id, now_ms=now_ms)

    def display_pending(self, now_ms: int) -> bool:
        self._rollover(local_day_start_ms(self.timezone_id, now_ms=now_ms))
        return self._published is None and self.needs_history_refresh(now_ms)

    def refresh_due(self, now_ms: int, last_refresh_ms: int, immediate: bool) -> bool:
        """Refresh on explicit changes/date rollover or the existing five-minute cadence."""
        return (immediate or self.needs_history_refresh(now_ms) or not last_refresh_ms
                or now_ms - last_refresh_ms >= 300_000)

    def refresh_available_history(
        self,
        report_service: ReportService,
        sessions: Sequence[NormalizedSession],
        quota_snapshots: Sequence[AccountSnapshot],
        now_ms: int,
        *, active_root_ids: Sequence[str] = (), fresh_root_ids: Sequence[str] = (), live_root_ids: Sequence[str] = (),
    ) -> AccountsQuotasProjection:
        self.schedule_history(report_service, sessions, now_ms, active_root_ids=active_root_ids,
                              fresh_root_ids=fresh_root_ids, live_root_ids=live_root_ids)
        while self._pending_history:
            self.advance_history(report_service, now_ms)
        return report_service.project_watch_accounts(quota_snapshots)[0]

    @property
    def history_pending(self) -> bool:
        return self._pending_catalog is not None or bool(self._pending_history)

    def defer_history(self, sessions: Sequence[NormalizedSession], now_ms: int, *,
                      active_root_ids: Sequence[str] = (), fresh_root_ids: Sequence[str] = (), live_root_ids: Sequence[str] = ()) -> None:
        """Even daily revision acquisition waits until the essential dashboard is drawn."""
        day = local_day_start_ms(self.timezone_id, now_ms=now_ms)
        self._rollover(day)
        if day == self._scheduled_day_start_ms and self._pending_history:
            # Polls must not restart a long enrichment plan at its active roots
            # forever. Reconcile removals/metadata, then finish the finite plan;
            # new activity is observed live and the next plan sees new roots.
            current = {root.session_id: root for root in sessions if root.parent_session_id is None}
            self._pending_history = tuple(current[root.session_id] for root in self._pending_history if root.session_id in current)
            if self._pending_history:
                return
        self._pending_catalog = tuple(sessions)
        self._pending_history = ()
        self._scheduled_day_start_ms = day
        self._history_day_start_ms = None
        self._active_history_roots = tuple(active_root_ids)
        self._fresh_history_roots = tuple(fresh_root_ids)
        self._live_history_roots = tuple(live_root_ids)

    def schedule_history(self, service: ReportService, sessions: Sequence[NormalizedSession], now_ms: int, *,
                         active_root_ids: Sequence[str] = (), fresh_root_ids: Sequence[str] = (), live_root_ids: Sequence[str] = ()) -> None:
        self._pending_catalog = None
        service.set_now_ms(now_ms)
        day = local_day_start_ms(self.timezone_id, now_ms=now_ms)
        self._rollover(day)
        self._active_history_roots = tuple(active_root_ids)
        self._fresh_history_roots = tuple(fresh_root_ids)
        self._live_history_roots = tuple(live_root_ids)
        self._pending_history = service.watch_history_candidates(sessions, active_root_ids=active_root_ids,
                                                                 fresh_root_ids=fresh_root_ids, live_root_ids=live_root_ids)
        self._scheduled_day_start_ms = day
        if self._pending_history:
            self._history_day_start_ms = None
        else:
            service.publish_watch_history()
            self.observe((), now_ms=now_ms, historical=True)

    def advance_history(self, service: ReportService, now_ms: int, *, batch_size: int = 4) -> bool:
        """Main-thread enrichment slice: no worker races or unbounded task queue.

        A new local date cancels the stale plan; the next source poll discovers
        its candidates. Publication is pending until the entire plan completes.
        """
        day = local_day_start_ms(self.timezone_id, now_ms=now_ms)
        if day != self._scheduled_day_start_ms:
            self._pending_history = ()
            self._pending_catalog = None
            self._rollover(day)
            return False
        if self._pending_catalog is not None:
            self.schedule_history(service, self._pending_catalog, now_ms, active_root_ids=self._active_history_roots,
                                  fresh_root_ids=self._fresh_history_roots, live_root_ids=self._live_history_roots)
        if not self._pending_history:
            return True
        service.set_now_ms(now_ms)
        selected = self._pending_history[:batch_size]
        entries = service.watch_history_batch(selected)
        self._pending_history = self._pending_history[len(selected):]
        if not self._pending_history:
            service.publish_watch_history()
        self.observe(entries, now_ms=now_ms, historical=not self._pending_history)
        return True

    def label(self, now_ms: int) -> str:
        """`Today`, or the explicit local date from midnight until 03:00 local wall time."""
        local = datetime.fromtimestamp(now_ms / 1000, tz=timezone.utc).astimezone(resolve_timezone(self.timezone_id))
        return local.date().isoformat() if local.hour < NIGHT_DATE_LABEL_END_HOUR else "Today"

    def project_from_report(self, report_service: ReportService, now_ms: int) -> ComparisonCost:
        self._rollover(local_day_start_ms(self.timezone_id, now_ms=now_ms))
        if self.needs_history_refresh(now_ms):
            # A refresh builds privately; only the first load has no published value.
            return self._published or ComparisonCost()
        self._published = self.project(now_ms=now_ms, valuation=report_service.token_reference_valuation())
        return self._published

    def observe(self, entries: Iterable[TraceEntry], *, now_ms: int, historical: bool = False) -> None:
        day_start_ms = local_day_start_ms(self.timezone_id, now_ms=now_ms)
        self._rollover(day_start_ms)
        for entry in entries:
            self._observe_entry(entry, day_start_ms, now_ms)
        if historical:
            self._history_day_start_ms = day_start_ms

    def project(self, *, now_ms: int, valuation: ReferenceValuation) -> ComparisonCost:
        self._rollover(local_day_start_ms(self.timezone_id, now_ms=now_ms))
        if self._dirty or valuation != self._valuation:
            self._total = comparison_cost(unique_usage(self._entries.values()), valuation)
            self._valuation = valuation
            self._dirty = False
        return self._total

    def _rollover(self, day_start_ms: int) -> None:
        if self._day_start_ms == day_start_ms:
            return
        self._day_start_ms = day_start_ms
        self._history_day_start_ms = None
        self._published = None
        self._entries.clear()
        self._stepped.clear()
        self._dirty = True

    @staticmethod
    def _base_identity(entry: TraceEntry) -> BaseIdentity:
        message = entry.message_id or (
            f"entry:{entry.parent_event_id}:{entry.sort_order}:{entry.model.provider}:{entry.model.model}"
        )
        return entry.source_instance, entry.session_id, message

    def _identity(self, entry: TraceEntry) -> RequestIdentity:
        return (*self._base_identity(entry), entry.step_part_id)

    def _remove(self, identity: RequestIdentity) -> None:
        if identity in self._entries:
            del self._entries[identity]
            self._dirty = True

    def _observe_entry(self, entry: TraceEntry, day_start_ms: int, now_ms: int) -> None:
        identity = self._identity(entry)
        base = self._base_identity(entry)
        if entry.step_part_id:
            self._remove((*base, None))
            self._stepped.add(base)
        elif base in self._stepped:
            self._remove(identity)
            return
        if not day_start_ms <= entry.completed_at_ms <= now_ms:
            self._remove(identity)
            return
        previous = self._entries.get(identity)
        updated = reconcile_usage(previous, entry)
        if previous != updated:
            self._entries[identity] = updated
            self._dirty = True
