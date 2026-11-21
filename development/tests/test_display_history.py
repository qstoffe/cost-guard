"""Exercise the real display-history database without an OpenCode installation."""
from contextlib import closing
from decimal import Decimal
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from src.application.session_archive_projection import SessionPublication
from src.application.session_archive_owner import SessionArchiveOwner
from src.application.cached_session_views import CachedSessionViews
from src.cache.display_history import DisplayHistory, SessionChange, SessionFact
from src.reports.models import SessionUsageRow


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
        self.assertIsNone(self.history.commit_sessions("first", missing=(("id", "r1"),)))

        self.assertEqual(3, self.history.commit_sessions("first", missing=(("id", "r2"),)))
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

    def test_failed_batch_does_not_publish_partial_rows_or_generation(self):
        self.history.commit_sessions("source", (SessionChange(SessionFact("a", "r1", "A"), None),))
        good = SessionChange(SessionFact("b", "r1", "B"), None)
        invalid = SessionChange(SessionFact("c", "r1", "C", ccost=Decimal("NaN")), None)

        with self.assertRaisesRegex(ValueError, "invalid_cost"):
            self.history.commit_sessions("source", (good, invalid))
        page = self.history.session_page("source")

        self.assertEqual(1, page.generation)
        self.assertEqual(["a"], [row.session_id for row in page.rows])

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
        first = SessionChange(SessionFact("id", "r1", "Old"), None)
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
        self.assertTrue(self.history.session_changes("chosen", confirmed.generation).resync)
        self.assertEqual(4, self.history.commit_sessions("chosen", (first,), archive_epoch=cleared.archive_epoch))

    def test_qualified_new_revision_from_partial_summary_retains_existing_fields(self):
        self.history.commit_sessions("source", (SessionChange(
            SessionFact("session", "old", "First title", ccost=Decimal("2.43"), context_tokens=48), None),))
        revisions = self.history.session_revisions("source", ("missing", "session"))
        proof = SessionPublication("session", "new", "observation", revisions["session"])
        row = SessionUsageRow("session", "Current title", "Current model", False, Decimal("0.3"), 1,
            complete=False, context_qualified=False, last_activity_ms=498, activity_latest_ms=500)

        update = proof.project(row, current_revision="new", current_epoch="observation")
        self.history.commit_sessions("source", (update,))
        snapshot, = self.history.session_page("source", start_ms=500, end_ms=501).rows

        self.assertEqual({"session": "old"}, revisions)
        self.assertEqual(("Current title", "Current model", "2.43", None, 48, 498, 500),
                         (snapshot.title, snapshot.model, snapshot.ccost, snapshot.prompts, snapshot.context_tokens,
                          snapshot.activity_ms, snapshot.latest_activity_ms))

    def test_rejected_revision_or_live_summary_never_becomes_archived_history(self):
        proof = SessionPublication("session", "r2", "observation", "persisted")
        settled = SessionUsageRow("session", "Title", "Model", False, Decimal("1"), 1)
        running = SessionUsageRow("session", "Title", "Model", False, Decimal("0"), 1, running=True)

        self.assertIsNone(proof.project(settled, current_revision="r3", current_epoch="observation"))
        self.assertIsNone(proof.project(settled, current_revision="r2", current_epoch="other"))
        self.assertIsNone(proof.project(running, current_revision="r2", current_epoch="observation"))

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
        self.assertEqual([("cache", {"view": "sessions", "binding": "first", "generation": 1}, 1, "Metadata")],
                         notifications)
        acquired = owner.admit(revisions)
        row = SessionUsageRow("session", "Authoritative", "Model", False, Decimal("2"), 1)
        owner.bind("other", "second")
        self.assertIsNone(owner.commit(acquired, {"session": row}, revisions))
        owner.bind("source", "third")
        admission = owner.admit(revisions)

        owner.commit(admission, {"session": row}, revisions)

        self.assertEqual(("cache", {"view": "sessions", "binding": "third", "generation": 2}, 2, "Authoritative"),
                         notifications[-1])
        self.assertEqual(2, len(notifications))
