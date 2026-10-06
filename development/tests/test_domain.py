from __future__ import annotations

import unittest
from decimal import Decimal

from src.domain import CostKind, CostObservation, QuotaWindow, QuotaWindowKind, TokenUsage


class DomainContractTests(unittest.TestCase):
    def test_token_usage_keeps_billing_categories_independent(self) -> None:
        usage = TokenUsage(input=10, cache_read=20, cache_write=30, output=40, reasoning=50)
        self.assertEqual(150, usage.total)
        self.assertEqual(30, usage.cache_write)

    def test_negative_tokens_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            TokenUsage(input=-1)

    def test_cost_observation_keeps_kind_and_currency_explicit(self) -> None:
        cost = CostObservation(Decimal("1.23"), "USD", CostKind.ESTIMATED_EQUIVALENT, estimated=True)
        self.assertEqual(Decimal("1.23"), cost.amount)
        self.assertEqual("USD", cost.currency)
        self.assertTrue(cost.estimated)

    def test_quota_fraction_is_not_a_dollar_conversion(self) -> None:
        window = QuotaWindow(
            name="5h",
            kind=QuotaWindowKind.ROLLING,
            used_fraction=Decimal("0.50"),
            remaining_fraction=Decimal("0.50"),
            native_unit="provider-percent",
        )
        self.assertEqual(Decimal("0.50"), window.used_fraction)
        self.assertIsNone(window.native_limit)

    def test_quota_fraction_outside_zero_one_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            QuotaWindow(name="bad", kind=QuotaWindowKind.UNKNOWN, used_fraction=Decimal("1.01"))


if __name__ == "__main__":
    unittest.main()
