"""Canonical Copilot AI-credit-equivalent reference pricing, never billing.

Acquisition retains native currency. This boundary converts native reference
rates once; CCost analysis receives these rates, not USD-shaped amounts.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Callable, Mapping

from .models import ModelPricing, ModelRef, PricingTier, TokenUsage

CCOST_PER_REFERENCE_USD = Decimal(100)
ReferenceValuation = Callable[[ModelRef, TokenUsage], Decimal | None]


def reference_usd_to_ccost(value: Decimal) -> Decimal:
    """1 CCost = 1 Copilot AI-credit-equivalent; no actual deduction implied."""
    return value * CCOST_PER_REFERENCE_USD


@dataclass(frozen=True, slots=True)
class CCostPricing:
    """Reference rates per million tokens, already expressed in CCost."""

    model: ModelRef
    tiers: tuple[PricingTier, ...]
    metadata: Mapping[str, str]

    def selected_tier(self, request_input_tokens: int) -> PricingTier | None:
        return next((tier for tier in self.tiers if tier.matches(request_input_tokens)),
                    self.tiers[0] if self.tiers else None)


def ccost_pricing(native: ModelPricing) -> CCostPricing:
    """Unknown currency has no reference rates; never guess an FX conversion."""
    fallback = native.selected_tier(0)
    tiers = native.tiers or ((fallback,) if fallback is not None else ())
    rates = ("per_million_input", "per_million_cache_read", "per_million_cache_write", "per_million_output")
    converted = tuple(replace(tier, **{
        name: reference_usd_to_ccost(value) if native.currency == "USD" and value is not None else None
        for name in rates for value in (getattr(tier, name),)
    }) for tier in tiers)
    return CCostPricing(native.model, converted, native.metadata)
