"""The archive cannot be rebound from a client hint or a reused local path."""
from contextlib import closing
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import sqlite3
import unittest
from unittest.mock import patch

from development.tests.fixtures.opencode_v1_database import create_v1_database
from development.tests.fixtures.report_runtime import FakePricingProvider
from src.cache import CacheDatabase, CacheRepository
from src.cache.display_history import SessionChange, SessionFact
from src.application.session_catalog import SessionCatalog
from src.domain import NormalizedSession, Provenance, SessionCapabilities
from src.reports.models import SessionUsageRow
from src.reports.service import ReportService
from src.sources.errors import FailureCode, SourceUnavailableError
from src.sources.opencode_v1 import OpenCodeV1Source
from src.sources.selection import SourceSelection
from src.watch.observers import CatalogObservation, observe_catalog
from src.web.display_archive import DisplayArchive
from src.web.display_binding import selected_display_binding


class DisplayBindingTests(unittest.TestCase):
    def test_local_mutation_keeps_scope_but_replacing_same_path_does_not(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)
            path = directory / "fixture"
            path.write_bytes(b"original")
            selected = SimpleNamespace(selected="v1", source=OpenCodeV1Source(path))
            initial = selected_display_binding(selected)

            path.write_bytes(b"more bytes in the same file")
            still_same = selected_display_binding(selected)
            replacement = directory / "replacement"
            replacement.write_bytes(b"separate fixture")
            replacement.replace(path)
            changed = selected_display_binding(selected)

        self.assertIsNotNone(initial)
        self.assertEqual(initial, still_same)
        self.assertIsNotNone(changed)
        self.assertNotEqual(initial.scope, changed.scope)

    def test_missing_local_binding_is_not_replaced_with_the_last_archive(self):
        with TemporaryDirectory() as tmp:
            source = OpenCodeV1Source(Path(tmp) / "missing")

            binding = selected_display_binding(SimpleNamespace(selected="v1", source=source))

        self.assertIsNone(binding)

    def test_startup_reads_warm_rows_before_any_new_catalog_and_revokes_on_auth_failure(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            driver = v1_driver(root)
            notifications = []
            archive = DisplayArchive(root, lambda kind, value: notifications.append((kind, value)))
            archive.initialize()
            source = selected_display_binding(driver.coordinator.report_service.selection).scope
            archive.history.commit_sessions(source, (SessionChange(SessionFact("saved", "r1", "Saved"), None),))

            archive.observe(driver, before_tick=True)
            rows = archive.views.page(period="all")["rows"]
            driver.error = SourceUnavailableError("Authentication rejected", code=FailureCode.AUTH)
            archive.observe(driver, before_tick=False)

            self.assertEqual(["saved"], [row["session_id"] for row in rows])
            self.assertIsNone(archive.views)
            self.assertEqual(("cache", {"view": "sessions", "binding": None}), notifications[-1])
            self.assertEqual(1, archive.history.session_page(source).total)

    def test_source_replacement_withdraws_old_snapshot_until_fresh_catalog(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            driver = v1_driver(root)
            archive = DisplayArchive(root, lambda *_: None)
            archive.initialize()
            archive.observe(driver, before_tick=True)
            initial = archive.views
            driver.coordinator.catalog_observation = object()
            archive.history.commit_sessions(initial.source,
                (SessionChange(SessionFact("prior", "r1", "Prior"), None),))
            replacement = root / "replacement"
            replacement.write_bytes(b"different source")
            replacement.replace(root / "source")

            archive.observe(driver, before_tick=True)
            self.assertIsNone(archive.views)
            archive.observe(driver, before_tick=False)
            self.assertIsNone(archive.views)
            driver.coordinator.catalog_observation = object()
            archive.observe(driver, before_tick=False)

            self.assertNotEqual(initial.source, archive.views.source)
            self.assertEqual(0, archive.views.page(period="all")["cached_total"])
            self.assertEqual(1, archive.history.session_page(initial.source).total)

    def test_publishes_metadata_in_bounded_slices_from_existing_catalog(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            driver = v1_driver(root)
            archive = DisplayArchive(root, lambda *_: None)
            archive.initialize()
            archive.observe(driver, before_tick=True)
            roots = tuple(NormalizedSession(f"root-{i}", f"Title {i}", 1, 2,
                                          Provenance("fixture", f"root-{i}"), SessionCapabilities())
                          for i in range(300))
            revisions = {item.session_id: "revision" for item in roots}
            catalog = SessionCatalog()
            catalog.observe(CatalogObservation(roots, roots, {}, revisions))
            service = driver.coordinator.report_service

            archive.publish_catalog(catalog, service)
            partial = archive.views.page(period="all")
            archive.publish_catalog(catalog, service)
            complete = archive.views.page(period="all")

            self.assertEqual(256, partial["cached_total"])
            self.assertEqual(300, complete["cached_total"])
            self.assertEqual("pending", complete["rows"][0]["fields"]["prompts"])
            self.assertEqual(0, archive.views.page(period="today")["cached_total"])

    def test_incompatible_database_cannot_be_read_as_an_empty_cache(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = DisplayArchive(root, lambda *_: None)
            archive.initialize()
            archive.observe(v1_driver(root), before_tick=True)
            with closing(sqlite3.connect(archive.history.path)) as db:
                db.execute("PRAGMA user_version=999")

            with self.assertRaisesRegex(sqlite3.DatabaseError, "unsupported_display_history_schema"):
                archive.views.page(period="all")
            self.assertFalse(archive.initialize())

    def test_restart_reconciles_source_membership_without_discarding_historical_values(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            driver = v1_driver(root)
            archive = DisplayArchive(root, lambda *_: None)
            archive.initialize()
            archive.observe(driver, before_tick=True)
            source = archive.views.source
            history_row = SessionFact("old", "r1", "Archived title", activity_ms=23, ccost=Decimal("2.15"))
            archive.history.commit_sessions(source, (SessionChange(history_row, None),))
            catalog = SessionCatalog()
            service = driver.coordinator.report_service
            empty = CatalogObservation((), (), {}, {})

            catalog.observe(empty, unavailable=True)
            archive.publish_catalog(catalog, service)
            retained, = archive.views.page(period="all")["rows"]
            catalog.observe(empty)
            archive.publish_catalog(catalog, service)
            absent, = archive.views.page(period="all")["rows"]

            self.assertTrue(retained["source_present"])
            self.assertFalse(absent["source_present"])
            self.assertEqual(("Archived title", "2.15", 23),
                             (absent["title"], absent["ccost"], absent["activity_ms"]))
            self.assertEqual("source-history-missing", absent["fields"]["prompts"])

    def test_settled_summary_uses_the_same_archive_as_metadata_and_refuses_stale_revision(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            driver = v1_driver(root)
            archive = DisplayArchive(root, lambda *_: None)
            archive.initialize()
            archive.observe(driver, before_tick=True)
            service = driver.coordinator.report_service
            row = SessionUsageRow("root", "Settled", "Model", False, Decimal("7.32"), 9)
            admission = archive.admit_summary(service, "root", "r1")

            archive.publish_summary(service, admission, row, "r2")
            self.assertEqual(0, archive.views.page(period="all")["cached_total"])
            archive.publish_summary(service, admission, row, "r1")
            result, = archive.views.page(period="all")["rows"]

            self.assertEqual(("Settled", "7.32", 9), (result["title"], result["ccost"], result["prompts"]))

    def test_unvisited_history_uses_one_root_per_slice_and_restores_qualified_v1_progress(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "fixture.db"
            create_v1_database(path)
            # The stock fixture ends with a synthetic user message. End this
            # disposable source at its earlier, terminal compaction summary.
            with closing(sqlite3.connect(path)) as db:
                db.execute("DELETE FROM part WHERE message_id='msg_synthetic'")
                db.execute("DELETE FROM message WHERE id='msg_synthetic'")
                db.commit()
            source = OpenCodeV1Source(path)
            selection = SourceSelection(source, "v1", (), source.probe())
            database = CacheDatabase(root)
            database.initialize()
            repository = CacheRepository(database)
            service = ReportService(selection=selection, pricing_provider=FakePricingProvider(),
                account_provider=None, cache_repository=repository, config={"timezone": "UTC"},
                now_ms=50_000, progress=lambda _: None)
            driver = SimpleNamespace(coordinator=SimpleNamespace(report_service=service, catalog_observation=None),
                                     error=None, terminal=False)
            archive = DisplayArchive(root, lambda *_: None)
            archive.initialize()
            archive.observe(driver, before_tick=True)
            catalog = SessionCatalog(clock_ms=lambda: 50_000)
            observation = observe_catalog(source, include_archived_revisions=True)
            catalog.observe(observation)

            archive.acquire_summaries(catalog, service)
            first_slice = archive.views.page(period="all")
            archive.acquire_summaries(catalog, service)
            full = archive.views.page(period="all")
            restarted = DisplayArchive(root, lambda *_: None)
            restarted.initialize()
            restarted.observe(driver, before_tick=True)
            with patch.object(service, "_analyze", side_effect=AssertionError("unnecessary source read")) as read:
                restarted.acquire_summaries(catalog, service)
                read.assert_not_called()

            self.assertFalse(catalog.leases)
            self.assertEqual(1, first_slice["cached_total"])
            self.assertEqual({"ses_root", "ses_other"}, {row["session_id"] for row in full["rows"]})
            by_id = {row["session_id"]: row for row in full["rows"]}
            self.assertEqual(0, by_id["ses_other"]["prompts"])
            self.assertEqual(1, by_id["ses_root"]["prompts"])
            self.assertEqual(full["generation"], restarted.views.page(period="all")["generation"])
            with database.connect() as db:
                self.assertEqual(0, db.execute("SELECT count(*) FROM cache_entries").fetchone()[0])

    def test_unreadable_first_root_does_not_starve_later_roots(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            driver = v1_driver(root)
            service = driver.coordinator.report_service
            service._load_catalog = lambda: None
            service._load_comparison_catalog = lambda: SimpleNamespace(diagnostic_signature="pricing")
            service._dependencies = lambda _: "config"
            service.retain_derived_cache_read_only = lambda: None
            clock = [100]
            archive = DisplayArchive(root, lambda *_: None)
            archive.initialize()
            archive.observe(driver, before_tick=True)
            catalog = SessionCatalog(clock=lambda: clock[0], clock_ms=lambda: 50_000)
            roots = tuple(NormalizedSession(key, key, 1, 2, Provenance("fixture", key), SessionCapabilities())
                          for key in ("a", "b", "c"))
            catalog.observe(CatalogObservation(roots, (), {}, dict.fromkeys(("a", "b", "c"), "r")))
            calls = []

            def summary(_service, item, revision, **kwargs):
                calls.append(item.session_id)
                if item.session_id == "a":
                    raise SourceUnavailableError("fixture")
                return SessionUsageRow(item.session_id, item.title, "Model", False, Decimal("1"), 1), revision

            with patch("src.application.session_archive_sweep.session_summary", side_effect=summary):
                for _ in range(4):
                    archive.acquire_summaries(catalog, service)
                self.assertFalse(archive.summary_pending(catalog))
                clock[0] = 160
                self.assertTrue(archive.summary_pending(catalog))
                archive.acquire_summaries(catalog, service)
                archive.acquire_summaries(catalog, service)

            self.assertEqual(["a", "b", "c", "a"], calls)
            self.assertEqual(["b", "c"], [row["session_id"] for row in archive.views.page(period="all")["rows"]])


def v1_driver(root):
    path = root / "source"
    path.write_bytes(b"test source identity only")
    service = SimpleNamespace(selection=SimpleNamespace(selected="v1", source=OpenCodeV1Source(path)), timezone_id="UTC")
    return SimpleNamespace(coordinator=SimpleNamespace(report_service=service, catalog_observation=None),
                           error=None, terminal=False)
