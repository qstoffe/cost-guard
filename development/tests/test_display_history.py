"""Exercise the real display-history database without an OpenCode installation."""
from contextlib import closing
from decimal import Decimal
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from src.cache.display_history import DisplayHistory, SessionChange, SessionFact


class DisplayHistoryTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.history = DisplayHistory(self.root)
        self.history.initialize()

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
