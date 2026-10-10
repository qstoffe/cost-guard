"""Small deterministic reference-price catalog for analysis/report fixtures."""
from __future__ import annotations

from decimal import Decimal

from src.domain import ModelPricing, ModelRef, PricingTier
from src.pricing.catalog import PricingCatalog


def catalog() -> PricingCatalog:
    def model(name: str, display: str, i: str, c: str, o: str) -> ModelPricing:
        tier = PricingTier(per_million_input=Decimal(i), per_million_cache_read=Decimal(c), per_million_output=Decimal(o))
        return ModelPricing(ModelRef("github-copilot", name, display), "USD", Decimal(i), Decimal(c), None, Decimal(o), (tier,), {"publisher":"Test"})
    return PricingCatalog((model("gpt-test", "GPT Test", "1", "0.1", "4"), model("claude-test", "Claude Test", "2", "0.2", "6")))
