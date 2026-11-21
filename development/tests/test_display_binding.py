"""The archive cannot be rebound from a client hint or a reused local path."""
from contextlib import closing
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
import time
from types import SimpleNamespace
import sqlite3
import unittest
from unittest.mock import patch

from development.tests.fixtures.catalog_prompt_activity import at, finished_snapshot
from development.tests.fixtures.opencode_v1_database import create_v1_database
from development.tests.fixtures.report_runtime import FakePricingProvider
from src.cache import CacheDatabase, CacheRepository
from src.cache.display_history import HistoryState, RunningSession, SessionChange, SessionFact
from src.application.session_catalog import SessionCatalog
from src.application.session_archive_sweep import checkpoint_dependency, scalar_dependency
from src.domain import BackgroundActivity, NormalizedSession, Provenance, SessionCapabilities, TerminalOutcome
from src.reports.models import SessionUsageRow
from src.reports.service import ReportService
from src.sources.errors import FailureCode, SourceUnavailableError
from src.sources.opencode_v1 import OpenCodeV1Source
from src.sources.selection import SourceSelection
from src.watch.observers import CatalogObservation, observe_catalog
from src.web.display_archive import DisplayArchive
from src.web.display_binding import selected_display_binding


class DisplayBindingTests(unittest.TestCase):
    def test_live_publisher_keeps_one_in_flight_snapshot_and_drops_intermediate_offers(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = DisplayArchive(root, lambda *_: None)
            archive.initialize()
            archive.observe(v1_driver(root), before_tick=True)
            committed = archive.sessions.commit_running
            started, release = Event(), Event()

            def held_write(*args, **kwargs):
                started.set()
                if not release.wait(5):
                    raise AssertionError("fixture did not release the SQLite writer")
                committed(*args, **kwargs)

            try:
                with patch.object(archive.sessions, "commit_running", side_effect=held_write) as writes:
                    archive.publish_running((RunningSession("a", "First", 100, 110),))
                    self.assertTrue(started.wait(5))
                    archive.publish_running((RunningSession("b", "Intermediate", 120, 130),))
                    first_job = archive._running_write
                    self.assertFalse(first_job.done())
                    self.assertEqual(1, writes.call_count)
                    release.set()
                    first_job.result(timeout=5)
                    archive.publish_running((RunningSession("c", "Latest", 140, 150),))
                    archive._running_write.result(timeout=5)
                    current = archive.views.page(period="all", now_ms=200)

                self.assertEqual(["c"], [row["session_id"] for row in current["rows"]])
                self.assertEqual(2, writes.call_count)
            finally:
                release.set()
                archive.close()

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
            admission = archive.admit_summary(service, "root", "r1", observation_sequence=1)

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

    def test_same_revision_terminal_waits_for_linked_work_and_retries_without_losing_the_prior_clock(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            driver = v1_driver(root)
            archive = DisplayArchive(root, lambda *_: None)
            self.addCleanup(archive.close)
            archive.initialize()
            archive.observe(driver, before_tick=True)
            source = driver.coordinator.report_service.selection.source
            database = CacheDatabase(root)
            database.initialize()
            now_ms = at("02:00:00")
            service = ReportService(selection=SourceSelection(source, "v1", (), None),
                pricing_provider=FakePricingProvider(), account_provider=None, cache_repository=CacheRepository(database),
                config={"timezone": "UTC"}, now_ms=now_ms, progress=lambda _: None)
            clock = [100]
            catalog = SessionCatalog(clock=lambda: clock[0], clock_ms=lambda: now_ms, display_archive=archive)
            base = finished_snapshot()
            live_root = replace(base.root, active=True)
            key = live_root.session_id
            work = BackgroundActivity("fixture-shell", key, "shell", at("01:17:59"),
                base.messages[-1].message_id, running=True)
            # The catalog still advertises a live candidate, but the fresh
            # hydrated snapshot independently sees the parent's idle state.
            unsettled = replace(base, background=(work,))
            finish = at("01:52:00")
            settled = replace(unsettled, background=(replace(work, running=False, ended_at_ms=finish,
                                                             outcome=TerminalOutcome.SUCCESS),))
            revision = unsettled.source_revision
            catalog.observe(CatalogObservation((live_root,), (live_root,), {}, {key: revision},
                                               live_candidates=frozenset({key})))
            archive.history.commit_sessions(archive.views.source, (SessionChange(
                SessionFact(key, "prior", "Prior", activity_ms=at("01:02:00"), ccost=Decimal("2.15")), None),))
            event = base.events[0]
            start = (live_root, revision, now_ms - 400, event.event_id, event.created_at_ms)
            stop = (live_root, revision, now_ms - 200, event.event_id, event.created_at_ms)
            catalog.observe_prompts(((*start, True, None, False),))
            archive.sessions.commit_running(archive.views.source, archive.views.binding,
                catalog.archive_running(((*start, True, None, False),)), clear_fence=0)
            running, = archive.views.page(period="all", now_ms=now_ms)["rows"]

            with (patch.object(source, "get_session_tree_revision", return_value=revision),
                  patch.object(source, "load_session_snapshot",
                              side_effect=(SourceUnavailableError("fixture"), unsettled, settled)) as load):
                catalog.observe_prompts(((*stop, False, None, True),))
                archive.sessions.commit_running(archive.views.source, archive.views.binding, (), clear_fence=0)
                archive.acquire_summaries(catalog, service)
                failed, = archive.views.page(period="all", now_ms=now_ms)["rows"]
                clock[0] = 102
                archive.acquire_summaries(catalog, service)
                pending, = archive.views.page(period="all", now_ms=now_ms)["rows"]
                clock[0] = 107
                archive.acquire_summaries(catalog, service)
                done, = archive.views.page(period="all", now_ms=now_ms)["rows"]
                catalog.observe_prompts(((*stop, False, None, True), (*start, True, None, False)))
                archive.acquire_summaries(catalog, service)

            self.assertTrue(running["running"])
            self.assertFalse(failed["running"])
            self.assertEqual((at("01:02:00"), "2.15"), (failed["activity_ms"], failed["ccost"]))
            self.assertEqual(failed, pending)
            self.assertEqual(("finish", finish, event.created_at_ms),
                             (done["activity_origin"], done["activity_ms"], done["prompt_started_ms"]))
            self.assertEqual(3, load.call_count)

    def test_recent_corrections_do_not_starve_unvisited_old_roots(self):
        with TemporaryDirectory() as tmp:
            archive, service, catalog, roots = archive_sweep_fixture(Path(tmp))
            self.addCleanup(archive.close)
            calls = []

            def summary(_service, root, revision, **_):
                calls.append((root.session_id, revision))
                return SessionUsageRow(root.session_id, root.title, "Model", False, Decimal("1"), 1), revision

            revisions = dict.fromkeys(("old", "recent"), "r0")
            catalog.observe(CatalogObservation(roots, roots, {}, revisions))
            with patch("src.application.session_archive_sweep.session_summary", side_effect=summary):
                for number in range(1, 6):
                    revisions = {**revisions, "recent": f"r{number}"}
                    catalog.observe(CatalogObservation(roots, roots, {}, revisions))
                    archive.acquire_summaries(catalog, service)

            self.assertEqual([("recent", "r1"), ("recent", "r2"), ("recent", "r3"),
                              ("old", "r0"), ("recent", "r5")], calls)

    def test_outage_during_acquisition_rejects_old_result_even_after_same_revision_recovery(self):
        with TemporaryDirectory() as tmp:
            archive, service, catalog, roots = archive_sweep_fixture(Path(tmp))
            self.addCleanup(archive.close)
            observation = CatalogObservation(roots, roots, {}, dict.fromkeys(("old", "recent"), "r0"))
            catalog.observe(observation)

            def crossed_gap(_service, root, revision, **_):
                catalog.observe(None, unavailable=True)
                catalog.observe(replace(observation))
                return SessionUsageRow(root.session_id, root.title, "Model", False, Decimal("50"), 1), revision

            with patch("src.application.session_archive_sweep.session_summary", side_effect=crossed_gap):
                archive.acquire_summaries(catalog, service)
                stale = archive.views.page(period="all")
            with patch("src.application.session_archive_sweep.session_summary",
                       return_value=(SessionUsageRow("old", "old", "Model", False, Decimal("3"), 1), "r0")):
                archive.acquire_summaries(catalog, service)
                current, = archive.views.page(period="all")["rows"]

            self.assertEqual(0, stale["cached_total"])
            self.assertEqual(("old", "3"), (current["session_id"], current["ccost"]))

    def test_confirmed_clear_fences_pending_writers_and_requires_a_fresh_catalog(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive, service, catalog, roots = archive_sweep_fixture(root)
            self.addCleanup(archive.close)
            observation = CatalogObservation(roots, roots, {}, dict.fromkeys(("old", "recent"), "r0"))
            catalog.observe(observation)
            archive.publish_catalog(catalog, service)
            views = archive.views
            other = "other-source"
            archive.history.commit_sessions(other, (SessionChange(SessionFact("other", "r1", "Other"), None),))
            admission = archive.admit_summary(service, "old", "late", observation_sequence=1)
            start = int(time.time() * 1000)
            offered = (RunningSession("pending", "Pending", start - 10, start),)
            archive.sessions.commit_running(views.source, views.binding, offered, clear_fence=0)
            saved = archive.clear_snapshot()

            archive.clear_confirmed(saved["binding"], HistoryState(saved["generation"], saved["archive_epoch"]),
                                    catalog, service, eligible=lambda: True)
            archive.publish_summary(service, admission,
                SessionUsageRow("old", "Pre-clear", "Model", False, Decimal("4"), 1), "late")
            archive.sessions.commit_running(views.source, views.binding, offered, clear_fence=0)
            archive.sessions.commit_running(views.source, views.binding, offered, clear_fence=1)
            archive.publish_catalog(catalog, service)
            blank = archive.views.page(period="all", now_ms=start + 1)
            catalog.observe(replace(observation))
            archive.publish_catalog(catalog, service)
            rewarmed = archive.views.page(period="all", now_ms=start + 1)

            self.assertEqual(0, blank["cached_total"])
            self.assertEqual(["old", "recent"], [row["session_id"] for row in rewarmed["rows"]])
            self.assertEqual(1, archive.history.session_page(other).total)
            self.assertEqual(b"test source identity only", (root / "source").read_bytes())

    def test_coverage_needs_a_source_roster_and_current_field_proof_and_skips_proven_recent_tail(self):
        with TemporaryDirectory() as tmp:
            archive, service, _, roots = archive_sweep_fixture(Path(tmp))
            self.addCleanup(archive.close)
            now_ms = at("12:00:00")
            old_ms = now_ms - 20 * 86_400_000
            recent_ms = now_ms - 1_000
            clock = [100]
            catalog = SessionCatalog(display_archive=archive, clock=lambda: clock[0], clock_ms=lambda: now_ms)
            revisions = {"old": "r1", "recent": "r1"}
            observed = CatalogObservation(roots, roots, {}, revisions, atomic_archive_roster=True,
                activity_floor={"old": old_ms, "recent": recent_ms})
            catalog.observe(observed)
            archive.publish_catalog(catalog, service)
            full_metadata = archive.views.page(period="all", now_ms=now_ms)

            for _ in range(2):
                archive.check_coverage(catalog, service)
            unknown = archive.views.page(period="today", now_ms=now_ms)
            row = SessionUsageRow("old", "Old", "M", False, Decimal("2"), 1, last_activity_ms=old_ms,
                                  context_qualified=False)
            admission = archive.admit_summary(service, "old", "r1", observation_sequence=1)
            dependency = checkpoint_dependency(scalar_dependency(service), ())
            archive.publish_summary(service, admission, row, "r1", dependency=dependency)
            clock[0] += 5
            for _ in range(2):
                archive.check_coverage(catalog, service)
            today = archive.views.page(period="today", now_ms=now_ms)
            all_time = archive.views.page(period="all", now_ms=now_ms)

            admission = archive.admit_summary(service, "old", "r1", observation_sequence=1)
            archive.publish_summary(service, admission, replace(row, context_qualified=True), "r1", dependency=dependency)
            clock[0] += 5
            for _ in range(2):
                archive.check_coverage(catalog, service)
            settled = archive.views.page(period="all", now_ms=now_ms)
            recent_revision = replace(observed, revisions={"old": "r1", "recent": "r2"})
            catalog.observe(recent_revision)
            recent_recheck = archive.coverage_pending(catalog)

            catalog.observe(replace(recent_revision, revisions={"old": "r2", "recent": "r2"}))
            archive.check_coverage(catalog, service)
            correcting = archive.views.page(period="all", now_ms=now_ms)

            self.assertEqual((2, "pending"), (full_metadata["cached_total"], full_metadata["history_coverage"]))
            self.assertEqual("pending", unknown["history_coverage"], "an unknown old clock can affect any period")
            self.assertEqual("as-of", today["history_coverage"])
            self.assertEqual("pending", all_time["history_coverage"])
            self.assertEqual("as-of", settled["history_coverage"])
            self.assertFalse(recent_recheck, "recent-tail churn must not restart the older walk")
            self.assertEqual("pending", correcting["history_coverage"])
            self.assertEqual("2", next(row["ccost"] for row in correcting["rows"] if row["session_id"] == "old"))

    def test_coverage_does_not_certify_a_walk_across_pricing_dependencies(self):
        with TemporaryDirectory() as tmp:
            archive, service, _, (root, _) = archive_sweep_fixture(Path(tmp))
            self.addCleanup(archive.close)
            now_ms = at("12:00:00")
            old_ms = now_ms - 86_400_000
            pricing = ["initial"]
            service._load_comparison_catalog = lambda: SimpleNamespace(diagnostic_signature=pricing[0])
            catalog = SessionCatalog(display_archive=archive, clock=lambda: 100, clock_ms=lambda: now_ms)
            catalog.observe(CatalogObservation((root,), (root,), {}, {"old": "r1"},
                            atomic_archive_roster=True, activity_floor={"old": old_ms}))
            archive.publish_catalog(catalog, service)
            row = SessionUsageRow("old", "Old", "M", False, Decimal("2"), 1, last_activity_ms=old_ms)
            admission = archive.admit_summary(service, "old", "r1", observation_sequence=1)
            archive.publish_summary(service, admission, row, "r1",
                                    dependency=checkpoint_dependency(scalar_dependency(service), ()))

            archive.check_coverage(catalog, service)
            pricing[0] = "changed"
            archive.check_coverage(catalog, service)
            page = archive.views.page(period="all", now_ms=now_ms)

            self.assertEqual("pending", page["history_coverage"])
            self.assertEqual("2", page["rows"][0]["ccost"])


def archive_sweep_fixture(root):
    driver = v1_driver(root)
    service = driver.coordinator.report_service
    service._load_catalog = lambda: None
    service._load_comparison_catalog = lambda: SimpleNamespace(diagnostic_signature="pricing")
    service._dependencies = lambda _: "config"
    service.retain_derived_cache_read_only = lambda: None
    archive = DisplayArchive(root, lambda *_: None)
    archive.initialize()
    archive.observe(driver, before_tick=True)
    catalog = SessionCatalog(clock=lambda: 100, display_archive=archive)
    roots = tuple(NormalizedSession(key, key, 1, 2, Provenance("fixture", key), SessionCapabilities())
                  for key in ("old", "recent"))
    return archive, service, catalog, roots


def v1_driver(root):
    path = root / "source"
    path.write_bytes(b"test source identity only")
    service = SimpleNamespace(selection=SimpleNamespace(selected="v1", source=OpenCodeV1Source(path)), timezone_id="UTC")
    return SimpleNamespace(coordinator=SimpleNamespace(report_service=service, catalog_observation=None),
                           error=None, terminal=False)
