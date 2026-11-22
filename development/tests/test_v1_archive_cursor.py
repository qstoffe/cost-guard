from contextlib import closing, contextmanager
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from src.analysis.causal import trace_entries
from src.application.v1_archive_trace import V1ArchiveTrace
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


def _trace_fixture(path, size):
    _seed(path)
    with closing(sqlite3.connect(path)) as db, db:
        _session(db, "child", ROOT)

        def message(key, clock, *, session=ROOT, **data):
            db.execute("INSERT INTO message VALUES(?,?,?,?,?)", (key, session, clock, clock, json.dumps(data)))

        def part(key, owner, clock, *, session=ROOT, **data):
            db.execute("INSERT INTO part VALUES(?,?,?,?,?,?)", (key, owner, session, clock, clock, json.dumps(data)))

        selection = {"providerID": "synthetic", "modelID": "sample", "variant": "medium"}
        message("tied-prompt", 100, role="user")
        part("tied-text", "tied-prompt", 100, type="text", text="PRIVATE_FIXTURE_TRANSCRIPT")
        message("wide", 400, role="assistant", parentID="continuation", **selection,
                time={"created": 400, "completed": 500}, tokens={"input": 9999})
        for number in range(size):
            part(f"response-{number:05d}", "wide", 401 + number, type="text", text="PRIVATE_FIXTURE_TRANSCRIPT")
        part("late-step", "wide", 500, type="step-finish", cost=0.5, tokens={"input": 17, "cache": {"read": 0}})
        # Fill output pages with noncalls. Put the other tied boundary later
        # in acquisition order and visit its part after the first boundary.
        for number in range(130):
            message(f"noncall-{number:05d}", 42, role="other")
        message("tied-task", 100, role="user", model=selection)
        part("task-later", "tied-task", 102, type="subtask", model={"variant": "high"})
        part("task-earlier", "tied-task", 101, type="subtask", model={"variant": "low"})
        message("continuation", 200, role="user", model=selection)
        message("synthetic", 210, role="user", model={**selection, "variant": "low"})
        part("synthetic-continue", "synthetic", 210, type="text", synthetic=True,
             text="Summarize the task tool output above and continue with your task.")
        message("at-tie", 100, role="user")
        message("unknown", 600, role="assistant", parentID="synthetic", **selection)
        part("unknown-reason", "unknown", 600, type="reasoning", text="PRIVATE_FIXTURE_TRANSCRIPT")
        message("same-clock", 601, role="assistant", parentID="at-tie", **selection, tokens={"input": 0})
        message("selected", 602, role="assistant", parentID="tied-task", **selection, tokens={"output": 5})
        message("child-call", 601, session="child", role="assistant", parentID="tied-task", **selection,
                tokens={"input": 8})
        message("no-response", 700, role="assistant", parentID="continuation", **selection)


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

    def test_bounded_trace_matches_whole_snapshot_with_a_late_step_and_tied_continuations(self):
        for size in (140, 2200):
            with self.subTest(parts=size):
                source_path = self.path.with_name(f"source-{size}.db")
                stage_path = self.path.with_name(f"stage-{size}.db")
                _trace_fixture(source_path, size)
                source = OpenCodeV1Source(source_path)
                subscriptions = frozenset({"synthetic"})
                expected = trace_entries(source.load_session_snapshot(ROOT), subscription_providers=subscriptions)
                with closing(sqlite3.connect(stage_path)) as db:
                    with source.archive_cursor(ROOT) as cursor:
                        builder = V1ArchiveTrace(source, cursor, db, subscription_providers=subscriptions)
                        with self.assertRaisesRegex(SourceDataError, "not ready"):
                            builder.trace_turn()
                        work = 0

                        def progress():
                            nonlocal work
                            work += 1
                            return 0

                        db.set_progress_handler(progress, 1)
                        costs = []
                        for _ in range(80):
                            start = work
                            if builder.capture_turn():
                                break
                            costs.append(work - start)
                        else:
                            self.fail("source trace capture did not reach EOF")
                    for _ in range(25):
                        if builder.prepare_turn():
                            break
                    else:
                        self.fail("fallback preparation did not reach EOF")
                    result = []
                    for _ in range(10):
                        page = builder.trace_turn()
                        if page is None:
                            break
                        result.extend(page)
                    else:
                        self.fail("trace replay did not reach EOF")

                self.assertEqual(expected, tuple(result))
                self.assertNotIn(b"PRIVATE_FIXTURE_TRANSCRIPT", stage_path.read_bytes())
                self.assertEqual(["wide:late-step", "unknown", "child-call", "same-clock", "selected"],
                                 [entry.invocation_id for entry in result])
                self.assertEqual([None, "tied-task", None, None, "tied-task"],
                                 [entry.logical_prompt_id for entry in result])
                self.assertEqual(["medium", "low", None, None, "high"], [entry.selected_effort for entry in result])
                self.assertEqual([("input", "cache_read"), (), ("input",), ("input",), ("output",)],
                                 [entry.tokens.known_fields for entry in result])
                self.assertEqual(17, result[0].tokens.input)
                self.assertEqual(ROOT, result[2].parent_session_id)
                self.assertLess(max(costs), 15000)

    def test_dense_root_replays_exact_order_and_identity_across_many_trace_turns(self):
        _seed(self.path)
        with closing(sqlite3.connect(self.path)) as db, db:
            for number in reversed(range(PROMPTS)):
                _prompt(db, ROOT, number)
        source = _MeasuredSource(self.path)
        expected = trace_entries(source.load_session_snapshot(ROOT))

        with closing(sqlite3.connect(":memory:")) as db:
            with source.archive_cursor(ROOT) as cursor:
                builder = V1ArchiveTrace(source, cursor, db)
                for _ in range(100):
                    if builder.capture_turn():
                        break
                else:
                    self.fail("dense input did not reach EOF")
            for _ in range(100):
                if builder.prepare_turn():
                    break
            else:
                self.fail("dense fallback did not reach EOF")
            result, sizes = [], []
            for _ in range(60):
                page = builder.trace_turn()
                if page is None:
                    break
                result.extend(page)
                sizes.append(len(page))
            else:
                self.fail("dense trace did not reach EOF")

        self.assertEqual([32] * 42 + [22], sizes)
        self.assertEqual(tuple(range(PROMPTS)), tuple(entry.sort_order for entry in result))
        self.assertEqual([_user(n) for n in range(PROMPTS)], [entry.logical_prompt_id for entry in result])
        self.assertEqual(expected, tuple(result))

    def test_failed_cursor_cannot_turn_partial_input_into_replayable_trace(self):
        _seed(self.path)
        source = OpenCodeV1Source(self.path)
        before = self.path.read_bytes()

        with closing(sqlite3.connect(":memory:")) as stage, source.archive_cursor(ROOT) as cursor:
            with closing(sqlite3.connect(self.path)) as wrong:
                with self.assertRaisesRegex(ValueError, "private staging database"):
                    V1ArchiveTrace(source, cursor, wrong)
            builder = V1ArchiveTrace(source, cursor, stage)
            self.assertFalse(builder.capture_turn())
            cursor.close()
            with self.assertRaises(SourceConcurrentChangeError):
                builder.capture_turn()
            with self.assertRaisesRegex(SourceDataError, "not ready"):
                builder.prepare_turn()
            with self.assertRaisesRegex(SourceDataError, "not ready"):
                builder.trace_turn()

        self.assertEqual(before, self.path.read_bytes())


if __name__ == "__main__":
    unittest.main()
