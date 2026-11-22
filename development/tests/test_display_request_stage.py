from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import sqlite3
import tempfile
from threading import Event
import unittest

from src.cache.display_history import DisplayHistory, SessionChange, SessionFact
from src.cache.display_request_install import INSTALL_SCHEMA, RequestInstallWitness, install_usage_slot
from src.cache.display_request_materialize import fixture_usage_fold_schema, fold_slot_correction, materialize_slot_timing
from src.cache.display_request_overlay import RequestSlot, countable_request_rows, request_birth_slice, request_clock_slice
from src.cache.display_request_slot_stats import slot_stats_candidates
from src.cache.display_request_stage import (
    RequestInputScope,
    append_request_attribution,
    append_request_input,
    open_request_input,
    open_request_preparation,
    prepare_fork_page,
    prepare_request_page,
    request_stage_schema,
    seal_request_input,
)
from src.cache.display_requests import REQUEST_COLUMNS, DisplayRequest, RequestRoster, publish_roster
from src.cache.display_stats_evidence import ResponseTiming, StatsCapture
from src.cache.display_stats_requests import StatsRequestIdentity, read_stats_candidates
from src.cache.display_stats_revision import StatsVersion, retained_stats_version
from src.cache.display_usage_reader import advance_usage_revision, retained_usage_version, usage_version


SOURCE = "synthetic"
SCOPE = RequestInputScope(SOURCE, "binding", 0, 5, "A", "rev-A", 0, "price", "dependency")
_SLOT = """
    CREATE TABLE probe_installed (
        source TEXT PRIMARY KEY, attempt TEXT NOT NULL REFERENCES archive_request_preparations(attempt),
        root_id TEXT NOT NULL, source_revision TEXT NOT NULL, usage_revision INTEGER NOT NULL
    ) WITHOUT ROWID;
"""


def _request(key, *, root="A", clock=20, tokens=9, fork=None, number=0):
    return DisplayRequest(
        key, clock, fork, "member", "prompt", "provider", "model", "recorded", None, (tokens, 1, 0, 2, 0),
        31, None, None, "included_subscription", (Decimal("0.50"), Decimal(0), Decimal(0), Decimal(1)),
        "medium", False, root, number,
    )


def _install(db, attempt, *, incarnation=5, dependency="dependency"):
    """Repository proof only: one indexed metadata CAS without touching live tables."""
    return db.execute("""
        INSERT INTO probe_installed
        SELECT i.source,p.attempt,i.root_id,i.revision,p.usage_revision+(p.edits>0)
        FROM archive_request_preparations AS p JOIN archive_request_inputs AS i USING(run)
        JOIN sources AS s USING(source)
        JOIN sessions AS root ON root.source=i.source AND root.session_id=i.root_id
        LEFT JOIN session_progress AS r ON r.source=i.source AND r.session_id=i.root_id
        LEFT JOIN archive_usage_revisions AS u ON u.source=i.source
        WHERE p.attempt=? AND p.sealed AND i.binding='binding' AND i.incarnation=? AND i.dependency=?
          AND root.source_present AND root.revision=i.revision AND coalesce(r.progress,0)=i.progress
          AND s.archive_epoch=i.archive_epoch AND coalesce(u.revision,0)=p.usage_revision
          AND NOT EXISTS(SELECT 1 FROM archive_prepare_forks f INDEXED BY archive_prepare_pending_forks
                          WHERE f.attempt=p.attempt AND NOT f.done)
          AND NOT EXISTS(SELECT 1 FROM archive_prepare_winners w INDEXED BY archive_prepare_pending_winners
                          WHERE w.attempt=p.attempt AND NOT w.done)
        ON CONFLICT(source) DO NOTHING
    """, (attempt, incarnation, dependency)).rowcount


def _visible(db, start, stop):
    installed = db.execute("SELECT attempt,usage_revision FROM probe_installed WHERE source=?", (SOURCE,)).fetchone()
    attempt, birth = installed if installed else ("", 0)
    return db.execute("""
        SELECT b.request_key,b.clock_ms,b.input_tokens,b.first_revision,b.dedup_tree
        FROM archive_requests b
        WHERE b.source=? AND b.clock_ms>=? AND b.clock_ms<?
          AND NOT EXISTS(SELECT 1 FROM archive_prepare_requests p WHERE p.source=? AND p.request_key=b.request_key)
        UNION ALL
        SELECT p.request_key,p.clock_ms,p.input_tokens,coalesce(p.first_revision,?),p.dedup_tree
        FROM archive_prepare_requests p WHERE p.source=? AND p.clock_ms>=? AND p.clock_ms<?
        ORDER BY 2,1
    """, (SOURCE, start, stop, attempt, birth, attempt, start, stop)).fetchall()


def _forks(db, fork):
    active = db.execute("SELECT attempt FROM probe_installed WHERE source=?", (SOURCE,)).fetchone()
    attempt = active[0] if active else ""
    return db.execute("""
        SELECT b.dedup_tree,b.multiplicity,b.first_ordinal,b.first_session
        FROM archive_fork_trees b WHERE b.source=? AND b.fork_key=?
          AND NOT EXISTS(SELECT 1 FROM archive_prepare_forks p
                         WHERE p.attempt=? AND p.fork_key=b.fork_key AND p.dedup_tree=b.dedup_tree)
        UNION ALL
        SELECT p.dedup_tree,p.multiplicity,p.first_ordinal,p.first_session
        FROM archive_prepare_forks p WHERE p.attempt=? AND p.fork_key=? AND p.multiplicity>0
        ORDER BY 2 DESC,3,4,1
    """, (SOURCE, fork, attempt, attempt, fork)).fetchall()


def _fold_one(db, slot, key, expected):
    """Fixture-only CAS: materialize one row with installed triggers intact."""
    if db.execute("SELECT attempt FROM probe_installed WHERE source=?", (SOURCE,)).fetchone() != (slot.attempt,):
        return False
    columns = ",".join(REQUEST_COLUMNS)
    staged = db.execute(f"""
        SELECT {columns},coalesce(first_revision,?) FROM archive_prepare_requests WHERE source=? AND request_key=?
    """, (slot.birth, slot.attempt, key)).fetchone()
    if staged is None:
        return False
    parameters = ",".join("?" for _ in staged)
    if expected is None:
        changed = db.execute(f"""
            INSERT INTO archive_requests(source,{columns},first_revision) VALUES(?,{parameters})
            ON CONFLICT(source,request_key) DO NOTHING
        """, (SOURCE, *staged)).rowcount
    else:
        changed = db.execute(f"""
            UPDATE archive_requests SET ({columns},first_revision)=({parameters})
            WHERE source=? AND request_key=? AND ({columns},first_revision) IS ({parameters})
        """, (*staged, SOURCE, key, *expected)).rowcount
    if changed:
        db.execute("DELETE FROM archive_prepare_requests WHERE source=? AND request_key=?", (slot.attempt, key))
    return bool(changed)


