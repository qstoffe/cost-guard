"""Small deterministic reference-price catalogs for analysis/report fixtures."""
from __future__ import annotations

from decimal import Decimal

from src.domain import ModelPricing, ModelRef, PricingTier
from src.pricing.catalog import PricingCatalog


def catalog() -> PricingCatalog:
    def model(name: str, display: str, i: str, c: str, o: str) -> ModelPricing:
        tier = PricingTier(per_million_input=Decimal(i), per_million_cache_read=Decimal(c), per_million_output=Decimal(o))
        return ModelPricing(ModelRef("github-copilot", name, display), "USD", Decimal(i), Decimal(c), None, Decimal(o), (tier,), {"publisher":"Test"})
    return PricingCatalog((model("gpt-test", "GPT Test", "1", "0.1", "4"), model("claude-test", "Claude Test", "2", "0.2", "6")))


def threshold_catalog() -> PricingCatalog:
    """One ``gpt-test`` model whose rates double above a 100K-token request input."""
    base = PricingTier(max_input_tokens=100_000, per_million_input=Decimal("1"),
                       per_million_cache_read=Decimal("0.1"), per_million_output=Decimal("4"))
    long = PricingTier(min_input_tokens=100_001, per_million_input=Decimal("2"),
                       per_million_cache_read=Decimal("0.2"), per_million_output=Decimal("8"))
    model = ModelPricing(ModelRef("github-copilot", "gpt-test", "GPT Test"), "USD", tiers=(base, long),
                         metadata={"publisher": "Test"})
    return PricingCatalog((model,))
