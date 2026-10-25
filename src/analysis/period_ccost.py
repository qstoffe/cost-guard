"""Provider/account-neutral period valuation over canonical deduplicated requests."""
from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable

from src.domain import AccountSnapshot, QuotaComponent
from src.domain.ccost import ReferenceValuation
from src.pricing.catalog import canonical_model_name
from .models import TraceEntry
from .valuation import ComparisonCost, comparison_cost, unique_usage
from .token_mix import MIX_FIELDS


def reconcile_usage(previous: TraceEntry | None, entry: TraceEntry) -> TraceEntry:
    """Retain known telemetry through incomplete observations; accept real corrections."""
    if previous is None:
        return entry
    old, new = previous.tokens, entry.tokens
    usage = replace(new, **{name: getattr(old, name) for name in MIX_FIELDS
                            if name not in new.known_fields and name in old.known_fields},
                    reasoning=old.reasoning if "output" not in new.known_fields else new.reasoning,
                    known_fields=tuple(name for name in MIX_FIELDS if name in new.known_fields or name in old.known_fields))
    return replace(entry, tokens=usage)


def usage_provider(provider: str) -> str:
    # These are supported integration aliases, not model publisher aliases.
    return {"codex": "openai", "openai-codex": "openai",
            "github-copilot-enterprise": "github-copilot"}.get(provider, provider)


def quota_window(component: QuotaComponent, now_ms: int) -> tuple[int, int, str] | None:
    duration = component.duration_seconds
    if not duration or duration <= 0 or (component.scope == "model" and not component.model_id):
        return None
    if component.reset_at_ms and component.reset_at_ms - duration * 1000 <= now_ms < component.reset_at_ms:
        return component.reset_at_ms - duration * 1000, now_ms + 1, "native reset window"
    if component.window_active is False and not component.reset_at_ms:
        return now_ms - duration * 1000, now_ms + 1, "observed trailing lookback; not a certified quota interval"
    return None


def monthly_quota_window(component: QuotaComponent, now_ms: int) -> tuple[int, int] | None:
    """Support native fixed UTC calendar months only; never guess from a percentage."""
    if (component.period != "fixed" or component.scope != "account" or component.model_id
            or component.window_active is False or component.origin != "provider_native"
            or component.label.casefold() not in {"monthly", "month"} or not component.reset_at_ms):
        return None
    try:
        end = datetime.fromtimestamp(component.reset_at_ms / 1000, timezone.utc)
        if (end.day, end.hour, end.minute, end.second, end.microsecond) != (1, 0, 0, 0, 0):
            return None
        start = end.replace(year=end.year - 1, month=12) if end.month == 1 else end.replace(month=end.month - 1)
        start_ms = int(start.timestamp() * 1000)
    except (ValueError, OverflowError, OSError):
        return None
    return (start_ms, now_ms + 1) if start_ms <= now_ms < component.reset_at_ms else None


def history_start(accounts: Iterable[AccountSnapshot], today_start_ms: int, now_ms: int, *,
                  include_copilot_month: bool = False) -> int:
    starts = [today_start_ms]
    for account in accounts:
        for component in account.quotas:
            if (window := quota_window(component, now_ms)) is not None:
                starts.append(window[0])
            if include_copilot_month and usage_provider(account.ref.provider_id) == "github-copilot":
                if (window := monthly_quota_window(component, now_ms)) is not None:
                    starts.append(window[0])
    return min(starts)


@dataclass
class _Series:
    times: list[int]
    totals: list[Decimal]
    priced: list[int]

    def between(self, start: int, end: int) -> ComparisonCost:
        left, right = bisect_left(self.times, start), bisect_left(self.times, end)
        return ComparisonCost(self.totals[right] - self.totals[left], right - left,
                              self.priced[right] - self.priced[left])


class PeriodCCostIndex:
    """Value once per history publication; moving windows query prefix sums, no rescans."""

    def __init__(self, entries: Iterable[TraceEntry], valuation: ReferenceValuation) -> None:
        self._series: dict[tuple, _Series] = {}
        for entry in unique_usage(entries):
            provider = usage_provider(entry.model.provider)
            account = entry.account_ref.key if entry.account_ref else None
            value = comparison_cost((entry,), valuation)
            for identity in ("provider", account):
                for model in (None, canonical_model_name(entry.model.model)):
                    key = provider, identity, model
                    series = self._series.setdefault(key, _Series([], [Decimal(0)], [0]))
                    series.times.append(entry.completed_at_ms)
                    series.totals.append(series.totals[-1] + value.known_ccost)
                    series.priced.append(series.priced[-1] + value.priced_requests)

    def cost(self, provider: str, identity: object, start: int, end: int,
             model_id: str | None = None) -> ComparisonCost:
        key = usage_provider(provider), identity, canonical_model_name(model_id) if model_id else None
        series = self._series.get(key)
        return series.between(start, end) if series else ComparisonCost()
