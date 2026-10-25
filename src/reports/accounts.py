"""Account-neutral report projection; quota never implies observed usage."""
from __future__ import annotations

from collections import Counter
from dataclasses import replace
from typing import Sequence

from src.analysis.models import TraceEntry
from src.analysis.period_ccost import PeriodCCostIndex, usage_provider, quota_window
from src.analysis.quota_pace import quota_pace
from src.analysis.valuation import billed_spend, comparison_cost, unique_usage
from src.domain import AccountSnapshot, CostDisposition
from src.domain.acquisition import AcquisitionMetrics
from src.pricing.catalog import PricingCatalog

from .models import AccountProjection, AccountsQuotasProjection


def account_projections(
    accounts: Sequence[AccountSnapshot], entries: Sequence[TraceEntry],
    catalog: PricingCatalog, *, now_ms: int, today_start_ms: int, month_start_ms: int,
    timezone_id: str = "UTC", workday_calendar: str = "",
    period_index: PeriodCCostIndex | None = None, watch: bool = False,
    observed_start_ms: int | None = None,
) -> tuple[AccountProjection, ...]:
    counts = Counter((item.ref.provider_id, item.plan) for item in accounts)
    providers = Counter(usage_provider(item.ref.provider_id) for item in accounts)
    index = period_index or PeriodCCostIndex(entries, catalog.reference_valuation)
    explained = set()
    labels: dict[str, int] = {}
    projections = []
    # Stable capacity/name/identity ordering, never balance, percentage or timing.
    for account in sorted(accounts, key=lambda item: (
        item.capacity_kind != "credit", item.provider_label.casefold(),
        (item.plan or "").casefold(), (item.ref.account_label or "").casefold(), item.key,
    )):
        label = account.provider_label + (" " + account.plan if account.plan else "")
        multiple = counts[(account.ref.provider_id, account.plan)] > 1
        if multiple and account.ref.account_label:
            label += " · " + account.ref.account_label
        # Distinguish unknown/same labels by source ordinal, not invented Personal/Work.
        labels[label] = labels.get(label, 0) + 1
        if multiple and (not account.ref.account_label or labels[label] > 1):
            label += f" · account {labels[label]}"
        attributed = tuple(entry for entry in entries if entry.account_ref and entry.account_ref.key == account.key
                           and entry.model.provider == account.ref.provider_id)
        scopes, notes, account_unknown = _period_scopes(account, index, providers, explained, today_start_ms,
                                       month_start_ms, now_ms, watch=watch, observed_start_ms=observed_start_ms)
        unassigned = any(entry.model.provider == account.ref.provider_id and entry.account_ref is None
                         and month_start_ms <= entry.completed_at_ms <= now_ms for entry in entries)
        billing_known = not unassigned

        def actual_billing(start_ms: int):
            selected = tuple(e for e in attributed if start_ms <= e.completed_at_ms <= now_ms)
            # Subscription inclusion is not evidence of actual monetary billing.
            has_billing = any(e.reported_cost > 0 or e.cost_disposition is CostDisposition.BILLED for e in selected)
            return billed_spend(selected) if billing_known and has_billing else None

        # Pace derives from current quota state and the calendar, never usage history.
        pace = tuple(value for component in account.quotas if (value := quota_pace(
            component, now_ms=now_ms, timezone_id=timezone_id, workday_calendar=workday_calendar)) is not None)
        projections.append(AccountProjection(
            account, label, tuple(scopes),
            actual_billing(today_start_ms), actual_billing(month_start_ms), pace, notes, account_unknown,
        ))
    return tuple(projections)


def _period_scopes(account, index, providers, explained, today_start_ms, month_start_ms, now_ms, *, watch,
                   observed_start_ms):
    provider = usage_provider(account.ref.provider_id)
    ranges = [("today", (today_start_ms, now_ms + 1, "configured local calendar day"), None)]
    if not watch:
        ranges.append(("this month", (month_start_ms, now_ms + 1, "configured local calendar month to date"), None))
    ranges.extend((component.label, quota_window(component, now_ms), component.model_id)
                  for component in account.quotas if component.duration_seconds)
    scopes, notes = [], []
    account_unknown = False
    for name, window, model in ranges:
        if window is None:
            scopes.append((name, None))
            notes.append(f"CCost {name}: period boundary unknown.")
            continue
        start, end, basis = window
        proven = index.cost(provider, account.key, start, end, model)
        unknown = index.cost(provider, None, start, end, model)
        if unknown.observed_requests and providers[provider] == 1:
            # Include proven requests only for this account, never another account's history.
            value = replace(proven, known_ccost=proven.known_ccost + unknown.known_ccost,
                            observed_requests=proven.observed_requests + unknown.observed_requests,
                            priced_requests=proven.priced_requests + unknown.priced_requests)
            attribution = "provider-attributed estimate; not verified account/billing attribution"
        elif unknown.observed_requests:
            value = None
            account_unknown = True
            attribution = "account unknown / not attributable among multiple compatible accounts"
            if (provider, name) not in explained:
                total = index.cost(provider, "provider", start, end, model)
                number = str(total.known_ccost) if total.priced_requests else "N/A"
                notes.append(f"Provider-only CCost {name}: {number}{' (partial pricing)' if not total.complete else ''}; not allocated to accounts.")
                explained.add((provider, name))
        else:
            # Empty attribution is not missing history: only an acquired scope
            # establishes an observed zero, irrespective of provider/account type.
            observed = observed_start_ms is not None and observed_start_ms <= start <= now_ms
            value = proven if proven.observed_requests or observed else None
            attribution = "verified request account references" if proven.observed_requests else "no attributable observed requests"
        scopes.append((name, value))
        notes.append(f"CCost {name}: {basis}; {attribution}.")
    return tuple(scopes), tuple(notes), account_unknown


