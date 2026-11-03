"""Cross-platform regression checks for live Watch model discovery."""
from __future__ import annotations

import threading
import time
import unittest
import tempfile
import sqlite3
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from development.tests.fixtures.sqlite_faults import SQLiteFaults
from development.tests.fixtures.watch_runtime import MutableSource, make_service
from development.tests.fixtures.session_snapshots import make_uncompacted_snapshot
from src.cache import CacheDatabase, CacheRepository
from src.domain import ModelPricing, ModelRef
from src.pricing.catalog import PricingCatalog
from src.runtime_errors import RuntimeErrors
from src.watch.coordinator import WatchCoordinator
from src.watch.model_discovery import WatchModelDiscovery


def catalog(*names, retrieved=1, dated=()):
    models = tuple(ModelPricing(
        model=ModelRef(provider="github-copilot", model=name.lower().replace(" ", "-"),
                       display_name=name),
        currency="USD", per_million_input=Decimal(1), per_million_output=Decimal(5),
        metadata={"release_date": "2026-10-08"} if name in dated else {},
    ) for name in names)
    return PricingCatalog(models=models, retrieved_at_ms=retrieved)


class FakeProvider:
    def __init__(self, catalog_value):
        self.current = catalog_value
        self.calls = 0

    def get_catalog(self, *, force=False):
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
        return WatchModelDiscovery(service, run_async=lambda work: work()), provider, source

    def test_catalog_updates_after_hour_without_touching_baseline(self):
        observer, provider, source = self.make_discovery()
        observer.refresh(1_000)
        self.assertEqual(0, provider.calls)
        provider.current = catalog("Old", "New Claude", retrieved=3_601_000)
        observer.refresh(3_601_001)
        self.assertEqual(1, provider.calls)
        self.assertIn("New Claude", observer.notice(3_601_001))
        self.assertIn("✦ New Models:", observer.notice(3_601_001))
        self.assertEqual(1, observer.service._load_catalog().retrieved_at_ms)

    def test_new_dated_model_visible_in_notice(self):
        observer, provider, source = self.make_discovery()
        observer.refresh(1_000)
        provider.current = catalog("Old", "Claude New", dated=("Claude New",))
        observer.refresh(3_601_001)
        self.assertIn("✦ New Models:", observer.notice(1791500000000))

    def test_new_available_without_price_uses_pending_notice(self):
        observer, provider, source = self.make_discovery()
        observer.refresh(1_000)
        source.models = ("github-copilot/old", "github-copilot/new-model")
        observer.refresh(901_001)
        self.assertEqual("", observer.notice(901_001))
        self.assertEqual(1, provider.calls)

    def test_v2_hint_forces_catalog_even_with_fresh_hourly_cache(self):
        observer, provider, source = self.make_discovery()
        observer.refresh(1_000)
        provider.current = catalog("Old", "New Model")
        source.models = ("github-copilot/old", "github-copilot/new-model")
        observer.refresh(901_001)
        self.assertEqual(1, provider.calls)
        self.assertIn("New Model", observer.notice(901_001))
        self.assertEqual(1, observer.diagnostics(901_001)["v2_price_refresh_triggers"])

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
        # Resume reads the (possibly cached) catalog; the novel V2 ID then forces a bypass.
        self.assertEqual(3, provider.calls)
        self.assertIn("New Model", observer.notice(3_601_002))

    def test_price_outage_keeps_previous_catalog(self):
        observer, provider, source = self.make_discovery()
        observer.refresh(1_000)
        provider.get_catalog = lambda **kwargs: (_ for _ in ()).throw(OSError("synthetic"))
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

