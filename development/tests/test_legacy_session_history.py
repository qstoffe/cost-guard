"""Probe only synthetic legacy SQLite files, including missing or foreign evidence."""
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from src.cache.database import CacheDatabase
from src.cache.legacy_session_history import MAX_PAYLOAD_BYTES, session_candidates
from src.cache.repository import CacheRepository
from src.cache.session_scope import SessionScope, root_key


class LegacySessionHistoryTests(unittest.TestCase):
    def setUp(self):
        root = TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.database = CacheDatabase(Path(root.name))
        self.database.initialize()
        self.repository = CacheRepository(self.database)
        self.origin = SimpleNamespace(source_type="opencode", source_generation="v2", source_instance="selected")
        self.foreign = SimpleNamespace(source_type="opencode", source_generation="v2", source_instance="other")

    def write(self, key, session_id, origin=None, **fields):
        scope = SessionScope(root_key(origin, session_id), 500) if origin is not None else None
        self.repository.put("session-summary", key, dict(session_id=session_id, **fields),
                            source_revision="revision", algorithm_version="summary", session_scope=scope)

    def test_legacy_cursor_reaches_matching_archival_summary_without_a_source_catalog(self):
        self.write("a", "known", self.foreign, title="Foreign title")
        self.write("b", "gone", self.origin, title="Recoverable title")
        self.write("c", "unproven", title="No durable binding")

        first = session_candidates(self.database, self.origin, limit=1)
        second = session_candidates(self.database, self.origin, after=first.next_key, limit=1)
        last = session_candidates(self.database, self.origin, after=second.next_key, limit=1)

        self.assertEqual((1, (), "a"), (first.unbound, first.candidates, first.next_key))
        candidate, = second.candidates
        self.assertEqual(("b", "gone", "revision", "summary", "Recoverable title"),
            (candidate.cache_key, candidate.session_id, candidate.source_revision,
             candidate.algorithm_version, candidate.payload["title"]))
        self.assertEqual((1, (), None), (last.unbound, last.candidates, last.next_key))
        self.assertEqual("Recoverable title", self.repository.get("session-summary", "b").payload["title"])

    def test_unknown_digest_revision_and_bulky_payload_do_not_become_candidates(self):
        self.write("oversized", "root-1", self.origin, title="x" * MAX_PAYLOAD_BYTES)
        self.write("stale", "root-2", self.origin)
        with self.database.connect() as db:
            db.execute("UPDATE cache_entry_lifecycle SET source_revision='previous' WHERE cache_key='stale'")

        page = session_candidates(self.database, self.origin)

        self.assertEqual((1, 1, (), None), (page.unreadable, page.unbound, page.candidates, page.next_key))

    def test_missing_legacy_file_is_not_created_during_read(self):
        absent = CacheDatabase(self.database.package_root / "another-install")

        with self.assertRaises(sqlite3.OperationalError):
            session_candidates(absent, self.origin)
        self.assertFalse(absent.paths.database.exists())
