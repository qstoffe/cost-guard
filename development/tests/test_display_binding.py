"""The archive cannot be rebound from a client hint or a reused local path."""
from contextlib import closing
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import sqlite3
import unittest

from src.cache.display_history import SessionChange, SessionFact
from src.application.session_catalog import SessionCatalog
from src.sources.errors import FailureCode, SourceUnavailableError
from src.sources.opencode_v1 import OpenCodeV1Source
from src.domain import NormalizedSession, Provenance, SessionCapabilities
from src.reports.models import SessionUsageRow
from src.watch.observers import CatalogObservation
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


def v1_driver(root):
    path = root / "source"
    path.write_bytes(b"test source identity only")
    service = SimpleNamespace(selection=SimpleNamespace(selected="v1", source=OpenCodeV1Source(path)), timezone_id="UTC")
    return SimpleNamespace(coordinator=SimpleNamespace(report_service=service, catalog_observation=None),
                           error=None, terminal=False)
