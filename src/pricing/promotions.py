"""Provider-neutral promotion validity; unknown starts never imply recency."""
from __future__ import annotations

from dataclasses import dataclass

from src.domain import ModelPricing

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
