"""Self-healing release-date metadata: classification, backoff, persistence and notices."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from email.message import Message
import json
from pathlib import Path
import socket
import ssl
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
import urllib.error

from src.cache import CacheDatabase, CacheRepository
from src.domain import ModelPricing, ModelRef, PricingTier
from src.pricing.catalog import PricingCatalog
from src.pricing.github_copilot import (
    CACHE_KEY, CACHE_NAMESPACE, GitHubCopilotPricingProvider, _catalog_from_payload, _catalog_payload,
)
from src.pricing.metadata_health import MetadataHealthStore, read_state, recent_events
from src.pricing.release_metadata import (
    MetadataAttempt, SourceResult, enrich_release_dates, merge_release_dates, stage_flags,
)
from src.watch.model_discovery import NEW_NOTICE_MS, WatchModelDiscovery

NOW = int(datetime(2026, 10, 8, 12, tzinfo=timezone.utc).timestamp() * 1000)
FEED = ("<rss><channel><item><title>Unrelated news</title>"
        "<pubDate>Wed, 07 Oct 2026 11:00:00 +0000</pubDate></item></channel></rss>")


def model(name: str, publisher: str = "OpenAI", date: str | None = None) -> ModelPricing:
    meta = {"publisher": publisher, **({"release_date": date} if date else {})}
    tier = PricingTier(per_million_input=Decimal(1), per_million_cache_read=Decimal("0.1"), per_million_output=Decimal(5))
    return ModelPricing(ModelRef("github-copilot", name.lower().replace(" ", "-"), name), "USD",
                        per_million_input=Decimal(1), per_million_cache_read=Decimal("0.1"),
                        per_million_output=Decimal(5), tiers=(tier,), metadata=meta)


def field_models(dated: bool = False) -> tuple[ModelPricing, ...]:
    """The real v80.15 failure: 32 priced Copilot models, the relevant one already present."""
    others = tuple(model(f"GPT-Test-{i}", date="2025-01-01" if dated else None) for i in range(1, 32))
    return (model("Claude Haiku 5.5", "Anthropic"), *others)


MODELS_DEV = {"anthropic/claude-haiku-5-5": {"name": "Claude Haiku 5.5", "release_date": "2026-10-07"},
              **{f"openai/gpt-test-{i}": {"name": f"GPT-Test-{i}", "release_date": "2025-01-01"} for i in range(1, 31)}}


class Network:
    """Fake HTTPS: never touches the real network."""

    def __init__(self, failure: BaseException | None) -> None:
        self.failure = failure
        self.calls: list[str] = []

    def __call__(self, url: str, timeout: int) -> str:
        self.calls.append(url)
        if "docs.github.com" in url:
            raise AssertionError("fresh pricing must not be refetched for metadata")
        if self.failure is not None:
            raise self.failure
        return json.dumps(MODELS_DEV) if "models.dev" in url else FEED


def http_error(code: int, retry_after: str | None = None) -> urllib.error.HTTPError:
    headers = Message()
    if retry_after:
        headers["Retry-After"] = retry_after
    return urllib.error.HTTPError("https://example.invalid", code, "private reason", headers, None)


class FieldFixture:
    def __init__(self, root: Path, failure: BaseException | None) -> None:
        database = CacheDatabase(root)
        database.initialize()
        self.repository = CacheRepository(database)
        fresh = PricingCatalog(models=field_models(), retrieved_at_ms=NOW - 600_000, source_revision="rev")
        self.repository.put(CACHE_NAMESPACE, CACHE_KEY, _catalog_payload(fresh), algorithm_version="pricing-1")
        self.clock = [NOW]
        self.network = Network(failure)
        self.provider = GitHubCopilotPricingProvider(
            cache=self.repository, max_age_hours=1, fetch_text=self.network, now_ms=lambda: self.clock[0],
            metadata_store=MetadataHealthStore(root), defer_metadata_refresh=True,
        )
        self.pinned = self.provider.get_catalog()  # ReportService/CCost pin
        source = SimpleNamespace(available_model_ids=lambda: ("github-copilot/claude-haiku-5.5",))
        service = SimpleNamespace(pricing_provider=self.provider, selection=SimpleNamespace(source=source),
                                  _load_catalog=lambda: self.pinned, cache_repository=self.repository)
        self.watch = WatchModelDiscovery(service, run_async=lambda work: work())

    def refresh(self, at: int) -> None:
        self.clock[0] = at
        self.watch.refresh(at)


class FieldRegressionTests(unittest.TestCase):
    """Priority regression: 32 priced models, 0 dates, fresh cache, model already in V2."""

    def test_incomplete_metadata_is_detected_refreshed_and_self_heals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fx = FieldFixture(root, urllib.error.URLError(socket.gaierror(11001, "secret-host")))
            self.assertEqual([], fx.network.calls)
            self.assertEqual("missing_release_dates", fx.provider.metadata_refresh_reason(fx.pinned, now_ms=NOW))

            fx.refresh(NOW)  # Watch start: metadata fetched despite the fresh 60-minute price cache
            self.assertTrue(any("models.dev" in url for url in fx.network.calls))
            self.assertEqual("", fx.watch.notice(NOW))
            state = read_state(root)
            self.assertEqual("unavailable", state["health"])
            self.assertEqual("dns_failure", state["sources"]["models.dev"]["last_error"]["code"])
            self.assertEqual(NOW + 60_000, state["next_retry_ms"])
            log_text = "".join(p.read_text(encoding="utf-8") for p in (root / "logs/errors").glob("*.log"))
            self.assertNotIn("secret", log_text)
            self.assertEqual("failure_started", recent_events(root)[0]["event"])

            calls = len(fx.network.calls)
            fx.refresh(NOW + 30_000)  # inside backoff: no traffic, skip reason recorded
            self.assertEqual(calls, len(fx.network.calls))
            self.assertEqual("backoff", read_state(root)["last_skip"]["reason"])
            fx.refresh(NOW + 61_000)
            self.assertGreater(len(fx.network.calls), calls)
            self.assertEqual(NOW + 361_000, read_state(root)["next_retry_ms"])

            fx.network.failure = None  # external source works again: no user action, no restart
            fx.refresh(NOW + 361_000)
            fx.refresh(NOW + 361_001)
            self.assertEqual("✦ New Models: Claude Haiku 5.5 (2026-10-07)", fx.watch.notice(NOW + 361_001))
            state = read_state(root)
            self.assertEqual("healthy", state["health"])
            self.assertEqual(2, state["sources"]["models.dev"]["last_recovery"]["failed_attempts"])
            self.assertIn("recovered", [event["event"] for event in recent_events(root)])
            self.assertEqual(["unavailable", "healthy"], [item["health"] for item in state["history"]])

            # CCost pin and pricing signature inputs never change through metadata recovery.
            self.assertFalse(any(m.metadata.get("release_date") for m in fx.pinned.models))
            cached = _catalog_from_payload(fx.repository.get(CACHE_NAMESPACE, CACHE_KEY).payload)
            self.assertEqual((NOW - 600_000, "rev"), (cached.retrieved_at_ms, cached.source_revision))
            self.assertEqual(31, sum(bool(m.metadata.get("release_date")) for m in cached.models))

    def test_report_mode_refreshes_inline_and_new_install_without_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fx = FieldFixture(Path(tmp), None)
            inline = GitHubCopilotPricingProvider(cache=fx.repository, max_age_hours=1, fetch_text=fx.network,
                                                  now_ms=lambda: NOW, metadata_store=MetadataHealthStore(None))
            catalog = inline.get_catalog()
            self.assertEqual("2026-10-07", catalog.resolve("Claude Haiku 5.5").metadata["release_date"])
            self.assertEqual("models.dev", catalog.resolve("Claude Haiku 5.5").metadata["release_date_source"])


class ClassificationTests(unittest.TestCase):
    def attempt(self, failure: BaseException | None = None, *, models_dev: str | None = None, feed: str = FEED):
        def fetch(url: str, timeout: int) -> str:
            if "models.dev" in url:
                if failure is not None:
                    raise failure
                return models_dev if models_dev is not None else json.dumps(MODELS_DEV)
            return feed
        return enrich_release_dates(field_models(), (), fetch)

    def test_transport_and_content_failures_have_stable_codes_and_phases(self) -> None:
        cases = {
            "dns_failure": urllib.error.URLError(socket.gaierror(-2, "x")),
            "connection_failure": urllib.error.URLError(ConnectionRefusedError()),
            "tls_failure": urllib.error.URLError(ssl.SSLCertVerificationError("x")),
            "timeout": TimeoutError(),
        }
        for code, failure in cases.items():
            result = self.attempt(failure)[1].sources[0]
            self.assertEqual(("failed", code), (result.status, result.code), code)
        self.assertEqual(15, self.attempt(urllib.error.URLError(socket.timeout()))[1].sources[0].timeout_seconds)
        for status in (403, 429, 500):
            result = self.attempt(http_error(status))[1].sources[0]
            self.assertEqual(("http_error", status), (result.code, result.http_status))
        self.assertEqual(120, self.attempt(http_error(429, "120"))[1].sources[0].retry_after_seconds)
        content = {"json_parse_error": "not json", "invalid_schema": "[]", "missing_fields": '{"a/b": {"x": 1}}',
                   "zero_matches": '{"openai/other": {"name": "Other", "release_date": "2026-01-01"}}'}
        for code, body in content.items():
            self.assertEqual(code, self.attempt(models_dev=body)[1].sources[0].code, code)
        self.assertEqual("invalid_schema", self.attempt(models_dev="{}")[1].sources[0].code)  # empty result
        for feed, code in (("<rss", "xml_parse_error"), ("<rss><channel/></rss>", "invalid_schema")):
            self.assertEqual(code, self.attempt(feed=feed)[1].sources[1].code)

    def test_successful_http_with_unusable_content_is_not_success(self) -> None:
        result = self.attempt(models_dev='{"openai/other": {"name": "Other", "release_date": "2026-01-01"}}')[1]
        self.assertTrue(result.failed)
        self.assertEqual({"https": True, "parse": True, "schema": True, "match": False},
                         stage_flags(result.sources[0].as_dict()))

    def test_partial_matches_and_single_working_source(self) -> None:
        models, attempt = self.attempt()
        self.assertEqual(("ok", "partial_matches", 31), (attempt.sources[0].status, attempt.sources[0].code, attempt.sources[0].matched))
        feed = ("<rss><channel><item><title>Claude Haiku 5.5 in GitHub Copilot</title>"
                "<pubDate>Wed, 07 Oct 2026 11:00:00 +0000</pubDate></item></channel></rss>")
        models, attempt = self.attempt(http_error(503), feed=feed)
        self.assertEqual("partial", attempt.health)
        self.assertEqual(("failed", "ok"), (attempt.sources[0].status, attempt.sources[1].status))
        self.assertEqual("github-changelog", models[0].metadata["release_date_source"])

    def test_failed_refresh_keeps_31_verified_dates_as_cache_fallback(self) -> None:
        previous = (model("Claude Haiku 5.5", "Anthropic"), *field_models(dated=True)[1:])
        merged, attempt = enrich_release_dates(field_models(), previous,
                                               lambda *_: (_ for _ in ()).throw(urllib.error.URLError(TimeoutError())))
        self.assertEqual(31, attempt.dated_models)
        self.assertTrue(attempt.cache_fallback)
        self.assertEqual("partial", attempt.health)

    def test_dates_never_move_to_a_neighbouring_or_renamed_identity(self) -> None:
        previous = (model("Claude Haiku 4.5", "Anthropic", "2025-10-15"),)
        current = (model("Claude Haiku 4.6", "Anthropic"),
                   ModelPricing(ModelRef("github-copilot", "claude-haiku-4.5", "Claude Haiku 4.5 Preview"), "USD",
                                metadata={"publisher": "Anthropic"}))
        merged, carried = merge_release_dates(current, previous)
        self.assertEqual((0, ("", "")), (carried, tuple(m.metadata.get("release_date", "") for m in merged)))


class ScheduleAndPersistenceTests(unittest.TestCase):
    failure = MetadataAttempt((SourceResult("models.dev", "failed", "dns_failure", "dns"),), 32, 0, False)
    success = MetadataAttempt((SourceResult("models.dev", "ok", "partial_matches", "complete", matched=31),), 32, 31, False)

    def test_backoff_survives_restart_and_recovery_spans_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = MetadataHealthStore(Path(tmp))
            first.record(self.failure, NOW, reason="missing_release_dates")
            restarted = MetadataHealthStore(Path(tmp))
            self.assertEqual("", restarted.refresh_reason(priced=32, dated=0, retrieved_at_ms=NOW, now_ms=NOW + 30_000))
            self.assertEqual("missing_release_dates",
                             restarted.refresh_reason(priced=32, dated=0, retrieved_at_ms=NOW, now_ms=NOW + 60_000))
            restarted.record(self.success, NOW + 60_000, reason="missing_release_dates")
            recovered = [e for e in recent_events(Path(tmp)) if e["event"] == "recovered"]
            self.assertEqual((1, 60_000, "dns_failure"),
                             (recovered[0]["attempts"], recovered[0]["duration_ms"], recovered[0]["previous_error_code"]))

    def test_long_outage_is_bounded_and_does_not_spam_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = MetadataHealthStore(Path(tmp))
            attempts = 0
            for at in range(NOW, NOW + 24 * 3_600_000, 5_000):  # a Watch poll every 5 seconds for 24 h
                if store.refresh_reason(priced=32, dated=0, retrieved_at_ms=NOW, now_ms=at):
                    store.record(self.failure, at, reason="poll")
                    attempts += 1
            self.assertLessEqual(attempts, 28)  # 1, 5, 15 minutes, then hourly
            events = [e["event"] for e in recent_events(Path(tmp))]
            self.assertEqual(["failure_started", "failure_summary", "failure_summary", "failure_summary"], events)

    def test_retry_after_is_respected_and_changed_failure_is_logged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = MetadataHealthStore(Path(tmp))
            limited = MetadataAttempt((SourceResult("models.dev", "failed", "http_error", "fetch", http_status=429,
                                                    retry_after_seconds=7200),), 32, 0, False)
            store.record(self.failure, NOW, reason="x")
            store.record(limited, NOW + 1, reason="x")
            self.assertEqual(NOW + 1 + 7_200_000, store.state["next_retry_ms"])
            changed = recent_events(Path(tmp))[-1]
            self.assertEqual(("failure_changed", "dns_failure", 429),
                             (changed["event"], changed["previous_error_code"], changed["http_status"]))

    def test_test_mode_store_never_writes_files(self) -> None:
        store = MetadataHealthStore(None)
        store.record(self.failure, NOW, reason="x")
        self.assertEqual(1, store.state["consecutive_failures"])


class BlockingProvider:
    def __init__(self) -> None:
        self.release = threading.Event()
        self.started = 0

    def get_catalog(self, *, force=False):
        return PricingCatalog(models=field_models(), retrieved_at_ms=NOW)

    def metadata_refresh_reason(self, catalog, *, now_ms, hint=""):
        return "missing_release_dates"

    def refresh_release_metadata(self, *, reason):
        self.started += 1
        self.release.wait(5)
        return None


class WatchIntegrationTests(unittest.TestCase):
    def test_worker_never_blocks_polling_and_runs_one_at_a_time(self) -> None:
        provider = BlockingProvider()
        catalog = provider.get_catalog()
        service = SimpleNamespace(pricing_provider=provider, selection=SimpleNamespace(source=None),
                                  _load_catalog=lambda: catalog)
        watch = WatchModelDiscovery(service)
        started = time.monotonic()
        for offset in range(5):
            watch.refresh(NOW + offset)
        self.assertLess(time.monotonic() - started, 1.0)
        provider.release.set()
        deadline = time.monotonic() + 5
        while watch.diagnostics(NOW)["metadata_refresh_active"] and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(1, provider.started)

    def test_first_v2_read_requests_metadata_but_marks_nothing_new(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fx = FieldFixture(Path(tmp), None)
            fx.provider.metadata.state.update(last_attempt_ms=NOW, last_complete_ms=NOW - 2 * 3_600_000,
                                              consecutive_failures=0)
            dated = PricingCatalog(models=(model("Claude Haiku 5.5", "Anthropic"), *field_models(dated=True)[1:]),
                                   retrieved_at_ms=NOW - 600_000)
            fx.watch.service._load_catalog = lambda: dated
            fx.watch.refresh(NOW)
            self.assertEqual("v2_undated_model", fx.watch.diagnostics(NOW)["last_metadata_refresh_reason"])
            self.assertEqual(0, fx.watch.diagnostics(NOW)["v2_price_refresh_triggers"])


class NoticeTests(unittest.TestCase):
    def watch(self, catalog, repository=None):
        provider = SimpleNamespace(current=catalog)
        provider.get_catalog = lambda force=False: provider.current
        service = SimpleNamespace(pricing_provider=provider, selection=SimpleNamespace(source=None),
                                  _load_catalog=lambda: catalog, cache_repository=repository)
        return WatchModelDiscovery(service), provider

    def test_old_verified_date_hides_a_newly_discovered_model(self) -> None:
        watch, provider = self.watch(PricingCatalog(models=(model("Old"),), retrieved_at_ms=1))
        watch.refresh(NOW)
        provider.current = PricingCatalog(models=(model("Old"), model("Late Listing", date="2025-01-01")), retrieved_at_ms=2)
        watch.refresh(NOW + 3_600_000)
        self.assertEqual("", watch.notice(NOW + 3_600_000))

    def test_catalog_history_without_date_lasts_seven_days_without_duplicates(self) -> None:
        watch, provider = self.watch(PricingCatalog(models=(model("Old"),), retrieved_at_ms=1))
        watch.refresh(NOW)
        provider.current = PricingCatalog(models=(model("Old"), model("Fresh")), retrieved_at_ms=2)
        watch.refresh(NOW + 3_600_000)
        watch.refresh(NOW + 3_600_001, resumed=True)
        self.assertEqual("✦ New Models: Fresh", watch.notice(NOW + 3_600_001))
        expired = NOW + 3_600_000 + NEW_NOTICE_MS
        watch.refresh(expired)
        self.assertEqual("", watch.notice(expired))

    def test_model_added_while_watch_was_closed_is_new_after_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            database = CacheDatabase(Path(tmp))
            database.initialize()
            repository = CacheRepository(database)
            self.watch(PricingCatalog(models=(model("Old"),), retrieved_at_ms=1), repository)[0].refresh(NOW)
            restarted = self.watch(PricingCatalog(models=(model("Old"), model("Fresh")), retrieved_at_ms=2), repository)[0]
            restarted.refresh(NOW + 86_400_000)
            self.assertEqual("✦ New Models: Fresh", restarted.notice(NOW + 86_400_000))


if __name__ == "__main__":
    unittest.main()
