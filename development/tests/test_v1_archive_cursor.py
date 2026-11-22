from contextlib import closing, contextmanager
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from src.sources.errors import SourceConcurrentChangeError, SourceDataError, SourceSchemaError
from src.sources.opencode_v1 import OpenCodeV1Source


SCHEMA = Path(__file__).parent / "fixtures/opencode_v1/schema.sql"
ROOT = "dense-root"
PROMPTS = 1366


def _session(db, session_id, parent=None, title="Synthetic root"):
    db.execute("INSERT INTO session VALUES(?,?,?,?,?,?,?,?)",
               (session_id, parent, "project", "/synthetic", title, 1000, 2000, None))


def _user(number):
    return f"user-{number:04d}"


def _assistant(number):
    return f"assistant-{number:04d}"


def _prompt(db, session_id, number):
    user, assistant = _user(number), _assistant(number)
    # Equal clocks exercise the complete composite key, not a clock-only seek.
    db.executemany("INSERT INTO message VALUES(?,?,?,?,?)", [
        (user, session_id, 1100, 1100, '{"role":"user"}'),
        (assistant, session_id, 1100, 1300, json.dumps({
            "role": "assistant", "parentID": user, "providerID": "synthetic", "modelID": "sample",
            "time": {"created": 1200, "completed": 1300}, "finish": "stop",
        })),
    ])
    # Insert assistant parts first: row position cannot establish the parent.
    db.executemany("INSERT INTO part VALUES(?,?,?,?,?,?)", [
        (f"step-{number:04d}", assistant, session_id, 1300, 1300,
         '{"type":"step-finish","tokens":{"input":9,"output":2}}'),
        (f"text-{number:04d}", user, session_id, 1100, 1100, '{"type":"text","text":"original"}'),
    ])


def _seed(path, *, encoding="UTF-8", composite=False, parent_index=True, unique_root=True):
    with closing(sqlite3.connect(path)) as db, db:
        db.execute(f"PRAGMA encoding='{encoding}'")
        schema = SCHEMA.read_text(encoding="utf-8")
        if not unique_root:
            schema = schema.replace("id TEXT PRIMARY KEY", "id TEXT", 1)
        db.executescript(schema)
        if not composite:
            # The upstream migration uses single-column owner indexes on these
            # rowid tables, not the composite index in our older test fixture.
            db.execute("DROP INDEX message_session_time_created_id_idx")
            db.execute("DROP INDEX part_message_id_id_idx")
            db.execute("CREATE INDEX message_session_idx ON message(session_id)")
            db.execute("CREATE INDEX part_message_idx ON part(message_id)")
        if parent_index:
            db.execute("CREATE INDEX session_parent_idx ON session(parent_id)")
        _session(db, ROOT)


def _finish(cursor):
    pages = []
    for _ in range(100):
        page = cursor.read_page()
        if page.eof:
            return pages
        pages.append(page)
    raise AssertionError("synthetic archive cursor did not reach EOF")


class _MeasuredSource(OpenCodeV1Source):
    @contextmanager
    def _connection(self):
        with super()._connection() as db:
            self.db = db
            self.steps = 0
            self.sql = []

            def progress():
                self.steps += 1
                return 0

            db.set_progress_handler(progress, 1)
            db.set_trace_callback(self.sql.append)
            yield db