class OptionalCachePollTests(unittest.TestCase):
    def test_synchronous_pragma_failure_during_observe_does_not_stop_normal_watch_poll(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = MutableSource(make_uncompacted_snapshot(running=True))
            config, selection, service, _ = make_service(tmp, source)
            notice_database = CacheDatabase(Path(tmp) / "notices")
            notice_database.initialize()
            repository = CacheRepository(notice_database)
            clock = [2200]
            watch = WatchCoordinator(selection=selection, report_service=service, config=config,
                                     clock_ms=lambda: clock[0], record_observations=False)
            self.addCleanup(watch.close)
            provider = FakeProvider(catalog("Old"))
            watch.model_discovery = WatchModelDiscovery(SimpleNamespace(
                pricing_provider=provider, _load_catalog=lambda: catalog("Old"),
                cache_repository=repository), run_async=lambda work: work())
            initial = watch.initialize().projection
            faults = SQLiteFaults(notice_database)
            faults.phase = "pragma"
            provider.current = catalog("Old", "Fresh")

            with faults.install():
                clock[0] += 3_600_000
                during = watch.poll_once(force_resync=True).projection
                source.snapshot = replace(make_uncompacted_snapshot(running=False), source_revision="updated")
                clock[0] += 5000
                subsequent = watch.poll_once(force_resync=True).projection

            self.assertGreater(faults.failures, 0)
            self.assertEqual(faults.opened, faults.closed)
            initial_prompt = next(row.prompt for row in initial.rows if row.prompt.event_id == "u_next")
            during_prompt = next(row.prompt for row in during.rows if row.prompt.event_id == "u_next")
            subsequent_prompt = next(row.prompt for row in subsequent.rows if row.prompt.event_id == "u_next")
            self.assertEqual(initial_prompt.ccost, during_prompt.ccost)
            self.assertEqual((initial_prompt.calls, initial_prompt.incoming_context_tokens, initial_prompt.token_mix_percent),
                             (during_prompt.calls, during_prompt.incoming_context_tokens, during_prompt.token_mix_percent))
            self.assertTrue(during_prompt.in_progress)
            self.assertFalse(subsequent_prompt.in_progress)
            self.assertIn("Fresh", watch.model_discovery.notice(clock[0]))
            self.assertEqual("unavailable", watch.model_discovery.diagnostics(clock[0])["notice_cache"]["status"])


class OptionalNoticeCacheTests(unittest.TestCase):
    def discovery(self, root):
        database = CacheDatabase(root)
        database.initialize()
        repository = CacheRepository(database)
        provider = FakeProvider(catalog("Old"))
        service = SimpleNamespace(pricing_provider=provider, _load_catalog=lambda: catalog("Old"),
                                  cache_repository=repository)
        return WatchModelDiscovery(service, run_async=lambda work: work()), provider, repository

    def test_startup_read_outage_does_not_invent_models_or_overwrite_unread_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            watch, provider, repository = self.discovery(Path(tmp))
            repository.put("watch.model-discovery", "known-catalog-ids", ["older"])
            repository.put("watch.model-discovery", "recent-discoveries", {"earlier": ["Earlier", 900]})
            faults = SQLiteFaults(repository.database)
            faults.phase = "read"

            with faults.install():
                watch.refresh(1000)
                self.assertEqual("", watch.notice(1000))
                self.assertEqual("read", watch.diagnostics(1000)["notice_cache"]["phase"])
                for now in range(2000, 61_000, 1000):
                    watch.refresh(now)
                self.assertEqual(1, faults.failures)
                faults.phase = ""
                watch.refresh(61_000)

            self.assertEqual("ok", watch.diagnostics(61_000)["notice_cache"]["status"])
            self.assertNotIn("Old", watch.notice(61_000))
            self.assertEqual({"earlier": ["Earlier", 900]},
                             repository.get("watch.model-discovery", "recent-discoveries").payload)
            self.assertEqual(0, provider.calls)
            self.assertEqual(faults.opened, faults.closed)

    def test_write_and_commit_outages_retry_dirty_state_and_log_sanitized_recovery(self):
        for phase in ("pragma", "write", "commit"):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                watch, provider, repository = self.discovery(root)
                reporter = RuntimeErrors(root)
                reporter.install()
                self.addCleanup(reporter.uninstall)
                watch.refresh(1000)
                faults = SQLiteFaults(repository.database)
                faults.phase = phase
                faults.error.sqlite_errorcode = sqlite3.SQLITE_IOERR_WRITE
                provider.current = catalog("Old", "Fresh")

                with faults.install():
                    watch.refresh(3_601_000)
                    text, spans = watch.notice_details(3_601_000)
                    self.assertIn("Fresh", text)
                    self.assertEqual((), spans, "failed shared evidence must not highlight a timestamp")
                    for now in range(3_606_000, 3_661_000, 5000):
                        watch.refresh(now)
                        watch.notice(now)
                    self.assertEqual(2, faults.failures, "one attempt for each optional component")
                    self.assertEqual(phase, watch.diagnostics(now)["notice_cache"]["phase"])
                    faults.phase = ""
                    watch.refresh(3_661_000)
                    text, spans = watch.notice_details(3_661_000)

                self.assertTrue(spans)
                self.assertEqual("ok", watch.diagnostics(3_661_000)["notice_cache"]["status"])
                self.assertEqual(["fresh", "old"], repository.get(
                    "watch.model-discovery", "known-catalog-ids").payload)
                self.assertEqual({"fresh": ["Fresh", 3_601_000]}, repository.get(
                    "watch.model-discovery", "recent-discoveries").payload)
                self.assertEqual("1970-01-01T01:00:01.000Z", repository.get_or_create_model_first_seen_at(
                    "github-copilot/fresh", "later"))
                self.assertEqual(1, provider.calls, "cache recovery must not fetch models")
                logs = "".join(p.read_text(encoding="utf-8") for p in (root / "logs/errors").glob("*.log"))
                self.assertNotIn("private path/token", logs)
                self.assertIn("SQLite code: 778", logs)
                self.assertIn(f"Cache phase: {phase}", logs)
                self.assertEqual(2, logs.count("Component later recovered."))
                self.assertFalse((root / "logs/crashes").exists())
                self.assertEqual(faults.opened, faults.closed)
                self.assertEqual(2, faults.rollbacks)
                reporter.uninstall()

    def test_sustained_outage_has_bounded_attempts_and_failure_change_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            watch, _, repository = self.discovery(root)
            reporter = RuntimeErrors(root)
            reporter.install()
            self.addCleanup(reporter.uninstall)
            faults = SQLiteFaults(repository.database)
            faults.phase = "pragma"
            with faults.install():
                for now in range(1000, 86_401_000, 5000):
                    watch.refresh(now)
                self.assertLessEqual(faults.failures, 28)
                self.assertEqual("unavailable", watch.diagnostics(now)["notice_cache"]["status"])
                faults.phase = "read"
                watch.refresh(watch.diagnostics(now)["notice_cache"]["next_retry_ms"])
            logs = "".join(p.read_text(encoding="utf-8") for p in (root / "logs/errors").glob("*.log"))
            self.assertIn("Failure changed.", logs)
            self.assertEqual(2, logs.count("Severity: recoverable"))
            self.assertLess(len(logs), 10_000)
            self.assertEqual(faults.opened, faults.closed)

    def test_real_readonly_connection_and_unavailable_directory_are_optional(self):
        with tempfile.TemporaryDirectory() as tmp:
            watch, _, repository = self.discovery(Path(tmp))
            connect = sqlite3.connect
            readonly_uri = repository.database.paths.database.as_uri() + "?mode=ro"
            with patch("src.cache.database.sqlite3.connect", lambda *a, **kw: connect(readonly_uri, uri=True, **kw)):
                watch.refresh(1000)
            self.assertEqual(sqlite3.SQLITE_READONLY, watch.diagnostics(1000)["notice_cache"]["sqlite_code"])
            self.assertEqual("", watch.notice(1000))
            watch.refresh(61_000)
            self.assertEqual("ok", watch.diagnostics(61_000)["notice_cache"]["status"])
            provider = watch.service.pricing_provider
            provider.current = catalog("Old", "Fresh")
            mkdir = Path.mkdir

            def unavailable(path, *args, **kwargs):
                if path == repository.database.paths.directory:
                    raise PermissionError("private path")
                return mkdir(path, *args, **kwargs)

            with patch.object(Path, "mkdir", unavailable):
                watch.refresh(3_601_000)
            self.assertEqual("connect", watch.diagnostics(3_601_000)["notice_cache"]["phase"])
            watch.refresh(3_661_000)
            self.assertEqual("ok", watch.diagnostics(3_661_000)["notice_cache"]["status"])

    def test_schema_and_programming_errors_are_not_silently_isolated(self):
        corrupt = sqlite3.DatabaseError("corruption")
        corrupt.sqlite_errorcode = sqlite3.SQLITE_CORRUPT
        for error in (sqlite3.ProgrammingError("bug"), sqlite3.IntegrityError("invariant"), corrupt,
                      sqlite3.OperationalError("SQL/schema error")):
            if isinstance(error, sqlite3.OperationalError):
                error.sqlite_errorcode = sqlite3.SQLITE_ERROR
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as tmp:
                watch, _, repository = self.discovery(Path(tmp))
                faults = SQLiteFaults(repository.database)
                faults.phase, faults.error = "read", error
                with faults.install(), self.assertRaises(type(error)):
                    watch.refresh(1000)
                self.assertEqual(faults.opened, faults.closed)


class AsyncDiscoveryTests(unittest.TestCase):
    def test_slow_reads_never_block_refresh_and_results_apply_on_a_later_poll(self):
        release = threading.Event()
        initial = catalog("Old", retrieved=1)
        provider = FakeProvider(catalog("Old", "New Model", retrieved=2))
        source = AvailableSource()
        blocked_reads = []

        def slow_read():
            blocked_reads.append(1)
            release.wait(5)
            return ("github-copilot/old", "github-copilot/new-model")

        source.available_model_ids = slow_read
        service = SimpleNamespace(pricing_provider=provider, selection=SimpleNamespace(source=source),
                                  _load_catalog=lambda: initial)
        observer = WatchModelDiscovery(service)
        started = time.monotonic()
        observer.refresh(1_000)
        observer.refresh(901_001)  # due again while the first read is still running
        self.assertLess(time.monotonic() - started, 1.0)
        self.assertEqual(1, len(blocked_reads), "one worker; overlapping requests merge")
        self.assertTrue(observer.diagnostics(901_001)["discovery_check_active"])
        release.set()
        deadline = time.monotonic() + 5
        while (observer.available_ids is None or len(blocked_reads) < 2) and time.monotonic() < deadline:
            observer.refresh(901_002)
            time.sleep(0.01)
        self.assertEqual(2, len(observer.available_ids))
        self.assertEqual(2, len(blocked_reads), "the merged request ran after the first completed")


if __name__ == "__main__":
    unittest.main()
