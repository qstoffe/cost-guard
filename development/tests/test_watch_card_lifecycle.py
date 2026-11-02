"""Persisted V2 lifecycle through isolated Web capture, retention and export."""
import copy
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from development.tests.fixtures.opencode_v2_service import source_with_current_service
from development.tests.fixtures.watch_runtime import make_service
from src.application.live_projection import project_live
from src.reports import ReportKind, ReportRequest
from src.reports.session_history import SessionHistory
from src.sources.opencode_v2 import OpenCodeV2Source
from src.watch.card_workers import CardWorkers
from src.watch.cards import WatchCards
from src.watch.models import WatchProjection
from src.watch.observers import CatalogObservation
from src.watch.tracker import WatchRowTracker
from src.sources.errors import SourceUnavailableError


class WebTerminalLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source, self.native, self.registration = self.enterContext(source_with_current_service())
        self.counter = 0
        self.workers = CardWorkers(self.service, workers=1)
        self.addCleanup(self.workers.close)
        self.cards = WatchCards(self.workers)
        self.root = self.source.load_session_snapshot("ses_current").root
        self.cards.catalog(CatalogObservation((self.root,), (self.root,), {},
            {self.root.session_id: "initial"}, frozenset({self.root.session_id})))

    def service(self, now):
        self.counter += 1
        source = OpenCodeV2Source(self.registration, timeout_seconds=2)
        return make_service(str(Path(self.temp.name) / str(self.counter)), source, now_ms=now)[2]

    def unfinished(self, usage="positive"):
        assistant = self.native.messages["ses_current"][1]
        assistant.pop("finish", None)
        assistant["time"].pop("completed", None)
        assistant["content"] = []
        if usage == "absent":
            assistant.pop("tokens", None)
            assistant.pop("cost", None)
        elif usage == "zero":
            assistant.update(tokens={"input": 0, "output": 0}, cost=0)
        return assistant

    def terminate(self, outcome="failed", quota=True):
        terminal = {"id": "idle_terminal", "type": "idle", "outcome": outcome,
            "time": {"created": 5000}}
        if quota:
            terminal["error"] = {"code": "quota_exceeded"}
        self.native.messages["ses_current"].append(terminal)
        self.native.active = {}

    def capture(self, now, previous=True):
        entry = self.cards.sessions[self.root.session_id]
        self.workers._capture(self.root, entry.generation, now,
            entry.snapshot if previous else None,
            tuple(row.event_id for row in entry.capture.rows) if entry.capture else ())
        results = self.workers.drain()
        for result in results:
            if result.phase != "timing":
                self.cards.accept(result, now)
        return results

    def row(self, now):
        active, history, _ = self.cards.project(now)
        return (active or history)[0].rows[-1].prompt

    def test_persisted_quota_closes_retained_active_child_and_preserves_final_usage(self):
        assistant = self.unfinished()
        assistant["content"] = [{"id": "task", "type": "tool", "name": "task",
            "time": {"created": 3200, "ran": 3300},
            "state": {"status": "running", "metadata": {"sessionId": "ses_current_child"}}}]
        self.native.active = {"ses_current_child": {"type": "running"}}
        self.capture(4000)
        self.assertTrue(self.row(4000).in_progress)
        self.terminate()
        self.native.sessions = self.native.sessions[:1]
        reports = self.service(10_000)
        expected, = reports.build(ReportRequest(ReportKind.SESSION, self.root.session_id)).prompt_blocks[0].rows
        self.assertFalse(expected.in_progress)
        self.capture(10_000)
        actual = self.row(10_000)
        self.assertFalse(actual.in_progress)
        self.assertTrue(actual.aborted)
        self.assertFalse(actual.completed_successfully)
        self.assertEqual("quota_limit", actual.abort_reason)
        self.assertEqual((expected.calls, expected.ccost), (actual.calls, actual.ccost))
        tool = self.cards.project(10_000)[0][0].rows[-1].tool
        self.assertEqual(("", 0, (), 0, ""), (tool.running_tool, tool.running_ms,
            tool.background_kinds, tool.todo_total, tool.active_todo))
        self.assertEqual(2000, actual.duration_ms)
        self.assertEqual(2000, self.row(39_999).duration_ms)
        self.assertEqual("!", self.cards.project(39_999)[0][0].rows[-1].marker)
        self.capture(20_000)
        self.assertEqual((), self.cards.project(40_000)[0], "refresh must not restart grace")

    def test_partial_omission_and_outage_freeze_last_observation_then_recover(self):
        self.unfinished()
        self.capture(4000)
        initial = self.row(4000)
        snapshot = self.source.load_session_snapshot(self.root.session_id)
        partial = replace(snapshot, messages=(), parts=(), events=(), invocations=(), complete=False)
        with patch.object(OpenCodeV2Source, "load_session_snapshot", return_value=partial):
            self.capture(10_000)
        self.assertEqual(initial, self.row(10_000))
        self.assertEqual("partial", self.cards.project(10_000)[0][0].state)
        self.assertEqual("partial", self.cards.project(10_000)[2])
        with patch.object(OpenCodeV2Source, "load_session_snapshot", side_effect=SourceUnavailableError("offline")):
            self.capture(20_000)
        self.assertTrue(self.row(20_000).in_progress, "last known state is not invented success")
        self.assertEqual("unavailable", self.cards.project(20_000)[0][0].state)
        self.terminate()
        self.capture(30_000)
        self.assertFalse(self.row(30_000).in_progress)
        self.assertEqual("quota_limit", self.row(30_000).abort_reason)

    def test_complete_zero_call_reclassification_matches_cli_retained_history(self):
        self.native.messages["ses_current"] = self.native.messages["ses_current"][:1]
        self.native.active = {"ses_current": {"type": "running"}}
        self.capture(4000)
        reports = self.service(4000)
        block, snapshot, _ = reports.build_watch_root(self.root, force_fresh=True)
        tracker = WatchRowTracker(started_at_ms=4000, recent_seconds=30, max_rows=20)
        tracker.project({self.root.session_id: block}, {self.root.session_id: snapshot}, now_ms=4000)
        self.native.active = {}
        self.capture(10_000)
        block, snapshot, _ = self.service(10_000).build_watch_root(self.root, force_fresh=True)
        cli, = tracker.project({self.root.session_id: block}, {self.root.session_id: snapshot}, now_ms=10_000)
        actual = self.row(10_000)
        self.assertFalse(actual.in_progress)
        self.assertFalse(actual.completed_successfully)
        self.assertIsNone(actual.completed_at_ms)
        self.assertEqual(cli.prompt.in_progress, actual.in_progress)
        self.capture(20_000)
        self.assertEqual(actual.duration_ms, self.row(20_000).duration_ms)

    def test_live_child_slow_tool_background_and_later_work_remain_running(self):
        assistant = self.unfinished()
        task = {"id": "task", "type": "tool", "name": "task",
            "time": {"created": 3200, "ran": 3300},
            "state": {"status": "running", "metadata": {"sessionId": "ses_current_child"}}}
        assistant["content"] = [task]
        self.terminate()
        self.native.active = {"ses_current_child": {"type": "running"}}
        self.capture(100_000_000)
        self.assertTrue(self.row(100_000_000).in_progress)
        self.native.active = {}
        task["name"] = "shell"
        task["time"] = {"created": 6000, "ran": 6100}
        self.capture(100_000_001)
        self.assertTrue(self.row(100_000_001).in_progress)
        assistant["content"] = [{"id": "background", "type": "tool", "name": "shell",
            "time": {"created": 3500, "ran": 3600, "completed": 3700},
            "state": {"status": "completed", "input": {"background": True},
                "metadata": {"status": "running", "shellID": "synthetic_job"}}}]
        self.native.shells = [{"id": "synthetic_job", "status": "running"}]
        self.capture(100_000_002)
        self.assertTrue(self.row(100_000_002).in_progress)
        self.assertTrue(self.row(100_000_002).background_kinds)

    def test_detail_uses_same_retained_lifecycle_as_cards(self):
        assistant = self.unfinished()
        assistant["content"] = [{"id": "task", "type": "tool", "name": "task",
            "time": {"created": 3200}, "state": {"status": "running",
                "metadata": {"sessionId": "ses_current_child"}}}]
        self.native.active = {"ses_current_child": {"type": "running"}}
        history = SessionHistory()
        history.acquire(self.service(4000), self.root.session_id)
        self.terminate()
        self.native.sessions = self.native.sessions[:1]
        report, state = history.acquire(self.service(10_000), self.root.session_id)
        self.assertEqual("history_retained", state)
        self.assertFalse(report.prompt_blocks[0].rows[-1].in_progress)
        self.assertEqual("quota_limit", report.prompt_blocks[0].rows[-1].abort_reason)

    def test_usage_variants_cold_start_reload_and_export_match_reports(self):
        for usage in ("absent", "zero", "positive"):
            for outcome, quota in (("failed", True), ("failed", False), ("interrupted", False), ("succeeded", False)):
                with self.subTest(usage=usage, outcome=outcome, quota=quota):
                    self.native.messages["ses_current"] = self.native.messages["ses_current"][:2]
                    assistant = self.unfinished(usage)
                    if usage == "positive":
                        assistant.update(tokens={"input": 100, "output": 10}, cost=1)
                    self.terminate(outcome, quota)
                    self.cards = WatchCards(self.workers)
                    self.cards.catalog(CatalogObservation((self.root,), (self.root,), {},
                        {self.root.session_id: "cold"}, frozenset()))
                    self.capture(100_000, previous=False)
                    expected, = self.service(100_000).build(
                        ReportRequest(ReportKind.SESSION, self.root.session_id)).prompt_blocks[0].rows
                    actual = self.row(100_000)
                    for field in ("in_progress", "aborted", "watch_error", "completed_successfully", "abort_reason", "ccost", "calls"):
                        self.assertEqual(getattr(expected, field), getattr(actual, field), field)
                    self.assertFalse(actual.in_progress)
                    self.assertFalse(self.cards.project(100_000)[0], "old terminal history never flashes active")
                    self.capture(200_000)
                    self.assertEqual(actual.duration_ms, self.row(200_000).duration_ms)
                    _, history, state = self.cards.project(200_000)
                    wire = project_live(WatchProjection("Watch", "fixture", (), now_ms=200_000,
                        history_cards=history, cards_state=state)).to_json()
                    projected = wire["history_cards"][0]["rows"][-1]["prompt"]
                    self.assertFalse(projected["in_progress"])
                    self.assertEqual(actual.abort_reason, projected["abort_reason"])

    def test_delayed_same_generation_capture_cannot_resurrect_terminal(self):
        self.unfinished()
        old_results = self.capture(4000)
        self.terminate()
        self.capture(10_000)
        for result in old_results:
            if result.phase == "rows":
                self.cards.accept(result, 11_000)
        self.assertFalse(self.row(11_000).in_progress)
        self.assertEqual(2000, self.row(11_000).duration_ms)
        self.assertEqual(1, len(self.cards.project(11_000)[0][0].rows))

    def test_omitted_terminal_evidence_does_not_resurrect_same_attempt_but_later_work_can(self):
        self.unfinished()
        self.capture(4000)
        self.terminate()
        self.capture(10_000)
        self.native.messages["ses_current"].pop()
        self.capture(20_000)
        self.assertFalse(self.row(20_000).in_progress)
        newer = copy.deepcopy(self.native.messages["ses_current"][1])
        newer.update(id="msg_new_attempt", time={"created": 21_000})
        self.native.messages["ses_current"].append(newer)
        self.capture(22_000)
        self.assertTrue(self.row(22_000).in_progress)


if __name__ == "__main__":
    unittest.main()
