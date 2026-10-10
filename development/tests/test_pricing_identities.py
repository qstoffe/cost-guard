"""Explicit reference identities never conflate versions, variants or billing."""
from decimal import Decimal as D
from dataclasses import replace
import unittest

from src.domain import ModelPricing, ModelRef, PricingTier, TokenUsage
from src.pricing.catalog import PricingCatalog
from src.reports.model_comparison import selectable_catalog
from src.sources.model_availability import OpenCodeModelAvailabilitySource


def price(identity, *, tiers=()):
    return ModelPricing(ModelRef("github-copilot", identity), "USD", D(2), D(".2"), D(3), D(10), tiers=tiers)


class ReferenceIdentityTests(unittest.TestCase):
    def test_alias_reference_value_never_changes_provider_reported_billing(self):
        from development.fixtures.session_snapshots import make_snapshot
        from src.analysis.causal import trace_entries
        from src.analysis.billing import actual_entry_cost
        from src.analysis.valuation import billed_spend, comparison_cost
        catalog = PricingCatalog((price("claude-haiku-4.5"),))
        entry = replace(trace_entries(make_snapshot())[0], model=ModelRef("claude-code", "claude-haiku-4-5-20251001"),
                        tokens=TokenUsage(input=1_000_000), reported_cost=D(42), account_ref=None)
        self.assertEqual(D(200), comparison_cost((entry,), catalog.reference_valuation).ccost)
        self.assertEqual(D(42), actual_entry_cost(entry, catalog.estimate).dollars)
        self.assertEqual(D(42), billed_spend((entry,)))

    def test_explicit_variant_rate_is_not_replaced_by_base_alias(self):
        base = price("claude-opus-5-5")
        variant = ModelPricing(ModelRef("github-copilot", "claude-opus-5-5[1m]"), "USD",
                               D(9), D(1), D(10), D(40))
        catalog = PricingCatalog((base, variant))
        self.assertIs(variant, catalog.resolve_reference("claude-code/claude-opus-5-5[1m]"))
        self.assertEqual(D(900), catalog.reference_valuation(ModelRef("claude-code", variant.model.model), TokenUsage(input=1_000_000)))
        self.assertIs(base, catalog.resolve_reference(base.model.model))

    def test_verified_dated_alias_and_context_capacity_match(self):
        catalog = PricingCatalog((price("claude-haiku-4.5"), price("claude-opus-5.5")))
        for selectable, base in (("claude-haiku-4-5-20251001", "claude-haiku-4.5"),
                                 ("claude-opus-5-5[1m]", "claude-opus-5.5")):
            self.assertEqual(base, catalog.resolve_reference(selectable).model.model)
            self.assertEqual(D(200), catalog.reference_valuation(ModelRef("claude-code", selectable), TokenUsage(input=1_000_000)))
        source = OpenCodeModelAvailabilitySource(runner=lambda: (0, "claude-code/claude-opus-5-5[1m]"))
        selected, warnings = selectable_catalog(catalog, availability_source=source)
        self.assertEqual(["claude-opus-5.5"], [m.model.model for m in selected.models])
        self.assertFalse(warnings)

    def test_unknown_and_ambiguous_aliases_remain_unknown(self):
        catalog = PricingCatalog((price("claude-opus-5.5"), price("claude-haiku-4.5")))
        for identity in ("claude-opus-5-5-fast", "claude-opus-5-5[2m]", "claude-opus-5-5-20260930",
                         "claude-haiku-4-5-20259999", "claude-future-9[1m]"):
            self.assertIsNone(catalog.resolve_reference(identity))
            self.assertIsNone(catalog.reference_valuation(ModelRef("claude-code", identity), TokenUsage(input=1)))
        ambiguous = PricingCatalog((price("claude-haiku-4.5"), price("claude-haiku-4-5")))
        self.assertIsNone(ambiguous.resolve_reference("claude-haiku-4-5-20251001"))

    def test_actual_input_selects_long_context_tier_not_capacity_suffix(self):
        tiers = (PricingTier("short", max_input_tokens=200_000, per_million_input=D(2),
                            per_million_cache_read=D(".2"), per_million_output=D(10)),
                 PricingTier("long", min_input_tokens=200_001, per_million_input=D(4),
                            per_million_cache_read=D(".4"), per_million_output=D(15)))
        catalog = PricingCatalog((price("claude-sonnet-4.6", tiers=tiers),))
        ref = ModelRef("claude-code", "claude-sonnet-4-6[1m]")
        self.assertEqual(D(20), catalog.reference_valuation(ref, TokenUsage(input=100_000)))
        self.assertEqual(D(120), catalog.reference_valuation(ref, TokenUsage(input=300_000)))
        self.assertEqual(tiers, catalog.resolve_reference(ref.model).tiers)


if __name__ == "__main__":
    unittest.main()
