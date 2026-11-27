"""Whole-tree request evidence × current quotas, with no extra source/provider IO.

Only compact process-local aggregates survive detail acquisition. Account refs
stay private; HTTP receives the same safe headings as Accounts and percentages.
"""
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Literal

from src.analysis.causal import trace_entries
from src.analysis.coverage import snapshot_coverage_complete
from src.analysis.effort_defaults import request_effort
from src.analysis.period_ccost import account_usage_routes, usage_provider
from src.analysis.valuation import comparison_cost, unique_usage
from src.domain import CostDisposition, CostKind
from src.domain.session_tree import root_by_session
from src.numbers import ccost_amount
from src.pricing.catalog import canonical_model_name
from src.pricing.identities import unverified_alias
from src.reports.model_details import executed, model_identity, selected_effort
from src.reports.session_effort import effort_name
from .projection import account, identity, quota_record
from .quota_ccost import quota_ccost_values
from .watch_accounts import primary_quota


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
class ModelEffort:
    provider: str
    model: str
    effort: str
    label: str


@dataclass(frozen=True)
class SessionContribution:
    id: str
    title: str
    main: bool
    groups: tuple[tuple[ModelEffort | None, Contribution], ...]


@dataclass(frozen=True)
class SessionQuotaEvidence:
    source: tuple
    complete: bool
    contributions: tuple[Contribution, ...]
    pricing: str = ""
    sessions: tuple[SessionContribution, ...] = ()


def _accumulate(groups, key, value, native):
    group = groups.setdefault(key, [Decimal(0), True, {}, 0])
    group[0] += value.known_ccost
    group[1] = group[1] and value.complete
    group[3] += 1
    if (native is not None and native.kind is CostKind.PROVIDER_REPORTED
            and not native.estimated and native.amount.is_finite()):
        unit = native.currency.casefold()
        amount, count = group[2].get(unit, (Decimal(0), 0))
        group[2][unit] = amount + native.amount, count + 1


def _contribution(key, group):
    amount, complete, native, count = group
    return Contribution(*key, amount, complete, tuple(native.items()), count)


def _executed_combination(entry):
    model = model_identity(entry)
    if model is None or not entry.model.model:
        return None
    evidence = request_effort(entry)
    effort = selected_effort(entry.variant)
    if effort is None or effort == "default":
        effort = selected_effort(evidence.effective or evidence.selected)
    if effort in {None, "default", "unknown"}:
        return None
    return model[0], entry.model.model, effort


