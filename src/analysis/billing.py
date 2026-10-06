"""Cost and billing semantics ported from the v77 behavioral contract."""
from __future__ import annotations

import struct
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from src.domain import CostDisposition, ModelRef, TokenUsage

from .models import CostEvaluation, LocalUsageSummary, PromptRecord, TraceEntry


CostEstimator = Callable[[ModelRef, TokenUsage], Decimal | None]
ProviderScope = str | None


def provider_matches(provider_id: str, scope: ProviderScope) -> bool:
    """Return whether an observed provider belongs to the requested billing scope.

    ``None`` means all canonical providers. A concrete provider keeps the v77
    compatibility surface for focused tests/tools.
    """
    return scope is None or provider_id == scope


@dataclass(frozen=True, slots=True)
class PromptBilling:
    cost: Decimal
    main_cost: Decimal
    subagent_cost: Decimal
    breakdown_known: bool
    has_cost_breakdown: bool
    main_estimated: bool
    subagent_estimated: bool
    fallback_requests: int
    estimated_fallback_requests: int
    unresolved_fallback_requests: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    model_costs: dict[str, Decimal]


def actual_entry_cost(entry: TraceEntry, estimator: CostEstimator | None = None) -> CostEvaluation:
    """Return authoritative stored cost or an explicitly estimated fallback.

    v77 semantics are preserved: any positive stored OpenCode cost wins.  A
    zero-cost request with no tokens is a genuine zero-usage observation.  A
    token-bearing zero-cost request may be repriced only through an injected
    pricing hook; absence/failure of that hook is unresolved, never silently 0.
    """
    if entry.reported_cost > 0:
        return CostEvaluation(entry.reported_cost)
    if entry.tokens.total <= 0:
        return CostEvaluation(Decimal("0"), zero_usage=True)
    if entry.cost_disposition is CostDisposition.INCLUDED_SUBSCRIPTION:
        return CostEvaluation(Decimal("0"))
    if estimator is None:
        return CostEvaluation(Decimal("0"), fallback=True, unresolved=True)
    estimated = estimator(entry.model, entry.tokens)
    if estimated is None:
        return CostEvaluation(Decimal("0"), fallback=True, unresolved=True)
    value = Decimal(estimated)
    if value < 0:
        raise ValueError("Pricing fallback cannot return a negative cost")
    return CostEvaluation(value, fallback=True, estimated=True)


def _double_bits_text(value: float) -> str:
    return str(struct.unpack(">q", struct.pack(">d", float(value)))[0])


def billing_request_fingerprint(entry: TraceEntry) -> str:
    """Fingerprint provider requests exactly on v77's clone-stable fields.

    Message/part/session ids are deliberately excluded because OpenCode forks
    clone historical provider work under fresh row ids while preserving request
    completion time, model, stored cost and token payload.
    """
    if entry.completed_at_ms <= 0 or not entry.model.provider.strip() or not entry.model.model.strip():
        return ""
    values = (
        str(entry.completed_at_ms),
        entry.model.provider,
        entry.model.model,
        _double_bits_text(float(entry.reported_cost)),
        _double_bits_text(entry.tokens.input),
        _double_bits_text(entry.tokens.cache_read),
        _double_bits_text(entry.tokens.cache_write),
        _double_bits_text(entry.tokens.output),
        _double_bits_text(entry.tokens.reasoning),
    )
    return "|".join(values)


def measure_prompt_billing(
    entries: Iterable[TraceEntry],
    root_entry_count: int,
    estimator: CostEstimator | None = None,
) -> PromptBilling:
    items = tuple(entries)
    breakdown_known = 0 <= root_entry_count <= len(items)
    total = Decimal("0")
    main = Decimal("0")
    fallback = estimated = unresolved = 0
    main_estimated = subagent_estimated = False
    input_tokens = output_tokens = cache_read = cache_write = 0
    model_costs: dict[str, Decimal] = {}
    for index, entry in enumerate(items):
        cost = actual_entry_cost(entry, estimator)
        total += cost.dollars
        if breakdown_known and index < root_entry_count:
            main += cost.dollars
            main_estimated = main_estimated or cost.estimated
        elif cost.estimated:
            subagent_estimated = True
        fallback += int(cost.fallback)
        estimated += int(cost.estimated)
        unresolved += int(cost.unresolved)
        input_tokens += entry.tokens.input
        output_tokens += entry.tokens.output + entry.tokens.reasoning
        cache_read += entry.tokens.cache_read
        cache_write += entry.tokens.cache_write
        model_costs[entry.model.model] = model_costs.get(entry.model.model, Decimal("0")) + cost.dollars
    subagent = total - main
    return PromptBilling(
        cost=total,
        main_cost=main,
        subagent_cost=subagent,
        breakdown_known=breakdown_known,
        has_cost_breakdown=breakdown_known and root_entry_count < len(items) and subagent > 0,
        main_estimated=main_estimated,
        subagent_estimated=subagent_estimated,
        fallback_requests=fallback,
        estimated_fallback_requests=estimated,
        unresolved_fallback_requests=unresolved,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read,
        cache_write_tokens=cache_write,
        model_costs=model_costs,
    )


