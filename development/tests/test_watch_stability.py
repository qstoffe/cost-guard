"""Qualified Web metrics and current-tool authority, independently of history."""
from dataclasses import replace
import tempfile
import unittest
from unittest.mock import patch

from development.tests.fixtures.session_snapshots import one_request, history, make_snapshot, moved_location
from development.tests.fixtures.watch_runtime import MutableSource, make_service
from development.tests.fixtures.watch_stability import refresh_publications
from development.tests.fixtures.mini_context import handoff_snapshot, handoff_capture
from src.analysis.duration import accumulated_duration
from src.domain import TokenUsage, ActiveContext
from src.domain.effort import EffortEvidence
from src.application.prompt_costs import watch_calls
from src.reports.watch_capture import capture_rows
from src.watch.cards import CardSession, WatchCards
from src.watch.card_workers import CardResult
from src.sources.errors import SourceUnavailableError


class WatchStabilityTests(unittest.TestCase):
    def test_complete_current_call_survives_unrelated_historical_omissions(self):
        with tempfile.TemporaryDirectory() as directory:
            frames = refresh_publications(directory)
        identity = frames[0]["active_cards"][0]["rows"][0]["tool"]["running_invocations"][0]["identity"]
        clocks = []
        durations = []
        for frame in frames:
            card = frame["active_cards"][0]
            tool = card["rows"][0]["tool"]
            self.assertTrue(card["invocation_verified"])
            self.assertEqual("observed", tool["detail_state"])
            self.assertEqual(identity, tool["running_invocations"][0]["identity"])
            self.assertIn("python safe.py", tool["running_invocations"][0]["text"])
            self.assertIn("python background.py", tool["background_invocations"][0]["text"])
            self.assertIn("src/missing.py", tool["failed_invocations"][0]["text"])
            clocks.append(tool["running_ms"])
            durations.append(card["session_summary"]["duration_ms"])
        self.assertEqual(sorted(set(clocks)), clocks)
        self.assertEqual("partial", frames[1]["active_cards"][0]["state"])
        self.assertTrue(all(value is not None for value in durations))
        self.assertEqual(sorted(set(durations)), durations)

    def test_running_delta_uses_current_footer_raw_context_even_on_first_prompt(self):
        for output in (0, 1, 4321):
            with self.subTest(output=output), tempfile.TemporaryDirectory() as directory:
                snapshot = one_request(usage=TokenUsage(input=12345, cache_read=0, cache_write=0, output=output))
                source = MutableSource(snapshot)
                _, _, service, _ = make_service(directory, source, now_ms=3000)
                capture, _ = capture_rows(service, snapshot.root)
                row = capture.rows[-1]
                self.assertEqual(12345, row.incoming_context_tokens)
                self.assertIsNotNone(capture.context.tokens)
                self.assertEqual(capture.context.tokens - 12345, row.watch_delta_context_tokens)
                self.assertEqual(output, row.watch_delta_context_tokens)

    def test_compaction_and_context_boundary_do_not_borrow_a_footer(self):
        for snapshot in (make_snapshot(running=True), moved_location(one_request(), 2500)):
            with self.subTest(revision=snapshot.source_revision), tempfile.TemporaryDirectory() as directory:
                source = MutableSource(snapshot)
                _, _, service, _ = make_service(directory, source, now_ms=4000)
                capture, _ = capture_rows(service, snapshot.root)
                row = next(row for row in capture.rows if row.event_id == "u_next")
                self.assertIsNone(row.watch_delta_context_tokens)

    def test_small_temporary_dispatch_does_not_replace_the_whole_context_footer(self):
        initial = one_request(usage=TokenUsage(input=12345, cache_read=0, cache_write=0, output=0))
        for next_input in (12001, 12345, 16432):
            with self.subTest(next_input=next_input), tempfile.TemporaryDirectory() as directory:
                request = replace(initial.invocations[0], invocation_id="i_later", message_id="a_later",
                    created_at_ms=2500, tokens=TokenUsage(input=next_input, cache_read=0, cache_write=0, output=0))
                assistant = replace(initial.messages[-1], message_id="a_later", created_at_ms=2500,
                    tokens=request.tokens)
                snapshot = replace(initial, invocations=(*initial.invocations, request),
                    messages=(*initial.messages, assistant),
                    active_contexts=(ActiveContext("root", ("u_next", "a_next", "a_later")),))
                source = MutableSource(snapshot)
                _, _, service, _ = make_service(directory, source, now_ms=3000)
                capture, _ = capture_rows(service, snapshot.root)
                expected = max(12345, next_input)
                self.assertEqual(expected, capture.context.tokens)
                self.assertEqual(12345, capture.rows[-1].incoming_context_tokens)
                self.assertEqual(expected - 12345, capture.rows[-1].watch_delta_context_tokens)

    def test_qualified_footer_contract_keeps_negative_zero_and_positive_raw_deltas(self):
        # Synthetic qualified observations test the join, not native shrink inference.
        snapshot = one_request(usage=TokenUsage(input=12345, cache_read=0, cache_write=0, output=0))
        with tempfile.TemporaryDirectory() as directory:
            _, _, service, _ = make_service(directory, MutableSource(snapshot), now_ms=3000)
            baseline, _ = capture_rows(service, snapshot.root)
            for tokens in (12001, 12345, 16432):
                with self.subTest(tokens=tokens), patch("src.reports.watch_capture.card_context",
                        return_value=replace(baseline.context, tokens=tokens)):
                    capture, _ = capture_rows(service, snapshot.root)
                    self.assertEqual(tokens - 12345, capture.rows[-1].watch_delta_context_tokens)

    def test_same_prompt_pending_footer_join_reconciles_retained_operands(self):
        snapshot = one_request()
        with tempfile.TemporaryDirectory() as directory:
            _, _, service, _ = make_service(directory, MutableSource(snapshot), now_ms=3000)
            capture, item = capture_rows(service, snapshot.root)
            cards = WatchCards(None)
            entry = CardSession(snapshot.root, snapshot.source_revision, 1)
            cards.sessions["root"] = entry
            cards.accept(CardResult("root", 1, "rows", (capture, (), item.snapshot)), 3000)
            pending = replace(capture, observed_at_ms=4000,
                context=replace(capture.context, tokens=None, context_state="pending"),
                rows=tuple(replace(row, watch_delta_context_tokens=None) for row in capture.rows))
            cards.accept(CardResult("root", 1, "rows", (pending, (), item.snapshot)), 4000)
            row = entry.capture.rows[-1]
            self.assertEqual(entry.capture.context.tokens - row.incoming_context_tokens,
                row.watch_delta_context_tokens)
            invalid = replace(pending, observed_at_ms=5000,
                context=replace(pending.context, context_epoch="new", context_state="invalidated"))
            cards.accept(CardResult("root", 1, "rows", (invalid, (), item.snapshot)), 5000)
            self.assertIsNone(entry.capture.rows[-1].watch_delta_context_tokens)

    def test_handoff_never_assigns_the_new_footer_to_the_old_prompt(self):
        for phase in ("prior", "early", "pending", "fresh", "reset", "model", "move"):
            with self.subTest(phase=phase):
                capture = handoff_capture(handoff_snapshot(phase))
                for row in capture.rows:
                    if not row.in_progress:
                        continue
                    if (phase == "fresh" and row.event_id == capture.context.owner_id
                            and row.incoming_context_tokens is not None):
                        self.assertEqual(capture.context.tokens - row.incoming_context_tokens,
                            row.watch_delta_context_tokens)
                    elif row.incoming_context_tokens is None or row.event_id != capture.context.owner_id:
                        self.assertIsNone(row.watch_delta_context_tokens)

    def test_late_capture_cannot_replace_newer_context_or_duration(self):
        snapshot = one_request()
        with tempfile.TemporaryDirectory() as directory:
            _, _, service, _ = make_service(directory, MutableSource(snapshot), now_ms=3000)
            capture, item = capture_rows(service, snapshot.root)
            cards = WatchCards(None)
            entry = CardSession(snapshot.root, snapshot.source_revision, 1)
            cards.sessions["root"] = entry
            cards.accept(CardResult("root", 1, "rows", (capture, (), item.snapshot)), 3000)
            stale = replace(capture, observed_at_ms=2000, duration_intervals=())
            cards.accept(CardResult("root", 1, "rows", (stale, (), item.snapshot)), 4000)
            self.assertEqual(3000, entry.capture.observed_at_ms)
            self.assertEqual(capture.context, entry.capture.context)
            self.assertEqual(capture.duration_intervals, entry.capture.duration_intervals)

    def test_calls_combine_roles_and_price_tiers_without_losing_effort_qualification(self):
        from decimal import Decimal
        from src.reports.prompt_costs import PromptCostPart
        from types import SimpleNamespace
        main = PromptCostPart("root", 0, "provider", "model", "high", "Model", "High",
            2, Decimal(0), 2, True, (Decimal(0),) * 4, "standard")
        child = replace(main, session_id="child", agent=1, price_tier="long", calls=3)
        row = SimpleNamespace(cost_parts=(main, child), calls=5, agent_coverage=(), linked_agent_count=1)
        self.assertEqual("provider/model (High): 5 calls", watch_calls(row))
        inferred = replace(main, effort="default", effort_evidence=(
            EffortEvidence("default", "high", "current-configuration", "revision"),))
        row.cost_parts = (inferred,)
        row.calls = 2
        self.assertIn("Inferred from current OpenCode", watch_calls(row))
        self.assertNotIn("Total Calls", watch_calls(row))

    def test_session_duration_reuses_all_canonical_intervals_and_clock_ticks(self):
        snapshot = history(((1000, 1200), (1100, 1500), (2000, None)))
        with tempfile.TemporaryDirectory() as directory:
            source = MutableSource(snapshot)
            _, _, service, _ = make_service(directory, source, now_ms=3000)
            capture, item = capture_rows(service, snapshot.root)
            entry = CardSession(snapshot.root, snapshot.source_revision, 1, capture=capture, state="observed")
            cards = WatchCards(None)
            focal = capture.rows[-1]
            self.assertEqual(1500, cards._card(entry, focal, 3000).session_duration_ms)
            self.assertEqual(2500, cards._card(entry, focal, 4000).session_duration_ms)
            self.assertEqual(1, source.load_count, "ticks and Mini reopen reuse the acquired root")
            expected = accumulated_duration([(record.prompt_time_ms, record.execution_duration_ms)
                for record in item.bundle.prompts] +
                [(record.created_at_ms, record.duration_ms) for record in item.bundle.compactions])
            self.assertEqual(expected, cards._card(entry, focal, 3000).session_duration_ms)
            entry.state = "unavailable"
            self.assertIsNone(cards._card(entry, focal, 4000).session_duration_ms)

    def test_duration_pending_refresh_reuses_intervals_and_correction_recomputes(self):
        snapshot = history(((1000, 1200), (1100, 1500), (2000, None)))
        with tempfile.TemporaryDirectory() as directory:
            source = MutableSource(snapshot)
            _, _, service, _ = make_service(directory, source, now_ms=3000)
            capture, item = capture_rows(service, snapshot.root)
            cards = WatchCards(None)
            entry = CardSession(snapshot.root, snapshot.source_revision, 1)
            cards.sessions["root"] = entry
            cards.accept(CardResult("root", 1, "rows", (capture, (), item.snapshot)), 3000)
            pending = replace(capture, retained=True, authoritative=False, duration_intervals=())
            cards.accept(CardResult("root", 1, "rows", (pending, (), replace(item.snapshot, complete=False))), 3100)
            self.assertEqual(1500, cards._card(entry, entry.capture.rows[-1], 4000).session_duration_ms)
            source.snapshot = replace(history(((1000, 1250), (1100, 1400), (2000, None))),
                source_revision=snapshot.source_revision)
            service.now_ms = 5000
            corrected, item = capture_rows(service, snapshot.root)
            cards.accept(CardResult("root", 1, "rows", (corrected, (), item.snapshot)), 5000)
            self.assertEqual(3400, cards._card(entry, entry.capture.rows[-1], 5000).session_duration_ms)

    def test_successful_current_capture_recovers_authority_without_completing_history(self):
        snapshot = one_request()
        with tempfile.TemporaryDirectory() as directory:
            source = MutableSource(snapshot)
            _, _, service, _ = make_service(directory, source, now_ms=3000)
            capture, item = capture_rows(service, snapshot.root)
            cards = WatchCards(None)
            entry = CardSession(snapshot.root, snapshot.source_revision, 1)
            cards.sessions["root"] = entry
            cards.accept(CardResult("root", 1, "unavailable", SourceUnavailableError("offline")), 3000)
            cards.accept(CardResult("root", 1, "rows", (replace(capture, retained=True), (), item.snapshot)), 3100)
            self.assertIsNone(entry.source_status.failed_at)
            self.assertEqual("partial", entry.state)
            self.assertTrue(cards._card(entry, entry.capture.rows[-1], 3100).invocation_verified)
            entry.generation = 2
            self.assertFalse(cards._card(entry, entry.capture.rows[-1], 3200).invocation_verified)
