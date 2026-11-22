"""Exercise the real display-history database without an OpenCode installation."""
from contextlib import closing
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from src.application.session_archive_projection import SessionPublication
from src.application.session_archive_owner import SessionArchiveOwner
from src.application.cached_session_views import CachedSessionViews
from src.cache.display_history import DisplayHistory, RunningSession, SessionChange, SessionCheckpoint, SessionCoverage, SessionFact
from src.domain.effort import EffortEvidence
from src.domain.reference_cost import ReferenceCostIssue
from src.reports.models import SessionUsageRow
from src.reports.session_models import SessionModel


class DisplayHistoryTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.history = DisplayHistory(self.root)
        self.history.initialize()

    def test_conditional_page_ignores_other_periods_but_not_a_clock_entering_the_scope(self):
        clock = 1_700_006_400_000  # UTC midnight
        views = CachedSessionViews(self.history, "source", "UTC", "binding")
        self.history.commit_sessions("source", (
            SessionChange(SessionFact("future", "r1", "Future", activity_ms=clock + 5000), None),
        ))
        results = views.page(now_ms=clock + 1000)
        fields = ("binding", "generation", "start_ms", "end_ms", "period", "sort", "direction", "offset")
        known = {name: results[name] for name in fields}
        self.history.commit_sessions("source", (
            SessionChange(SessionFact("past", "r1", "Past", activity_ms=clock - 1), None),
        ))

        unrelated = views.page(now_ms=clock + 3000, known=known)
        eligible = views.page(now_ms=clock + 6000, known=known)

        self.assertEqual(0, results["cached_total"])
        self.assertEqual((True, 2), (unrelated["unchanged"], unrelated["generation"]))
        self.assertEqual(["future"], [row["session_id"] for row in eligible["rows"]])
        other = CachedSessionViews(self.history, "source", "UTC", "new-incarnation")
        self.assertIn("rows", other.page(now_ms=clock + 1000, known=known))

    def test_cold_page_and_partial_sorts_order_nulls_last_then_id(self):
        self.assertEqual((), self.history.session_page("source", sort="ccost").rows)
        exact_low = Decimal("2.000000000000000000000000001")
        exact_high = Decimal("2.000000000000000000000000002")
        facts = (
            SessionFact("a", "r1", "B", activity_ms=101, model="model Z", ccost=exact_high),
            SessionFact("b", "r1", "A", activity_ms=105, model="model a", ccost=exact_low),
            SessionFact("c", "r1", "a", ccost=exact_low),
            SessionFact("d", "r1", "A", activity_ms=99, ccost=Decimal("-2")),
            SessionFact("e", "r1", "B"),
        )
        generation = self.history.commit_sessions("source", tuple(SessionChange(fact, None) for fact in facts))

        asc = self.history.session_page("source", sort="ccost", direction=1)
        desc = self.history.session_page("source", sort="ccost", direction=-1, offset=1, limit=3)
        filtered = self.history.session_page("source", sort="name", start_ms=100, end_ms=105)
        text = self.history.session_page("source", sort="name", direction=-1, limit=3)

        self.assertEqual(1, generation)
        self.assertEqual(generation, desc.generation)
        self.assertEqual(5, desc.total)
        self.assertEqual(["d", "b", "c", "a", "e"], [row.session_id for row in asc.rows])
        self.assertEqual(["b", "c", "d"], [row.session_id for row in desc.rows])
        self.assertEqual(["a"], [row.session_id for row in filtered.rows])
        self.assertEqual(["a", "e", "b"], [row.session_id for row in text.rows])

    def test_source_absence_and_partial_metadata_keep_acquired_values_after_restart(self):
        original = SessionFact("id", "r1", "Original", activity_ms=123, ccost=Decimal("0.34"), prompts=7)
        self.history.commit_sessions("first", (SessionChange(original, None),))
        self.history.commit_sessions("other", (SessionChange(SessionFact("id", "r1", "Other"), None),))
        provisional = SessionChange(SessionFact("id", "r2", "Renamed"), "r1", frozenset())
        self.history.commit_sessions("first", (provisional,))
        self.assertIsNone(self.history.commit_sessions("first", missing=(("id", SessionCheckpoint("r1", 0)),)))

        self.assertEqual(3, self.history.commit_sessions("first", missing=(("id", SessionCheckpoint("r2", 0)),)))
        restarted = DisplayHistory(self.root)
        restarted.initialize()
        page = restarted.session_page("first", start_ms=123, end_ms=124)
        other = restarted.session_page("other")

        row, = page.rows
        self.assertEqual(("r2", "Renamed", 123, "0.34", 7, False),
                         (row.revision, row.title, row.activity_ms, row.ccost, row.prompts, row.source_present))
        self.assertEqual(3, page.generation)
        self.assertEqual("Other", other.rows[0].title)
        self.assertTrue(other.rows[0].source_present)
        self.assertEqual(0, restarted.session_page("unbound").total)

    def test_qualified_correction_replaces_contribution_but_stale_write_cannot(self):
        old = SessionFact("id", "r1", "Title", activity_ms=10, ccost=Decimal("1"))
        new = SessionFact("id", "r2", "Title", activity_ms=11, ccost=Decimal("2"))
        self.history.commit_sessions("source", (SessionChange(old, None),))
        self.assertEqual(2, self.history.commit_sessions("source", (SessionChange(new, "r1"),)))

        self.assertIsNone(self.history.commit_sessions("source", (SessionChange(old, "r1"),)))
        self.assertIsNone(self.history.commit_sessions("source", (SessionChange(new, "r2"),)))
        page = self.history.session_page("source")

        self.assertEqual(2, page.generation)
        self.assertEqual(1, page.total)
        self.assertEqual((11, "2"), (page.rows[0].activity_ms, page.rows[0].ccost))

    def test_projection_help_survives_partial_correction_deletion_and_restart(self):
        owner = SessionArchiveOwner(self.history, lambda *_: None)
        owner.bind("source", "epoch")
        inferred = EffortEvidence("default", "medium", "current-configuration")
        row = SessionUsageRow("id", "Title", "Friendly", True, Decimal(2), 1, context_tokens=723,
                              context_detail="Provisional text estimate.", has_model_details=True,
                              main_models=(SessionModel("provider", "raw-selector", "catalog-model", (inferred,)),),
                              linked_model_selections=("provider/subagent-selection",))
        owner.commit(owner.admit({"id": "r1"}), {"id": row}, {"id": "r1"}, dependency="initial")
        partial = replace(row, model="Unqualified", model_pending=True, context_tokens=None, context_qualified=False)
        owner.commit(owner.admit({"id": "r2"}), {"id": partial}, {"id": "r2"})
        owner.commit(owner.admit({"id": "r2"}), {}, {}, missing=("id",))

        restarted = DisplayHistory(self.root)
        restarted.initialize()
        cached, = CachedSessionViews(restarted, "source", "UTC", "new-host").page(period="all")["rows"]

        self.assertFalse(cached["source_present"])
        self.assertEqual(("Friendly", True, 723, "Provisional text estimate."),
                         (cached["model"], cached["has_model_details"], cached["context_tokens"], cached["context_detail"]))
        for help_line in ("provider/raw-selector", "Catalog modelID: catalog-model", "default (medium)",
                          "historical settings may differ", "not a confirmed executed contributor"):
            self.assertIn(help_line, cached["model_help"])

    def test_help_columns_migrate_without_removing_existing_archive_rows(self):
        self.history.commit_sessions("source", (SessionChange(
            SessionFact("old", "r1", "Stored", activity_ms=20, model="Known Model", ccost=Decimal(5)), None),))
        self.history.publish_session_coverage("source", SessionCoverage(30, False, False, None), archive_epoch=0)
        with closing(sqlite3.connect(self.history.path)) as db:
            db.executescript("""
                DROP TABLE archive_prompt_state;
                DROP TABLE archive_prompt_history;
                DROP VIEW archive_countable_requests;
                DROP TABLE archive_fork_trees;
                DROP TABLE archive_prompt_attribution;
                DROP TABLE archive_request_membership;
                DROP TABLE archive_request_rosters;
                DROP TABLE archive_requests;
                ALTER TABLE sessions DROP COLUMN context_detail;
                ALTER TABLE sessions DROP COLUMN model_help;
                ALTER TABLE sessions DROP COLUMN has_model_details;
                PRAGMA user_version=6;
            """)

        restarted = DisplayHistory(self.root)
        restarted.initialize()
        page = CachedSessionViews(restarted, "source", "UTC", "epoch", coverage_supported=True).page(period="all")

        stored, = page["rows"]
        self.assertEqual(("Known Model", "5", None), (stored["model"], stored["ccost"], stored["model_help"]))
        self.assertEqual("pending", page["history_coverage"])

    def test_failed_batch_does_not_publish_partial_rows_or_generation(self):
        self.history.commit_sessions("source", (SessionChange(SessionFact("a", "r1", "A"), None),))
        good = SessionChange(SessionFact("b", "r1", "B"), None, dependency="pricing", previous_progress=0)
        invalid = SessionChange(SessionFact("c", "r1", "C", ccost=Decimal("NaN")), None)

        with self.assertRaisesRegex(ValueError, "invalid_cost"):
            self.history.commit_sessions("source", (good, invalid))
        page = self.history.session_page("source")

        self.assertEqual(1, page.generation)
        self.assertEqual(["a"], [row.session_id for row in page.rows])
        self.assertEqual(set(), self.history.completed_sessions("source", {"b": "r1"}, "pricing"))

    def test_reader_stays_on_committed_snapshot_while_writer_holds_wal_lock(self):
        self.history.commit_sessions("source", (SessionChange(SessionFact("a", "r1", "A"), None),))
        with self.history._connect() as pending:
            pending.execute("BEGIN IMMEDIATE")
            pending.execute("UPDATE sessions SET title='uncommitted'")

            page = self.history.session_page("source")

            self.assertEqual(1, page.generation)
            self.assertEqual("A", page.rows[0].title)
        self.assertEqual("A", self.history.session_page("source").rows[0].title)

    def test_change_hint_covers_both_old_and_new_clock_and_ignores_other_sources(self):
        original = SessionFact("id", "r1", "Title", activity_ms=10)
        self.history.commit_sessions("source", (SessionChange(original, None),))
        moved = SessionFact("id", "r2", "Title", activity_ms=35)
        self.history.commit_sessions("source", (SessionChange(moved, "r1"),))
        unrelated = SessionFact("id", "r1", "Other", activity_ms=80)
        self.history.commit_sessions("other", (SessionChange(unrelated, None),))

        changes = self.history.session_changes("source", 1)

        self.assertEqual((2, 10, 35), (changes.generation, changes.oldest_activity_ms, changes.latest_activity_ms))
        self.assertTrue(changes.affects(1, start_ms=10, end_ms=11))
        self.assertTrue(changes.affects(1, start_ms=35, end_ms=36))
        self.assertFalse(changes.affects(1, start_ms=36, end_ms=80))
        self.assertFalse(self.history.session_changes("source", 2).affects(2))

    def test_later_linked_activity_controls_membership_but_not_displayed_activity(self):
        fact = SessionFact("root", "rev", "Title", activity_ms=99, latest_activity_ms=105)
        self.history.commit_sessions("source", (SessionChange(fact, None),))

        page = self.history.session_page("source", start_ms=100, end_ms=106)
        changes = self.history.session_changes("source", 0)

        row, = page.rows
        self.assertEqual((99, 105), (row.activity_ms, row.latest_activity_ms))
        self.assertTrue(changes.affects(0, start_ms=100, end_ms=106))
        self.assertFalse(changes.affects(0, start_ms=99, end_ms=100))

    def test_lost_change_window_triggers_resync_even_for_a_narrow_period(self):
        self.history.commit_sessions("source", (SessionChange(SessionFact("id", "r1", "Title"), None),))
        for revision in range(2, 67):
            fact = SessionFact("id", f"r{revision}", "Title", activity_ms=50)
            self.history.commit_sessions("source", (SessionChange(fact, f"r{revision - 1}"),))
        restarted = DisplayHistory(self.root)

        changes = restarted.session_changes("source", 1)
        recent = restarted.session_changes("source", 2)

        self.assertEqual(66, changes.generation)
        self.assertTrue(changes.resync)
        self.assertTrue(changes.affects(1, start_ms=500))
        self.assertFalse(recent.resync)
        self.assertFalse(recent.affects(2, start_ms=500))
        self.assertTrue(restarted.session_changes("source", 67).resync)

    def test_unavailable_or_foreign_database_is_not_empty_history(self):
        missing = DisplayHistory(self.root / "absent")
        with self.assertRaises(sqlite3.OperationalError):
            missing.session_page("source")
        self.assertFalse(missing.path.exists())
        missing.path.parent.mkdir(parents=True)
        with closing(sqlite3.connect(missing.path)) as db:
            db.execute("CREATE TABLE another_app(id INTEGER)")

        with self.assertRaisesRegex(sqlite3.DatabaseError, "unsupported_display_history_schema"):
            missing.initialize()

    def test_confirmed_clear_is_source_scoped_and_rejects_pre_clear_work(self):
        first = SessionChange(SessionFact("id", "r1", "Old"), None, dependency="pricing", previous_progress=0)
        self.history.commit_sessions("chosen", (first,))
        self.history.commit_sessions("other", (first,))
        stale_confirmation = self.history.source_state("chosen")
        second = SessionChange(SessionFact("id", "r2", "Different"), "r1")
        self.history.commit_sessions("chosen", (second,))
        self.assertIsNone(self.history.clear_confirmed_sessions("chosen", stale_confirmation))
        self.assertEqual(1, self.history.session_page("chosen").total)
        confirmed = self.history.source_state("chosen")

        cleared = self.history.clear_confirmed_sessions("chosen", confirmed)
        rejected = self.history.commit_sessions("chosen", (first,), archive_epoch=confirmed.archive_epoch)

        self.assertIsNone(rejected)
        self.assertEqual((3, 1), (cleared.generation, cleared.archive_epoch))
        self.assertEqual(0, self.history.session_page("chosen").total)
        self.assertEqual(1, self.history.session_page("other").total)
        self.assertEqual(set(), self.history.completed_sessions("chosen", {"id": "r1"}, "pricing"))
        self.assertEqual({"id"}, self.history.completed_sessions("other", {"id": "r1"}, "pricing"))
        self.assertTrue(self.history.session_changes("chosen", confirmed.generation).resync)
        self.assertEqual(4, self.history.commit_sessions("chosen", (first,), archive_epoch=cleared.archive_epoch))

    def test_qualified_new_revision_from_partial_summary_retains_existing_fields(self):
        self.history.commit_sessions("source", (SessionChange(
            SessionFact("session", "old", "First title", ccost=Decimal("2.43"), context_tokens=48), None),))
        checkpoints = self.history.session_checkpoints("source", ("missing", "session"))
        proof = SessionPublication("session", "new", "observation", checkpoints["session"])
        row = SessionUsageRow("session", "Current title", "Current model", False, Decimal("0.3"), 1,
            complete=False, context_qualified=False, last_activity_ms=498, activity_latest_ms=500)

        update = proof.project(row, current_revision="new", current_epoch="observation")
        self.history.commit_sessions("source", (update,))
        snapshot, = self.history.session_page("source", start_ms=500, end_ms=501).rows

        self.assertEqual({"session": SessionCheckpoint("old", 0)}, checkpoints)
        self.assertEqual(("Current title", "Current model", "2.43", None, 48, 498, 500),
                         (snapshot.title, snapshot.model, snapshot.ccost, snapshot.prompts, snapshot.context_tokens,
                          snapshot.activity_ms, snapshot.latest_activity_ms))

    def test_rejected_revision_or_live_summary_never_becomes_archived_history(self):
        proof = SessionPublication("session", "r2", "observation", SessionCheckpoint("persisted", 0))
        settled = SessionUsageRow("session", "Title", "Model", False, Decimal("1"), 1)
        running = SessionUsageRow("session", "Title", "Model", False, Decimal("0"), 1, running=True)

        self.assertIsNone(proof.project(settled, current_revision="r3", current_epoch="observation"))
        self.assertIsNone(proof.project(settled, current_revision="r2", current_epoch="other"))
        self.assertIsNone(proof.project(running, current_revision="r2", current_epoch="observation"))

    def test_version_one_upgrade_keeps_rows_without_inventing_work_progress(self):
        original = SessionFact("root", "r1", "Saved title", ccost=Decimal("2.43"))
        self.history.commit_sessions("source", (SessionChange(original, None),))
        with closing(sqlite3.connect(self.history.path, isolation_level=None)) as db:
            db.executescript("""
                DROP TABLE archive_prompt_state;
                DROP TABLE archive_prompt_history;
                DROP VIEW archive_countable_requests;
                DROP TABLE archive_fork_trees;
                DROP TABLE archive_prompt_attribution;
                DROP TABLE archive_request_membership;
                DROP TABLE archive_request_rosters;
                DROP TABLE archive_requests;
                DROP TABLE session_progress;
                DROP TABLE session_running;
                DROP TABLE session_scope_coverage;
                ALTER TABLE sessions DROP COLUMN prompt_started_ms;
                ALTER TABLE sessions DROP COLUMN activity_origin;
                ALTER TABLE sessions DROP COLUMN catalog_activity_ms;
                ALTER TABLE sessions DROP COLUMN field_evidence;
                ALTER TABLE sessions DROP COLUMN context_detail;
                ALTER TABLE sessions DROP COLUMN model_help;
                ALTER TABLE sessions DROP COLUMN has_model_details;
                PRAGMA user_version=1;
            """)

        reopened = DisplayHistory(self.root)
        reopened.initialize()

        page = reopened.session_page("source", sort="ccost")
        self.assertEqual((1, "Saved title", "2.43"), (page.generation, page.rows[0].title, page.rows[0].ccost))
        self.assertEqual({"root": SessionCheckpoint("r1", 0)}, reopened.session_checkpoints("source", ("root",)))
        self.assertEqual(set(), reopened.completed_sessions("source", {"root": "r1"}, "pricing"))

    def test_field_evidence_distinguishes_pending_empty_unavailable_and_retained_cells_after_restart(self):
        source = "source"
        owner = SessionArchiveOwner(self.history, lambda *_: None)
        owner.bind(source, "observation")
        initial = dict.fromkeys(("partial", "empty", "unavailable", "pending"), "v1")
        owner.publish_catalog(owner.admit(initial), dict.fromkeys(initial, "Title"), initial)
        owner.commit(owner.admit(initial), {
            "partial": SessionUsageRow("partial", "Known", "M", False, Decimal("1.2"), 4, context_tokens=314),
            "empty": SessionUsageRow("empty", "No prompts", "N/A", False, Decimal(0), 0, empty_history=True),
            "unavailable": SessionUsageRow("unavailable", "No context", "M", False, Decimal("2.3"), 2),
        }, initial)
        correction = {"partial": "v2"}
        owner.commit(owner.admit(correction), {"partial": SessionUsageRow(
            "partial", "Revised", "M2", False, Decimal("3.4"), 5, context_qualified=False)}, correction)

        reopened = DisplayHistory(self.root)
        reopened.initialize()
        result = CachedSessionViews(reopened, source, "UTC").page(period="all", sort="ctx")
        by_id = {row["session_id"]: row for row in result["rows"]}

        self.assertEqual("partial", result["rows"][0]["session_id"])
        self.assertEqual(("3.4", 314, "retained"), (by_id["partial"]["ccost"], by_id["partial"]["context_tokens"],
                                                 by_id["partial"]["fields"]["ctx"]))
        self.assertEqual("complete_empty_history", by_id["empty"]["fields"]["ctx"])
        self.assertEqual("source-field-unavailable", by_id["unavailable"]["fields"]["ctx"])
        self.assertEqual("pending", by_id["pending"]["fields"]["ctx"])

    def test_cache_distinguishes_catalog_time_from_prompt_start_and_causal_finish(self):
        owner = SessionArchiveOwner(self.history, lambda *_: None)
        owner.bind("source", "observation")
        revisions = {"known": "r", "preliminary": "r", "no-finish": "r", "empty": "r"}
        titles = dict.fromkeys(revisions, "Title")
        owner.publish_catalog(owner.admit(revisions), titles, revisions, activity=dict.fromkeys(revisions, 500))
        rows = {
            "known": SessionUsageRow("known", "Title", "Model", False, Decimal(1), 1,
                                      last_activity_ms=1000, activity_latest_ms=1500, prompt_started_ms=800),
            "no-finish": SessionUsageRow("no-finish", "Title", "Model", False, Decimal(1), 1,
                                         activity_latest_ms=810, prompt_started_ms=810),
            "empty": SessionUsageRow("empty", "Title", "N/A", False, Decimal(0), 0, empty_history=True),
        }
        owner.commit(owner.admit(revisions), rows, revisions, dependency="pricing")

        result = CachedSessionViews(self.history, "source", "UTC").page(period="all", now_ms=3000)
        by_key = {row["session_id"]: row for row in result["rows"]}
        expected = {
            "known": ("finish", 800, 1000, None),
            "preliminary": (None, None, None, 500),
            "no-finish": ("start", 810, None, None),
            "empty": ("no-prompt", None, None, None),
        }
        fields = ("activity_origin", "prompt_started_ms", "activity_ms", "catalog_activity_ms")
        self.assertEqual(expected, {key: tuple(row[field] for field in fields) for key, row in by_key.items()})
        window = self.history.session_page("source", start_ms=1200, end_ms=1501)
        self.assertEqual(["known"], [row.session_id for row in window.rows])

    def test_live_starts_sort_first_across_pages_only_for_the_current_binding(self):
        midnight = 1_700_006_400_000
        observed = midnight + 100
        starts = tuple(RunningSession(f"live-{index:02}", "Running", midnight - index - 1, observed)
                       for index in range(26))
        self.history.commit_sessions("source", (
            SessionChange(SessionFact("live-25", "prior", "Original", activity_ms=midnight + 2, ccost=Decimal(7)), None),
            SessionChange(SessionFact("history", "r", "History", activity_ms=midnight + 2, ccost=Decimal(3)), None),
        ))
        active = CachedSessionViews(self.history, "source", "UTC", "current-host")
        restarted = CachedSessionViews(self.history, "source", "UTC", "new-host")
        initial = active.page(now_ms=observed)

        self.history.replace_running("source", "current-host", starts, archive_epoch=0)
        first = active.page(sort="ccost", direction=1, now_ms=observed + 10)
        second = active.page(sort="ccost", direction=1, offset=25, now_ms=observed + 10)
        after_restart = restarted.page(now_ms=observed + 10)
        self.assertTrue(self.history.session_changes("source", initial["generation"]).affects(
            initial["generation"], start_ms=midnight, end_ms=observed + 10))

        self.assertEqual(27, first["cached_total"])
        self.assertEqual([f"live-{index:02}" for index in range(25)], [row["session_id"] for row in first["rows"]])
        self.assertEqual([("live-25", True, "7"), ("history", False, "3")],
                         [(row["session_id"], row["running"], row["ccost"]) for row in second["rows"]])
        self.assertEqual(14_990, first["running_refresh_ms"])
        self.assertEqual({"history", "live-25"}, {row["session_id"] for row in after_restart["rows"]})
        self.assertFalse(any(row["running"] for row in after_restart["rows"]))

    def test_running_expiry_is_not_not_modified_or_a_new_durable_finish(self):
        views = CachedSessionViews(self.history, "source", "UTC", "binding")
        original = SessionFact("root", "r1", "Historical", activity_ms=900, prompt_started_ms=800,
                               activity_origin="finish", ccost=Decimal(4))
        self.history.commit_sessions("source", (SessionChange(original, None),))
        self.history.replace_running("source", "binding", (RunningSession("root", "Working", 1000, 1200),),
                                     archive_epoch=0)
        first = views.page(period="all", now_ms=1300)
        fields = ("binding", "generation", "start_ms", "end_ms", "period", "sort", "direction", "offset")
        known = {key: first[key] for key in fields}

        expired = views.page(period="all", now_ms=16_200, known=known)
        generation = self.history.source_state("source")
        self.history.clear_confirmed_sessions("source", generation)
        rejected = self.history.replace_running("source", "binding", (RunningSession("root", "Working", 1000, 1200),),
                                                archive_epoch=generation.archive_epoch)

        self.assertTrue(first["rows"][0]["running"])
        self.assertNotIn("unchanged", expired)
        row, = expired["rows"]
        self.assertEqual((False, "Historical", 900, "4"), (row["running"], row["title"], row["activity_ms"], row["ccost"]))
        self.assertIsNone(expired["running_refresh_ms"])
        self.assertIsNone(rejected)
        self.assertEqual(0, views.page(period="all", now_ms=1300)["cached_total"])

    def test_dependency_only_publication_survives_restart_and_rejects_stale_same_revision(self):
        root = SessionFact("id", "r1", "Original", ccost=Decimal("2.43"))
        self.history.commit_sessions("source", (SessionChange(root, None, dependency="price-a", previous_progress=0),))
        update = SessionChange(root, "r1", dependency="price-b", previous_progress=1)
        stale = SessionChange(replace(root, ccost=Decimal("0")), "r1", dependency="price-a", previous_progress=1)

        self.assertIsNone(self.history.commit_sessions("source", (update,)))
        self.assertIsNone(self.history.commit_sessions("source", (stale,)))
        restarted = DisplayHistory(self.root)

        self.assertEqual({"id"}, restarted.completed_sessions("source", {"id": "r1"}, "price-b"))
        self.assertEqual(set(), restarted.completed_sessions("source", {"id": "r1"}, "price-a"))
        self.assertEqual(set(), restarted.completed_sessions("source", {"id": "r2"}, "price-b"))
        page = restarted.session_page("source")
        self.assertEqual((1, "2.43"), (page.generation, page.rows[0].ccost))

    def test_partial_same_revision_cost_proof_invalidates_the_marker_not_the_as_of_cost(self):
        owner = SessionArchiveOwner(self.history, lambda *_: None)
        owner.bind("source", "observation")
        revisions = {"id": "r"}
        settled = SessionUsageRow("id", "Original", "Model", False, Decimal("2.43"), 1)
        owner.commit(owner.admit(revisions), {"id": settled}, revisions, dependency="price-a")
        self.assertEqual({"id"}, self.history.completed_sessions("source", revisions, "price-a"))
        partial = replace(settled, ccost=Decimal(0), ccost_unavailable=(ReferenceCostIssue("rate"),))

        owner.commit(owner.admit(revisions), {"id": partial}, revisions, dependency="price-a")

        self.assertEqual(set(), self.history.completed_sessions("source", revisions, "price-a"))
        page = CachedSessionViews(self.history, "source", "UTC").page(period="all")
        row, = page["rows"]
        self.assertEqual((2, "2.43", "retained"), (page["generation"], row["ccost"], row["fields"]["ccost"]))

    def test_absence_invalidates_in_flight_progress_even_if_the_same_revision_returns(self):
        root = SessionFact("id", "r1", "Original")
        initial = SessionChange(root, None, dependency="pricing", previous_progress=0)
        self.history.commit_sessions("source", (initial,))
        stale = SessionChange(root, "r1", dependency="pricing", previous_progress=1)

        self.history.commit_sessions("source", missing=(("id", SessionCheckpoint("r1", 1)),))
        self.assertEqual(set(), self.history.completed_sessions("source", {"id": "r1"}, "pricing"))
        self.history.commit_sessions("source", present=(("id", SessionCheckpoint("r1", 2)),))
        self.history.commit_sessions("source", (stale,))

        self.assertEqual(set(), self.history.completed_sessions("source", {"id": "r1"}, "pricing"))
        self.assertTrue(self.history.session_page("source").rows[0].source_present)

    def test_owner_announces_only_committed_observations_and_refuses_old_binding(self):
        notifications = []
        def observed(kind, event):
            snapshot = self.history.session_page("source")
            notifications.append((kind, event, snapshot.generation, snapshot.rows[0].title))
        owner = SessionArchiveOwner(self.history, observed)
        revisions = {"session": "r"}
        self.assertIsNone(owner.admit(revisions))
        owner.bind("source", "first")
        admission = owner.admit(revisions)
        owner.publish_catalog(admission, {"session": "Metadata"}, revisions)
        self.assertEqual([("cache", {"view": "sessions", "binding": "first", "generation": 1,
                                     "detail_roots": ["session"]}, 1, "Metadata")], notifications)
        acquired = owner.admit(revisions)
        row = SessionUsageRow("session", "Authoritative", "Model", False, Decimal("2"), 1)
        owner.bind("other", "second")
        self.assertIsNone(owner.commit(acquired, {"session": row}, revisions))
        owner.bind("source", "third")
        admission = owner.admit(revisions)

        owner.commit(admission, {"session": row}, revisions)

        self.assertEqual(("cache", {"view": "sessions", "binding": "third", "generation": 2,
                                    "detail_roots": ["session"]}, 2, "Authoritative"), notifications[-1])
        self.assertEqual(2, len(notifications))

    def test_large_catalog_commit_announces_an_unscoped_detail_change(self):
        notifications = []
        owner = SessionArchiveOwner(self.history, lambda _, hint: notifications.append(hint))
        owner.bind("source", "first")
        revisions = {f"s-{key}": "r" for key in range(17)}
        titles = dict.fromkeys(revisions, "Cached")
        admission = owner.admit(revisions)

        owner.publish_catalog(admission, titles, revisions)

        self.assertEqual([{"view": "sessions", "binding": "first", "generation": 1}], notifications)
        self.assertEqual(17, self.history.session_page("source").total)
