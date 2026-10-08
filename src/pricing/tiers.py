"""Context-ordered catalog tiers and their exact published lower bounds."""
from __future__ import annotations

from src.domain import ModelPricing, PricingTier
from src.domain.ccost import CCostPricing


def ordered_tiers(model: ModelPricing | CCostPricing) -> tuple[PricingTier, ...]:
    fallback = model.selected_tier(0)
    tiers = model.tiers or ((fallback,) if fallback is not None else ())
    return tuple(sorted(tiers, key=lambda tier: tier.min_input_tokens or 0))


def lower_bound(tier: PricingTier, previous: PricingTier | None = None) -> tuple[str, int] | None:
    minimum = tier.min_input_tokens
    if minimum is None:
        return None
    operator = tier.input_threshold_operator
    if operator is None:
        # Older caches normalized >N to N+1 without retaining the operator.
        operator = ">" if previous is not None and previous.max_input_tokens == minimum - 1 else "≥"
    return operator, minimum - 1 if operator == ">" else minimum
