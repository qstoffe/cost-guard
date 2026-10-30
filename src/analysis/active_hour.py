"""Reference spending per overlap-safe observed execution hour, never billing."""
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from .duration import accumulated_duration
from .models import RootAnalysisBundle, TraceEntry
from .period_ccost import reconcile_usage
from .timezones import local_day_start_ms, local_month_start_ms
from .valuation import comparison_cost, unique_usage

HOUR_MS = 3_600_000
ROLLING_MS = 30 * 24 * HOUR_MS
USAGE_FIELDS = frozenset({"input", "cache_read", "cache_write", "output"})


@dataclass(frozen=True, slots=True)
class ActiveHour:
    scope: str
    start_ms: int | None
    end_ms: int | None
    known_ccost: Decimal
    cost_complete: bool
    duration_ms: int | None
    rate: Decimal | None
    status: str
    observed_requests: int = 0


def active_hour(scope, start_ms, end_ms, cost, duration_ms, *, complete=True,
                provisional=False, observed_requests=0):
    """Round only at display. Unknown pricing/time never becomes an exact rate."""
    rate = (cost / (Decimal(duration_ms) / HOUR_MS)
            if complete and duration_ms is not None and duration_ms > 0 else None)
    status = ("partial" if not complete else "unavailable" if rate is None else
              "provisional" if provisional else "complete")
    return ActiveHour(scope, start_ms, end_ms, cost, complete, duration_ms, rate, status, observed_requests)


def period_windows(timezone_id, now_ms):
    return (("Today", local_day_start_ms(timezone_id, now_ms=now_ms)),
            ("Month to date", local_month_start_ms(timezone_id, now_ms=now_ms)),
            ("Rolling 30 days", now_ms - ROLLING_MS))


def deduplicated_requests(entries: Iterable[TraceEntry]):
    """Canonical identity reconciliation before the existing clone deduplication.

    A step replaces its message-level fallback, just as in period/Watch history.
    Distinct requests made concurrently still each contribute cost.
    """
    values = {}
    stepped = set()
    for entry in entries:
        message = entry.message_id or (entry.parent_event_id, entry.sort_order)
        base = entry.source_instance, entry.session_id, message
        if entry.step_part_id:
            values.pop((*base, None), None)
            stepped.add(base)
        elif base in stepped:
            continue
        key = (*base, entry.step_part_id)
        values[key] = reconcile_usage(values.get(key), entry)
    return unique_usage(values.values())


def period_active_hours(bundles: Iterable[RootAnalysisBundle], valuation, *, timezone_id,
                        now_ms, source_complete=True):
    bundles = tuple(bundles)
    entries = deduplicated_requests(entry for bundle in bundles for entry in bundle.trace_entries)
    intervals = tuple((p.prompt_time_ms, p.execution_duration_ms, p.in_progress)
                      for bundle in bundles for p in bundle.prompts) + tuple(
                      (c.created_at_ms, c.duration_ms, c.in_progress)
                      for bundle in bundles for c in bundle.compactions)
    results = []
    for scope, start in period_windows(timezone_id, now_ms):
        # Cost uses the canonical request event/completion timestamp, inclusive of
        # this observation; time is clipped to [start, now). No token proration.
        selected = tuple(e for e in entries if start <= e.completed_at_ms <= now_ms)
        cost = comparison_cost(selected, valuation)
        complete = source_complete and cost.complete and all(
            USAGE_FIELDS <= set(e.tokens.known_fields) for e in selected)
        complete &= not any(p.in_progress and not p.entries and p.prompt_time_ms < now_ms
                            for bundle in bundles for p in bundle.prompts)
        clipped = []
        provisional = False
        for left, duration, running in intervals:
            if left >= now_ms:
                continue
            if left <= 0 or duration is None or duration < 0:
                # An unknown end before this window cannot prove non-overlap.
                clipped.append((max(1, start), None))
                continue
            right = min(now_ms, left + duration)
            left = max(start, left)
            if right > left:
                clipped.append((left, right - left))
                provisional |= running
        results.append(active_hour(scope, start, now_ms, cost.known_ccost,
            accumulated_duration(clipped), complete=complete, provisional=provisional,
            observed_requests=cost.observed_requests))
    return tuple(results)
