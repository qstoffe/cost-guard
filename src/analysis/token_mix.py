"""Raw-volume token mix, with conservative incomplete-telemetry semantics.

Category CCost is priced request by request (each request's own model and tier)
and only then aggregated; it is never derived by pricing aggregated tokens.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Callable, Hashable, Iterable, Mapping, Sequence

from src.domain import ModelRef, TokenUsage

from .models import TraceEntry

MIX_FIELDS = ("input", "cache_read", "cache_write", "output")
CategoryCosts = tuple[Decimal, Decimal, Decimal, Decimal]
CategoryValuation = Callable[[ModelRef, TokenUsage], "CategoryCosts | None"]


@dataclass(frozen=True, slots=True)
class TokenMix:
    totals: tuple[int | None, int | None, int | None, int | None] = (None, None, None, None)
    percentages: tuple[int | None, int | None, int | None, int | None] = (None, None, None, None)
    sample_size: int = 0
    request_count: int = 0  # observed usage records; 0 means no token data at all
    # Known CCost per I/C/W/O category over priced requests; None when not valued.
    costs: CategoryCosts | None = None
    priced_requests: int = 0

    @property
    def cost_complete(self) -> bool:
        return self.costs is not None and self.priced_requests == self.request_count

    @property
    def total_tokens(self) -> int | None:
        return None if any(value is None for value in self.totals) else sum(self.totals)

    @property
    def shares(self) -> tuple[Decimal | None, Decimal | None, Decimal | None, Decimal | None]:
        """Exact unrounded percentages; defined exactly when `percentages` is."""
        total = self.total_tokens
        if not total or any(value is None for value in self.percentages):
            return (None, None, None, None)
        return tuple(Decimal(100) * value / total for value in self.totals)  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class ModelTokenMix:
    """One model's usage: unique contributing prompts, attributed calls and mix."""
    model: ModelRef
    prompts: int
    calls: int
    mix: TokenMix


def token_mix(usages: Iterable[TokenUsage], *, sample_size: int = 0) -> TokenMix:
    totals = [0, 0, 0, 0]
    known = set(MIX_FIELDS)
    count = 0
    for usage in usages:
        count += 1
        known.intersection_update(usage.known_fields)
        for index, name in enumerate(MIX_FIELDS):
            totals[index] += getattr(usage, name)
        # Canonical reasoning is separate; the established display folds it into O.
        totals[3] += usage.reasoning
    values = tuple(value if count and name in known else None
                   for name, value in zip(MIX_FIELDS, totals))
    total = sum(totals)
    if not count or len(known) != 4 or not total:
        # An unknown category makes the denominator unknown for every share.
        return TokenMix(values, sample_size=sample_size, request_count=count)
    percentages = [100 * value // total for value in totals]
    order = sorted(range(4), key=lambda i: (-(100 * totals[i] % total), i))
    for index in order[:100 - sum(percentages)]:
        percentages[index] += 1
    return TokenMix(values, tuple(percentages), sample_size, count)


def priced_token_mix(
    requests: Iterable[tuple[ModelRef, TokenUsage]], valuation: CategoryValuation, *, sample_size: int = 0,
) -> TokenMix:
    """Token mix plus per-category CCost that reconciles with comparison_cost."""
    items = tuple(requests)
    costs = [Decimal(0)] * 4
    priced = 0
    for model, tokens in items:
        # Same zero-usage and unknown-price rules as analysis.valuation.comparison_cost.
        parts = valuation(model, tokens) if tokens.total else (Decimal(0),) * 4
        if parts is None:
            continue
        for index, value in enumerate(parts):
            value = Decimal(value)
            if not value.is_finite() or value < 0:
                raise ValueError("Reference valuation must be finite and nonnegative")
            costs[index] += value
        priced += 1
    mix = token_mix((tokens for _model, tokens in items), sample_size=sample_size)
    return replace(mix, costs=tuple(costs), priced_requests=priced)


def model_token_mixes(
    entries: Sequence[TraceEntry], prompt_of: Mapping[TraceEntry, Hashable],
    valuation: CategoryValuation, *, model_key: Callable[[ModelRef], str],
) -> tuple[ModelTokenMix, ...]:
    """Group requests by model identity.

    Calls count every attributed request. Prompts count unique initiating user
    prompts per model, so one prompt may appear on several model rows.
    """
    groups: dict[str, list[TraceEntry]] = {}
    for entry in entries:
        groups.setdefault(model_key(entry.model), []).append(entry)
    result = []
    for group in groups.values():
        prompts = {prompt_of[entry] for entry in group if entry in prompt_of}
        result.append(ModelTokenMix(
            group[-1].model, len(prompts), len(group),
            priced_token_mix(((entry.model, entry.tokens) for entry in group), valuation,
                             sample_size=len(prompts)),
        ))
    return tuple(result)
