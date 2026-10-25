"""Watch price refresh must not pull optional metadata onto its startup thread."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest

from src.cache import CacheDatabase, CacheRepository
from src.pricing.catalog import PricingCatalog
from src.pricing.github_copilot import (
    CACHE_KEY, CACHE_NAMESPACE, GitHubCopilotPricingProvider, _catalog_payload, parse_pricing_markdown,
)
from src.pricing.metadata_health import MetadataHealthStore
from src.watch.model_discovery import WatchModelDiscovery
from src.watch import WatchCoordinator
from development.tests.fixtures.watch_runtime import MutableSource, make_service

NOW = int(datetime(2026, 10, 20, 12, tzinfo=timezone.utc).timestamp() * 1000)
PRICES = (
    "## OpenAI\nModel | Input | Cached input | Output\n--- | --- | --- | ---\n"
    + "\n".join(f"GPT-Test-{i} | $2 | $0.5 | $8" for i in range(1, 6))
)


class WatchPricingStartupTests(unittest.TestCase):
    def test_dashboard_initializes_while_optional_metadata_is_still_waiting(self):
        with tempfile.TemporaryDirectory() as temp:
            config, selection, service, _ = make_service(temp, MutableSource(), now_ms=NOW)
            entered, release = threading.Event(), threading.Event()
            inline_calls, workers = [], []
            main_thread = threading.current_thread()
            def fetch(url, timeout):
                if "article/body" in url:
                    return PRICES
                if threading.current_thread() is main_thread:
                    inline_calls.append(url)
                    raise TimeoutError("optional metadata must not block startup")
                entered.set()
                release.wait(2)
                raise TimeoutError("metadata remains unavailable")
            provider = GitHubCopilotPricingProvider(cache=service.cache_repository, fetch_text=fetch,
                now_ms=lambda: NOW, metadata_store=MetadataHealthStore(None), defer_metadata_refresh=True)
            service.pricing_provider = service.comparison_pricing_provider = provider
            watch = WatchCoordinator(selection=selection, report_service=service, config=config,
                                     clock_ms=lambda: NOW, record_observations=False)
            def run_async(work):
                thread = threading.Thread(target=work, daemon=True)
                workers.append(thread)
                thread.start()
            watch.model_discovery = WatchModelDiscovery(service, run_async=run_async)
            try:
                cycle = watch.initialize(defer_history=True)

                self.assertTrue(entered.wait(1), "metadata worker should have started")
                self.assertEqual([], inline_calls)
                self.assertTrue(cycle.projection.rows, "dashboard exists before metadata completes")
                self.assertTrue(watch.model_discovery.diagnostics(NOW)["metadata_refresh_active"])
            finally:
                release.set()
                watch.close()
                for thread in workers:
                    thread.join(2)
                    self.assertFalse(thread.is_alive())

    def test_cold_and_expired_prices_defer_metadata_until_watch_worker(self):
        for expired_cache in (False, True):
            with self.subTest(expired_cache=expired_cache), tempfile.TemporaryDirectory() as temp:
                database = CacheDatabase(Path(temp))
                database.initialize()
                repository = CacheRepository(database)
                if expired_cache:
                    old = list(parse_pricing_markdown(PRICES.replace("$2", "$1")))
                    old[0] = replace(old[0], metadata={**old[0].metadata,
                        "release_date": "2026-10-01", "release_date_source": "models.dev"})
                    repository.put(CACHE_NAMESPACE, CACHE_KEY, _catalog_payload(PricingCatalog(
                        tuple(old), retrieved_at_ms=NOW - 7_200_000, source_revision="old")))
                calls = []
                def fetch(url, timeout):
                    calls.append(url)
                    if "article/body" in url:
                        return PRICES
                    if "models.dev" in url:
                        return json.dumps({f"openai/gpt-test-{i}": {
                            "name": f"GPT-Test-{i}", "release_date": "2026-10-02"} for i in range(1, 6)})
                    raise AssertionError("all models already have release dates")
                metadata = MetadataHealthStore(None)
                provider = GitHubCopilotPricingProvider(cache=repository, max_age_hours=1, fetch_text=fetch,
                    now_ms=lambda: NOW, metadata_store=metadata, defer_metadata_refresh=True)

                pinned = provider.get_catalog()

                self.assertEqual(1, len(calls), "startup must fetch prices only, not optional release dates")
                self.assertNotIn("last_attempt_ms", metadata.snapshot())
                self.assertEqual(2, pinned.models[0].per_million_input)
                self.assertEqual("2026-10-01" if expired_cache else None,
                                 pinned.models[0].metadata.get("release_date"))
                queued = []
                service = SimpleNamespace(pricing_provider=provider, _load_catalog=lambda: pinned,
                                          cache_repository=repository)
                discovery = WatchModelDiscovery(service, run_async=queued.append)
                discovery.refresh(NOW)
                self.assertEqual(1, len(queued))
                self.assertEqual(1, len(calls), "scheduling must not run metadata inline")

                queued.pop()()
                discovery.refresh(NOW + 1)

                self.assertEqual(2, len(calls))
                self.assertEqual("2026-10-02", discovery.catalog.models[0].metadata["release_date"])
                self.assertEqual(pinned.analysis_signature, discovery.catalog.analysis_signature)
                self.assertEqual("2026-10-01" if expired_cache else None,
                                 pinned.models[0].metadata.get("release_date"), "CCost catalog stays pinned")

    def test_report_price_refresh_still_enriches_inline(self):
        with tempfile.TemporaryDirectory() as temp:
            database = CacheDatabase(Path(temp))
            database.initialize()
            calls = []
            def fetch(url, timeout):
                calls.append(url)
                if "article/body" in url:
                    return PRICES
                if "models.dev" in url:
                    return json.dumps({f"openai/gpt-test-{i}": {
                        "name": f"GPT-Test-{i}", "release_date": "2026-10-02"} for i in range(1, 6)})
                raise AssertionError("all models already have release dates")
            provider = GitHubCopilotPricingProvider(cache=CacheRepository(database), fetch_text=fetch,
                now_ms=lambda: NOW, metadata_store=MetadataHealthStore(None))

            catalog = provider.get_catalog()

            self.assertEqual(2, len(calls))
            self.assertTrue(all(model.metadata.get("release_date") == "2026-10-02" for model in catalog.models))


if __name__ == "__main__":
    unittest.main()
