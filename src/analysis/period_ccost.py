"""Provider/account-neutral period valuation over canonical deduplicated requests."""
from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass, replace
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


def history_start(accounts: Iterable[AccountSnapshot], today_start_ms: int, now_ms: int) -> int:
    return min([today_start_ms] + [window[0] for account in accounts for component in account.quotas
                                 if (window := quota_window(component, now_ms)) is not None])


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
