"""Canonical request coverage and revisions through Watch capture/cards/export."""
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from development.tests.fixtures.session_snapshots import make_snapshot, make_uncompacted_snapshot
from development.tests.fixtures.watch_runtime import MutableSource, make_service
from src.application.live_projection import project_live
from src.domain import ModelRef, TokenUsage
from src.reports import ReportKind, ReportRequest
from src.reports.watch_capture import capture_rows
from src.watch.card_workers import CardResult
from src.watch.cards import WatchCards
from src.watch.models import WatchProjection
from src.watch.observers import CatalogObservation


class WatchTokenMixTests(unittest.TestCase):
    def setUp(self):
        temp = self.enterContext(tempfile.TemporaryDirectory())
        self.source = MutableSource(make_uncompacted_snapshot(running=True))
        self.service = make_service(temp, self.source, now_ms=4000)[2]
        self.root = self.source.snapshot.root
        self.cards = WatchCards(None)
        self.cards.catalog(CatalogObservation((self.root,), (self.root,), {},
            {self.root.session_id: "initial"}, frozenset({self.root.session_id})))

    def capture(self, snapshot, now=4000):
        self.source.snapshot = snapshot
        self.service.set_now_ms(now)
        capture, item = capture_rows(self.service, self.root)
        return capture, item

    def publish(self, capture, generation=None):
        entry = self.cards.sessions[self.root.session_id]
        self.cards.accept(CardResult(self.root.session_id,
            entry.generation if generation is None else generation, "rows", (capture, (), None)), capture.observed_at_ms)

    def wire(self, now=4000):
        active, history, state = self.cards.project(now)
        return project_live(WatchProjection("Watch", "fixture", (), now_ms=now,
            active_cards=active, history_cards=history, cards_state=state)).to_json()

    def report_row(self, event_id):
        report = self.service.build(ReportRequest(ReportKind.SESSION, self.root.session_id))
        return next(row for row in report.prompt_blocks[0].rows if row.event_id == event_id)

    def usage_snapshot(self, usages, *, running=True, revision="usage"):
        snapshot = make_uncompacted_snapshot(running=running)
        original = next(item for item in snapshot.invocations if item.invocation_id == "i_next")
        message = next(item for item in snapshot.messages if item.message_id == "a_next")
        invocations = tuple(item for item in snapshot.invocations if item.invocation_id != "i_next")
        messages = tuple(item for item in snapshot.messages if item.message_id != "a_next")
        for index, usage in enumerate(usages):
            mid = "call-" + str(index)
            terminal = not running or index < len(usages) - 1
            end = 2300 + index * 100 if terminal else None
            messages += (replace(message, message_id=mid, created_at_ms=2100 + index * 100,
                completed_at_ms=end, finish_reason="stop" if terminal else None),)
            invocations += (replace(original, invocation_id=mid, message_id=mid,
                created_at_ms=2100 + index * 100, completed_at_ms=end, tokens=usage),)
        return replace(snapshot, messages=messages, invocations=invocations, source_revision=revision)

    def test_live_cumulative_calls_corrections_and_unknown_terminal_replace_not_accumulate(self):
        first = TokenUsage(input=100)
        cached = TokenUsage(cache_read=300)
        output = TokenUsage(output=80, reasoning=20)
        cases = [((first,), (100, 0, 0, 0)), ((first, cached), (25, 75, 0, 0)),
            ((first, cached, output), (20, 60, 0, 20)),
            ((first, TokenUsage(cache_read=100), output), (33, 33, 0, 34)),
            ((first, TokenUsage(input=100, known_fields=("input",))), None)]
        captures = []
        for index, (usages, expected) in enumerate(cases):
            snapshot = self.usage_snapshot(usages, running=index != 4, revision=str(index))
            capture, _ = self.capture(snapshot, now=4000 + index * 1000)
            row = next(row for row in capture.rows if row.event_id == "u_next")
            self.assertEqual(expected, row.token_mix_percent)
            self.assertEqual(len(usages), row.calls)
            self.publish(capture)
            wire = self.wire(4000 + index * 1000)["active_cards"][-1]["rows"][0]["prompt"]
            self.assertEqual(None if expected is None else list(expected), wire["token_mix_percent"])
            self.assertEqual("N/A" if expected is None else "/".join(map(str, expected)), wire["display"]["token_mix_percent"])
            self.assertEqual(wire["token_mix_percent"], self.wire(4500 + index * 1000)["active_cards"][-1]["rows"][0]["prompt"]["token_mix_percent"], "ticks cannot manufacture usage")
            captures.append(capture)
        self.publish(captures[0])
        self.assertIsNone(self.wire(8000)["active_cards"][-1]["rows"][0]["prompt"]["token_mix_percent"], "older captures cannot restore a superseded mix")
        generation = self.cards.sessions[self.root.session_id].generation
        self.cards.catalog(CatalogObservation((self.root,), (self.root,), {},
            {self.root.session_id: "new"}, frozenset()))
        self.publish(replace(captures[0], observed_at_ms=9000), generation)
        self.assertIsNone(self.wire(9000)["active_cards"][-1]["rows"][0]["prompt"]["token_mix_percent"])
        history = self.wire(39000)["history_cards"][-1]["rows"][0]["prompt"]
        self.assertIsNone(history["token_mix_percent"])
        self.assertEqual(history["duration_ms"], self.wire(99000)["history_cards"][-1]["rows"][0]["prompt"]["duration_ms"])

    def test_complete_known_cache_reasoning_child_and_compaction_agree_with_cli(self):
        snapshot = make_snapshot()
        invocations = tuple(replace(item, model=ModelRef("other", "child-model"),
            tokens=TokenUsage(input=10, cache_read=70, cache_write=10, output=5, reasoning=5))
            if item.invocation_id == "i_child" else item for item in snapshot.invocations)
        capture, _ = self.capture(replace(snapshot, invocations=invocations))
        for row in capture.rows:
            self.assertEqual(self.report_row(row.event_id).token_mix_percent, row.token_mix_percent)
        child = next(row for row in capture.rows if row.event_id == "u_sub")
        self.assertTrue(child.has_additional_model)
        self.assertGreater(child.calls, 1)
        self.assertIsNotNone(child.token_mix_percent)

    def test_completed_partial_child_is_unknown_without_changing_cli_or_other_metrics(self):
        snapshot = make_uncompacted_snapshot()
        invocations = tuple(replace(item, tokens=TokenUsage(input=20, output=5,
            known_fields=("input", "output")))
            if item.invocation_id == "i_child" else item for item in snapshot.invocations)
        capture, _ = self.capture(replace(snapshot, invocations=invocations))
        actual = next(row for row in capture.rows if row.event_id == "u_sub")
        cli = self.report_row("u_sub")
        self.assertIsNone(actual.token_mix_percent)
        self.assertIsNotNone(cli.token_mix_percent, "approved Watch-only exception; CLI behavior stays unchanged")
        self.assertEqual((cli.calls, cli.ccost), (actual.calls, actual.ccost))

    def test_zero_and_absent_usage_never_invent_zero_percentages(self):
        for usage in (TokenUsage(), TokenUsage(known_fields=())):
            with self.subTest(usage=usage):
                snapshot = self.usage_snapshot((usage,), running=False)
                capture, _ = self.capture(snapshot)
                actual = next(row for row in capture.rows if row.event_id == "u_next")
                self.assertIsNone(actual.token_mix_percent)
                self.assertIsNone(self.report_row("u_next").token_mix_percent)

    @unittest.skipUnless(shutil.which("node"), "optional JavaScript VM unavailable")
    def test_accepted_sse_updates_dom_without_reload_and_rejects_stale_mix(self):
        frames = []
        usages = (TokenUsage(input=100), TokenUsage(cache_read=300), TokenUsage(output=100))
        for index in range(3):
            capture, _ = self.capture(self.usage_snapshot(usages[:index + 1], revision=str(index)), now=4000 + index * 1000)
            self.publish(capture)
            frames.append(dict(state="running", view=self.wire(4000 + index * 1000)))
        result = subprocess.run([shutil.which("node"), "development/tests/integration/web_live.cjs"],
            input=json.dumps(dict(tokenMixFrames=frames)), text=True, capture_output=True,
            cwd=Path(__file__).resolve().parents[2], timeout=10)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("web token mix SSE passed", result.stdout)

    def test_clock_is_local_hhmm_across_dates_and_dst_without_renumbering(self):
        capture, _ = self.capture(make_uncompacted_snapshot())
        self.publish(capture)
        active, history, state = self.cards.project(4000)
        base = history[-1]
        clocks = []
        for stamp in ("2026-10-24T23:30:00+00:00", "2026-10-25T01:30:00+00:00"):
            at = int(datetime.fromisoformat(stamp).astimezone(timezone.utc).timestamp() * 1000)
            card = replace(base, rows=(replace(base.rows[0], prompt=replace(base.rows[0].prompt,
                prompt_number=12, at_ms=at)),))
            wire = project_live(WatchProjection("Watch", "fixture", (), history_cards=(card,)), "Europe/Stockholm").to_json()
            row = wire["history_cards"][0]["rows"][0]["prompt"]
            clocks.append((row["display"]["clock"], row["display"]["date_time"]))
            self.assertEqual(12, row["prompt_number"])
        self.assertEqual([("01:30", "2026-10-25 01:30"), ("02:30", "2026-10-25 02:30")], clocks)