class WatchAccountProjection:
    """Native account publication reuses unchanged local accounting, never source I/O."""

    def __init__(self, metrics: AcquisitionMetrics) -> None:
        self.metrics = metrics
        self._entries: tuple[TraceEntry, ...] | None = None
        self._catalog: PricingCatalog | None = None
        self._boundaries: tuple[int, int] | None = None
        self._local: tuple[AccountsQuotasProjection, tuple[TraceEntry, ...]] | None = None
        self._period_index: PeriodCCostIndex | None = None
        self._period_entries: tuple[TraceEntry, ...] | None = None
        self._period_catalog: PricingCatalog | None = None

    def project(self, accounts: Sequence[AccountSnapshot], entries: tuple[TraceEntry, ...], catalog: PricingCatalog, *,
                now_ms: int, day_start_ms: int, month_start_ms: int, timezone_id: str,
                 workday_calendar: str, period_entries: tuple[TraceEntry, ...] | None = None,
                 observed_start_ms: int | None = None) -> tuple[AccountsQuotasProjection, tuple[TraceEntry, ...]]:
        boundaries = (day_start_ms, month_start_ms)
        if self._entries is not entries or self._catalog is not catalog or self._boundaries != boundaries:
            self._local = accounts_quota_projection_with_today_entries(
                (), entries, catalog, now_ms=now_ms, today_start_ms=day_start_ms, month_start_ms=month_start_ms)
            self._entries, self._catalog, self._boundaries = entries, catalog, boundaries
            self.metrics.add("daily_usage_projections")
        period_entries = entries if period_entries is None else period_entries
        if self._period_entries is not period_entries or self._period_index is None or self._period_catalog is not catalog:
            self._period_index = PeriodCCostIndex(period_entries, catalog.reference_valuation)
            self._period_entries, self._period_catalog = period_entries, catalog
        assert self._local is not None
        projection, today = self._local
        native = account_projections(accounts, (), catalog, now_ms=now_ms, today_start_ms=day_start_ms,
                                     month_start_ms=month_start_ms, timezone_id=timezone_id,
                                     workday_calendar=workday_calendar, period_index=self._period_index, watch=True,
                                     observed_start_ms=observed_start_ms)
        return replace(projection, accounts=native, now_ms=now_ms), today


def accounts_quota_projection(
    accounts: Sequence[AccountSnapshot], entries: Sequence[TraceEntry], catalog: PricingCatalog,
    *, now_ms: int, today_start_ms: int, month_start_ms: int,
    today_prompt_count: int = 0, today_session_count: int = 0,
    timezone_id: str = "UTC", workday_calendar: str = "",
    observed_start_ms: int | None = None,
) -> AccountsQuotasProjection:
    return accounts_quota_projection_with_today_entries(
        accounts, entries, catalog, now_ms=now_ms, today_start_ms=today_start_ms,
        month_start_ms=month_start_ms, today_prompt_count=today_prompt_count,
        today_session_count=today_session_count, timezone_id=timezone_id,
        workday_calendar=workday_calendar,
        observed_start_ms=observed_start_ms,
    )[0]


def accounts_quota_projection_with_today_entries(
    accounts: Sequence[AccountSnapshot], entries: Sequence[TraceEntry], catalog: PricingCatalog,
    *, now_ms: int, today_start_ms: int, month_start_ms: int,
    today_prompt_count: int = 0, today_session_count: int = 0,
    timezone_id: str = "UTC", workday_calendar: str = "",
    observed_start_ms: int | None = None,
) -> tuple[AccountsQuotasProjection, tuple[TraceEntry, ...]]:
    """Project quota data and expose its exact deduplicated daily request scope."""
    entries = unique_usage(entries)
    today = tuple(e for e in entries if today_start_ms <= e.completed_at_ms <= now_ms)
    month = tuple(e for e in entries if month_start_ms <= e.completed_at_ms <= now_ms)
    projection = AccountsQuotasProjection(
        comparison_today=comparison_cost(today, catalog.reference_valuation),
        comparison_month=comparison_cost(month, catalog.reference_valuation),
        accounts=account_projections(accounts, entries, catalog, now_ms=now_ms,
                                     today_start_ms=today_start_ms, month_start_ms=month_start_ms,
                                     timezone_id=timezone_id, workday_calendar=workday_calendar,
                                     observed_start_ms=observed_start_ms),
        billed_today=billed_spend(today), billed_month=billed_spend(month),
        today_prompt_count=today_prompt_count, today_session_count=today_session_count,
        today_request_count=len(today),
        included_subscription_requests=sum(e.cost_disposition is CostDisposition.INCLUDED_SUBSCRIPTION for e in month),
        now_ms=now_ms,
    )
    return projection, today
