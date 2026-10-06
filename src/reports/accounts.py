"""Account-neutral report projection; quota never implies observed usage."""
from __future__ import annotations

from collections import Counter
from typing import Sequence

from src.analysis.models import TraceEntry
from src.analysis.quota_pace import quota_pace
from src.analysis.valuation import billed_spend, comparison_cost, unique_usage
from src.domain import AccountSnapshot, CostDisposition
from src.pricing.catalog import PricingCatalog, canonical_model_name

from .models import AccountProjection, AccountsQuotasProjection


def account_projections(
    accounts: Sequence[AccountSnapshot], entries: Sequence[TraceEntry],
    catalog: PricingCatalog, *, now_ms: int, today_start_ms: int, month_start_ms: int,
    timezone_id: str = "UTC", workday_calendar: str = "",
) -> tuple[AccountProjection, ...]:
    counts = Counter((item.ref.provider_id, item.plan) for item in accounts)
    labels: dict[str, int] = {}
    projections = []
    for account in accounts:
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
        scopes = []
        rolling = [component for component in account.quotas if component.duration_seconds]
        ranges = [(component.label, (component.reset_at_ms or now_ms + 1) - component.duration_seconds * 1000,
                   min(component.reset_at_ms or now_ms + 1, now_ms + 1), component.model_id, component.scope) for component in rolling]
        if not ranges:
            ranges = [("today", today_start_ms, now_ms + 1, None, "account")]
        for name, start, end, model_id, scope in ranges:
            selected = [entry for entry in attributed if start <= entry.completed_at_ms < end
                        and (model_id is None or canonical_model_name(entry.model.model) == canonical_model_name(model_id))]
            # Visible attributable calls prove that subset, not completeness of a
            # rolling window containing other unassigned calls from this provider.
            unknown = any(entry.model.provider == account.ref.provider_id and entry.account_ref is None
                          and start <= entry.completed_at_ms < end
                          and (model_id is None or canonical_model_name(entry.model.model) == canonical_model_name(model_id)) for entry in entries)
            value = comparison_cost(selected, catalog.reference_valuation) if (
                (selected or account.usage_attribution_complete) and not unknown and (scope != "model" or model_id is not None)
            ) else None
            scopes.append((name, value))
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
            actual_billing(today_start_ms), actual_billing(month_start_ms), pace,
        ))
    return tuple(projections)


def accounts_quota_projection(
    accounts: Sequence[AccountSnapshot], entries: Sequence[TraceEntry], catalog: PricingCatalog,
    *, now_ms: int, today_start_ms: int, month_start_ms: int,
    today_prompt_count: int = 0, today_session_count: int = 0,
    timezone_id: str = "UTC", workday_calendar: str = "",
) -> AccountsQuotasProjection:
    entries = unique_usage(entries)
    today = tuple(e for e in entries if today_start_ms <= e.completed_at_ms <= now_ms)
    month = tuple(e for e in entries if month_start_ms <= e.completed_at_ms <= now_ms)
    return AccountsQuotasProjection(
        comparison_today=comparison_cost(today, catalog.reference_valuation),
        comparison_month=comparison_cost(month, catalog.reference_valuation),
        accounts=account_projections(accounts, entries, catalog, now_ms=now_ms,
                                     today_start_ms=today_start_ms, month_start_ms=month_start_ms,
                                     timezone_id=timezone_id, workday_calendar=workday_calendar),
        billed_today=billed_spend(today), billed_month=billed_spend(month),
        today_prompt_count=today_prompt_count, today_session_count=today_session_count,
        today_request_count=len(today),
        included_subscription_requests=sum(e.cost_disposition is CostDisposition.INCLUDED_SUBSCRIPTION for e in month),
        now_ms=now_ms,
    )
