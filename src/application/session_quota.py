"""Whole-tree request evidence × current quotas, with no extra source/provider IO.

Only compact process-local aggregates survive detail acquisition. Account refs
stay private; HTTP receives the same safe headings as Accounts and percentages.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from src.analysis.causal import trace_entries
from src.analysis.coverage import snapshot_coverage_complete
from src.analysis.period_ccost import account_usage_routes, usage_provider
from src.analysis.valuation import comparison_cost, unique_usage
from src.domain import CostDisposition, CostKind
from src.pricing.catalog import canonical_model_name
from src.pricing.identities import unverified_alias
from .projection import account, identity, quota_record
from .quota_ccost import quota_ccost_values


def source_scope(source):
    return source.source_id, getattr(source, "source_instance", None), getattr(source, "observation_epoch", None)


@dataclass(frozen=True)
class Contribution:
    route: str
    account_key: tuple | None
    model: str | None
    amount: Decimal
    complete: bool
    native: tuple
    requests: int


@dataclass(frozen=True)
class SessionQuotaEvidence:
    source: tuple
    complete: bool
    contributions: tuple[Contribution, ...]


def session_quota_evidence(history, service):
    snapshot = history.snapshot
    if snapshot is None:
        return None
    cached = getattr(history, "quota_evidence", None)
    signature = (snapshot, history.retained,
                 service._load_comparison_catalog().diagnostic_signature, source_scope(service.source))
    if getattr(history, "quota_signature", None) == signature:
        return cached
    catalog = service._load_comparison_catalog()
    entries = unique_usage(trace_entries(snapshot))
    groups = {}
    for entry in entries:
        route = usage_provider(entry.model.provider)
        # An API invoice/foreign account is never a first-party subscription guess.
        if route == "claude-agent" and (entry.cost_disposition is CostDisposition.BILLED or
                entry.account_ref is not None and entry.account_ref.provider_id != "claude-code"):
            continue
        model = (canonical_model_name(entry.model.model) if entry.model.model
                 and not unverified_alias(entry.model.model, entry.model.provider) else None)
        key = route, entry.account_ref.key if entry.account_ref else None, model
        group = groups.setdefault(key, [Decimal(0), True, {}, 0])
        value = comparison_cost((entry,), catalog.reference_valuation)
        group[0] += value.known_ccost
        group[1] = group[1] and value.complete
        group[3] += 1
        native = snapshot.invocations[entry.sort_order].cost
        if (native is not None and native.kind is CostKind.PROVIDER_REPORTED
                and not native.estimated and native.amount.is_finite()):
            unit = native.currency.casefold()
            amount, count = group[2].get(unit, (Decimal(0), 0))
            group[2][unit] = amount + native.amount, count + 1
    evidence = SessionQuotaEvidence(source_scope(service.source),
        snapshot_coverage_complete(snapshot, entries) and not history.retained,
        tuple(Contribution(*key, amount, complete, tuple(native.items()), count)
              for key, (amount, complete, native, count) in groups.items()))
    history.quota_signature, history.quota_evidence = signature, evidence
    return evidence


def percentage(amount, capacity, estimated):
    value = amount * 100 / capacity
    # Avoid a false displayed zero for a genuinely nonzero tiny share.
    text = (format(Decimal(format(value, ".2g")), "f") if 0 < value < Decimal("0.05")
            else f"{value:.1f}".removesuffix(".0"))
    return ("~" if estimated else "") + text + "%"


def quota_contributions(evidence, native, quota, candidates):
    """Resolve membership independently of capacity, freshness and formatting."""
    if quota.scope not in {"account", "model"} or quota.scope == "model" and not quota.model_id:
        return [], False, True
    model = canonical_model_name(quota.model_id) if quota.scope == "model" else None
    if model and unverified_alias(quota.model_id, native.ref.provider_id):
        return [], False, True
    routes = account_usage_routes(native, proven=True)
    eligible, estimated, uncertain = [], False, False
    for part in evidence.contributions:
        if part.route and part.route not in routes:
            continue
        if model and part.model is not None and part.model != model:
            continue
        if part.account_key is not None and part.account_key != native.key:
            continue
        if not part.route or model and part.model is None:
            uncertain = True
            continue
        if part.account_key is None:
            if candidates.get(part.route) != (native.key,):
                uncertain = True
                continue
            estimated = True
        eligible.append(part)
    return eligible, estimated, uncertain


def quota_contribution(evidence, native, quota, candidates) -> Literal["positive", "zero", "unknown"]:
    """Wire-safe positive/zero/unknown state; no account refs or raw costs."""
    eligible, _, uncertain = quota_contributions(evidence, native, quota, candidates)
    unit = (quota.unit or "").casefold()
    direct = bool(eligible and unit) and all(
        part.account_key == native.key and dict(part.native).get(unit, (0, 0))[1] == part.requests
        for part in eligible)
    amounts = ([dict(part.native)[unit][0] for part in eligible] if direct
               else [amount for part in eligible for amount in
                     (part.amount, *(amount for amount, _ in dict(part.native).values()))])
    if any(amount > 0 for amount in amounts):
        return "positive"
    if evidence.complete and not uncertain and (direct or all(part.complete for part in eligible)):
        return "zero"
    return "unknown"


def quota_share(evidence, native, quota, reference, candidates, *, stale=False):
    if quota.unlimited:
        return "Unlimited"
    capacity = reference.get("capacity")
    if stale or not evidence.complete or not reference.get("current") or not reference.get("coherent"):
        return "—"
    eligible, estimated, uncertain = quota_contributions(evidence, native, quota, candidates)
    if uncertain:
        return "—"
    estimated = estimated or reference["basis"] == "ratio"
    # A native same-unit per-request observation is exact only with proven
    # account identity. Reference valuation is not a native provider debit.
    unit = (quota.unit or "").casefold()
    direct = bool(unit) and quota.limit is not None and quota.limit > 0
    native_amount = Decimal(0)
    for part in eligible:
        amount, count = dict(part.native).get(unit, (Decimal(0), 0))
        direct = direct and part.account_key == native.key and count == part.requests
        native_amount += amount
    if direct:
        return percentage(native_amount, quota.limit, False)
    if capacity is None or capacity <= 0:
        return "—"
    if not eligible:
        return "0%"
    if not all(part.complete for part in eligible):
        return "—"
    return percentage(sum((part.amount for part in eligible), Decimal(0)), capacity,
                      estimated or reference["basis"] == "native")


def session_quota_usage(evidence, accounts, source, now_ms, *, stale=False):
    if evidence is None or accounts is None or evidence.source != source:
        return None
    candidates = {}
    for item in accounts.accounts:
        for route in account_usage_routes(item.account):
            candidates.setdefault(route, []).append(item.account.key)
    candidates = {route: tuple(keys) for route, keys in candidates.items()}
    cards = []
    for item in accounts.accounts:
        native = item.account
        observation = dict(dict(account(item).fields)["observation"].fields)
        safe = {key: observation[key] for key in ("id", "provider_id", "label", "provider_label", "plan")}
        rows = []
        for index, quota in enumerate(native.quotas):
            period = next((p for p in item.quota_periods if p.quota is quota), None)
            values = dict(quota_record(quota, period.cost if period else None,
                provider_id=native.ref.provider_id, availability=native.availability).fields)
            reference = quota_ccost_values(values, now_ms)
            rows.append(dict(id=identity((index, quota.label, quota.scope, quota.model_id)),
                label=quota.label, scope=quota.scope, model_id=quota.model_id,
                contribution=quota_contribution(evidence, native, quota, candidates),
                percent=quota_share(evidence, native, quota, reference, candidates, stale=stale)))
        cards.append(dict(observation=safe, quotas=rows))
    return dict(scope=identity(evidence.source), accounts=cards)