def aggregate_local_usage(
    prompt_records: Iterable[PromptRecord],
    *,
    since_ms: int,
    tracked_provider: ProviderScope,
    estimator: CostEstimator | None = None,
    extra_entries: Iterable[TraceEntry] = (),
) -> LocalUsageSummary:
    """Aggregate provider work with v77-style cross-session fork deduplication.

    Prompt records normally cover causal prompt work.  ``extra_entries`` exists
    for separately billed completed compactions or future non-prompt work.
    """
    entries: list[TraceEntry] = []
    for record in prompt_records:
        entries.extend(record.entries)
    entries.extend(extra_entries)
    entries.sort(key=lambda e: (e.completed_at_ms, e.sort_order, e.session_id))

    total = Decimal("0")
    fallback = estimated = unresolved = requests = included = 0
    dedup_requests = 0
    dedup_dollars = Decimal("0")
    fingerprint_session: dict[str, str] = {}
    session_ids: set[str] = set()
    by_model: dict[str, Decimal] = {}
    by_day: dict[str, Decimal] = {}

    for entry in entries:
        if entry.completed_at_ms < since_ms or not provider_matches(entry.model.provider, tracked_provider):
            continue
        fingerprint = billing_request_fingerprint(entry)
        if fingerprint:
            first_session = fingerprint_session.get(fingerprint)
            if first_session is not None and first_session != entry.session_id:
                clone_cost = actual_entry_cost(entry, estimator)
                dedup_requests += 1
                dedup_dollars += clone_cost.dollars
                continue
            fingerprint_session.setdefault(fingerprint, entry.session_id)
        cost = actual_entry_cost(entry, estimator)
        requests += 1
        included += int(entry.cost_disposition is CostDisposition.INCLUDED_SUBSCRIPTION)
        session_ids.add(entry.session_id)
        total += cost.dollars
        fallback += int(cost.fallback)
        estimated += int(cost.estimated)
        unresolved += int(cost.unresolved)
        by_model[entry.model.model] = by_model.get(entry.model.model, Decimal("0")) + cost.dollars
        day = datetime.fromtimestamp(entry.completed_at_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        by_day[day] = by_day.get(day, Decimal("0")) + cost.dollars

    return LocalUsageSummary(
        dollars=total,
        requests=requests,
        sessions=len(session_ids),
        fallback_requests=fallback,
        estimated_fallback_requests=estimated,
        unresolved_fallback_requests=unresolved,
        deduplicated_clone_requests=dedup_requests,
        deduplicated_clone_dollars=dedup_dollars,
        included_subscription_requests=included,
        by_model=by_model,
        by_day_utc=by_day,
    )


def aggregate_trace_usage(
    entries: Iterable[TraceEntry],
    *,
    since_ms: int,
    tracked_provider: ProviderScope,
    estimator: CostEstimator | None = None,
) -> LocalUsageSummary:
    """Aggregate authoritative trace entries directly, including compactions.

    This is the source-neutral equivalent of v77 ``Calculate-LocalUsage`` and
    should be preferred for month/day totals.  Prompt records are a presentation
    attribution view and are not the authoritative inventory of provider calls.
    """
    ordered = sorted(entries, key=lambda e: (e.completed_at_ms, e.sort_order, e.session_id))
    total = Decimal("0")
    fallback = estimated = unresolved = requests = included = 0
    dedup_requests = 0
    dedup_dollars = Decimal("0")
    fingerprint_session: dict[str, str] = {}
    session_ids: set[str] = set()
    by_model: dict[str, Decimal] = {}
    by_day: dict[str, Decimal] = {}
    for entry in ordered:
        if entry.completed_at_ms < since_ms or not provider_matches(entry.model.provider, tracked_provider):
            continue
        fingerprint = billing_request_fingerprint(entry)
        if fingerprint:
            first_session = fingerprint_session.get(fingerprint)
            if first_session is not None and first_session != entry.session_id:
                clone_cost = actual_entry_cost(entry, estimator)
                dedup_requests += 1
                dedup_dollars += clone_cost.dollars
                continue
            fingerprint_session.setdefault(fingerprint, entry.session_id)
        cost = actual_entry_cost(entry, estimator)
        requests += 1
        included += int(entry.cost_disposition is CostDisposition.INCLUDED_SUBSCRIPTION)
        session_ids.add(entry.session_id)
        total += cost.dollars
        fallback += int(cost.fallback)
        estimated += int(cost.estimated)
        unresolved += int(cost.unresolved)
        by_model[entry.model.model] = by_model.get(entry.model.model, Decimal("0")) + cost.dollars
        day = datetime.fromtimestamp(entry.completed_at_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        by_day[day] = by_day.get(day, Decimal("0")) + cost.dollars
    return LocalUsageSummary(
        dollars=total,
        requests=requests,
        sessions=len(session_ids),
        fallback_requests=fallback,
        estimated_fallback_requests=estimated,
        unresolved_fallback_requests=unresolved,
        deduplicated_clone_requests=dedup_requests,
        deduplicated_clone_dollars=dedup_dollars,
        included_subscription_requests=included,
        by_model=by_model,
        by_day_utc=by_day,
    )