def _install_fixture_fold_guard(db):
    """Only in the test database: distinguish exact materialization from writes."""
    db.execute("CREATE TABLE probe_fold_before AS SELECT * FROM archive_requests WHERE 0")
    columns = (*REQUEST_COLUMNS, "first_revision")
    old = " AND ".join(f"OLD.{column} IS b.{column}" for column in columns)
    new = " AND ".join(f"NEW.{column} IS p.{column}" for column in columns)
    guard = f"""NOT EXISTS(
        SELECT 1 FROM probe_fold_before b JOIN probe_installed i USING(source)
        JOIN archive_prepare_requests p ON p.source=i.attempt AND p.request_key=b.request_key
        WHERE OLD.source=b.source AND NEW.source=b.source AND {old} AND {new}
    )"""
    for trigger, connective in (("archive_usage_correction", "WHEN"),
                                ("archive_stats_request_identity_stale", "AND")):
        sql, = db.execute("SELECT sql FROM sqlite_schema WHERE type='trigger' AND name=?", (trigger,)).fetchone()
        before, body = sql.split("BEGIN", 1)
        db.execute(f"DROP TRIGGER {trigger}")
        db.execute(f"{before} {connective} {guard} BEGIN {body}")


class DisplayRequestStageTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.history = DisplayHistory(Path(temp.name))
        self.history.initialize()
        with self.history._connect() as db:
            db.executescript(request_stage_schema() + INSTALL_SCHEMA + _SLOT)
        with self.write() as db:
            db.execute("INSERT INTO sources(source) VALUES(?)", (SOURCE,))
            db.executemany("""
                INSERT INTO sessions(source,session_id,revision,title,title_key,source_present)
                VALUES(?,?,?,?,?,1)
            """, ((SOURCE, root, "rev-" + root, root, root.lower()) for root in ("A", "B")))

    @contextmanager
    def write(self):
        with self.history._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()

    def _stage(self, requests):
        with self.write() as db:
            self.assertTrue(open_request_input(db, "spool", SCOPE))
        count = 0
        for offset in range(0, len(requests), 32):
            with self.write() as db:
                self.assertTrue(append_request_input(db, "spool", count, requests[offset:offset + 32]))
            count += 1
        with self.write() as db:
            self.assertTrue(seal_request_input(db, "spool", count))

    def _prepare(self, attempt):
        with self.write() as db:
            self.assertTrue(open_request_preparation(db, "spool", attempt))
        for work in (prepare_request_page, prepare_fork_page):
            for _ in range(160):
                with self.write() as db:
                    result = work(db, attempt)
                if result is True:
                    break
                self.assertIs(result, False, work.__name__)
            else:
                self.fail(f"{work.__name__} did not reach EOF")

    def test_spool_restarts_between_pages_and_seal_never_changes_display_readiness(self):
        evidence = replace(_request(b"step", clock=200),
                           response=ResponseTiming(100, 40),
                           stats_identity=StatsRequestIdentity(b"m" * 32, b"s" * 32, b"h" * 32, b"k" * 32, "medium"))

        with self.write() as db:
            self.assertTrue(open_request_input(db, "spool", SCOPE))
            self.assertFalse(append_request_input(db, "spool", 1, (evidence,)))
            self.assertFalse(seal_request_input(db, "spool", 1))
            self.assertFalse(open_request_preparation(db, "spool", "early"))
            self.assertTrue(append_request_input(db, "spool", 0, (evidence,)))
        with self.write() as db:
            self.assertFalse(append_request_input(db, "spool", 0, (evidence,)))
            self.assertTrue(seal_request_input(db, "spool", 1))
            self.assertFalse(append_request_input(db, "spool", 1, (_request(b"late"),)))

        with self.history._connect(read=True) as db:
            self.assertEqual((1, 1), db.execute("SELECT next_page,sealed FROM archive_request_inputs").fetchone())
            self.assertEqual((b"step", 100, 40, 0, b"m" * 32, b"s" * 32, b"h" * 32, b"k" * 32, "medium"),
                             db.execute("""
                                 SELECT request_key,timing_start,timing_duration,timing_excluded,message_key,step_key,
                                        sample_hash,source_model_key,stats_effort FROM archive_input_requests
                             """).fetchone())
            for table in ("archive_requests", "archive_request_rosters", "archive_stats_request_ready", "session_progress"):
                self.assertIsNone(db.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone(), table)
            self.assertEqual(0, usage_version(db, SOURCE).revision)

    def test_page_errors_do_not_advance_progress_or_accept_oversized_payload(self):
        with self.write() as db:
            self.assertTrue(open_request_input(db, "spool", SCOPE))
        with self.assertRaises(sqlite3.IntegrityError), self.write() as db:
            append_request_input(db, "spool", 0, (_request(b"same"), _request(b"same")))
        with self.assertRaisesRegex(ValueError, "exceeds_size"), self.write() as db:
            append_request_input(db, "spool", 0, (replace(_request(b"a"), effort="x" * (128 * 1024)),))
        with self.assertRaisesRegex(ValueError, "invalid_request_input_page"), self.write() as db:
            append_request_input(db, "spool", 0, tuple(_request(bytes([i])) for i in range(33)))

        with self.history._connect(read=True) as db:
            self.assertEqual((0, 0), db.execute("SELECT next_page,sealed FROM archive_request_inputs").fetchone())
            self.assertIsNone(db.execute("SELECT 1 FROM archive_input_requests").fetchone())

    def test_causal_edges_are_atomic_ordered_and_can_share_a_physical_call(self):
        with self.write() as db:
            self.assertTrue(open_request_input(db, "spool", SCOPE))
            self.assertTrue(append_request_input(db, "spool", 0, (_request(b"one"),)))
            self.assertFalse(append_request_attribution(db, "spool", 2, ((b"one", "a"),)))
        with self.assertRaises(sqlite3.IntegrityError), self.write() as db:
            append_request_attribution(db, "spool", 1, ((b"one", "a"), (b"one", "a")))
        with self.write() as db:
            self.assertTrue(append_request_attribution(db, "spool", 1, ((b"one", "a"), (b"one", "b"))))
            self.assertFalse(append_request_input(db, "spool", 2, (_request(b"late"),)))
            self.assertTrue(seal_request_input(db, "spool", 2))
            self.assertFalse(append_request_attribution(db, "spool", 2, ((b"one", "late"),)))

        with self.history._connect(read=True) as db:
            self.assertEqual([(b"one", "a"), (b"one", "b")], db.execute("""
                SELECT request_key,prompt_id FROM archive_input_attribution WHERE run='spool' ORDER BY prompt_id
            """).fetchall())
            self.assertIsNone(db.execute("SELECT 1 FROM archive_prompt_attribution").fetchone())

    def test_effective_clock_scan_cannot_jump_an_unresolved_shadow_prefix(self):
        with self.write() as db:
            publish_roster(db, SOURCE, "A", "rev-A", RequestRoster("price", (
                _request(b"left", clock=10), _request(b"middle", clock=20), _request(b"keep", clock=30),
                _request(b"moved-in", clock=90),
            ), ()))
        self._stage((_request(b"left", clock=70), _request(b"middle", clock=80), _request(b"moved-in", clock=40)))
        self._prepare("candidate")

        with self.history._connect(read=True) as db:
            db.execute("BEGIN")
            old = request_clock_slice(db, SOURCE, 1, 50, limit=2)
            self.assertEqual([10, 20], [row[1] for row in old.rows])

            with self.write() as writer:
                self.assertEqual(1, _install(writer, "candidate"))
                attempt, birth = writer.execute("SELECT attempt,usage_revision FROM probe_installed").fetchone()
                slot = RequestSlot(attempt, birth)
            old_tail = request_clock_slice(db, SOURCE, 1, 50, cursor=old.next_cursor, limit=2)
            self.assertEqual([30], [row[1] for row in old_tail.rows])
            self.assertIsNone(old_tail.next_cursor)

        with self.history._connect(read=True) as db:
            db.execute("BEGIN")
            first = request_clock_slice(db, SOURCE, 1, 50, slot=slot, limit=2)
            self.assertEqual((), first.rows)
            self.assertIsNotNone(first.next_cursor)
            self.assertEqual((20, b"middle"), first.next_cursor.scanned_through)
            self.assertIsNone(request_clock_slice(db, SOURCE, 1, 50, slot=slot, cursor=old.next_cursor, limit=2))
            final = request_clock_slice(db, SOURCE, 1, 50, slot=slot, cursor=first.next_cursor, limit=2)
            self.assertEqual([(b"keep", 30), (b"moved-in", 40)], [row[:2] for row in final.rows])
            self.assertEqual([1, 1], [row[-1] for row in final.rows])
            self.assertIsNone(final.next_cursor)

    def test_clock_cursor_rejects_layout_change_even_at_identical_usage_revision(self):
        self._stage(tuple(_request(key, clock=20) for key in (b"a", b"b", b"c")))
        self._prepare("candidate")
        with self.write() as db:
            self.assertEqual(1, _install(db, "candidate"))
            attempt, birth = db.execute("SELECT attempt,usage_revision FROM probe_installed").fetchone()
        slot = RequestSlot(attempt, birth)
        with self.history._connect(read=True) as db:
            db.execute("BEGIN")
            first = request_clock_slice(db, SOURCE, 1, 50, slot=slot, limit=2)
            self.assertEqual([b"a", b"b"], [row[0] for row in first.rows])
            version = usage_version(db, SOURCE)

        # Fixture simulates one representation-only move, not production fold.
        with self.write() as db:
            columns = ",".join(REQUEST_COLUMNS)
            db.execute(f"""
                INSERT INTO archive_requests(source,{columns},first_revision)
                SELECT ?,{columns},? FROM archive_prepare_requests WHERE source=? AND request_key=?
            """, (SOURCE, birth, slot.attempt, b"c"))
            db.execute("DELETE FROM archive_prepare_requests WHERE source=? AND request_key=?",
                       (slot.attempt, b"c"))
        moved = replace(slot, layout=1)
        with self.history._connect(read=True) as db:
            db.execute("BEGIN")
            self.assertEqual(version, usage_version(db, SOURCE))
            self.assertIsNone(request_clock_slice(db, SOURCE, 1, 50, slot=moved, cursor=first.next_cursor, limit=2))
            current = request_clock_slice(db, SOURCE, 1, 50, slot=moved, limit=2)
            tail = request_clock_slice(db, SOURCE, 1, 50, slot=moved, cursor=current.next_cursor, limit=2)
            self.assertEqual([b"a", b"b", b"c"], [row[0] for row in current.rows + tail.rows])
            self.assertIsNone(tail.next_cursor)

    def test_birth_scan_preserves_correction_birth_and_seeks_through_equal_revision_keys(self):
        count = 1366
        keys = tuple(number.to_bytes(2, "big") for number in range(count))
        with self.write() as db:
            publish_roster(db, SOURCE, "A", "rev-A",
                           RequestRoster("price", tuple(_request(key) for key in keys), ()))
        self._stage(tuple(_request(key, tokens=70) for key in keys) + (_request(b"\0", tokens=20),))
        self._prepare("candidate")
        with self.write() as db:
            self.assertEqual(1, _install(db, "candidate"))
            attempt, birth = db.execute("SELECT attempt,usage_revision FROM probe_installed").fetchone()
        slot = RequestSlot(attempt, birth)

        with self.history._connect(read=True) as db:
            db.execute("BEGIN")
            self.assertIsNone(request_birth_slice(db, SOURCE, 1, slot=slot))
            steps = 0

            def progress():
                nonlocal steps
                steps += 1
                return 0

            db.set_progress_handler(progress, 1)
            found, work = [], []
            cursor = None
            for _ in range(50):
                steps = 0
                page = request_birth_slice(db, SOURCE, 2, slot=slot, cursor=cursor, limit=32)
                self.assertLessEqual(len(page.rows), 32)
                found.extend((row[0], row[9], row[-1]) for row in page.rows)
                work.append(steps)
                cursor = page.next_cursor
                if cursor is None:
                    break
            else:
                self.fail("effective birth scan exceeded 50 slices")
            db.set_progress_handler(None, 0)

        expected = [(key, 70, 1) for key in keys] + [(b"\0", 20, 2)]
        self.assertEqual(expected, found)
        self.assertLess(max(work), 6000)

    def test_existing_fold_triggers_invalidate_fresh_stats_after_publication(self):
        key = b"corrected"
        recipe = StatsRequestIdentity(b"m" * 32, None, b"s" * 32, b"p" * 32, "medium")
        initial = replace(_request(key), stats_identity=recipe)
        capture = StatsCapture((), False, None, ())
        columns = ",".join(REQUEST_COLUMNS)
        with self.write() as db:
            publish_roster(db, SOURCE, "A", "rev-A", RequestRoster("price", (initial,), (), stats=capture))
            expected = db.execute(f"SELECT {columns},first_revision FROM archive_requests").fetchone()
            old = usage_version(db, SOURCE)
        self._stage((replace(initial, clock_ms=40, effort="high"),))
        self._prepare("candidate")

        with self.write() as db:
            self.assertEqual(1, _install(db, "candidate"))
            attempt, birth = db.execute("SELECT attempt,usage_revision FROM probe_installed").fetchone()
            slot = RequestSlot(attempt, birth)
            # Simulate a semantic publication that creates fresh Stats evidence.
            advance_usage_revision(db, SOURCE, changed_winner=True)
            new = usage_version(db, SOURCE)
            next_evidence = db.execute(
                "SELECT revision+1 FROM archive_stats_revisions WHERE source=?", (SOURCE,)).fetchone()[0]
            db.execute("""
                UPDATE archive_stats_request_identity SET effort='high',first_revision=? WHERE source=? AND request_key=?
            """, (next_evidence, SOURCE, key))
            db.execute("UPDATE archive_stats_revisions SET revision=? WHERE source=?", (next_evidence, SOURCE))
            published_stats = StatsVersion(new, next_evidence)
            self.assertEqual(published_stats, retained_stats_version(db, SOURCE, published_stats))
            self.assertEqual(new, retained_usage_version(db, SOURCE, new))
            self.assertIsNone(retained_usage_version(db, SOURCE, old))
            self.assertEqual("high", db.execute("SELECT effort FROM archive_stats_request_identity").fetchone()[0])

            db.execute("SAVEPOINT fold")
            self.assertTrue(_fold_one(db, slot, key, expected))
            self.assertEqual([(key, 40)], [row[:2] for row in request_clock_slice(db, SOURCE, 1, 50, slot=slot).rows])
            self.assertEqual(new, usage_version(db, SOURCE))
            self.assertIsNone(retained_usage_version(db, SOURCE, new))
            self.assertIsNone(retained_usage_version(db, SOURCE, old))
            self.assertIsNone(db.execute("SELECT 1 FROM archive_stats_request_identity").fetchone())
            self.assertIsNone(db.execute("SELECT 1 FROM archive_stats_request_ready").fetchone())
            db.execute("ROLLBACK TO fold")
            db.execute("RELEASE fold")
            self.assertEqual(new, retained_usage_version(db, SOURCE, new))
            self.assertEqual(published_stats, retained_stats_version(db, SOURCE, published_stats))
            self.assertEqual("high", db.execute("SELECT effort FROM archive_stats_request_identity").fetchone()[0])

            db.execute("UPDATE archive_requests SET input_tokens=99 WHERE source=? AND request_key=?", (SOURCE, key))
            self.assertFalse(_fold_one(db, slot, key, expected), "same slot does not fence a changed base row")
            self.assertEqual((99,), db.execute("SELECT input_tokens FROM archive_requests").fetchone())
            self.assertEqual((40,), db.execute("SELECT clock_ms FROM archive_prepare_requests").fetchone())

    def test_new_request_needs_real_parent_before_dependent_evidence_can_commit(self):
        key = b"new"
        self._stage((_request(key, clock=40),))
        self._prepare("candidate")
        with self.write() as db:
            self.assertEqual(1, db.execute("PRAGMA foreign_keys").fetchone()[0])
            self.assertEqual(1, _install(db, "candidate"))
            attempt, birth = db.execute("SELECT attempt,usage_revision FROM probe_installed").fetchone()
            slot = RequestSlot(attempt, birth)
            self.assertEqual([(key, 40)], [row[:2] for row in request_clock_slice(db, SOURCE, 1, 50, slot=slot).rows])
            sql = "INSERT INTO archive_response_timing VALUES(?,?,40,10,25,0,1)"
            with self.assertRaisesRegex(sqlite3.IntegrityError, "FOREIGN KEY"):
                db.execute(sql, (SOURCE, key))

            self.assertTrue(_fold_one(db, slot, key, None))
            db.execute(sql, (SOURCE, key))
        with self.history._connect(read=True) as db:
            self.assertEqual((key, 1, 25), db.execute("""
                SELECT request_key,request.first_revision,duration_ms
                FROM archive_response_timing JOIN archive_requests AS request USING(source,request_key)
            """).fetchone())

    def test_exact_fixture_fold_guard_preserves_fresh_fences_but_does_not_exempt_other_updates(self):
        key = b"same"
        recipe = StatsRequestIdentity(b"m" * 32, None, b"s" * 32, b"p" * 32, "medium")
        initial = replace(_request(key), stats_identity=recipe)
        columns = ",".join(REQUEST_COLUMNS)
        with self.write() as db:
            publish_roster(db, SOURCE, "A", "rev-A",
                           RequestRoster("price", (initial,), (), stats=StatsCapture((), False, None, ())))
            expected = db.execute(f"SELECT {columns},first_revision FROM archive_requests").fetchone()
            old = usage_version(db, SOURCE)
        self._stage((replace(initial, effort="high"),))
        self._prepare("candidate")

        with self.write() as db:
            self.assertEqual(1, _install(db, "candidate"))
            slot = RequestSlot(*db.execute("SELECT attempt,usage_revision FROM probe_installed").fetchone())
            advance_usage_revision(db, SOURCE, changed_winner=True)
            new = usage_version(db, SOURCE)
            db.execute("UPDATE archive_stats_request_identity SET effort='high',first_revision=2")
            db.execute("UPDATE archive_stats_revisions SET revision=2 WHERE source=?", (SOURCE,))
            evidence = StatsVersion(new, 2)
            _install_fixture_fold_guard(db)
            db.execute("INSERT INTO probe_fold_before SELECT * FROM archive_requests WHERE source=? AND request_key=?",
                       (SOURCE, key))

            db.execute("SAVEPOINT ordinary")
            db.execute("UPDATE archive_requests SET effort='low' WHERE source=? AND request_key=?", (SOURCE, key))
            self.assertIsNone(retained_usage_version(db, SOURCE, new))
            self.assertIsNone(db.execute("SELECT 1 FROM archive_stats_request_identity").fetchone())
            self.assertIsNone(db.execute("SELECT 1 FROM archive_stats_request_ready").fetchone())
            db.execute("ROLLBACK TO ordinary")
            db.execute("RELEASE ordinary")

            self.assertTrue(_fold_one(db, slot, key, expected))
            self.assertIsNone(retained_usage_version(db, SOURCE, old))
            self.assertEqual(new, retained_usage_version(db, SOURCE, new))
            self.assertEqual(evidence, retained_stats_version(db, SOURCE, evidence))
            self.assertEqual("high", db.execute("SELECT effort FROM archive_stats_request_identity").fetchone()[0])
            self.assertEqual(("rev-A",), db.execute("SELECT source_revision FROM archive_stats_request_ready").fetchone())
            self.assertIsNone(db.execute("SELECT 1 FROM archive_prepare_requests").fetchone())

    def test_real_summary_writer_cannot_use_identical_fold_guard_and_rechecks_admission(self):
        key = b"same"
        initial = _request(key)
        replacement = replace(initial, effort="high")
        columns = ",".join(REQUEST_COLUMNS)
        with self.write() as db:
            publish_roster(db, SOURCE, "A", "rev-A", RequestRoster("price", (initial,), ()))
            expected = db.execute(f"SELECT {columns},first_revision FROM archive_requests").fetchone()
            _install_fixture_fold_guard(db)
        self._stage((replacement,))
        self._prepare("candidate")
        attempted, entered = Event(), Event()
        change = SessionChange(SessionFact("A", "rev-A", "A"), "rev-A", frozenset(),
                               previous_progress=0, request_roster=RequestRoster("price", (replacement,), ()))

        def ordinary_write():
            attempted.set()
            return self.history.commit_summary(SOURCE, change, archive_epoch=0, eligible=still_current)

        def still_current():
            entered.set()
            with self.history._connect(read=True) as reader:
                return reader.execute("SELECT 1 FROM archive_prepare_requests WHERE source='candidate'").fetchone() is not None

        with ThreadPoolExecutor(max_workers=1) as pool:
            with self.history._write_lock, self.write() as db:
                self.assertEqual(1, _install(db, "candidate"))
                slot = RequestSlot(*db.execute("SELECT attempt,usage_revision FROM probe_installed").fetchone())
                db.execute("INSERT INTO probe_fold_before SELECT * FROM archive_requests WHERE request_key=?", (key,))
                ordinary = pool.submit(ordinary_write)
                self.assertTrue(attempted.wait(5))
                self.assertFalse(entered.is_set())
                self.assertTrue(_fold_one(db, slot, key, expected))
                db.execute("DELETE FROM probe_fold_before")
            denied = ordinary.result(timeout=5)

        self.assertTrue(entered.is_set())
        self.assertEqual(0, denied.applied)
        accepted = self.history.commit_summary(SOURCE, change, archive_epoch=0, eligible=lambda: True)
        self.assertEqual(1, accepted.applied)
        with self.history._connect(read=True) as db:
            self.assertEqual(("high",), db.execute("SELECT effort FROM archive_requests").fetchone())
            self.assertIsNone(db.execute("SELECT 1 FROM probe_fold_before").fetchone())

    def test_peer_commit_invalidates_next_prepare_page_and_spool_replays_without_early_birth(self):
        shared = b"z-shared"
        incoming = tuple(_request(n.to_bytes(2, "big")) for n in range(64)) + (_request(shared, tokens=70),)
        self._stage(incoming)
        with self.write() as db:
            self.assertTrue(open_request_preparation(db, "spool", "first"))
            self.assertIs(prepare_request_page(db, "first"), False)
        with self.write() as db:
            publish_roster(db, SOURCE, "B", "rev-B", RequestRoster("peer-price", (_request(shared, root="B"),), ()))
        with self.write() as db:
            self.assertIsNone(prepare_request_page(db, "first"))
            self.assertTrue(open_request_preparation(db, "spool", "retry"))
        for expected in (False, False, True):
            with self.write() as db:
                self.assertIs(prepare_request_page(db, "retry"), expected)

        with self.history._connect(read=True) as db:
            self.assertEqual((shared, 1, 9, "B"), db.execute("""
                SELECT request_key,first_revision,input_tokens,dedup_tree FROM archive_requests
            """).fetchone())
            self.assertEqual((shared, 1, 70, "A"), db.execute("""
                SELECT request_key,first_revision,input_tokens,dedup_tree FROM archive_prepare_requests
                WHERE source='retry' AND request_key=?
            """, (shared,)).fetchone())
            self.assertEqual(64, db.execute("""
                SELECT count(*) FROM archive_prepare_requests WHERE source='retry' AND first_revision IS NULL
            """).fetchone()[0])
            self.assertEqual(32, db.execute("""
                SELECT count(*) FROM archive_prepare_requests WHERE source='first'
            """).fetchone()[0])
            self.assertEqual((1, 1), db.execute("""
                SELECT usage_revision,sealed FROM archive_request_preparations WHERE attempt='retry'
            """).fetchone())
            self.assertEqual([("B", "rev-B")], db.execute("SELECT root_id,revision FROM archive_request_rosters").fetchall())

    def test_clear_epoch_fences_persistent_private_pages(self):
        self._stage((_request(b"old"),))
        with self.write() as db:
            self.assertTrue(open_request_preparation(db, "spool", "attempt"))
        state = self.history.source_state(SOURCE)
        self.assertEqual(1, self.history.clear_confirmed_sessions(SOURCE, state).archive_epoch)

        with self.write() as db:
            self.assertIsNone(prepare_request_page(db, "attempt"))
            self.assertFalse(open_request_preparation(db, "spool", "against-cleared-db"))
            self.assertFalse(open_request_input(db, "stale-epoch", SCOPE))


    def test_sealed_correction_replays_after_peer_and_resolves_shadows_before_scope(self):
        fork = b"same-fork"
        initial = (_request(b"omitted", clock=15, fork=fork, number=6),)
        peer = (_request(b"shared", root="B", clock=25, fork=fork, number=2),
                _request(b"peer-only", root="B", clock=30, fork=fork, number=5))
        correction = (_request(b"shared", clock=120, tokens=70, fork=fork, number=9),
                      _request(b"new", clock=140, fork=fork, number=8))
        with self.write() as db:
            publish_roster(db, SOURCE, "A", "older", RequestRoster("older-price", initial, ()))
        self._stage(correction)
        self._prepare("stale")

        with self.write() as db:
            publish_roster(db, SOURCE, "B", "rev-B", RequestRoster("peer-price", peer, ()))
        with self.write() as db:
            self.assertEqual(0, _install(db, "stale"))
        with self.history._connect(read=True) as db:
            self.assertEqual("B", _forks(db, fork)[0][0])
            self.assertEqual([(b"omitted", 15, 9, 1, "A"), (b"shared", 25, 9, 2, "B"), (b"peer-only", 30, 9, 2, "B")],
                             _visible(db, 0, 100))
            self.assertIsNone(db.execute("SELECT 1 FROM probe_installed").fetchone())
            self.assertEqual(2, usage_version(db, SOURCE).revision)
            self.assertEqual(("older",), db.execute(
                "SELECT revision FROM archive_request_rosters WHERE root_id='A'").fetchone())

        self._prepare("ready")
        with self.history._connect(read=True) as reader:
            reader.execute("BEGIN")
            old = _visible(reader, 0, 100)
            with self.write() as db:
                self.assertEqual(0, _install(db, "ready", incarnation=6))
                self.assertEqual(0, _install(db, "ready", dependency="new-price"))
                self.assertEqual(1, _install(db, "ready"))
            self.assertEqual(old, _visible(reader, 0, 100))
            self.assertEqual("B", _forks(reader, fork)[0][0])

        with self.history._connect(read=True) as db:
            visible = _visible(db, 0, 200)
            forks = _forks(db, fork)
            self.assertEqual([(b"omitted", 15, 9, 1, "A"), (b"peer-only", 30, 9, 2, "B")], _visible(db, 0, 100))
            self.assertEqual([(b"shared", 120, 70, 2, "A"), (b"new", 140, 9, 3, "A")], _visible(db, 100, 200))
            self.assertEqual([("A", 3, 6, "member"), ("B", 1, 5, "member")], forks)
            self.assertEqual(("A", 1), db.execute("""
                SELECT winner,changed FROM archive_prepare_winners WHERE attempt='ready' AND fork_key=? AND done
            """, (fork,)).fetchone())
        with self.write() as db:
            db.execute("DELETE FROM probe_installed")
            publish_roster(db, SOURCE, "A", "rev-A", RequestRoster("price", correction, ()))
        with self.history._connect(read=True) as db:
            self.assertEqual(visible, _visible(db, 0, 200))
            self.assertEqual(forks, _forks(db, fork))

    def test_metadata_install_vm_work_does_not_grow_with_prepared_rows(self):
        counts = []
        for size in (1, 1366):
            with self.subTest(size=size):
                self._stage(tuple(_request(n.to_bytes(2, "big")) for n in range(size)))
                self._prepare("ready")
                vm_steps = []
                with self.write() as db:
                    db.set_progress_handler(lambda: vm_steps.append(None) or 0, 1)
                    self.assertEqual(1, _install(db, "ready"))
                    db.commit()
                    db.set_progress_handler(None, 0)
                    db.execute("DELETE FROM probe_installed")
                    db.execute("DELETE FROM archive_prepare_requests")
                    db.execute("DELETE FROM archive_prepare_before")
                    db.execute("DELETE FROM archive_request_preparations")
                    db.execute("DELETE FROM archive_input_requests")
                    db.execute("DELETE FROM archive_request_inputs")
                counts.append(len(vm_steps))
        self.assertLessEqual(counts[1], counts[0] + 20)
        self.assertLess(counts[1], 1500)

    def test_usage_slot_cas_checks_independent_stats_fences_and_advances_retention_atomically(self):
        updated = b"corrected"
        with self.write() as db:
            publish_roster(db, SOURCE, "A", "rev-A", RequestRoster("price", (_request(updated),), ()))
            old = usage_version(db, SOURCE)
        self._stage((_request(updated, tokens=70), _request(b"new")))
        self._prepare("candidate")
        witness = RequestInstallWitness(SOURCE, "binding", 5, "price", "dependency", 0, 0)

        with self.history._connect(read=True) as reader:
            reader.execute("BEGIN")
            self.assertEqual(old, usage_version(reader, SOURCE))
            with self.write() as db:
                db.execute("INSERT INTO archive_stats_revisions VALUES(?,1,0)", (SOURCE,))
                self.assertIsNone(install_usage_slot(db, "candidate", witness, eligible=lambda: True))
                db.execute("INSERT INTO archive_stats_geometry_revisions VALUES(?,1,0)", (SOURCE,))
                self.assertIsNone(install_usage_slot(db, "candidate", replace(witness, evidence=1),
                                                     eligible=lambda: True))
                latest = replace(witness, evidence=1, geometry=1)
                self.assertIsNone(install_usage_slot(db, "candidate", latest, eligible=lambda: False))
                self.assertEqual(old, usage_version(db, SOURCE))
                self.assertIsNone(db.execute("SELECT 1 FROM archive_request_slots").fetchone())
                slot = install_usage_slot(db, "candidate", latest, eligible=lambda: True)
                self.assertEqual(RequestSlot("candidate", 2), slot)
            self.assertIsNone(reader.execute("SELECT 1 FROM archive_request_slots").fetchone())
            self.assertEqual(old, retained_usage_version(reader, SOURCE, old))

        with self.history._connect(read=True) as db:
            db.execute("BEGIN")
            self.assertEqual(("candidate", 2, 0), db.execute(
                "SELECT attempt,birth,layout FROM archive_request_slots WHERE source=?", (SOURCE,)).fetchone())
            self.assertEqual(2, usage_version(db, SOURCE).revision)
            self.assertIsNone(retained_usage_version(db, SOURCE, old))
            page = request_birth_slice(db, SOURCE, 2, slot=slot)
            self.assertEqual([(updated, 70, 1), (b"new", 9, 2)],
                             [(row[0], row[9], row[-1]) for row in page.rows])
            self.assertIsNone(db.execute("SELECT 1 FROM archive_stats_request_ready").fetchone())
            self.assertIsNone(db.execute("SELECT 1 FROM archive_prompt_attribution").fetchone())

    def test_slot_winner_is_global_even_when_its_requests_are_outside_the_window(self):
        fork = b"same-fork"
        with self.write() as db:
            publish_roster(db, SOURCE, "B", "rev-B",
                           RequestRoster("price", (_request(b"local", root="B", clock=20, fork=fork),), ()))
        self._stage((_request(b"outside-a", clock=80, fork=fork), _request(b"outside-b", clock=90, fork=fork),
                     _request(b"independent", clock=30)))
        self._prepare("candidate")
        witness = RequestInstallWitness(SOURCE, "binding", 5, "price", "dependency", 0, 0)
        with self.history._connect(read=True) as db:
            db.execute("BEGIN")
            before = request_clock_slice(db, SOURCE, 0, 40)
            self.assertEqual([b"local"], [row[0] for row in countable_request_rows(db, SOURCE, before.rows)])
            with self.write() as writer:
                slot = install_usage_slot(writer, "candidate", witness, eligible=lambda: True)
                self.assertEqual(RequestSlot("candidate", 2), slot)
            self.assertEqual([b"local"], [row[0] for row in countable_request_rows(db, SOURCE, before.rows)])

        with self.history._connect(read=True) as db:
            db.execute("BEGIN")
            scoped = request_clock_slice(db, SOURCE, 0, 40, slot=slot)
            self.assertEqual([b"local", b"independent"], [row[0] for row in scoped.rows])
            scoped_countable = countable_request_rows(db, SOURCE, scoped.rows, slot=slot)
            self.assertEqual([b"independent"], [row[0] for row in scoped_countable])
            all_windows = request_clock_slice(db, SOURCE, 0, 100, slot=slot)
            all_countable = countable_request_rows(db, SOURCE, all_windows.rows, slot=slot)
            self.assertEqual([b"independent", b"outside-a", b"outside-b"], [row[0] for row in all_countable])

    def test_append_only_usage_slot_retains_old_revision_without_relabeling_new_keys(self):
        with self.write() as db:
            publish_roster(db, SOURCE, "A", "rev-A", RequestRoster("price", (_request(b"old"),), ()))
            old = usage_version(db, SOURCE)
        self._stage((_request(b"new"),))
        self._prepare("candidate")

        with self.write() as db:
            slot = install_usage_slot(db, "candidate",
                                      RequestInstallWitness(SOURCE, "binding", 5, "price", "dependency", 0, 0),
                                      eligible=lambda: True)
            self.assertEqual(old, retained_usage_version(db, SOURCE, old))
            self.assertEqual(RequestSlot("candidate", 2), slot)
            retained = request_birth_slice(db, SOURCE, old.revision, slot=slot)
            self.assertEqual([(b"old", 1)], [(row[0], row[-1]) for row in retained.rows])
            self.assertEqual((1, 0, 0), db.execute("""
                SELECT edits,corrections,winner_changes FROM archive_request_preparations WHERE attempt='candidate'
            """).fetchone())

    def test_timing_materializes_one_fk_parent_and_rollback_keeps_other_slot_work(self):
        key = b"instant"
        self._stage((replace(_request(key, clock=90), response=ResponseTiming(20, 50)),
                     _request(b"later", clock=100)))
        self._prepare("candidate")
        witness = RequestInstallWitness(SOURCE, "binding", 5, "price", "dependency", 0, 0)
        with self.history._write_lock, self.write() as db:
            slot = install_usage_slot(db, "candidate", witness, eligible=lambda: True)
            self.assertEqual(RequestSlot("candidate", 1), slot)

        with self.history._write_lock, self.write() as db:
            for rejected in (replace(witness, evidence=1), replace(witness, geometry=1), replace(witness, incarnation=6)):
                self.assertFalse(materialize_slot_timing(db, slot, rejected, key, eligible=lambda: True))
            eligibility = iter((True, False))
            self.assertFalse(materialize_slot_timing(db, slot, witness, key, eligible=lambda: next(eligibility)))
            self.assertIsNone(db.execute("SELECT 1 FROM archive_requests").fetchone())
            self.assertIsNone(db.execute("SELECT 1 FROM archive_response_timing").fetchone())
            self.assertEqual([(key,), (b"later",)], db.execute("""
                SELECT request_key FROM archive_prepare_requests ORDER BY request_key
            """).fetchall())
            self.assertTrue(materialize_slot_timing(db, slot, witness, key, eligible=lambda: True))
            self.assertFalse(materialize_slot_timing(db, slot, witness, key, eligible=lambda: True))

        with self.history._connect(read=True) as db:
            db.execute("BEGIN")
            current = RequestSlot(*db.execute("SELECT attempt,birth,layout FROM archive_request_slots").fetchone())
            self.assertEqual(RequestSlot("candidate", 1, 1), current)
            self.assertEqual((key, 20, 50, 1), db.execute("""
                SELECT request_key,start_ms,duration_ms,first_revision FROM archive_response_timing
            """).fetchone())
            self.assertEqual([(key, 90), (b"later", 100)],
                             [row[:2] for row in request_clock_slice(db, SOURCE, 20, 110, slot=current).rows])
            self.assertEqual([(b"later",)], db.execute("SELECT request_key FROM archive_prepare_requests").fetchall())
            self.assertIsNone(db.execute("SELECT 1 FROM archive_stats_request_ready").fetchone())

    def test_slot_stats_reuses_only_evidence_compatible_with_the_effective_request(self):
        recipe = StatsRequestIdentity(b"m" * 32, None, b"s" * 32, b"p" * 32, "medium")
        timing = ResponseTiming(10, 25)
        requests = tuple(replace(_request(key, clock=60), stats_identity=recipe, response=timing)
                         for key in (b"clock", b"effort", b"missing", b"parent", b"tokens"))
        with self.write() as db:
            publish_roster(db, SOURCE, "A", "rev-A",
                           RequestRoster("price", requests, (), stats=StatsCapture((), False, None, ())))
        self._stage((replace(requests[0], clock_ms=70), replace(requests[1], effort="high"),
                     replace(requests[2], tokens=(65, 1, 0, 2, 0), stats_identity=None),
                     replace(requests[3], stats_identity=replace(recipe, sample_hash=b"q" * 32)),
                     replace(requests[4], tokens=(70, 1, 0, 2, 0)), _request(b"new", clock=75)))
        self._prepare("candidate")
        witness = RequestInstallWitness(SOURCE, "binding", 5, "price", "dependency", 1, 0)

        with self.history._connect(read=True) as reader:
            reader.execute("BEGIN")
            old = read_stats_candidates(reader, SOURCE)
            self.assertEqual(old.entries, slot_stats_candidates(reader, SOURCE, slot=None).entries)
            with self.write() as db:
                slot = install_usage_slot(db, "candidate", witness, eligible=lambda: True)
                self.assertEqual(RequestSlot("candidate", 2), slot)
            self.assertEqual(old, read_stats_candidates(reader, SOURCE))

        with self.history._connect(read=True) as reader:
            reader.execute("BEGIN")
            self.assertIsNone(slot_stats_candidates(reader, SOURCE, expected=old.version, slot=slot))
            fresh = slot_stats_candidates(reader, SOURCE, slot=slot, limit=2)
            middle = slot_stats_candidates(reader, SOURCE, slot=slot, cursor=fresh.next_cursor, limit=2)
            tail = slot_stats_candidates(reader, SOURCE, slot=slot, cursor=middle.next_cursor, limit=2)
            visible = {item.usage.request_key: item for item in fresh.entries + middle.entries + tail.entries}
            self.assertIsNone(tail.next_cursor)
            self.assertEqual({
                b"clock": (70, None, None),
                b"effort": (60, None, timing),
                b"missing": (60, None, timing),
                b"parent": (60, None, timing),
                b"tokens": (60, recipe, timing),
                b"new": (75, None, None),
            }, {key: (item.usage.clock_ms, item.identity, item.response) for key, item in visible.items()})
            self.assertEqual(70, visible[b"tokens"].usage.tokens[0])
            self.assertEqual((b"s" * 32,), reader.execute("""
                SELECT sample_hash FROM archive_stats_request_identity WHERE source=? AND request_key=?
            """, (SOURCE, b"missing")).fetchone())
        with self.history._connect() as db:
            db.executescript(fixture_usage_fold_schema())
        with self.history._write_lock, self.write() as db:
            self.assertFalse(fold_slot_correction(db, slot, witness, b"missing", eligible=lambda: True))
            self.assertEqual((65,), db.execute("""
                SELECT input_tokens FROM archive_prepare_requests WHERE source='candidate' AND request_key=?
            """, (b"missing",)).fetchone())
            self.assertTrue(fold_slot_correction(db, slot, witness, b"parent", eligible=lambda: True))
            self.assertIsNone(db.execute("""
                SELECT 1 FROM archive_stats_request_identity WHERE source=? AND request_key=?
            """, (SOURCE, b"parent")).fetchone())

    def test_restart_fold_keeps_effective_request_and_never_resurrects_stale_identity(self):
        key = b"corrected"
        recipe = StatsRequestIdentity(b"m" * 32, None, b"s" * 32, b"p" * 32, "medium")
        original = replace(_request(key, clock=60), stats_identity=recipe, response=ResponseTiming(10, 25))
        with self.history._connect() as db:
            db.executescript(fixture_usage_fold_schema())
        with self.write() as db:
            publish_roster(db, SOURCE, "A", "rev-A",
                           RequestRoster("price", (original,), (), stats=StatsCapture((), False, None, ())))
            old = usage_version(db, SOURCE)
        self._stage((replace(original, clock_ms=80, effort="high"),))
        self._prepare("candidate")
        witness = RequestInstallWitness(SOURCE, "binding", 5, "price", "dependency", 1, 0)
        with self.write() as db:
            slot = install_usage_slot(db, "candidate", witness, eligible=lambda: True)
        with self.history._connect(read=True) as db:
            db.execute("BEGIN")
            before = slot_stats_candidates(db, SOURCE, slot=slot)
            self.assertIsNone(before.entries[0].identity)
            self.assertIsNone(before.entries[0].response)

        with self.history._write_lock, self.write() as db:
            self.assertFalse(fold_slot_correction(db, slot, replace(witness, geometry=1), key, eligible=lambda: True))
            eligibility = iter((True, False))
            self.assertFalse(fold_slot_correction(db, slot, witness, key, eligible=lambda: next(eligibility)))
            self.assertEqual((60,), db.execute("SELECT clock_ms FROM archive_requests").fetchone())
            self.assertEqual((80,), db.execute("SELECT clock_ms FROM archive_prepare_requests").fetchone())
            db.execute("SAVEPOINT peer")
            db.execute("UPDATE archive_requests SET input_tokens=99 WHERE request_key=?", (key,))
            self.assertFalse(fold_slot_correction(db, slot, witness, key, eligible=lambda: True))
            self.assertEqual((99,), db.execute("SELECT input_tokens FROM archive_requests").fetchone())
            self.assertEqual((80,), db.execute("SELECT clock_ms FROM archive_prepare_requests").fetchone())
            db.execute("ROLLBACK TO peer")
            db.execute("RELEASE peer")
            self.assertTrue(fold_slot_correction(db, slot, witness, key, eligible=lambda: True))

        with self.history._connect(read=True) as db:
            db.execute("BEGIN")
            current = RequestSlot(*db.execute("SELECT attempt,birth,layout FROM archive_request_slots").fetchone())
            self.assertEqual(replace(slot, layout=1), current)
            self.assertEqual(before, slot_stats_candidates(db, SOURCE, slot=current))
            self.assertIsNone(retained_usage_version(db, SOURCE, old))
            self.assertIsNone(db.execute("SELECT 1 FROM archive_usage_fold_guard").fetchone())
            self.assertIsNone(db.execute("SELECT 1 FROM archive_prepare_before").fetchone())
            self.assertIsNone(db.execute("SELECT 1 FROM archive_stats_request_ready").fetchone())

    def test_fork_preparation_resumes_past_tied_shadowed_candidates(self):
        fork = b"fork"
        keys = tuple(n.to_bytes(2, "big") for n in range(1367))
        initial = tuple(_request(key, root="B", fork=fork) for key in keys)
        with self.write() as db:
            publish_roster(db, SOURCE, "B", "rev-B", RequestRoster("price", initial, ()))
        self._stage(tuple(_request(key, fork=fork) for key in keys[:-1]))
        with self.write() as db:
            self.assertTrue(open_request_preparation(db, "spool", "ready"))
            for _ in range(42):
                self.assertIs(prepare_request_page(db, "ready"), False)
            self.assertIs(prepare_request_page(db, "ready"), True)
            self.assertEqual(0, _install(db, "ready"), "pending fork rows must block installation")
            steps = 0

            def measure():
                nonlocal steps
                steps += 1
                return 0

            db.set_progress_handler(measure, 1)
            counts = []
            for _ in range(50):
                before = steps
                if prepare_fork_page(db, "ready"):
                    break
                counts.append(steps - before)
            else:
                self.fail("shadowed candidates never exhausted")
            db.set_progress_handler(None, 0)
            self.assertEqual(45, len(counts))
            self.assertLess(max(counts), 3500, counts)
            self.assertEqual(1, _install(db, "ready"))

        with self.history._connect(read=True) as db:
            self.assertEqual([("A", 1366, 0, "member"), ("B", 1, 0, "member")], _forks(db, fork))

    def test_winner_preparation_seeks_past_tied_shadowed_trees(self):
        fork = b"fork"
        with self.write() as db:
            db.executemany("INSERT INTO archive_fork_trees VALUES(?,?,?,1,0,'member')",
                           ((SOURCE, fork, f"tree-{n:04d}") for n in range(1372)))
        self._stage(())
        with self.write() as db:
            self.assertTrue(open_request_preparation(db, "spool", "ready"))
            self.assertTrue(prepare_request_page(db, "ready"))
            db.executemany("""
                INSERT INTO archive_prepare_forks(attempt,fork_key,dedup_tree,change,multiplicity,done)
                VALUES('ready',?,?,-1,0,1)
            """, ((fork, f"tree-{n:04d}") for n in range(1366)))
            db.execute("INSERT INTO archive_prepare_winners(attempt,fork_key) VALUES('ready',?)", (fork,))
            self.assertEqual(0, _install(db, "ready"))

            steps = 0

            def measure():
                nonlocal steps
                steps += 1
                return 0

            db.set_progress_handler(measure, 1)
            work = []
            for _ in range(45):
                steps = 0
                if prepare_fork_page(db, "ready"):
                    break
                work.append(steps)
            else:
                self.fail("shadowed winner prefix never exhausted")
            db.set_progress_handler(None, 0)
            self.assertEqual(43, len(work))
            self.assertLess(max(work), 3500)
            self.assertEqual(1, _install(db, "ready"))
            self.assertEqual(("tree-1366", 1), db.execute("""
                SELECT winner,changed FROM archive_prepare_winners WHERE attempt='ready' AND fork_key=? AND done
            """, (fork,)).fetchone())

    def test_same_revision_reappearance_rejects_pre_gap_payload(self):
        self._stage((_request(b"before-gap"),))
        self._prepare("ready")

        before = self.history.session_checkpoints(SOURCE, ("A",))["A"]
        self.history.commit_sessions(SOURCE, missing=(("A", before),))
        with self.write() as db:
            self.assertEqual(0, _install(db, "ready"))
        absent = self.history.session_checkpoints(SOURCE, ("A",))["A"]
        self.history.commit_sessions(SOURCE, present=(("A", absent),))
        present = self.history.session_checkpoints(SOURCE, ("A",))["A"]
        with self.write() as db:
            self.assertEqual(0, _install(db, "ready"))

        self.assertEqual((before.revision, before.progress + 2), (present.revision, present.progress))
        with self.history._connect(read=True) as db:
            self.assertEqual([], _visible(db, 0, 200))
            self.assertIsNone(db.execute("SELECT 1 FROM probe_installed").fetchone())

    def test_unchanged_and_lower_authority_inputs_do_not_create_overlay_or_new_birth(self):
        captured = (_request(b"same"), _request(b"known"))
        with self.write() as db:
            publish_roster(db, SOURCE, "A", "older", RequestRoster("price", captured, ()))
        self._stage((captured[0], replace(captured[1], known=3, tokens=(0, 0, 0, 0, 0))))

        self._prepare("ready")
        with self.write() as db:
            self.assertEqual(1, _install(db, "ready"))
        with self.history._connect(read=True) as db:
            self.assertEqual((0,), db.execute("SELECT edits FROM archive_request_preparations").fetchone())
            self.assertIsNone(db.execute("SELECT 1 FROM archive_prepare_requests").fetchone())
            self.assertIsNone(db.execute("SELECT 1 FROM archive_prepare_before").fetchone())
            self.assertEqual((1,), db.execute("SELECT usage_revision FROM probe_installed").fetchone())
            self.assertEqual([(b"known", 20, 9, 1, "A"), (b"same", 20, 9, 1, "A")], _visible(db, 0, 100))


if __name__ == "__main__":
    unittest.main()
