"""Real SQLite write failures cannot become committed archive evidence."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from decimal import Decimal

from src.application.session_archive_owner import SessionArchiveOwner
from src.application.session_catalog import SessionUsageRow
from src.cache.display_history import DisplayHistory, SessionChange, SessionFact
from src.web.display_archive import DisplayArchive


class DisplayArchiveFailureTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.history = DisplayHistory(self.root)

    def test_disk_full_does_not_publish_partial_rows_or_progress_and_can_retry(self):
        self.history.initialize()
        self.history.commit_sessions("source", (
            SessionChange(SessionFact("known", "initial", "Known title"), None, previous_progress=0),))
        evidence = []
        owner = SessionArchiveOwner(self.history, lambda kind, event: evidence.append((kind, event)))
        owner.bind("source", "binding")
        admission = owner.admit({"known": "changed", "overflow": "new"}, binding=("source", "binding"))
        change = SessionChange(SessionFact("known", "changed", "Small correction"), "initial", previous_progress=1)
        overflow = SessionChange(SessionFact("overflow", "new", "Large title " * 8192), None, previous_progress=0)
        actual_connect = self.history._connect

        @contextmanager
        def capped_connection(**kwargs):
            with actual_connect(**kwargs) as connection:
                size, = connection.execute("PRAGMA page_count").fetchone()
                cap, = connection.execute(f"PRAGMA max_page_count={size}").fetchone()
                self.assertEqual(size, cap)
                yield connection

        with patch.object(self.history, "_connect", side_effect=capped_connection):
            with self.assertRaises(sqlite3.OperationalError) as failure:
                owner._commit(admission, (change, overflow))

        self.assertEqual(sqlite3.SQLITE_FULL, failure.exception.sqlite_errorcode)
        self.assertEqual([], evidence)
        held = self.history.session_page("source")
        self.assertEqual((1, 1, "Known title"), (held.generation, held.total, held.rows[0].title))
        self.assertEqual(1, self.history.session_checkpoints("source", ("known",))["known"].progress)

        committed = owner._commit(admission, (change, overflow))

        self.assertEqual(2, committed)
        self.assertEqual([("cache", {"view": "sessions", "binding": "binding", "generation": 2})], evidence)
        self.assertEqual(2, self.history.session_checkpoints("source", ("known",))["known"].progress)
        self.assertEqual(2, self.history.session_page("source").total)

    def test_corrupt_storage_is_not_reinitialized_as_an_empty_archive(self):
        self.history.path.parent.mkdir()
        original = b"not a valid database" * 1024
        self.history.path.write_bytes(original)
        archive = DisplayArchive(self.root, lambda *_: None)
        self.addCleanup(archive.close)

        usable = archive.initialize()

        self.assertFalse(usable)
        with self.assertRaises(sqlite3.DatabaseError):
            self.history.session_page("source")
        self.assertEqual(original, self.history.path.read_bytes())

    def test_lost_progress_compare_and_swap_does_not_report_summary_accepted(self):
        self.history.initialize()
        owner = SessionArchiveOwner(self.history, lambda *_: None)
        owner.bind("source", "binding")
        older = owner.admit({"id": "revision"})
        newer = owner.admit({"id": "revision"})
        row = SessionUsageRow("id", "Already committed", "Model", False, Decimal("3"), 1)
        stale_row = SessionUsageRow("id", "Stale title", "Model", False, Decimal("5"), 1)

        applied = owner.commit_summary(newer, row, "revision", dependency=None, eligible=lambda: True, usage=None)
        stale = owner.commit_summary(older, stale_row, "revision", dependency=None, eligible=lambda: True, usage=None)

        self.assertTrue(applied)
        self.assertFalse(stale)
        self.assertEqual("Already committed", self.history.session_page("source").rows[0].title)

    def test_summary_rolls_back_if_binding_is_revoked_during_sqlite_write(self):
        self.history.initialize()
        events = []
        owner = SessionArchiveOwner(self.history, lambda *event: events.append(event))
        owner.bind("source", "first")
        admission = owner.admit({"id": "revision"})
        row = SessionUsageRow("id", "Pending write", "Model", False, Decimal("3"), 1)
        real_apply = self.history._apply_session

        def change_binding(*args):
            changed = real_apply(*args)
            owner.bind("source", "second")
            return changed

        with patch.object(self.history, "_apply_session", side_effect=change_binding):
            accepted = owner.commit_summary(admission, row, "revision", dependency=None,
                                            eligible=lambda: True, usage=None)

        self.assertFalse(accepted)
        self.assertEqual([], events)
        self.assertEqual({}, self.history.session_checkpoints("source", ("id",)))
        self.assertEqual(0, self.history.session_page("source").total)
