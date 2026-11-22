from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from development.tests.test_v1_archive_cursor import ROOT, _seed, _session
from src.analysis import analyze_snapshot
from src.analysis.causal import trace_entries
from src.analysis.child_links import ChildLinkIndex, OPEN_END, scoped_entries
from src.application.v1_archive_trace import V1ArchiveTrace
from src.application.v1_child_launches import DirectChildWindow
from src.application.v1_child_membership import ChildAssistant
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
            _message(db, "child", "continuation", 3340, role="assistant", parentID="in-second",
                     time={"completed": 3600})
            _message(db, "child", "unrelated-after-return", 3360, role="assistant", parentID="other",
                     time={"completed": 3370})
            _message(db, "child", "unrelated-after-cutoff", 3500, role="assistant", parentID="independent",
                     time={"completed": 3600})
            _message(db, "late-start", "post-ack", 3350, role="assistant", parentID="first-after-ack",
                     time={"completed": 3600})
        source = OpenCodeV1Source(self.source_path)
        snapshot = source.load_session_snapshot(ROOT)

        windows, sizes, work, members = self._windows(source)

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
        self.assertEqual({
            ("child", 2000): [],
            ("child", 3000): [ChildAssistant("crossing", 3100, 3500, True),
                              ChildAssistant("continuation", 3340, 3600, True)],
            ("late-start", 3200): [ChildAssistant("post-ack", 3350, 3600, True)],
            ("empty", 1900): [],
        }, members)
        for window in windows:
            scope = next(scope for scope in index.links_by_message[window.message_id]
                         if scope.session_id == window.session_id and scope.start_ms == window.start_ms)
            self.assertEqual({msg.message_id for msg in index.messages((scope,))},
                             {msg.message_id for msg in members[window.session_id, window.start_ms]})
            self.assertEqual(set(scope.continuing_ids), {msg.message_id
                             for msg in members[window.session_id, window.start_ms] if msg.continuing})
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

        windows, sizes, work, _ = self._windows(source)

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
            windows, sizes, work, members = [], [], [], {}
            for _ in range(32):
                before = steps
                page = stage.child_launch_turn()
                if page is None:
                    break
                windows.extend(page)
                sizes.append(len(page))
                work.append(steps - before)
            else:
                self.fail("child launch stage did not reach EOF")
            for window in windows:
                membership = stage.child_window_membership(window)
                rows = []
                for _ in range(32):
                    before = steps
                    page = membership.turn()
                    if page is None:
                        break
                    rows.extend(page)
                    work.append(steps - before)
                else:
                    self.fail("child membership stage did not reach EOF")
                members[window.session_id, window.start_ms] = rows
        return windows, sizes, work, members

    def test_crossing_membership_seeks_dense_equal_clocks_and_does_not_invent_late_owner(self):
        with closing(sqlite3.connect(self.source_path)) as db, db:
            _session(db, "wide-child", ROOT)
            db.execute("UPDATE session SET time_created=2050 WHERE id='wide-child'")
            _message(db, ROOT, "launch", 1500, role="assistant")
            _tool(db, ROOT, "launch", "open", "open", 2000, 2200, 2300, metadata={"sessionID": "wide-child"})
            _turn(db, "wide-child", "owner-after-ack", 2220)
            _turn(db, "wide-child", "next", 3000)
            _message(db, "wide-child", "old-attempt", 1975, role="assistant", parentID="owner-after-ack",
                     time={"completed": 1999})
            _message(db, "wide-child", "no-late-binding", 2240, role="assistant", parentID="owner-after-ack")
            for number in reversed(range(256)):
                _message(db, "wide-child", f"wide-{number:03d}", 2125, role="assistant", parentID="wide-owner",
                         time={"completed": 2150}, finish="tool-calls" if number == 255 else "stop")
            _message(db, "wide-child", "continued", 2500, role="assistant", parentID="wide-owner")
            _message(db, "wide-child", "beyond", 3000, role="assistant", parentID="wide-owner")
        source = OpenCodeV1Source(self.source_path)
        index = ChildLinkIndex(source.load_session_snapshot(ROOT))

        windows, _, work, members = self._windows(source)

        self.assertEqual([DirectChildWindow(ROOT, "launch", "wide-child", 2000, 2200, 3000,
                                            "owner-after-ack", False)], windows)
        rows = members["wide-child", 2000]
        expected = [f"wide-{number:03d}" for number in range(256)] + ["continued"]
        self.assertEqual(expected, [row.message_id for row in rows])
        self.assertTrue(all(row.continuing for row in rows))
        self.assertEqual(set(expected), set(index.links_by_message["launch"][0].continuing_ids))
        self.assertLess(max(work), 2500)

    def test_walk_clips_foreground_allows_background_and_follows_only_proven_crossing_attempt(self):
        with closing(sqlite3.connect(self.source_path)) as db, db:
            _session(db, "child", ROOT)
            for session in ("foreground", "background", "continued", "unrelated"):
                _session(db, session, "child")
            _message(db, ROOT, "launch", 1500, role="assistant")
            _tool(db, ROOT, "launch", "first", "first", 2000, 2400, 2400, metadata={"sessionID": "child"})
            _turn(db, "child", "in-window", 2050)
            _turn(db, "child", "later-owner", 2750)
            _message(db, "child", "short", 2100, role="assistant", parentID="in-window", time={"completed": 2350},
                     providerID="tracked", modelID="sample", tokens={"input": 5})
            _tool(db, "child", "short", "foreground", "foreground", 2150, 2650, 2650,
                  metadata={"sessionID": "foreground"})
            _tool(db, "child", "short", "background", "background", 2200, 2300, 2300,
                  metadata={"sessionID": "background", "background": True})
            _message(db, "child", "crossing", 2300, role="assistant", parentID="bound", time={"completed": 2640},
                     providerID="tracked", modelID="sample")
            for number in range(130):
                _part(db, "child", "crossing", f"step-{number:03d}", 2330, 2330,
                      type="step-finish", tokens={"input": 2})
            _tool(db, "child", "crossing", "continued", "continued", 2500, 2800, 2800,
                  metadata={"sessionID": "continued"})
            _message(db, "child", "later", 2780, role="assistant", parentID="later-owner", time={"completed": 2950},
                     providerID="tracked", modelID="sample", tokens={"input": 7})
            _tool(db, "child", "later", "unrelated", "unrelated", 2800, 2900, 2900,
                  metadata={"sessionID": "unrelated"})
            for session, name, start, end, provider in [
                ("foreground", "at-bound", 2160, 2400, "tracked"),
                ("foreground", "after-bound", 2160, 2401, "tracked"),
                ("foreground", "foreign", 2160, 2399, "other"),
                ("background", "background-call", 4200, 5000, "tracked"),
                ("continued", "continued-call", 2600, 2700, "tracked"),
            ]:
                _message(db, session, name, start, role="assistant", time={"completed": end},
                         providerID=provider, modelID="sample", tokens={"input": 10})
        source = OpenCodeV1Source(self.source_path)
        snapshot = source.load_session_snapshot(ROOT)
        root_assistant = next(message for message in snapshot.messages if message.message_id == "launch")
        legacy = ChildLinkIndex(snapshot).scopes([root_assistant])

        with closing(sqlite3.connect(self.stage_path)) as db:
            with source.archive_cursor(ROOT) as cursor:
                trace = V1ArchiveTrace(source, cursor, db, tracked_provider="tracked")
                for _ in range(64):
                    if trace.capture_turn():
                        break
                else:
                    self.fail("source cursor did not reach EOF")
            with self.assertRaisesRegex(SourceDataError, "not ready"):
                trace.child_scope_walk("launch")
            self.assertEqual((), trace.child_launch_turn())  # All five winners are qualified in one turn.
            walk = trace.child_scope_walk("launch")
            scopes = []
            for _ in range(64):
                page = walk.turn()
                if page is None:
                    break
                scopes.extend(page)
            else:
                self.fail("scope walk did not reach EOF")
            with self.assertRaisesRegex(SourceDataError, "prepared trace"):
                trace.scoped_calls(scopes[0])
            for _ in range(16):
                if trace.prepare_turn():
                    break
            else:
                self.fail("trace calls were not prepared")
            calls, sizes = [], []
            for scope in scopes:
                scoped_calls = trace.scoped_calls(scope)
                for _ in range(64):
                    page = scoped_calls.turn()
                    if page is None:
                        break
                    calls.extend((item.session_id, item.invocation_id, item.message_id, item.step_part_id) for item in page)
                    sizes.append(len(page))
                else:
                    self.fail("scoped call population did not reach EOF")

        expected = {
            ("child", 2000, 2400, 2750, False),
            ("foreground", 2150, 2400, OPEN_END, False),
            ("background", 2200, OPEN_END, OPEN_END, True),
            ("continued", 2500, 2750, OPEN_END, False),
        }
        self.assertEqual(expected, {(s.session_id, s.start_ms, s.end_ms, s.invocation_end_ms, s.background)
                                    for s in legacy})
        self.assertEqual(expected, {(s.direct.session_id, s.direct.start_ms, s.end_ms,
                                     s.direct.invocation_end_ms, s.direct.background) for s in scopes})
        self.assertEqual(len(expected), len(scopes))
        canonical = scoped_entries(snapshot, trace_entries(snapshot), legacy, "tracked")
        self.assertEqual({(row.session_id, row.invocation_id, row.message_id, row.step_part_id)
                          for row in canonical}, set(calls))
        self.assertEqual({"at-bound", "background-call", "continued-call", "short",
                          *(f"crossing:step-{num:03d}" for num in range(130))},
                         {item[1] for item in calls})
        self.assertEqual(134, len(calls))
        self.assertEqual(4, sizes.count(32))

    def test_prompt_allocation_keeps_tied_windows_and_deduplicates_child_calls_per_prompt(self):
        with closing(sqlite3.connect(self.source_path)) as db, db:
            _session(db, "child", ROOT)
            _turn(db, ROOT, "prompt-a", 1400)
            _turn(db, ROOT, "prompt-b", 1400)
            _turn(db, ROOT, "later-prompt", 1600)
            _message(db, ROOT, "continuation", 1450, role="user")
            _message(db, ROOT, "equal-cutoff", 1600, role="user")
            for name, parent, provider in [
                ("direct-a", "prompt-a", "tracked"), ("launch-one", "continuation", "tracked"),
                ("launch-two", "continuation", "other"), ("excluded", "equal-cutoff", "tracked"),
            ]:
                _message(db, ROOT, name, 1650, role="assistant", parentID=parent, providerID=provider,
                         modelID="sample", time={"completed": 1900}, finish="stop", tokens={"input": 2})
            for suffix in ("one", "two"):
                _tool(db, ROOT, f"launch-{suffix}", f"link-{suffix}", f"call-{suffix}", 2000, 3000, 3000,
                      metadata={"sessionID": "child"})
            _turn(db, "child", "child-prompt", 2100)
            _message(db, "child", "nested", 2150, role="assistant", parentID="child-prompt", providerID="tracked",
                     time={"completed": 2400}, modelID="sample", tokens={"input": 3})
        source = OpenCodeV1Source(self.source_path)
        bundle = analyze_snapshot(source.load_session_snapshot(ROOT), tracked_provider="tracked", now_ms=100_000)

        with closing(sqlite3.connect(self.stage_path)) as db:
            with source.archive_cursor(ROOT) as cursor:
                trace = V1ArchiveTrace(source, cursor, db, tracked_provider="tracked")
                for _ in range(32):
                    if trace.capture_turn():
                        break
                else:
                    self.fail("source cursor did not reach EOF")
            with self.assertRaisesRegex(SourceDataError, "prepared trace"):
                trace.root_prompt_calls("prompt-a")
            self.assertTrue(trace.prepare_turn())
            self.assertEqual((), trace.child_launch_turn())
            with self.assertRaisesRegex(SourceDataError, "eligible root window"):
                trace.root_prompt_calls("child-prompt")
            seen = {}
            for name in ("prompt-a", "prompt-b", "later-prompt"):
                build = trace.root_prompt_calls(name)
                calls = seen[name] = []
                for _ in range(96):
                    page = build.turn()
                    if page is None:
                        break
                    calls.extend((call.session_id, call.invocation_id, call.message_id, call.step_part_id)
                                 for call in page)
                else:
                    self.fail(f"bounded prompt allocation for {name} did not finish")

        self.assertEqual({
            "prompt-a": {("dense-root", "direct-a"), ("dense-root", "launch-one"), ("child", "nested")},
            "prompt-b": {("dense-root", "launch-one"), ("child", "nested")},
            "later-prompt": set(),
        }, {prompt: {row[:2] for row in rows} for prompt, rows in seen.items()})
        self.assertEqual({"prompt-a": 3, "prompt-b": 2, "later-prompt": 0},
                         {prompt: len(rows) for prompt, rows in seen.items()})
        for row in bundle.prompts:
            self.assertEqual({(entry.session_id, entry.invocation_id, entry.message_id, entry.step_part_id)
                              for entry in row.entries}, set(seen[row.prompt_id]))

    def test_dense_prompt_pages_calls_without_visiting_every_attempt(self):
        with closing(sqlite3.connect(self.source_path)) as db, db:
            _turn(db, ROOT, "dense-prompt", 1400)
            _message(db, ROOT, "wide", 1500, role="assistant", parentID="dense-prompt",
                     providerID="tracked", modelID="sample", time={"completed": 2000}, tokens={"input": 99})
            for number in range(70):
                _part(db, ROOT, "wide", f"step-{number:04d}", 1900, 1900,
                      type="step-finish", tokens={"input": 2})
            for number in range(1336):
                _message(db, ROOT, f"call-{number:04d}", 1500, role="assistant", parentID="dense-prompt",
                         providerID="tracked" if number < 1296 else "other", modelID="sample",
                         time={"completed": 2000}, tokens={"input": 3})
            for number in range(4100):
                _message(db, ROOT, f"silent-{number:04d}", 1500, role="assistant", parentID="dense-prompt",
                         providerID="tracked", modelID="sample", time={"completed": 2000})
        source = OpenCodeV1Source(self.source_path)
        bundle = analyze_snapshot(source.load_session_snapshot(ROOT), tracked_provider="tracked", now_ms=100_000)
        expected = {(entry.session_id, entry.invocation_id, entry.message_id, entry.step_part_id)
                    for entry in bundle.prompts[0].entries}
        calls, sizes, work = [], [], []
        steps = 0

        def tick():
            nonlocal steps
            steps += 1
            return 0

        with closing(sqlite3.connect(self.stage_path)) as db:
            with source.archive_cursor(ROOT) as cursor:
                trace = V1ArchiveTrace(source, cursor, db, tracked_provider="tracked")
                for _ in range(100):
                    if trace.capture_turn():
                        break
                else:
                    self.fail("source cursor did not reach EOF")
            for _ in range(200):
                if trace.prepare_turn():
                    break
            else:
                self.fail("trace did not finish preparing calls")
            self.assertEqual((), trace.child_launch_turn())
            db.set_progress_handler(tick, 1)
            build = trace.root_prompt_calls("dense-prompt")
            for _ in range(50):
                steps = 0
                page = build.turn()
                work.append(steps)
                if page is None:
                    break
                sizes.append(len(page))
                calls.extend((call.session_id, call.invocation_id, call.message_id, call.step_part_id)
                             for call in page)
            else:
                self.fail("dense prompt allocation did not finish within 50 turns")
            db.set_progress_handler(None, 0)
            self.assertEqual(0, db.execute("SELECT count(*) FROM trace_walks").fetchone()[0])
            self.assertEqual(0, db.execute("SELECT count(*) FROM trace_prompt_runs").fetchone()[0])

        self.assertEqual(1366, len(calls))
        self.assertEqual(expected, set(calls))
        self.assertLessEqual(max(sizes), 32)
        self.assertLess(max(work), 2500)
