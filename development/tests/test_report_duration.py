"""Deterministic accumulated execution duration, reports, cache and layout contracts."""
from __future__ import annotations

from dataclasses import replace
import unittest
from unittest.mock import patch

from development.tests.fixtures.compact_reports import rendered, report_service
from development.tests.fixtures.report_runtime import FakeSource
from development.tests.fixtures.session_snapshots import (
    MODEL, make_snapshot, make_native_v2_compaction_snapshot, message, part, prov,
)
from src.analysis.core import analyze_snapshot
from src.analysis.duration import accumulated_duration
from src.bootstrap import _report_request
from src.cli import parse_command
from src.domain import BackgroundActivity, EventKind, MessageRole, ModelInvocation, NormalizedEvent, TokenUsage, TerminalEvidence, TerminalOutcome
from src.presentation.duration import duration_text
from src.presentation.watch import _duration as watch_duration
from src.reports import ReportKind, ReportRequest

DAY = 86_400_000


def history(spans, *, archived=False, generation="v1"):
    """Root-only canonical history: spans are explicit start/end evidence."""
    base = make_snapshot(generation=generation)
    root = replace(base.root, archived_at_ms=DAY * 9 if archived else None, updated_at_ms=DAY * 8)
    events, messages, invocations = [], [], []
    for index, (start, end) in enumerate(spans):
        uid, aid = f"u{index}", f"a{index}"
        events.append(NormalizedEvent(uid, "root", EventKind.USER_PROMPT, start, prov("root", uid), "work"))
        messages.extend((message(uid, "root", MessageRole.USER, start),
                         message(aid, "root", MessageRole.ASSISTANT, start + 1, parent=uid,
                                 completed=end, model=MODEL, finish="stop" if end is not None else None)))
        invocations.append(ModelInvocation(aid, "root", start + 1, MODEL, TokenUsage(input=30, output=4),
                                           prov("root", aid), completed_at_ms=end, initiating_event_id=uid, message_id=aid))
    return replace(base, root=root, sessions=(root,), messages=tuple(messages), parts=(), events=tuple(events),
                   invocations=tuple(invocations), source_revision=f"duration-{generation}-{spans}")


def cells(line):
    return [cell.strip() for cell in line.split("|")[1:-1]]


