from contextlib import contextmanager
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import sqlite3
import tempfile
import unittest

from src.cache.display_history import DisplayHistory
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
from src.cache.display_requests import DisplayRequest, RequestRoster, publish_roster
from src.cache.display_stats_evidence import ResponseTiming
from src.cache.display_stats_requests import StatsRequestIdentity
from src.cache.display_usage_reader import usage_version


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


class DisplayRequestStageTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.history = DisplayHistory(Path(temp.name))
        self.history.initialize()
        with self.history._connect() as db:
            db.executescript(request_stage_schema() + _SLOT)
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
                    db.execute("DELETE FROM archive_request_preparations")
                    db.execute("DELETE FROM archive_input_requests")
                    db.execute("DELETE FROM archive_request_inputs")
                counts.append(len(vm_steps))
        self.assertLessEqual(counts[1], counts[0] + 20)
        self.assertLess(counts[1], 1500)

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
            self.assertEqual(44, len(counts))
            self.assertLess(max(counts), 3500, counts)
            self.assertEqual(1, _install(db, "ready"))

        with self.history._connect(read=True) as db:
            self.assertEqual([("A", 1366, 0, "member"), ("B", 1, 0, "member")], _forks(db, fork))

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
            self.assertEqual((1,), db.execute("SELECT usage_revision FROM probe_installed").fetchone())
            self.assertEqual([(b"known", 20, 9, 1, "A"), (b"same", 20, 9, 1, "A")], _visible(db, 0, 100))


if __name__ == "__main__":
    unittest.main()
