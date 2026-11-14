"""Provider-neutral promotion validity; unknown starts never imply recency."""
from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
from decimal import Decimal, InvalidOperation
import json

from src.domain import ModelPricing, PricingTier
from .catalog import FIXED_REFERENCE_MIX, weighted_tier_price
from .tiers import ordered_tiers

WEEK_MS = 7 * 86_400_000


@dataclass(frozen=True, slots=True)
class PricePromotion:
    expires_ms: int
    starts_ms: int | None = None
    discount_percent: str = ""

    def active(self, now_ms: int) -> bool:
        return (self.starts_ms is None or self.starts_ms <= now_ms) and now_ms < self.expires_ms

    def recent(self, now_ms: int) -> bool:
        return self.active(now_ms) and self.starts_ms is not None and 0 <= now_ms - self.starts_ms < WEEK_MS


def model_promotion(model: ModelPricing) -> PricePromotion | None:
    metadata = model.metadata
    if str(metadata.get("promotion_active", "false")).lower() != "true":
        return None
    try:
        expires = int(metadata["promotion_expires_ms"])
        raw_start = metadata.get("promotion_starts_ms")
        starts = int(raw_start) if raw_start is not None else None
    except (KeyError, TypeError, ValueError):
        return None
    if starts is not None and starts >= expires:
        return None
    return PricePromotion(expires, starts, str(metadata.get("promotion_discount_percent", "")).strip())


def promotion_price_ratios(model: ModelPricing) -> tuple[Decimal | None, ...]:
    """Compare published current/verified standard tiers under the fixed weights."""
    tiers = ordered_tiers(model)
    rate_names = ('per_million_input', 'per_million_cache_read', 'per_million_cache_write', 'per_million_output')
    try:
        raw = model.metadata.get('promotion_standard_tiers')
        if raw:
            decoded = json.loads(raw)
            if not isinstance(decoded, list) or not all(isinstance(item, dict) for item in decoded):
                return ()
            standard = tuple(PricingTier(
                min_input_tokens=int(item['min']) if item.get('min') is not None else None,
                max_input_tokens=int(item['max']) if item.get('max') is not None else None,
                input_threshold_operator=item.get('threshold_operator'),
                **{name: Decimal(str(item[key])) if item.get(key) is not None else None
                   for name, key in zip(rate_names, ('i', 'c', 'w', 'o'))},
            ) for item in decoded)
            standard = tuple(sorted(standard, key=lambda tier: tier.min_input_tokens or 0))
        else:
            discount = Decimal(str(model.metadata.get('promotion_discount_percent', '')))
            if not discount.is_finite() or not 0 < discount < 100:
                return ()
            factor = 1 - discount / 100
            standard = tuple(replace(tier, **{name: getattr(tier, name) / factor
                if getattr(tier, name) is not None else None for name in rate_names}) for tier in tiers)
        if len(standard) != len(tiers):
            return ()
        ratios = []
        for current, original in zip(tiers, standard):
            bounds = lambda tier: (tier.min_input_tokens, tier.max_input_tokens, tier.input_threshold_operator)
            if bounds(current) != bounds(original):
                return ()
            values = [getattr(tier, name) for tier in (current, original) for name in rate_names]
            if any(value is not None and (not value.is_finite() or value < 0) for value in values):
                ratios.append(None)
                continue
            before = weighted_tier_price(FIXED_REFERENCE_MIX, original)
            after = weighted_tier_price(FIXED_REFERENCE_MIX, current)
            ratios.append(after / before if before and after is not None and 0 <= after <= before else None)
        return tuple(ratios)
    except (TypeError, ValueError, InvalidOperation, ArithmeticError):
        return ()
