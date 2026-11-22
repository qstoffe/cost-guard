from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from development.tests.test_v1_archive_cursor import ROOT, _seed, _session
from src.analysis.child_links import ChildLinkIndex, OPEN_END
from src.application.v1_archive_trace import V1ArchiveTrace
from src.application.v1_child_launches import DirectChildWindow
from src.sources.errors import SourceDataError
from src.sources.opencode_v1 import OpenCodeV1Source


def _message(db, session, key, created, **payload):
    db.execute("INSERT INTO message VALUES(?,?,?,?,?)", (key, session, created, created, json.dumps(payload)))


def _part(db, session, message, key, created, updated, **payload):
    db.execute("INSERT INTO part VALUES(?,?,?,?,?,?)", (key, message, session, created, updated, json.dumps(payload)))


def _turn(db, session, key, created):
    _message(db, session, key, created, role="user")
    _part(db, session, key, f"text-{key}", created, created, type="text", text="FIXTURE_ONLY_TEXT")


def _tool(db, session, message, key, call, start, finish, updated, **data):
    _part(db, session, message, key, 2000, updated, type="tool", callID=call,
          tool=data.pop("tool", "task"), state={"time": {"start": start, "end": finish}, **data})


class V1ChildLaunchTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.source_path = Path(temp.name) / "native.db"
        self.stage_path = Path(temp.name) / "stage.db"
        _seed(self.source_path, encoding="UTF-16le")

    def test_launch_windows_match_whole_index_with_call_replacement_relaunch_and_independent_work(self):
        with closing(sqlite3.connect(self.source_path)) as db, db:
            for child, parent in [("child", ROOT), ("empty", ROOT), ("wrong-parent", "child"),
                                  ("replaced", ROOT), ("timing", ROOT), ("late-start", ROOT)]:
                _session(db, child, parent)
            db.execute("UPDATE session SET time_created=3250 WHERE id='late-start'")
            _turn(db, ROOT, "root-prompt", 1400)
            _message(db, ROOT, "origin", 1500, role="assistant", parentID="root-prompt")
            _message(db, ROOT, "next", 1600, role="assistant", parentID="root-prompt")
            _tool(db, ROOT, "origin", "first", "first", 2000, 2200, 2300,
                  metadata={"sessionID": "child", "background": True}, output="FIXTURE_ONLY_TEXT")
            _tool(db, ROOT, "next", "second", "second", 3000, 3300, 3400, metadata={"sessionID": "child"})
            _tool(db, ROOT, "next", "after-ack", "after-ack", 3200, 3300, 3400,
                  metadata={"sessionID": "late-start"})
            _tool(db, ROOT, "origin", "empty", "empty", 1900, 2100, 2300, metadata={"sessionID": "empty"})
            _tool(db, ROOT, "origin", "spoof", "spoof", 2000, 2200, 2300,
                  metadata={"sessionID": "wrong-parent"})
            _tool(db, ROOT, "origin", "before", "timing", 1499, 2200, 9999,
                  metadata={"sessionID": "timing"})
            _tool(db, ROOT, "origin", "stale", "reused", 2000, 2200, 2300,
                  metadata={"sessionID": "replaced"})
            _tool(db, ROOT, "next", "newest", "reused", 2500, 2600, 2700, tool="read")
            _turn(db, "child", "in-first", 2050)
            _turn(db, "child", "in-second", 3050)
            _turn(db, "child", "independent", 3400)
            _turn(db, "late-start", "first-after-ack", 3330)
            _turn(db, "late-start", "next-independent", 3500)
            _message(db, "child", "crossing", 3100, role="assistant", parentID="in-second",
                     time={"completed": 3500})
        source = OpenCodeV1Source(self.source_path)
        snapshot = source.load_session_snapshot(ROOT)

        windows, sizes, work = self._windows(source)

        self.assertEqual({
            DirectChildWindow(ROOT, "origin", "child", 2000, 3000, 3000, "in-first", True),
            DirectChildWindow(ROOT, "next", "child", 3000, 3300, 3400, "in-second", False),
            DirectChildWindow(ROOT, "next", "late-start", 3200, 3300, 3500, "first-after-ack", False),
            DirectChildWindow(ROOT, "origin", "empty", 1900, 2100, OPEN_END, "", False),
        }, set(windows))
        index = ChildLinkIndex(snapshot)
        whole = {DirectChildWindow(ROOT, mid, scope.session_id, scope.start_ms, scope.end_ms,
                                   scope.invocation_end_ms, scope.owner_id, scope.background)
                 for mid, scopes in index.links_by_message.items() for scope in scopes}
        self.assertEqual(whole, set(windows))
        self.assertEqual(("crossing",), next(scope for scope in index.links_by_message["next"]
                                            if scope.session_id == "child").continuing_ids)
        self.assertEqual([0, 4], sizes)
        self.assertLess(max(work), 2500)
        self.assertNotIn(b"FIXTURE_ONLY_TEXT", self.stage_path.read_bytes())

    def test_equal_rank_uses_native_message_then_part_order_and_pages_unqualified_winners(self):
        with closing(sqlite3.connect(self.source_path)) as db, db:
            _session(db, "first-child", ROOT)
            _session(db, "last-child", ROOT)
            # In UTF-16LE, Ā sorts before ä; rowid and decoded string order
            # both pick the wrong first assistant/part on these tied clocks.
            for key in ("m-ä", "m-Ā"):
                _message(db, ROOT, key, 1500, role="assistant")
            _tool(db, ROOT, "m-ä", "a-loser", "same-message-rank", 2000, 2200, 2300,
                  metadata={"sessionID": "last-child"})
            for key, child in [("p-ä", "last-child"), ("p-Ā", "first-child")]:
                _tool(db, ROOT, "m-Ā", key, "same-message-rank", 2000, 2200, 2300,
                      metadata={"sessionID": child})
            for number in range(160):
                _tool(db, ROOT, "m-ä", f"noise-{number}", f"noise-{number}", 2000, 2100, 2200, tool="read")
        source = OpenCodeV1Source(self.source_path)
        index = ChildLinkIndex(source.load_session_snapshot(ROOT))

        windows, sizes, work = self._windows(source)

        self.assertEqual([DirectChildWindow(ROOT, "m-Ā", "first-child", 2000, 2200, OPEN_END, "", False)], windows)
        self.assertEqual(["m-Ā"], list(index.links_by_message))
        self.assertEqual("first-child", index.links_by_message["m-Ā"][0].session_id)
        self.assertEqual([0] * 6 + [1], sizes)
        self.assertLess(max(work), 2500)

    def _windows(self, source):
        with closing(sqlite3.connect(self.stage_path)) as db:
            with source.archive_cursor(ROOT) as cursor:
                stage = V1ArchiveTrace(source, cursor, db)
                with self.assertRaisesRegex(SourceDataError, "not ready"):
                    stage.child_launch_turn()
                for _ in range(64):
                    if stage.capture_turn():
                        break
                else:
                    self.fail("source cursor did not reach EOF")
            steps = 0

            def progress():
                nonlocal steps
                steps += 1
                return 0

            db.set_progress_handler(progress, 1)
            windows, sizes, work = [], [], []
            for _ in range(32):
                before = steps
                page = stage.child_launch_turn()
                if page is None:
                    return windows, sizes, work
                windows.extend(page)
                sizes.append(len(page))
                work.append(steps - before)
        self.fail("child launch stage did not reach EOF")
