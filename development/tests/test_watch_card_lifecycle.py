"""Persisted V2 lifecycle through isolated Web capture, retention and export."""
import copy
from concurrent.futures import Future
from dataclasses import replace
import json
from pathlib import Path
import shutil
import subprocess
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
from src.watch.running import running_prompts
from src.watch.observers import CatalogObservation, observe_catalog
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
        self.native.active = {"ses_current": {"type": "running"}}
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
        # Pin the actual catalog revision, not the old synthetic "initial" token.
        self.cards.catalog(observe_catalog(self.service(now).source))
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
        active, _, state = self.cards.project(4000)
        self.assertEqual(1, running_prompts(active, state).count)
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
        active, _, state = self.cards.project(10_000)
        aggregate = running_prompts(active, state)
        self.assertEqual("partial", state, "removed child history remains explicitly partial")
        self.assertEqual((None, None, None), (aggregate.count, aggregate.ccost, aggregate.duration_ms))
        self.assertFalse(aggregate.complete)
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
        self.assertEqual("retrying", self.cards.project(20_000)[0][0].state)
        self.assertEqual(self.row(20_000).duration_ms, self.row(90_000).duration_ms)
        self.terminate()
        self.capture(30_000)
        self.assertFalse(self.row(30_000).in_progress)
        self.assertEqual("quota_limit", self.row(30_000).abort_reason)

    def test_native_usage_observations_update_mix_then_terminal_matches_cli(self):
        first = self.unfinished()
        first["tokens"] = {"input": 100, "output": 0, "reasoning": 0, "cache": {"read": 0, "write": 0}}
        self.native.sessions = self.native.sessions[:1]
        self.native.active = {"ses_current": {"type": "running"}}
        self.capture(4000)
        self.assertEqual((100, 0, 0, 0), self.row(4000).token_mix_percent)
        first.update(finish="stop", time={"created": 3100, "completed": 4100})
        second = copy.deepcopy(first)
        second.update(id="second-observed-call", time={"created": 4200},
            tokens={"input": 0, "output": 0, "reasoning": 0, "cache": {"read": 300, "write": 0}})
        second.pop("finish")
        self.native.messages["ses_current"].append(second)
        self.capture(5000)
        self.assertEqual((25, 75, 0, 0), self.row(5000).token_mix_percent)
        self.assertEqual(2, self.row(5000).calls)
        second.update(finish="stop", time={"created": 4200, "completed": 5100})
        third = copy.deepcopy(second)
        third.update(id="third-observed-call", time={"created": 5200},
            tokens={"input": 0, "output": 80, "reasoning": 20, "cache": {"read": 0, "write": 0}})
        third.pop("finish")
        self.native.messages["ses_current"].append(third)
        self.capture(6000)
        self.assertEqual((20, 60, 0, 20), self.row(6000).token_mix_percent)
        self.assertEqual(3, self.row(6000).calls)
        self.capture(7000)
        self.assertEqual(3, self.row(7000).calls, "repeated observations cannot duplicate calls")
        third.update(finish="stop", time={"created": 5200, "completed": 7100})
        self.native.active = {}
        self.capture(8000)
        cli, = self.service(8000).build(ReportRequest(ReportKind.SESSION, self.root.session_id)).prompt_blocks[0].rows
        self.assertFalse(self.row(8000).in_progress)
        self.assertEqual(cli.token_mix_percent, self.row(8000).token_mix_percent)
        active, _, _ = self.cards.project(8000)
        wire = project_live(WatchProjection("Watch", "fixture", (), active_cards=active)).to_json()
        self.assertEqual("20/60/0/20", wire["active_cards"][0]["rows"][0]["prompt"]["display"]["token_mix_percent"])

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
        self.native.active = {"ses_current": {"type": "running"}}
        self.capture(22_000)
        self.assertTrue(self.row(22_000).in_progress)

    def test_revision_churn_admits_stopped_root_through_source_capture_and_export(self):
        original_session = copy.deepcopy(self.native.sessions[0])
        original_messages = copy.deepcopy(self.native.messages["ses_current"])
        for stop in ("quota", "interrupted", "abandoned-continuation"):
            with self.subTest(stop=stop):
                self.native.sessions = [copy.deepcopy(original_session) for _ in range(6)]
                self.native.messages = {"ses_current": copy.deepcopy(original_messages)}
                assistant = self.unfinished({"quota": "absent", "interrupted": "zero"}.get(stop, "positive"))
                if stop == "abandoned-continuation":
                    assistant.update(finish="tool-calls", time={"created": 3100, "completed": 4000})
                messages = copy.deepcopy(self.native.messages["ses_current"][:2])
                self.native.messages = {}
                for index, session in enumerate(self.native.sessions):
                    session["id"] = f"ses_{index}"
                    self.native.messages[session["id"]] = copy.deepcopy(messages)
                self.native.active = {session["id"]: {"type": "running"} for session in self.native.sessions}
                cards = WatchCards(self.workers)
                cards.catalog(observe_catalog(self.source))
                for entry in cards.sessions.values():
                    self.workers._capture(entry.root, entry.generation, 5000, None, ())
                for result in self.workers.drain():
                    if result.phase != "timing":
                        cards.accept(result, 5000)
                stopped = "ses_5"
                initial_active, initial_history, state = cards.project(5000)
                initial = project_live(WatchProjection("Watch", "fixture", (), now_ms=5000,
                    active_cards=initial_active, history_cards=initial_history, cards_state=state)).to_json()
                self.native.active.pop(stopped)
                if stop != "abandoned-continuation":
                    terminal = {"id": "idle_stopped", "type": "idle", "time": {"created": 6000},
                        "outcome": "failed" if stop == "quota" else "interrupted"}
                    if stop == "quota":
                        terminal["error"] = {"code": "quota_exceeded"}
                    self.native.messages[stopped].append(terminal)
                cli_service = self.service(70_000)
                root = cards.sessions[stopped].root
                block, _, _ = cli_service.build_watch_root(root, force_fresh=True)
                expected, = block.rows
                self.assertFalse(expected.in_progress)
                self.assertFalse(expected.completed_successfully)
                scheduled = []
                def submit(root, generation, now, previous, focal_ids):
                    self.workers.jobs[root.session_id] = Future()
                    scheduled.append((root, generation, now, previous, focal_ids))
                    return True
                self.workers.limit = 4
                with patch.object(self.workers, "submit", side_effect=submit):
                    for cycle in range(3):
                        now = 70_000 + cycle * 10_000
                        for session in self.native.sessions[:5]:
                            session["time"]["updated"] += 1
                        cards.catalog(observe_catalog(self.source))
                        cards.tick(now)
                        for args in scheduled:
                            self.workers._capture(*args)
                            self.workers.jobs[args[0].session_id].set_result(None)
                        scheduled.clear()
                        for result in self.workers.drain():
                            if result.phase != "timing":
                                cards.accept(result, now)
                actual, = [row.prompt for card in cards.project(90_000)[0] + cards.project(90_000)[1]
                    if card.session_id == stopped for row in card.rows]
                self.assertEqual(expected.in_progress, actual.in_progress)
                self.assertEqual(expected.abort_reason, actual.abort_reason)
                self.assertEqual((expected.calls, expected.ccost), (actual.calls, actual.ccost))
                self.assertFalse(actual.completed_successfully)
                self.assertEqual(expected.duration_ms, actual.duration_ms)
                terminal_active, terminal_history, state = cards.project(90_000)
                terminal = project_live(WatchProjection("Watch", "fixture", (), now_ms=90_000,
                    active_cards=terminal_active, history_cards=terminal_history, cards_state=state,
                    history_state=cards.history.state, history_epoch=cards.history.epoch)).to_json()
                entry = cards.sessions[stopped]
                self.workers._capture(entry.root, entry.generation, 100_000, entry.snapshot, ())
                for result in self.workers.drain():
                    if result.phase != "timing":
                        cards.accept(result, 100_000)
                # Fair admission is not global history proof: account for all
                # remaining changed roots before expecting authoritative history.
                for candidate in cards.sessions.values():
                    self.workers._capture(candidate.root, candidate.generation, 100_000, candidate.snapshot, ())
                for result in self.workers.drain():
                    if result.phase != "timing":
                        cards.accept(result, 100_000)
                active, history, state = cards.project(130_000)
                self.assertNotIn(stopped, [card.session_id for card in active])
                wire = project_live(WatchProjection("Watch", "fixture", (), now_ms=130_000,
                    active_cards=active, history_cards=history, cards_state=state,
                    history_state=cards.history.state, history_epoch=cards.history.epoch)).to_json()
                exported, = [row["prompt"] for card in wire["history_cards"]
                    if card["session_id"] == stopped for row in card["rows"]]
                self.assertFalse(exported["in_progress"])
                self.assertEqual(actual.duration_ms, self.row_for(cards, stopped, 130_000).duration_ms)
                cold = WatchCards(self.workers)
                cold.catalog(observe_catalog(self.source))
                cold_entry = cold.sessions[stopped]
                for candidate in cold.sessions.values():
                    self.workers._capture(candidate.root, candidate.generation, 130_000, None, ())
                for result in self.workers.drain():
                    if result.phase != "timing":
                        cold.accept(result, 130_000)
                self.assertEqual(actual, self.row_for(cold, stopped, 130_000))
                detail, _ = SessionHistory().acquire(self.service(130_000), stopped)
                self.assertFalse(detail.prompt_blocks[0].rows[-1].in_progress)
                if shutil.which("node"):
                    result = subprocess.run([shutil.which("node"), "development/tests/integration/web_live.cjs"],
                        input=json.dumps(dict(lifecycle=[initial, terminal, wire], stopped=stopped)),
                        text=True, capture_output=True, timeout=15)
                    self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def row_for(self, cards, session_id, now):
        active, history, _ = cards.project(now)
        return next(row.prompt for card in active + history if card.session_id == session_id for row in card.rows)


if __name__ == "__main__":
    unittest.main()
