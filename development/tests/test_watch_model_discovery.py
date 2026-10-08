"""Cross-platform regression checks for live Watch model discovery."""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from src.domain import ModelPricing, ModelRef
from src.pricing.catalog import PricingCatalog
from src.watch.model_discovery import WatchModelDiscovery


def catalog(*names, retrieved=1, dated=()):
    models = tuple(ModelPricing(
        model=ModelRef(provider="github-copilot", model=name.lower().replace(" ", "-"),
                       display_name=name),
        currency="USD",
        metadata={"release_date": "2026-10-08"} if name in dated else {},
    ) for name in names)
    return PricingCatalog(models=models, retrieved_at_ms=retrieved)


class FakeProvider:
    def __init__(self, catalog_value):
        self.current = catalog_value
        self.calls = 0

    def get_catalog(self):
        self.calls += 1
        return self.current


class AvailableSource:
    def __init__(self):
        self.models = ("github-copilot/old",)
        self.calls = 0

    def available_model_ids(self):
        self.calls += 1
        return self.models


class WatchModelDiscoveryTests(unittest.TestCase):
    def make_discovery(self):
        initial = catalog("Old", retrieved=1)
        provider = FakeProvider(initial)
        source = AvailableSource()
        service = SimpleNamespace(
            pricing_provider=provider,
            selection=SimpleNamespace(source=source),
            _load_catalog=lambda: initial,
        )
        return WatchModelDiscovery(service), provider, source

    def test_catalog_updates_after_hour_without_touching_baseline(self):
        observer, provider, source = self.make_discovery()
        observer.refresh(1_000)
        self.assertEqual(0, provider.calls)
        provider.current = catalog("Old", "New Claude", retrieved=3_601_000)
        observer.refresh(3_601_001)
        self.assertEqual(1, provider.calls)
        self.assertIn("New Claude", observer.notice(3_601_001))
        self.assertIn("release date unverified", observer.notice(3_601_001))
        self.assertEqual(1, observer.service._load_catalog().retrieved_at_ms)

    def test_new_dated_model_visible_in_notice(self):
        observer, provider, source = self.make_discovery()
        observer.refresh(1_000)
        provider.current = catalog("Old", "Claude New", dated=("Claude New",))
        observer.refresh(3_601_001)
        self.assertIn("✦ New in Copilot catalog", observer.notice(1791500000000))

    def test_new_available_without_price_uses_pending_notice(self):
        observer, provider, source = self.make_discovery()
        observer.refresh(1_000)
        source.models = ("github-copilot/old", "github-copilot/new-model")
        observer.refresh(901_001)
        self.assertIn("pricing pending", observer.notice(901_001))
        self.assertNotIn("New in Copilot catalog", observer.notice(901_001))

    def test_rate_limit_and_resume(self):
        observer, provider, source = self.make_discovery()
        observer.refresh(1_000)
        observer.refresh(20_000)
        self.assertEqual(0, provider.calls)
        self.assertEqual(1, source.calls)
        observer.refresh(20_000, resumed=True)
        self.assertEqual(1, provider.calls)
        self.assertEqual(2, source.calls)

    def test_new_priced_model_becomes_selectable_independently(self):
        observer, provider, source = self.make_discovery()
        observer.refresh(1_000)
        provider.current = catalog("Old", "New Model")
        observer.refresh(3_601_001)
        self.assertIn("New Model", observer.notice(3_601_001))
        source.models = ("github-copilot/old", "github-copilot/new-model")
        observer.refresh(3_601_002, resumed=True)
        self.assertIn("✓ New selectable in OpenCode", observer.notice(3_601_002))

    def test_price_outage_keeps_previous_catalog(self):
        observer, provider, source = self.make_discovery()
        observer.refresh(1_000)
        provider.get_catalog = lambda: (_ for _ in ()).throw(OSError("synthetic"))
        observer.refresh(3_601_001)
        self.assertEqual("unavailable", observer.diagnostics(3_601_001)["pricing_status"])
        self.assertEqual(("Old",), tuple(m.model.display_name for m in observer.catalog.models))

    def test_availability_failure_retains_snapshot(self):
        observer, provider, source = self.make_discovery()
        observer.refresh(1_000)
        source.available_model_ids = lambda: (_ for _ in ()).throw(OSError("synthetic"))
        observer.refresh(901_001)
        self.assertEqual(("github-copilot/old",), observer.available_ids)
        self.assertEqual("unavailable", observer.diagnostics(901_001)["availability_status"])

if __name__ == "__main__":
    unittest.main()
