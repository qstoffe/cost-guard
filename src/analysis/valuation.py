"""CCost: reference valuation of observed usage, independent of actual billing."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable, Mapping

from src.domain import CostDisposition
from src.domain.ccost import ReferenceValuation
from src.domain.reference_cost import ReferenceCostDiagnosis, ReferenceCostIssue, bounded_issues
from .billing import billing_request_fingerprint
from .models import TraceEntry

_DAY_MS = 86_400_000


@dataclass(frozen=True, slots=True)
class ComparisonCost:
    known_ccost: Decimal = Decimal(0)
    observed_requests: int = 0
    priced_requests: int = 0
    by_model: Mapping[str, Decimal] = field(default_factory=dict)
    by_day_utc: Mapping[str, Decimal] = field(default_factory=dict)
    unavailable: tuple[ReferenceCostIssue, ...] = ()
    source_complete: bool = True

    @property
    def complete(self) -> bool:
        return self.source_complete and self.priced_requests == self.observed_requests

    @property
    def ccost(self) -> Decimal | None:
        return self.known_ccost if self.complete else None


def unique_usage(entries: Iterable[TraceEntry]) -> tuple[TraceEntry, ...]:
    """Retain independent calls within a tree; clone matching is cross-tree only.

    Equal tokens/model/completion time never identify two sibling requests.
    Repeated captures of a physical request use its canonical source identity.
    Legacy fork matching retains the largest observed tree multiplicity.
    """
    physical, legacy = {}, []
    for entry in entries:
        if not entry.invocation_id:
            legacy.append(entry)
            continue
        key = (entry.source_instance, entry.session_id, entry.invocation_id, entry.message_id, entry.step_part_id)
        previous = physical.get(key)
        if previous is not None:
            # Prefer complete telemetry over a partial capture; equally complete
            # later publications may correct the physical request's counters.
            chosen = max((previous, entry), key=lambda value: (
                len(value.tokens.known_fields), value.completed_at_ms, value is entry))
            tree = previous if previous.parent_session_id else entry
            entry = replace(chosen, root_session_id=tree.root_session_id, parent_session_id=tree.parent_session_id)
        physical[key] = entry
    groups, ungrouped = {}, []
    for entry in sorted((*physical.values(), *legacy), key=lambda e: (e.completed_at_ms, e.sort_order, e.session_id)):
        fingerprint = billing_request_fingerprint(entry)
        if fingerprint:
            trees = groups.setdefault((entry.source_instance, fingerprint), {})
            tree = entry.root_session_id if entry.parent_session_id or entry.root_session_id == entry.session_id else entry.session_id
            trees.setdefault(tree, []).append(entry)
        else:
            ungrouped.append(entry)

    result = ungrouped
    for trees in groups.values():
        result.extend(max(trees.values(), key=len))
    return tuple(sorted(result, key=lambda e: (e.completed_at_ms, e.sort_order, e.session_id)))


def comparison_cost(entries: Iterable[TraceEntry], reference_valuation: ReferenceValuation, *,
                    diagnose: ReferenceCostDiagnosis | None = None) -> ComparisonCost:
    total = Decimal(0)
    priced = observed = 0
    by_model: dict[str, Decimal] = {}
    by_day: dict[str, Decimal] = {}
    day_names: dict[int, str] = {}  # whole UTC days since the epoch -> "YYYY-MM-DD", formatted once
    issues = set()
    usage_complete = True
    for entry in entries:
        observed += 1
        usage_known = {"input", "cache_read", "cache_write", "output"} <= set(entry.tokens.known_fields)
        usage_complete = usage_complete and usage_known
        value = reference_valuation(entry.model, entry.tokens) if entry.tokens.total or not usage_known else Decimal(0)
        if value is None:
            if diagnose is not None:
                issues.add(diagnose(entry.model, entry.tokens))
            continue
        value = Decimal(value)
        if not value.is_finite() or value < 0:
            raise ValueError("Reference valuation must be finite and nonnegative")
        priced += 1
        total += value
        by_model[entry.model.model] = by_model.get(entry.model.model, Decimal(0)) + value
        day_index = entry.completed_at_ms // _DAY_MS
        day = day_names.get(day_index)
        if day is None:
            day = day_names[day_index] = datetime.fromtimestamp(entry.completed_at_ms / 1000, timezone.utc).strftime("%Y-%m-%d")
        by_day[day] = by_day.get(day, Decimal(0)) + value
    return ComparisonCost(total, observed, priced, by_model, by_day, bounded_issues(issues), usage_complete)


def billed_spend(entries: Iterable[TraceEntry]) -> Decimal | None:
    """Never substitute reference/fallback prices for actual provider billing."""
    total = Decimal(0)
    for entry in entries:
        if entry.reported_cost > 0:
            total += entry.reported_cost
        elif entry.cost_disposition in {CostDisposition.BILLED, CostDisposition.INCLUDED_SUBSCRIPTION}:
            continue
        elif entry.tokens.total or not {"input", "cache_read", "cache_write", "output"} <= set(entry.tokens.known_fields):
            return None
    return total