def _breakdown_evidence(source, snapshot, sessions, catalog):
    titles = {session.session_id: session.title for session in snapshot.sessions}
    root = snapshot.root.session_id
    titles[root] = snapshot.root.title
    result = []
    labels = {}
    for sid in sorted(sessions, key=lambda sid: sid != root):
        title = " ".join("".join(char for char in word if char.isprintable())
                         for word in (titles[sid] or "").split()).strip()
        if len(title) > 512:
            title = title[:511].rstrip() + "…"
        groups = []
        for (key, combination), group in sessions[sid].items():
            if combination is not None:
                provider, model, effort = combination
                if (provider, model) not in labels:
                    labels[provider, model] = catalog.display_name(model, provider, exact=True)
                combination = ModelEffort(provider, model, effort, labels[provider, model])
            groups.append((combination, _contribution(key, group)))
        result.append(SessionContribution(identity((source, sid)), title or "Untitled session",
                                          sid == root, tuple(groups)))
    return tuple(result)


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
    groups, sessions = {}, {}
    source = signature[-1]
    root = snapshot.root.session_id
    ancestry = root_by_session(snapshot.sessions)
    for entry in entries:
        route = usage_provider(entry.model.provider)
        # An API invoice/foreign account is never a first-party subscription guess.
        if route == "claude-agent" and (entry.cost_disposition is CostDisposition.BILLED or
                entry.account_ref is not None and entry.account_ref.provider_id != "claude-code"):
            continue
        model = (canonical_model_name(entry.model.model) if entry.model.model
                 and not unverified_alias(entry.model.model, entry.model.provider) else None)
        key = route, entry.account_ref.key if entry.account_ref else None, model
        value = comparison_cost((entry,), catalog.reference_valuation)
        native = snapshot.invocations[entry.sort_order].cost
        _accumulate(groups, key, value, native)
        sid = entry.session_id
        if (sid == root or ancestry.get(sid) == root) and executed(entry):
            _accumulate(sessions.setdefault(sid, {}), (key, _executed_combination(entry)), value, native)
    evidence = SessionQuotaEvidence(source,
        snapshot_coverage_complete(snapshot, entries) and not history.retained,
        tuple(_contribution(key, group) for key, group in groups.items()), repr(catalog.diagnostic_signature),
        _breakdown_evidence(source, snapshot, sessions, catalog))
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
    def result(percent, state, reason):
        return dict(percent=percent, state=state, reason=reason)

    if quota.unlimited:
        return result("Unlimited", "verified", "No finite quota limit.")
    capacity = reference.get("capacity")
    eligible, estimated, uncertain = quota_contributions(evidence, native, quota, candidates)
    if not reference.get("coherent") or quota.window_active is False:
        return result("?", "impossible", "No coherent compatible quota capacity/window.")
    if quota_contribution(evidence, native, quota, candidates) == "zero":
        return result("0%", "verified", "Qualified zero session consumption for this quota.")
    if uncertain and not eligible:
        return result("?", "impossible", "Session consumption cannot be allocated to this account/model.")
    estimated = (estimated or stale or uncertain or not evidence.complete or
                 not reference.get("current") or reference.get("retained") or
                 not all(part.complete for part in eligible))
    # A native same-unit per-request observation is exact only with proven
    # account identity. Reference valuation is not a native provider debit.
    unit = (quota.unit or "").casefold()
    direct = bool(eligible and unit) and quota.limit is not None and quota.limit > 0
    native_amount = Decimal(0)
    for part in eligible:
        amount, count = dict(part.native).get(unit, (Decimal(0), 0))
        direct = direct and part.account_key == native.key and count == part.requests
        native_amount += amount
    if direct:
        if native_amount == 0 and not evidence.complete:
            pending = not stale and reference.get("current")
            return result("Loading…" if pending else "?", "pending" if pending else "impossible",
                "Recorded portion is zero; complete usage has not been established.")
        return result(percentage(native_amount, quota.limit, bool(estimated)),
            "estimated" if estimated else "verified",
            "Recorded same-unit session debit / matching quota limit." +
            (" Observed portion only; attribution, coverage or freshness is uncertain." if estimated else ""))
    if capacity is None or capacity <= 0:
        return result("?", "impossible", "No compatible reference quota capacity is available.")
    amount = sum((part.amount for part in eligible), Decimal(0))
    if amount <= 0:
        pending = not evidence.complete and not stale and reference.get("current")
        return result("Loading…" if pending else "?",
            "pending" if pending else "impossible",
            "No usable priced session consumption yet; token/pricing evidence is missing.")
    return result(percentage(amount, capacity, True), "estimated",
        "Observed attributed reference CCost / compatible reference capacity; not a native debit or bill." +
        (" Partial usage/attribution; observed portion only." if estimated else "") +
        (" Retained same-window capacity sample." if reference.get("retained") else ""))


def quota_reference(values, now_ms, cache, key):
    """Session-only estimate: reuse coherent samples within the identical window."""
    reference = quota_ccost_values(values, now_ms)
    compatible = (values.get("origin") == "provider_native" and values.get("window_active") is not False
        and values.get("status") not in {"blocked", "invalid", "paused"}
        and (values.get("reset_at_ms") is None or values["reset_at_ms"] > now_ms)
        and not (values.get("reset_at_ms") is not None and values.get("duration_seconds")
                 and now_ms < values["reset_at_ms"] - values["duration_seconds"] * 1000))
    if not compatible:
        cache.pop(key, None)
        return {**reference, "capacity": None, "coherent": False}
    if not reference.get("current"):
        # A stale sample is not current/exact. Re-evaluate only its existing raw
        # facts, never another quota or an expired/reset window.
        sample = quota_ccost_values({**values, "availability": "available", "status": "available"}, now_ms)
        reference = {**sample, "current": False, "retained": True}
    if reference.get("capacity") is not None and reference.get("coherent"):
        cache[key] = reference["capacity"]
    elif reference.get("coherent") and key in cache:
        reference = {**reference, "capacity": cache[key], "retained": True}
    else:
        cache.pop(key, None)
    return reference


