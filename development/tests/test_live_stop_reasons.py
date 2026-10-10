"""Live interruption attribution requires matching authoritative terminal history."""
from __future__ import annotations

from contextlib import closing
import io
import json
import tempfile
import unittest

from development.fixtures.opencode_v2_service import source_with_current_service
from development.fixtures.watch_runtime import make_service
from src.analysis.core import analyze_snapshot
from src.presentation import WatchRenderer
from src.sources.errors import SourceResyncRequiredError
from src.sources.opencode_v2 import OpenCodeV2Source
from src.sources.opencode_v2_interruptions import LiveInterruptionReasons
from src.watch import WatchCoordinator


def interruption(*, event_id="evt_cancelled", session_id="ses_current", at_ms=5000, reason="user"):
    return {"id": event_id, "type": "session.execution.interrupted", "created": at_ms,
            "data": {"sessionID": session_id, "reason": reason}}


def cancel_history(native, *, outcome="interrupted", terminal_id="msg_cancelled", at_ms=5000):
    native.messages["ses_current"][1].update(error={"type": "aborted", "message": "Step interrupted"}, finish="error")
    native.messages["ses_current"].append({"id": terminal_id, "type": "idle", "outcome": outcome,
                                           "time": {"created": at_ms}})


def consume_interrupt(source, native, event):
    native.events = [json.dumps(event)]
    with closing(source.iter_changes()) as changes:
        return next(changes)


