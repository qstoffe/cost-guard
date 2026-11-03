"""Persisted failures before an assistant response, including resumed prompts."""
import copy
import unittest
from dataclasses import replace
from unittest.mock import patch

from development.tests.fixtures.opencode_v2_service import source_with_current_service
from development.tests.fixtures.pre_response_watch import PreResponseWatch, failed_resume
from src.analysis.causal import build_prompt_records
from src.domain import MessageRole
from src.reports.session_history import SessionHistory
from src.sources.opencode_v2 import OpenCodeV2Source
from src.watch.card_workers import CardResult


class PreResponseTerminalTests(unittest.TestCase):
    def test_failed_continuation_ends_prompt_without_reassigning_old_assistant(self):
        with source_with_current_service() as (source, native, _):
            assistant = native.messages["ses_current"][1]
            assistant.pop("finish")
            assistant["time"].pop("completed")
            assistant.pop("tokens")
            assistant.pop("cost")
            assistant["content"] = []
            native.messages["ses_current"].extend([
                {"id": "resume", "type": "synthetic", "text": "resume existing work",
                 "time": {"created": 6000}},
                {"id": "system", "type": "system", "text": "provider unavailable",
                 "time": {"created": 6100}},
                {"id": "failed", "type": "idle", "outcome": "failed",
                 "error": {"type": "provider.no-route"}, "time": {"created": 6200}},
            ])

            snapshot = source.load_session_snapshot("ses_current")
            row, = build_prompt_records(snapshot, tracked_provider=None, now_ms=100_000_000)

            self.assertFalse(row.in_progress)
            self.assertTrue(row.watch_error)
            self.assertFalse(row.aborted)
            self.assertFalse(row.completed_successfully)
            self.assertEqual("", row.abort_reason)
            self.assertEqual((6200, 3200, 3200),
                (row.terminal_time_ms, row.duration_ms, row.execution_duration_ms))
            self.assertEqual((), row.entries)
            original = next(m for m in snapshot.messages if m.role is MessageRole.ASSISTANT)
            self.assertIsNone(original.termination, "the failed resume is a distinct attempt")
            self.assertIsNone(original.completed_at_ms)

    def test_failed_initial_request_without_assistant_keeps_supported_cause(self):
        for outcome, error, aborted, watch_error, reason in (
                ("failed", {"code": "quota_exceeded"}, True, False, "quota_limit"),
                ("failed", {"type": "provider.no-route"}, False, True, ""),
                ("interrupted", None, True, False, "")):
            with self.subTest(outcome=outcome, error=error):
                with source_with_current_service() as (source, native, _):
                    native.messages["ses_current"] = native.messages["ses_current"][:1] + [
                        {"id": "system", "type": "system", "text": "unavailable",
                         "time": {"created": 4000}},
                        {"id": "failed", "type": "idle", "outcome": outcome,
                         "error": error, "time": {"created": 5000}}]

                    row, = build_prompt_records(source.load_session_snapshot("ses_current"),
                        tracked_provider=None, now_ms=100_000_000)

                    self.assertFalse(row.in_progress)
                    self.assertEqual((aborted, watch_error, reason),
                        (row.aborted, row.watch_error, row.abort_reason))
                    self.assertFalse(row.completed_successfully)
                    self.assertEqual(2000, row.execution_duration_ms)

    def test_later_assistant_and_new_prompt_do_not_inherit_failed_resume(self):
        with source_with_current_service() as (source, native, _):
            original = native.messages["ses_current"][1]
            original.pop("finish")
            original["time"].pop("completed")
            original["content"] = []
            native.messages["ses_current"].extend([
                {"id": "resume", "type": "synthetic", "text": "resume",
                 "time": {"created": 4500}},
                {"id": "failed", "type": "idle", "outcome": "failed",
                 "error": {"code": "quota_exceeded"}, "time": {"created": 5000}}])
            before = source.load_session_snapshot("ses_current")
            row, = build_prompt_records(before, tracked_provider=None, now_ms=6000)
            self.assertFalse(row.in_progress)
            self.assertEqual("quota_limit", row.abort_reason)
            newer = copy.deepcopy(original)
            newer.update(id="new_attempt", time={"created": 7000})
            native.messages["ses_current"].append(newer)

            resumed, = build_prompt_records(source.load_session_snapshot("ses_current"),
                tracked_provider=None, now_ms=8000)

            self.assertTrue(resumed.in_progress)
            self.assertFalse(resumed.aborted)
            native.messages["ses_current"].insert(-1, {
                "id": "new_prompt", "type": "user", "text": "different work",
                "time": {"created": 6500}})
            old, new = build_prompt_records(source.load_session_snapshot("ses_current"),
                tracked_provider=None, now_ms=8000)
            self.assertFalse(old.in_progress)
            self.assertTrue(new.in_progress)
            self.assertEqual("quota_limit", old.abort_reason)

    def test_status_success_compaction_and_ambiguous_order_do_not_end_prior_attempt(self):
        for boundary, terminal in (
                ({"type": "system"}, {"type": "idle"}),
                ({"type": "synthetic"}, {"type": "idle", "outcome": "succeeded"}),
                ({"type": "compaction", "status": "completed"}, {"type": "idle", "outcome": "failed"}),
                ({"type": "synthetic", "time": {"created": 5000}},
                 {"type": "idle", "outcome": "failed"})):
            with self.subTest(boundary=boundary, terminal=terminal):
                with source_with_current_service() as (source, native, _):
                    assistant = native.messages["ses_current"][1]
                    assistant.pop("finish")
                    assistant["time"].pop("completed")
                    assistant["content"] = []
                    native.messages["ses_current"].extend([
                        {"id": "boundary", "text": "synthetic", "time": {"created": 4500}, **boundary},
                        {"id": "terminal", "time": {"created": 5000}, **terminal}])

                    snapshot = source.load_session_snapshot("ses_current")

                    self.assertFalse(any(m.termination for m in snapshot.messages))

    def test_scheduled_retention_cli_mini_and_cold_capture_share_terminal_truth(self):
        for outcome, error, reason in (
                ("failed", {"code": "quota_exceeded"}, "quota_limit"),
                ("failed", {"type": "provider.no-route"}, ""),
                ("interrupted", None, "")):
            with self.subTest(outcome=outcome, error=error), PreResponseWatch() as case:
                messages = case.native.messages[case.stopped]
                priced = copy.deepcopy(messages[1])
                priced.update(id="priced_step", finish="tool-calls", cost=1,
                    tokens={"input": 100, "output": 10}, time={"created": 3050, "completed": 3090})
                messages.insert(1, priced)
                for now in (4000, 4100):
                    case.capture(now)
                initial = case.row(4100)
                self.assertTrue(initial.in_progress)
                entry = case.cards.sessions[case.stopped]
                delayed = CardResult(case.stopped, entry.generation, "rows",
                    (entry.capture, tuple(entry.tools.items()), entry.snapshot), 4100)
                history = SessionHistory()
                history.acquire(case.service(4100), case.stopped)
                messages.extend(failed_resume(outcome=outcome, error=error))
                case.native.active.pop(case.stopped)

                for now in (10_000, 11_000, 12_000):
                    case.capture(now, churn=True)

                terminal = case.row(12_000)
                self.assertFalse(terminal.in_progress)
                self.assertFalse(terminal.completed_successfully)
                self.assertEqual(reason, terminal.abort_reason)
                self.assertEqual((initial.calls, initial.ccost), (terminal.calls, terminal.ccost))
                self.assertGreater(terminal.ccost, 0)
                cli, _, _ = case.service(12_000).build_watch_root(entry.root, force_fresh=True)
                self.assertEqual(cli.rows[-1].in_progress, terminal.in_progress)
                self.assertEqual(cli.rows[-1].abort_reason, terminal.abort_reason)
                self.assertEqual(5, case.export(12_000)["running"]["count"])
                detail, _ = history.acquire(case.service(12_000), case.stopped)
                self.assertFalse(detail.prompt_blocks[0].rows[-1].in_progress)
                case.cards.accept(delayed, 13_000)
                self.assertFalse(case.row(13_000).in_progress)

                full = case.source.load_session_snapshot(case.stopped)
                for complete in (False, True):
                    omitted = replace(full, complete=complete,
                        messages=tuple(m for m in full.messages if m.message_id not in {"resume", "system"}),
                        events=tuple(e for e in full.events if e.event_id != "resume"),
                        parts=tuple(p for p in full.parts if p.message_id not in {"resume", "system"}))
                    with patch.object(OpenCodeV2Source, "load_session_snapshot", return_value=omitted):
                        case.workers._capture(entry.root, entry.generation, 20_000, entry.snapshot, ())
                        retained, _ = history.acquire(case.service(20_000), case.stopped)
                    for result in case.workers.drain():
                        if result.phase != "timing":
                            case.cards.accept(result, 20_000)
                    self.assertFalse(case.row(20_000).in_progress)
                    self.assertEqual(terminal.duration_ms, case.row(20_000).duration_ms)
                    self.assertFalse(retained.prompt_blocks[0].rows[-1].in_progress)
                self.assertNotIn(case.stopped, [card.session_id for card in case.cards.project(50_000)[0]])
                cold = case.cold_capture(50_000)
                cold_row = cold.project(50_000)[1][0].rows[-1].prompt
                self.assertFalse(cold_row.in_progress)
                self.assertEqual(terminal.duration_ms, cold_row.duration_ms)
                newer = copy.deepcopy(messages[2])
                newer.update(id="genuinely_new_attempt", type="assistant", content=[],
                    time={"created": 51_000}, model={"providerID": "openai", "id": "gpt-5.6"})
                messages.append(newer)
                case.native.active[case.stopped] = {"type": "running"}
                for now in (52_000, 53_000, 54_000):
                    case.capture(now, churn=True)
                self.assertTrue(case.row(54_000).in_progress)
                self.assertEqual(6, case.export(54_000)["running"]["count"])


if __name__ == "__main__":
    unittest.main()