def _attributed_parts(evidence, native, quota, candidates):
    eligible, _, _ = quota_contributions(evidence, native, quota, candidates)
    if not eligible:
        return ()
    # Incomplete history or other ambiguous activity must not turn a proven
    # zero among the requests attributable to this subscription into usage.
    observed = replace(evidence, complete=True, contributions=tuple(eligible))
    return eligible if quota_contribution(observed, native, quota, candidates) != "zero" else ()


def _session_breakdown(evidence, native, quota, reference, candidates, stale, ccost_display_unit):
    rows = []
    for session in evidence.sessions:
        local = replace(evidence, contributions=tuple(part for _, part in session.groups), sessions=())
        if not _attributed_parts(local, native, quota, candidates):
            continue
        combinations = {}
        for combination, part in session.groups:
            if combination is not None:
                combinations.setdefault(combination, []).append(part)
        details = []
        for combination, parts in combinations.items():
            group = replace(local, contributions=tuple(parts))
            eligible = _attributed_parts(group, native, quota, candidates)
            if not eligible:
                continue
            amount = sum((part.amount for part in eligible), Decimal(0))
            ccost = ccost_amount(amount, unit=ccost_display_unit) if all(part.complete for part in eligible) else "?"
            provider_label = {"openai": "OpenAI", "github-copilot": "GitHub Copilot",
                              "claude-agent": "Claude Agent"}.get(combination.provider, combination.provider)
            share = quota_share(group, native, quota, reference, candidates, stale=stale)
            details.append(dict(provider=provider_label, model=combination.label, effort=effort_name(combination.effort),
                                percent=share["percent"], ccost=ccost))
        share = quota_share(local, native, quota, reference, candidates, stale=stale)
        rows.append(dict(id=session.id, title=session.title, main=session.main, details=details,
                         percent=share["percent"], state=share["state"]))
    if any(not row["main"] for row in rows):
        return dict(label=quota.label, rows=rows)
    return None


def session_quota_usage(evidence, accounts, source, now_ms, *, stale=False, capacity_cache=None,
                        ccost_display_unit="credits"):
    if evidence is None or accounts is None or evidence.source != source:
        return None
    candidates = {}
    for item in accounts.accounts:
        for route in account_usage_routes(item.account):
            candidates.setdefault(route, []).append(item.account.key)
    candidates = {route: tuple(keys) for route, keys in candidates.items()}
    cards = []
    cache = capacity_cache if capacity_cache is not None else {}
    wanted = set()
    for item in accounts.accounts:
        native = item.account
        observation = dict(dict(account(item).fields)["observation"].fields)
        safe = {key: observation[key] for key in ("id", "provider_id", "label", "provider_label", "plan")}
        rows = []
        card = dict(observation=safe, quotas=rows)
        primary = primary_quota(native) if any(not session.main for session in evidence.sessions) else None
        for index, quota in enumerate(native.quotas):
            period = next((p for p in item.quota_periods if p.quota is quota), None)
            values = dict(quota_record(quota, period.cost if period else None,
                provider_id=native.ref.provider_id, availability=native.availability).fields)
            key = (source, evidence.pricing, native.key, index, quota.label, quota.scope, quota.model_id,
                   quota.unit, quota.limit, quota.reset_at_ms, quota.duration_seconds, quota.period)
            wanted.add(key)
            reference = quota_reference(values, now_ms, cache, key)
            rows.append(dict(id=identity((index, quota.label, quota.scope, quota.model_id)),
                label=quota.label, scope=quota.scope, model_id=quota.model_id,
                contribution=quota_contribution(evidence, native, quota, candidates),
                **quota_share(evidence, native, quota, reference, candidates, stale=stale)))
            if quota is primary:
                breakdown = _session_breakdown(evidence, native, quota, reference, candidates, stale, ccost_display_unit)
                if breakdown is not None:
                    card["session_breakdown"] = breakdown
        cards.append(card)
    for key in set(cache) - wanted:
        del cache[key]
    return dict(scope=identity(evidence.source), accounts=cards)