class ReportDurationTests(unittest.TestCase):
    def detail(self, snapshot, *, now=DAY * 10):
        return report_service(self, FakeSource(snapshot), now_ms=now).build(
            ReportRequest(ReportKind.SESSION, session_id="root"))

    def test_completed_rows_total_placement_and_shared_watch_format(self):
        report = self.detail(history(((1000, 513_000), (DAY * 3, DAY * 3 + 255_000))))
        block, = report.prompt_blocks
        self.assertEqual([512_000, 255_000], [row.duration_ms for row in block.rows])
        self.assertEqual(767_000, block.duration_ms)
        text = rendered(report)
        header = next(cells(line) for line in text.splitlines() if "| Prompt" in line)
        self.assertEqual(["Calls", "Duration", "~Ictx"], header[2:5])
        total = next(cells(line) for line in text.splitlines() if line.startswith("| Total "))
        self.assertEqual("12m47s", total[3])
        self.assertIn("8m32s", text)
        self.assertIn("4m15s", text)
        for ms, expected in ((None, "N/A"), (499, "0s"), (500, "1s"), (59_500, "1m"),
                             (512_000, "8m32s"), (3_600_000, "1h"), (DAY + 3_600_000, "1d1h")):
            self.assertEqual(expected, duration_text(ms))
            self.assertEqual(expected, watch_duration(ms))

    def test_idle_gaps_overlaps_and_large_union(self):
        spans = ((1000, 1_201_000), (DAY * 3, DAY * 3 + 2_400_000))
        self.assertEqual(3_600_000, self.detail(history(spans)).prompt_blocks[0].duration_ms)
        overlap = self.detail(history(((1000, 10_000), (5000, 20_000))))
        self.assertEqual(19_000, overlap.prompt_blocks[0].duration_ms)
        self.assertEqual(100_001, accumulated_duration((n, 2) for n in range(100_000, 0, -1)))
        self.assertEqual(0, accumulated_duration(()))

    def test_child_work_is_not_added_twice_or_extended_by_session_metadata(self):
        snapshot = make_snapshot()
        root, child = snapshot.sessions
        child = replace(child, updated_at_ms=DAY * 8)
        block, = self.detail(replace(snapshot, sessions=(root, child))).prompt_blocks
        self.assertEqual([700, 300, 300], [row.duration_ms for row in block.rows])
        self.assertEqual(1300, block.duration_ms)
        self.assertEqual(3, block.rows[0].calls)
        self.assertGreater(block.rows[0].subagent_ccost, 0)

    def test_watch_retains_existing_duration_values_and_lifecycle(self):
        snapshot = make_snapshot()
        service = report_service(self, FakeSource(snapshot), now_ms=10_000)
        watch, _, bundle = service.build_watch_root(snapshot.root)
        self.assertEqual([record.duration_ms for record in bundle.prompts],
                         [row.duration_ms for row in watch.rows if not row.is_compaction])
        self.assertEqual(800, watch.rows[0].duration_ms)
        detail = service.build(ReportRequest(ReportKind.SESSION, session_id="root"))
        self.assertEqual(700, detail.prompt_blocks[0].rows[0].duration_ms)
        self.assertEqual([row.in_progress for row in watch.rows],
                         [row.in_progress for row in detail.prompt_blocks[0].rows])

    def test_terminated_success_failure_cancellation_freeze_without_changing_outcomes(self):
        for outcome in TerminalOutcome:
            snapshot = history(((1000, 4000),))
            user, assistant = snapshot.messages
            evidence = TerminalEvidence(completed_at_ms=5000, outcome=outcome)
            assistant = replace(assistant, completed_at_ms=None, finish_reason=None, termination=evidence)
            snapshot = replace(snapshot, messages=(user, assistant))
            early = self.detail(snapshot, now=10_000).prompt_blocks[0].rows[0]
            late = self.detail(snapshot, now=DAY * 10).prompt_blocks[0].rows[0]
            self.assertEqual(4000, early.duration_ms)
            self.assertEqual(early.duration_ms, late.duration_ms)
            self.assertFalse(late.in_progress)
            self.assertEqual(outcome is TerminalOutcome.CANCELLATION, late.aborted)
            self.assertEqual(outcome is TerminalOutcome.FAILURE, late.watch_error)

    def test_running_duration_uses_report_clock_and_open_session_does_not_extend_completed(self):
        snapshot = history(((1000, None),))
        early = self.detail(snapshot, now=4000).prompt_blocks[0]
        late = self.detail(snapshot, now=8000).prompt_blocks[0]
        self.assertTrue(early.rows[0].in_progress)
        self.assertEqual(3000, early.duration_ms)
        self.assertEqual(7000, late.duration_ms)
        done = self.detail(history(((1000, 4000),)), now=DAY * 10).prompt_blocks[0]
        self.assertFalse(done.rows[0].in_progress)
        self.assertEqual(3000, done.duration_ms)

    def test_missing_terminal_and_invalid_start_poison_total_not_zero(self):
        snapshot = history(((1000, 2000), (3000, None)))
        messages = tuple(replace(m, error_name="ProviderError") if m.message_id == "a1" else m
                         for m in snapshot.messages)
        report = self.detail(replace(snapshot, messages=messages))
        block, = report.prompt_blocks
        self.assertEqual([1000, None], [row.duration_ms for row in block.rows])
        self.assertIsNone(block.duration_ms)
        self.assertEqual("N/A", next(cells(line)[3] for line in rendered(report).splitlines() if line.startswith("| Total ")))
        listing = report_service(self, FakeSource(replace(snapshot, messages=messages))).build(ReportRequest(ReportKind.SESSIONS))
        self.assertIsNone(listing.session_usage[0].duration_ms)
        self.assertIsNone(self.detail(history(((0, 4000),))).prompt_blocks[0].duration_ms)
        self.assertIsNone(accumulated_duration(((1000, 1000), (4000, None))))

    def test_background_wait_resume_and_unknown_registry_completion(self):
        snapshot = history(((1000, 2000),))
        job = BackgroundActivity("job", "root", "shell", 1500, "a0")
        waiting = replace(snapshot, background=(job,))
        block = self.detail(waiting, now=6000).prompt_blocks[0]
        self.assertTrue(block.rows[0].in_progress)
        self.assertEqual(5000, block.duration_ms)
        done = replace(job, running=False, ended_at_ms=5000)
        finished = replace(snapshot, background=(done,))
        self.assertEqual(4000, self.detail(finished).prompt_blocks[0].duration_ms)
        missing = replace(snapshot, background=(replace(job, running=False),))
        self.assertIsNone(self.detail(missing).prompt_blocks[0].duration_ms)
        notice = NormalizedEvent("notice", "root", EventKind.BACKGROUND_COMPLETION, 5000, prov("root", "notice"))
        resumed = message("resumed", "root", MessageRole.ASSISTANT, 5100, parent="notice", completed=8000,
                          model=MODEL, finish="stop")
        request = replace(snapshot.invocations[0], invocation_id="resumed", message_id="resumed",
                          initiating_event_id="notice", created_at_ms=5100, completed_at_ms=8000)
        resumed_snapshot = replace(finished, events=(*finished.events, notice),
                                   messages=(*finished.messages, resumed), invocations=(*finished.invocations, request))
        block = self.detail(resumed_snapshot).prompt_blocks[0]
        self.assertEqual(1, len(block.rows))
        self.assertEqual(7000, block.duration_ms)

    def test_billable_and_nonbillable_compactions_and_missing_completion(self):
        billable = self.detail(make_snapshot()).prompt_blocks[0]
        self.assertEqual(300, billable.rows[-1].duration_ms)
        native = make_native_v2_compaction_snapshot()
        native = replace(native, messages=tuple(replace(m, completed_at_ms=2100) if m.message_id == "u_comp" else m
                                                for m in native.messages))
        report = self.detail(native)
        compaction = next(row for row in report.prompt_blocks[0].rows if row.is_compaction)
        self.assertEqual(300, compaction.duration_ms)
        self.assertEqual(0, compaction.calls)
        self.assertEqual(1200, report.prompt_blocks[0].duration_ms)
        self.assertIn("0s", next(line for line in rendered(report).splitlines() if "/compact" in line))
        native = replace(native, messages=tuple(replace(m, completed_at_ms=None) if m.message_id == "u_comp" else m
                                                for m in native.messages))
        block = self.detail(native).prompt_blocks[0]
        self.assertIsNone(next(row.duration_ms for row in block.rows if row.is_compaction))
        self.assertIsNone(block.duration_ms)

    def test_running_compaction_uses_observation_time_without_changing_watch(self):
        snapshot = make_snapshot()
        root = replace(snapshot.root, active=True)
        compact = part("p_comp", "u_comp", "root", "compaction", {"status": "running"}, 3000)
        messages = tuple(replace(m, parts=(compact,)) if m.message_id == "u_comp" else m
                         for m in snapshot.messages if m.message_id != "a_comp")
        snapshot = replace(snapshot, root=root, sessions=(root, snapshot.sessions[1]), messages=messages,
                           parts=tuple(p for m in messages for p in m.parts),
                           invocations=tuple(i for i in snapshot.invocations if i.message_id != "a_comp"))
        early = self.detail(snapshot, now=6000).prompt_blocks[0]
        late = self.detail(snapshot, now=8000).prompt_blocks[0]
        self.assertTrue(early.rows[-1].is_compaction)
        self.assertTrue(early.rows[-1].in_progress)
        self.assertEqual(3000, early.rows[-1].duration_ms)
        self.assertEqual(4000, early.duration_ms)
        self.assertEqual(6000, late.duration_ms)

    def test_date_and_date_range_totals_use_selected_event_scope(self):
        snapshot = history(((DAY, DAY + 60_000), (DAY * 3, DAY * 3 + 120_000), (DAY * 4, DAY * 4 + 180_000)))
        for dates, expected in ((("1970-01-04",), 120_000), (("1970-01-04:1970-01-05",), 300_000)):
            command = parse_command(list(dates))
            service = report_service(self, FakeSource(snapshot), now_ms=DAY * 10)
            report = service.build(_report_request(command))
            self.assertEqual(expected, report.prompt_blocks[0].duration_ms)
            self.assertIn("Duration", rendered(report))

    def test_sessions_numeric_all_archive_cache_and_no_extra_hydration(self):
        for generation in ("v1", "v2"):
            source = FakeSource(history(((1000, 1_201_000), (DAY * 3, DAY * 3 + 2_400_000)),
                                        archived=True, generation=generation))
            service = report_service(self, source)
            with patch.object(source, "load_session_snapshot", wraps=source.load_session_snapshot) as load:
                for limit in ("10", "all"):
                    report = service.build(_report_request(parse_command(["--sessions", limit])))
                    self.assertEqual(3_600_000, report.session_usage[0].duration_ms)
                    text = rendered(report)
                    self.assertIn("Duration", text)
                    self.assertIn("1h", text)
                    self.assertNotIn("| Total", text)
                self.assertEqual(1, load.call_count)
                fresh = report_service(self, source)
                fresh._acquisition.cache = service._derived
                cached = fresh.build(ReportRequest(ReportKind.SESSIONS))
                self.assertEqual(3_600_000, cached.session_usage[0].duration_ms)
                self.assertEqual(1, load.call_count)

    def test_narrow_layout_stays_aligned_and_protects_numeric_cells(self):
        report = self.detail(history(((1000, 513_000),)))
        for width in (60, 100, 120, 180):
            lines = rendered(report, width=width).splitlines()
            table = [line for line in lines if line.startswith("|")]
            self.assertEqual(1, len({len(line) for line in table}))
            header = next(line for line in table if "| Prompt" in line)
            self.assertLessEqual(len(header), max(width, 113))
            self.assertIn("8m32s", "\n".join(table))


if __name__ == "__main__":
    unittest.main()