class V1ArchiveCursorTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "opencode.db"

    def test_native_seek_reads_dense_root_once_with_bounded_sql_and_no_revision_scan(self):
        _seed(self.path)
        with closing(sqlite3.connect(self.path)) as db, db:
            _session(db, "other")
            # Put unrelated records before and between root records in rowid order.
            for n in range(PROMPTS):
                _prompt(db, "other", n + 10000)
                _prompt(db, ROOT, n)
            for n in range(PROMPTS, 8000):
                _prompt(db, "other", n + 10000)
        before = self.path.read_bytes()
        source = _MeasuredSource(self.path)

        pages = []
        with source.archive_cursor(ROOT) as cursor:
            self.assertLess(source.steps, 2000, "cursor open must not scan the dense root")
            for _ in range(100):
                start = source.steps
                page = cursor.read_page()
                pages.append((page, source.steps - start))
                if page.eof:
                    break
            self.assertTrue(pages[-1][0].eof)

        messages = [message for page, _ in pages for message in page.messages]
        parts = [part for page, _ in pages for part in page.parts]
        expected_messages = [record for n in range(PROMPTS)
                             for record in [(_user(n), None), (_assistant(n), _user(n))]]
        expected_parts = [record for n in range(PROMPTS)
                          for record in [(f"step-{n:04d}", _assistant(n)), (f"text-{n:04d}", _user(n))]]
        self.assertEqual(expected_messages, [(m.message_id, m.parent_message_id) for m in messages])
        self.assertEqual(expected_parts, [(p.part_id, p.message_id) for p in parts])
        self.assertTrue(all(m.session_id == ROOT and not m.parts for m in messages))
        self.assertTrue(all(p.session_id == ROOT for p in parts))
        for facts in ("messages", "parts"):
            full_pages = [steps for page, steps in pages if len(getattr(page, facts)) == 128]
            self.assertEqual(21, len(full_pages))
            self.assertLess(max(full_pages), 5000)
            self.assertLessEqual(max(full_pages) - min(full_pages), 80, facts)
        self.assertTrue(any("message INDEXED BY" in sql and "(rowid)>" in sql for sql in source.sql))
        self.assertTrue(any("part INDEXED BY" in sql and "(rowid)>" in sql for sql in source.sql))
        self.assertFalse(any("WITH RECURSIVE" in sql or "COUNT(" in sql.upper() for sql in source.sql))
        self.assertEqual(before, self.path.read_bytes())

    def test_composite_seek_handles_equal_clocks_without_rescanning(self):
        _seed(self.path, composite=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            for n in reversed(range(PROMPTS)):
                _prompt(db, ROOT, n)
        source = _MeasuredSource(self.path)
        ids = []
        steps = []

        with source.archive_cursor(ROOT) as cursor:
            for _ in range(100):
                start = source.steps
                page = cursor.read_page()
                ids.extend(m.message_id for m in page.messages)
                if len(page.messages) == 128:
                    steps.append(source.steps - start)
                if page.eof:
                    break
            self.assertTrue(page.eof)

        self.assertEqual([_assistant(n) for n in range(PROMPTS)] + [_user(n) for n in range(PROMPTS)], ids)
        self.assertEqual(21, len(steps))
        self.assertLess(max(steps), 5000)
        self.assertLessEqual(max(steps[1:]) - min(steps[1:]), 80)

    def test_wal_writer_cannot_change_remaining_tree_and_eof_releases_pin(self):
        _seed(self.path)
        source = OpenCodeV1Source(self.path)
        with closing(sqlite3.connect(self.path, timeout=0)) as writer:
            self.assertEqual("wal", writer.execute("PRAGMA journal_mode=WAL").fetchone()[0])
            with writer:
                _session(writer, "child", ROOT)
                _session(writer, "grandchild", "child")
                _prompt(writer, "grandchild", 100)
                _prompt(writer, ROOT, 1)
                _prompt(writer, ROOT, 2)
            writer.execute("PRAGMA wal_checkpoint(TRUNCATE)")

            with source.archive_cursor(ROOT) as cursor:
                root = cursor.read_page()
                messages = cursor.read_page()
                with writer:
                    writer.execute("UPDATE session SET title='Changed' WHERE id=?", (ROOT,))
                    writer.execute("UPDATE part SET data=? WHERE id='text-0001'", ('{"type":"text","text":"new"}',))
                    writer.execute("DELETE FROM part WHERE id='text-0002'")
                    writer.execute("DELETE FROM session WHERE id='child'")
                    _session(writer, "new-child", ROOT)
                    _prompt(writer, ROOT, 3)
                self.assertEqual(1, writer.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0])
                rest = _finish(cursor)
                self.assertEqual(0, writer.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0])
                with self.assertRaises(SourceConcurrentChangeError):
                    cursor.read_page()

            self.assertEqual("Synthetic root", root.sessions[0].title)
            self.assertEqual([_user(1), _assistant(1), _user(2), _assistant(2)],
                             [m.message_id for m in messages.messages])
            self.assertEqual([("child", ROOT), ("grandchild", "child")],
                             [(s.session_id, s.parent_session_id) for p in rest for s in p.sessions])
            self.assertEqual([(_user(100), "grandchild"), (_assistant(100), "grandchild")],
                             [(m.message_id, m.session_id) for p in rest for m in p.messages])
            self.assertEqual([("text-0001", _user(1), "original"), ("text-0002", _user(2), "original"),
                              ("text-0100", _user(100), "original")],
                             [(p.part_id, p.message_id, p.data["text"]) for page in rest for p in page.parts
                              if p.kind == "text"])

            with source.archive_cursor(ROOT) as cursor:
                fresh = _finish(cursor)
            self.assertEqual([(ROOT, "Changed"), ("new-child", "Synthetic root")],
                             [(s.session_id, s.title) for p in fresh for s in p.sessions])
            self.assertEqual([("text-0001", "new"), ("text-0003", "original")],
                             [(p.part_id, p.data["text"]) for page in fresh for p in page.parts if p.kind == "text"])

    def test_missing_bounded_child_index_fails_before_emitting_or_scanning_facts(self):
        _seed(self.path, parent_index=False)
        source = _MeasuredSource(self.path)
        before = self.path.read_bytes()

        with self.assertRaisesRegex(SourceSchemaError, "bounded archive seek for session"):
            with source.archive_cursor(ROOT):
                self.fail("unsupported shape opened")

        self.assertLess(source.steps, 1000)
        self.assertFalse(any("SELECT id," in sql for sql in source.sql))
        self.assertEqual(before, self.path.read_bytes())

    def test_nonunique_root_identity_does_not_qualify_even_with_an_id_index(self):
        _seed(self.path, unique_root=False)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE INDEX session_id_search ON session(id)")
            _session(db, ROOT, title="Duplicate")

        with self.assertRaisesRegex(SourceSchemaError, "unique archive identity for session"):
            with OpenCodeV1Source(self.path).archive_cursor(ROOT):
                self.fail("nonunique native identity opened")

    def test_utf16_text_is_sliced_at_the_byte_budget_without_skipping_a_part(self):
        _seed(self.path, encoding="UTF-16le")
        text = "ä☀" * 160_000  # Over half the 1 MiB page in native bytes.
        with closing(sqlite3.connect(self.path)) as db, db:
            _prompt(db, ROOT, 1)
            _prompt(db, ROOT, 2)
            db.execute("UPDATE part SET data=? WHERE id LIKE 'text-%'",
                       (json.dumps({"type": "text", "text": text}, ensure_ascii=False),))

        with OpenCodeV1Source(self.path).archive_cursor(ROOT) as cursor:
            pages = _finish(cursor)

        self.assertEqual([["step-0001", "text-0001", "step-0002"], ["text-0002"]],
                         [[p.part_id for p in page.parts] for page in pages if page.parts])
        self.assertTrue(all(p.data["text"] == text for page in pages for p in page.parts if p.kind == "text"))

    def test_oversized_payload_closes_pin_without_signaling_eof(self):
        _seed(self.path)
        with closing(sqlite3.connect(self.path)) as db, db:
            _prompt(db, ROOT, 1)
            db.execute("UPDATE message SET data=? WHERE id=?", (" " * (1024 * 1024 + 1), _user(1)))
        source = _MeasuredSource(self.path)

        with source.archive_cursor(ROOT) as cursor:
            self.assertFalse(cursor.read_page().eof)
            with self.assertRaisesRegex(SourceDataError, "decode budget"):
                cursor.read_page()
            self.assertFalse(source.db.in_transaction)
            with self.assertRaises(SourceConcurrentChangeError):
                cursor.read_page()

    def test_expired_closed_and_lost_pins_are_not_eof(self):
        _seed(self.path)
        source = _MeasuredSource(self.path)
        with patch("src.sources.v1_archive_cursor.monotonic", side_effect=[10, 41]):
            with source.archive_cursor(ROOT) as cursor:
                with self.assertRaises(SourceConcurrentChangeError):
                    cursor.read_page()
                self.assertFalse(source.db.in_transaction)

        with source.archive_cursor(ROOT) as cursor:
            cursor.close()
            self.assertFalse(source.db.in_transaction)
            with self.assertRaises(SourceConcurrentChangeError):
                cursor.read_page()

        with source.archive_cursor(ROOT) as cursor:
            source.db.rollback()
            with self.assertRaises(SourceConcurrentChangeError):
                cursor.read_page()

        with source.archive_cursor(ROOT) as cursor:
            source.db.close()
            with self.assertRaises(SourceConcurrentChangeError):
                cursor.read_page()

    def test_blob_with_valid_json_bytes_is_not_accepted_as_native_text(self):
        _seed(self.path)
        with closing(sqlite3.connect(self.path)) as db, db:
            _prompt(db, ROOT, 1)
            db.execute("UPDATE message SET data=? WHERE id=?", (b'{"role":"user"}', _user(1)))
        source = _MeasuredSource(self.path)

        with source.archive_cursor(ROOT) as cursor:
            self.assertFalse(cursor.read_page().eof)
            with self.assertRaisesRegex(SourceDataError, "not JSON text"):
                cursor.read_page()
            self.assertFalse(source.db.in_transaction)

    def test_page_crossing_pin_deadline_is_discarded(self):
        _seed(self.path)
        source = _MeasuredSource(self.path)

        with patch("src.sources.v1_archive_cursor.monotonic", side_effect=[10, 39, 40]):
            with source.archive_cursor(ROOT) as cursor:
                with self.assertRaises(SourceConcurrentChangeError):
                    cursor.read_page()
                self.assertFalse(source.db.in_transaction)


if __name__ == "__main__":
    unittest.main()
