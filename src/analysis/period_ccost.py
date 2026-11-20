"""Provider/account-neutral period valuation over canonical deduplicated requests."""
from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable

from src.domain import AccountSnapshot, QuotaComponent, CostDisposition
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


def account_usage_routes(account: AccountSnapshot, *, proven: bool = False) -> tuple[str, ...]:
    """Reference compatibility only; current login never proves historical billing.

    Claude Agent is an SDK route, not an Anthropic publisher alias. Its unassigned
    reference subtotal is eligible only for discovered first-party subscriptions;
    the caller still requires a unique compatible account and marks it estimated.
    """
    provider = usage_provider(account.ref.provider_id)
    evidence = account.observations
    subscription = (provider == 'claude-code' and evidence.get('account_kind') == 'subscription'
        and evidence.get('backend_status') == 'first_party' and evidence.get('auth_status') == 'authenticated')
    return (provider, 'claude-agent') if subscription or proven and provider == 'claude-code' else (provider,)


def combined_cost(values: Iterable[ComparisonCost]) -> ComparisonCost:
    values = tuple(values)
    return ComparisonCost(sum((v.known_ccost for v in values), Decimal(0)),
        sum(v.observed_requests for v in values), sum(v.priced_requests for v in values),
        source_complete=all(v.source_complete for v in values))


def quota_window(component: QuotaComponent, now_ms: int, *, include_monthly: bool = False) -> tuple[int, int, str] | None:
    duration = component.duration_seconds
    monthly = (include_monthly and duration is None and component.period == "fixed"
               and component.scope == "account" and component.model_id is None
               and component.label.casefold() in {"monthly", "month"})
    if ((not monthly and (not duration or duration <= 0)) or component.scope not in {"account", "model"}
            or (component.scope == "model" and not component.model_id)):
        return None
    if component.origin != "provider_native":
        return None
    if component.window_active is False:
        if (component.reset_at_ms is None and component.used in (None, 0)
                and component.remaining_fraction in (None, 1)
                and not (component.remaining is not None and component.limit is not None
                         and component.remaining < component.limit)):
            # An explicitly empty period has no historical interval. The empty
            # half-open range cannot pick up requests even at the observation time.
            return now_ms, now_ms, "provider-confirmed empty window"
        return None  # Inactive plus a reset/nonzero usage is contradictory evidence.
    if monthly:
        window = monthly_quota_window(component, now_ms)
        return (*window, "native UTC calendar month") if window is not None else None
    if component.reset_at_ms and component.reset_at_ms - duration * 1000 <= now_ms < component.reset_at_ms:
        return component.reset_at_ms - duration * 1000, now_ms + 1, "native reset window"
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
                  include_copilot_month: bool = False, include_native_month: bool = False) -> int:
    starts = [today_start_ms]
    for account in accounts:
        for component in account.quotas:
            monthly = include_native_month or (include_copilot_month and usage_provider(account.ref.provider_id) == "github-copilot")
            if (window := quota_window(component, now_ms, include_monthly=monthly)) is not None:
                starts.append(window[0])
    return min(starts)


@dataclass
class _Series:
    times: list[int]
    totals: list[Decimal]
    priced: list[int]
    incomplete: list[int]

    def between(self, start: int, end: int) -> ComparisonCost:
        left, right = bisect_left(self.times, start), bisect_left(self.times, end)
        return ComparisonCost(self.totals[right] - self.totals[left], right - left,
                              self.priced[right] - self.priced[left],
                              source_complete=self.incomplete[right] == self.incomplete[left])


class PeriodCCostIndex:
    """Value once per history publication; moving windows query prefix sums, no rescans."""

    def __init__(self, entries: Iterable[TraceEntry], valuation: ReferenceValuation, *,
                 account_only: bool = False, timeline_valuation=None, timeline_accounts=()) -> None:
        self._series: dict[tuple, _Series] = {}
        self.earliest_ms = None
        canonical = tuple(entry for entry in unique_usage(entries) if _eligible(entry, account_only))
        clues = _account_clues(canonical, timeline_accounts)
        values = (timeline_valuation(canonical) if timeline_valuation is not None
                  else (comparison_cost((entry,), valuation) for entry in canonical))
        for entry, value in zip(canonical, values):
            provider = usage_provider(entry.model.provider)
            if timeline_valuation is not None and not provider and entry.account_ref is not None:
                provider = usage_provider(entry.account_ref.provider_id)
            account = entry.account_ref.key if entry.account_ref else None
            if account is None:
                account = clues.get((entry.source_instance, entry.session_id, provider))
                if account is not None:
                    value = replace(value, source_complete=False)
            if self.earliest_ms is None and entry.completed_at_ms > 0:
                self.earliest_ms = entry.completed_at_ms
            scopes = (None,) if account_only else (None, canonical_model_name(entry.model.model))
            for identity in ("provider", account):
                for scope in scopes:
                    key = provider, identity, scope
                    series = self._series.setdefault(key, _Series([], [Decimal(0)], [0], [0]))
                    series.times.append(entry.completed_at_ms)
                    series.totals.append(series.totals[-1] + value.known_ccost)
                    series.priced.append(series.priced[-1] + value.priced_requests)
                    series.incomplete.append(series.incomplete[-1] + (not value.source_complete))

    def cost(self, provider: str, identity: object, start: int, end: int,
             model_id: str | None = None) -> ComparisonCost:
        model = canonical_model_name(model_id) if model_id else None
        series = self._series.get((usage_provider(provider), identity, model))
        return series.between(start, end) if series else ComparisonCost()


def _eligible(entry, account_only):
    if account_only and entry.completed_at_ms <= 0:
        return False
    # Explicit API/foreign-account proof must not become a Pro estimate.
    return not (usage_provider(entry.model.provider) == 'claude-agent' and (
        entry.cost_disposition is CostDisposition.BILLED
        or entry.account_ref is not None and entry.account_ref.provider_id != 'claude-code'))


def _account_clues(entries, candidates):
    """A unique same-source, same-route account in the same session is a clue."""
    if not candidates:
        return {}
    refs = {}
    for entry in entries:
        if entry.source_instance and entry.model.provider and entry.account_ref is not None:
            group = entry.source_instance, entry.session_id, usage_provider(entry.model.provider)
            refs.setdefault(group, set()).add(entry.account_ref.key)
    return {group: account for group, accounts in refs.items() if len(accounts) == 1
            for account in accounts if (group[2], account) in candidates}
