"""CCost: reference valuation of observed usage, independent of actual billing."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable, Mapping

from src.domain import CostDisposition
from src.domain.ccost import ReferenceValuation
from .billing import billing_request_fingerprint
from .models import TraceEntry


@dataclass(frozen=True, slots=True)
class ComparisonCost:
    known_ccost: Decimal = Decimal(0)
    observed_requests: int = 0
    priced_requests: int = 0
    by_model: Mapping[str, Decimal] = field(default_factory=dict)
    by_day_utc: Mapping[str, Decimal] = field(default_factory=dict)

    @property
    def complete(self) -> bool:
        return self.priced_requests == self.observed_requests

    @property
    def ccost(self) -> Decimal | None:
        return self.known_ccost if self.complete else None


def unique_usage(entries: Iterable[TraceEntry]) -> tuple[TraceEntry, ...]:
    """Use billing's clone fingerprint, retaining independent source instances."""
    first: dict[tuple[str | None, str], str] = {}
    result = []
    for entry in sorted(entries, key=lambda e: (e.completed_at_ms, e.sort_order, e.session_id)):
        fingerprint = billing_request_fingerprint(entry)
        key = entry.source_instance, fingerprint
        if fingerprint and key in first and first[key] != entry.session_id:
            continue
        if fingerprint:
            first.setdefault(key, entry.session_id)
        result.append(entry)
    return tuple(result)


def comparison_cost(entries: Iterable[TraceEntry], reference_valuation: ReferenceValuation) -> ComparisonCost:
    total = Decimal(0)
    priced = observed = 0
    by_model: dict[str, Decimal] = {}
    by_day: dict[str, Decimal] = {}
    for entry in entries:
        observed += 1
        value = reference_valuation(entry.model, entry.tokens) if entry.tokens.total else Decimal(0)
        if value is None:
            continue
        value = Decimal(value)
        if not value.is_finite() or value < 0:
            raise ValueError("Reference valuation must be finite and nonnegative")
        priced += 1
        total += value
        by_model[entry.model.model] = by_model.get(entry.model.model, Decimal(0)) + value
        day = datetime.fromtimestamp(entry.completed_at_ms / 1000, timezone.utc).strftime("%Y-%m-%d")
        by_day[day] = by_day.get(day, Decimal(0)) + value
    return ComparisonCost(total, observed, priced, by_model, by_day)


def billed_spend(entries: Iterable[TraceEntry]) -> Decimal | None:
    """Never substitute reference/fallback prices for actual provider billing."""
    total = Decimal(0)
    for entry in entries:
        if entry.reported_cost > 0:
            total += entry.reported_cost
        elif entry.cost_disposition in {CostDisposition.BILLED, CostDisposition.INCLUDED_SUBSCRIPTION}:
            continue
        elif entry.tokens.total:
            return None
    return total