class LiveStopReasonTests(unittest.TestCase):
    def test_real_event_pump_records_cause_before_watch_refresh(self):
        with source_with_current_service() as (source, native, _), tempfile.TemporaryDirectory() as td:
            cancel_history(native)
            native.events = [json.dumps(interruption())]
            config, selection, reports, _ = make_service(td, source)
            watch = WatchCoordinator(selection=selection, report_service=reports, config=config,
                                     session_id="ses_current", clock_ms=lambda: 10_000)
            try:
                watch.initialize()

                event = watch._event_pump.get(timeout=2)
                row = watch.poll_once(hinted_session_ids=(event.change.session_id,)).projection.rows[0]

                self.assertEqual("user", row.prompt.abort_reason)
                self.assertTrue(row.prompt.aborted)
            finally:
                watch.close()

    def test_live_user_reason_reaches_watch_survives_resync_but_not_fresh_source(self):
        with source_with_current_service() as (source, native, registration), tempfile.TemporaryDirectory() as td:
            cancel_history(native)
            config, selection, reports, _ = make_service(td, source)
            clock = [10_000]
            watch = WatchCoordinator(selection=selection, report_service=reports, config=config,
                                     session_id="ses_current", clock_ms=lambda: clock[0])
            renderer = WatchRenderer(config, stream=io.StringIO(), interactive=True)
            old = watch.initialize().projection.rows[0]
            self.assertIn("[ABORTED]", renderer._row_label(old))
            before_revision = source.get_session_tree_revision("ses_current")

            change = consume_interrupt(source, native, interruption())
            live = watch.poll_once(hinted_session_ids=(change.session_id,)).projection.rows[0]
            clock[0] = 100_000
            aged = watch.poll_once(force_resync=True).projection.rows[0]

            self.assertEqual("ses_current", change.session_id)
            self.assertNotEqual(before_revision, source.get_session_tree_revision("ses_current"))
            for row in (live, aged):
                self.assertTrue(row.prompt.aborted)
                self.assertFalse(row.prompt.in_progress)
                self.assertIn("[ABORTED by user]", renderer._row_label(row))
            self.assertEqual("", aged.marker)
            snapshot = source.load_session_snapshot("ses_current")
            self.assertFalse(analyze_snapshot(snapshot, tracked_provider=None).cacheable)
            watch.close()

            fresh = OpenCodeV2Source(registration, timeout_seconds=2)
            _, fresh_selection, fresh_reports, _ = make_service(td, fresh)
            restored = WatchCoordinator(selection=fresh_selection, report_service=fresh_reports, config=config,
                                        session_id="ses_current", clock_ms=lambda: 100_000)
            try:
                self.assertIn("[ABORTED]", renderer._row_label(restored.initialize().projection.rows[0]))
            finally:
                restored.close()

    def test_unmatched_non_user_and_malformed_events_never_invent_user_cause(self):
        events = (
            interruption(event_id="evt_other"), interruption(session_id="ses_current_child"),
            interruption(at_ms=5001), interruption(reason="inactivity"), interruption(reason="shutdown"),
            interruption(reason="superseded"), interruption(reason="unknown"), interruption(at_ms=True),
            interruption(at_ms=float("inf")), interruption(at_ms=0), interruption(event_id="cancelled"),
            {**interruption(), "type": "session.status"},
            {**interruption(), "data": {"sessionID": "ses_current", "message": "user"}},
        )
        for event in events:
            with self.subTest(event=event), source_with_current_service() as (source, native, _):
                cancel_history(native)
                consume_interrupt(source, native, event)

                record, = analyze_snapshot(source.load_session_snapshot("ses_current"), tracked_provider=None).prompts

                self.assertTrue(record.aborted)
                self.assertEqual("", record.abort_reason)

    def test_live_event_without_terminal_history_does_not_end_running_work(self):
        with source_with_current_service() as (source, native, _):
            assistant = native.messages["ses_current"][1]
            assistant.pop("finish")
            assistant["time"].pop("completed")
            native.active = {"ses_current": {"type": "running"}}
            consume_interrupt(source, native, interruption())

            record, = analyze_snapshot(source.load_session_snapshot("ses_current"), tracked_provider=None).prompts

            self.assertTrue(record.in_progress)
            self.assertFalse(record.aborted)
            self.assertEqual("", record.abort_reason)

    def test_success_and_later_unknown_abort_do_not_inherit_old_user_reason(self):
        with source_with_current_service() as (source, native, _):
            cancel_history(native)
            consume_interrupt(source, native, interruption())
            native.messages["ses_current"].append({"id": "msg_success", "type": "idle", "outcome": "succeeded",
                                                   "time": {"created": 6000}})

            succeeded, = analyze_snapshot(source.load_session_snapshot("ses_current"), tracked_provider=None).prompts

            self.assertTrue(succeeded.completed_successfully)
            self.assertEqual("", succeeded.abort_reason)
            native.messages["ses_current"].append({"id": "msg_later", "type": "idle", "outcome": "interrupted",
                                                   "time": {"created": 7000}})
            later, = analyze_snapshot(source.load_session_snapshot("ses_current"), tracked_provider=None).prompts
            self.assertTrue(later.aborted)
            self.assertEqual("", later.abort_reason)

    def test_current_object_event_and_legacy_hints_keep_session_routing(self):
        with source_with_current_service() as (source, native, _):
            native.events = [interruption(), {"payload": {"type": "session.updated",
                                                        "properties": {"sessionID": "ses_current_child"}}}]
            with closing(source.iter_changes()) as changes:
                current, legacy = next(changes), next(changes)
                with self.assertRaises(SourceResyncRequiredError):
                    next(changes)

            self.assertEqual("ses_current", current.session_id)
            self.assertEqual("ses_current_child", legacy.session_id)

    def test_retention_is_bounded_and_duplicate_events_do_not_change_revision(self):
        reasons = LiveInterruptionReasons()
        for index in range(reasons.MAX_OBSERVATIONS + 1):
            reasons.observe(interruption(event_id=f"evt_{index}"))
        signature = reasons.signature("ses_current")
        reasons.observe(interruption(event_id=f"evt_{reasons.MAX_OBSERVATIONS}"))

        self.assertEqual(signature, reasons.signature("ses_current"))
        self.assertEqual(reasons.MAX_OBSERVATIONS, len(signature))
        self.assertEqual("", reasons.reason({"id": "msg_0", "type": "idle", "outcome": "interrupted",
                                             "time": {"created": 5000}}, "ses_current"))
        self.assertEqual("user", reasons.reason({"id": f"msg_{reasons.MAX_OBSERVATIONS}", "type": "idle",
                                                 "outcome": "interrupted", "time": {"created": 5000}}, "ses_current"))


if __name__ == "__main__":
    unittest.main()
