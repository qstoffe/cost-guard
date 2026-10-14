"""Process-local retention for the current local day's deduplicated CCost."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Iterable, Sequence

from src.analysis.models import TraceEntry
from src.analysis.timezones import local_day_start_ms, resolve_timezone
from src.analysis.token_mix import MIX_FIELDS
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
        self._valuation: ReferenceValuation | None = None
        self._dirty = True

    def needs_history_refresh(self, now_ms: int) -> bool:
        """Refresh historical candidates once for a new local date, not per status wake."""
        return self._history_day_start_ms != local_day_start_ms(self.timezone_id, now_ms=now_ms)

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
    ) -> AccountsQuotasProjection:
        report_service.set_now_ms(now_ms)
        projection, entries = report_service.build_watch_quota_with_today_entries(
            sessions, quota_snapshots=quota_snapshots, query_account=False,
        )
        self.observe(entries, now_ms=now_ms, historical=True)
        return projection

    def label(self, now_ms: int) -> str:
        """`Today`, or the explicit local date from midnight until 03:00 local wall time."""
        local = datetime.fromtimestamp(now_ms / 1000, tz=timezone.utc).astimezone(resolve_timezone(self.timezone_id))
        return local.date().isoformat() if local.hour < NIGHT_DATE_LABEL_END_HOUR else "Today"

    def project_from_report(self, report_service: ReportService, now_ms: int) -> ComparisonCost:
        return self.project(now_ms=now_ms, valuation=report_service.token_reference_valuation())

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

    @staticmethod
    def _reconcile(previous: TraceEntry | None, entry: TraceEntry) -> TraceEntry:
        if previous is None:
            return entry
        old = previous.tokens
        new = entry.tokens
        usage = replace(
            new,
            **{name: getattr(old, name) for name in MIX_FIELDS
               if name not in new.known_fields and name in old.known_fields},
            reasoning=old.reasoning if "output" not in new.known_fields else new.reasoning,
            known_fields=tuple(name for name in MIX_FIELDS
                               if name in new.known_fields or name in old.known_fields),
        )
        return replace(entry, tokens=usage)

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
        updated = self._reconcile(previous, entry)
        if previous != updated:
            self._entries[identity] = updated
            self._dirty = True
