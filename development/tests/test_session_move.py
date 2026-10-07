"""Session location moves, context epochs, Watch-run CCost total and Next Ictx labels."""
from __future__ import annotations

import io
import re
import tempfile
import unittest
from dataclasses import replace
from decimal import Decimal
from urllib.parse import parse_qs, urlsplit

from development.tests.test_analysis_core import MODEL, make_snapshot, message, part, prov
from development.tests.test_context_warning_presentation import prompt, report_projection, watch_projection
from development.tests.test_opencode_v2 import source_with_current_service
from development.tests.test_step6_context_comparisons import catalog as sample_catalog
from development.tests.test_step8_watch import MutableSource, make_service
from development.tests.test_v786_regressions import _threshold_catalog
from src.analysis import analyze_snapshot
from src.analysis.context import PriceWarningSeverity, watch_context_state
from src.domain import ContextBoundary, EventKind, MessageRole, ModelInvocation, NormalizedEvent, TokenUsage
from src.numbers import ccost_amount
from src.presentation import ReportRenderer, WatchRenderer
from src.reports.prompts import build_prompt_block
from src.watch import WatchCoordinator
from src.watch.token_mix import WatchTokenMix


def completed_history():
    snapshot = make_snapshot(running=False)
    messages = tuple(item for item in snapshot.messages if item.message_id not in {"u_comp", "a_comp"})
    return replace(snapshot, messages=messages, parts=tuple(p for m in messages for p in m.parts),
                   events=tuple(e for e in snapshot.events if e.event_id != "u_comp"),
                   invocations=tuple(i for i in snapshot.invocations if i.invocation_id != "i_comp"))


def moved(snapshot, at_ms, revision="moved"):
    """Same session ID, new location: only a non-billable boundary is added."""
    return replace(snapshot, source_revision=revision,
                   context_boundaries=(*snapshot.context_boundaries, ContextBoundary("root", f"loc_{at_ms}", at_ms)))


def with_prompt(snapshot, key, at_ms, usage=None, revision=None):
    """Append a root prompt; ``usage=None`` means it is still waiting for its first request."""
    user = message(f"u_{key}", "root", MessageRole.USER, at_ms,
                   parts=(part(f"p_{key}", f"u_{key}", "root", "text", {"text": "after move", "synthetic": False}, at_ms),))
    messages = [*snapshot.messages, user]
    invocations = list(snapshot.invocations)
    if usage is None:
        messages.append(message(f"a_{key}", "root", MessageRole.ASSISTANT, at_ms + 100, parent=user.message_id, model=MODEL))
    else:
        assistant = replace(message(f"a_{key}", "root", MessageRole.ASSISTANT, at_ms + 100, parent=user.message_id,
                                    completed=at_ms + 300, model=MODEL, finish="stop"), tokens=usage)
        messages.append(assistant)
        invocations.append(ModelInvocation(f"i_{key}", "root", at_ms + 100, MODEL, usage, prov("root", f"i_{key}"),
                                           completed_at_ms=at_ms + 300, initiating_event_id=user.message_id,
                                           message_id=assistant.message_id))
    event = NormalizedEvent(user.message_id, "root", EventKind.USER_PROMPT, at_ms, prov("root", user.message_id), "after move",
                            metadata={"provider_id": MODEL.provider, "model_id": MODEL.model})
    return replace(snapshot, messages=tuple(messages), parts=tuple(p for m in messages for p in m.parts),
                   events=(*snapshot.events, event), invocations=tuple(invocations),
                   source_revision=revision or snapshot.source_revision + "+" + key)


def block_for(snapshot, catalog=None):
    return build_prompt_block(session_id="root", title="Root", bundle=analyze_snapshot(snapshot, now_ms=9000),
                              snapshot=snapshot, catalog=catalog or sample_catalog(),
                              config={"thresholds": {"nextIctxPriceThresholdWarningPercent": 75}})


def row(block, event_id):
    return next(item for item in block.rows if item.event_id == event_id)


class ContextEpochTests(unittest.TestCase):
    def test_move_invalidates_old_baseline_estimate_and_warning(self):
        history = completed_history()
        large = replace(history, invocations=tuple(replace(i, tokens=TokenUsage(input=80_000, output=5))
                                                   if i.invocation_id == "i_next" else i for i in history.invocations))
        before = block_for(large, _threshold_catalog())
        self.assertEqual(80_005, before.next_context_tokens)
        self.assertEqual(PriceWarningSeverity.APPROACHING, before.next_context_warning_severity)
        after = block_for(moved(large, 2500), _threshold_catalog())
        self.assertIsNone(after.next_context_tokens)
        self.assertEqual("", after.next_context_warning)
        stale = row(after, "u_next")
        self.assertEqual((None, None, ""), (stale.next_context_tokens, stale.watch_next_context_tokens,
                                            stale.watch_next_context_warning))
        historical = row(after, "u_sub")
        self.assertIsNotNone(historical.next_context_tokens, "an anchor already followed by a same-epoch request stays")
        self.assertEqual(row(before, "u_sub").next_context_tokens, historical.next_context_tokens)
        self.assertEqual(row(before, "u_sub").delta_context_tokens, historical.delta_context_tokens)
        self.assertEqual(before.total_ccost, after.total_ccost, "the boundary itself is not billable")
        self.assertEqual(before.total_calls, after.total_calls)

    def test_waits_for_first_real_request_then_new_baseline_resumes(self):
        history = completed_history()
        waiting = with_prompt(history, "after", 3000)
        provisional = row(block_for(waiting), "u_after")
        self.assertIsNotNone(provisional.watch_next_context_tokens, "without a move the old baseline is reused")
        waiting_moved = row(block_for(with_prompt(moved(history, 2500), "after", 3000)), "u_after")
        self.assertIsNone(waiting_moved.watch_next_context_tokens, "no estimate from the retired epoch")

        usage = TokenUsage(input=50, output=5)
        unmoved = row(block_for(with_prompt(history, "after", 3000, usage)), "u_after")
        self.assertEqual((55, 21), (unmoved.watch_next_context_tokens, unmoved.watch_delta_context_tokens))
        snapshot = with_prompt(moved(history, 2500), "after", 3000, usage)
        block = block_for(snapshot)
        resumed = row(block, "u_after")
        self.assertEqual(55, resumed.watch_next_context_tokens)
        self.assertEqual(5, resumed.watch_delta_context_tokens, "delta is measured from the new epoch's first request")
        self.assertEqual(5, resumed.delta_context_tokens)
        self.assertEqual(55, block.next_context_tokens)
        self.assertIsNotNone(block.next_context_cached_ccost)

    def test_running_prompt_spanning_the_move_drops_mixed_epoch_delta(self):
        history = completed_history()
        snapshot = with_prompt(history, "span", 2400, TokenUsage(input=50, output=5))
        snapshot = moved(snapshot, 2600)  # its only request completed at 2700, after the move
        bundle = analyze_snapshot(snapshot, now_ms=9000)
        record = next(item for item in bundle.prompts if item.prompt_id == "u_span")
        state = watch_context_state(snapshot, bundle, record, sample_catalog())
        self.assertEqual(55, state.next_tokens)
        self.assertEqual(5, state.delta_tokens)
        stale = moved(with_prompt(history, "span", 2400, TokenUsage(input=50, output=5)), 2800)
        bundle = analyze_snapshot(stale, now_ms=9000)
        record = next(item for item in bundle.prompts if item.prompt_id == "u_span")
        self.assertIsNone(watch_context_state(stale, bundle, record, sample_catalog()).next_tokens)


class WatchTotalAndMoveTests(unittest.TestCase):
    def test_watch_total_starts_at_zero_counts_new_ccost_once_across_rescans_and_moves(self):
        with tempfile.TemporaryDirectory() as td:
            source = MutableSource(completed_history())
            config, selection, service, _ = make_service(td, source)
            clock = [4000]
            watch = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: clock[0])
            initial = watch.initialize().projection
            self.assertEqual(0, initial.token_mix.request_count, "pre-Watch history is excluded")
            self.assertIn("Watch total CCost: 0", self.rendered(initial))

            usage = TokenUsage(input=50, output=5)
            source.snapshot = with_prompt(source.snapshot, "new", 4100, usage)
            clock[0] = 4500
            first = watch.poll_once().projection
            expected = "Watch total CCost: " + ccost_amount(
                service._load_comparison_catalog().reference_valuation(MODEL, usage))
            lines = self.rendered(first).splitlines()
            mix = next(index for index, line in enumerate(lines) if line.startswith("Token Mix %"))
            self.assertEqual(expected, lines[mix + 1], "dedicated row directly below Token Mix")

            source.snapshot = moved(source.snapshot, 4600, "moved-to-worktree")
            clock[0] = 4700
            for cycle in (watch.poll_once(), watch.poll_once(force_resync=True), watch.poll_once()):
                self.assertEqual(first.token_mix, cycle.projection.token_mix, "rehydration/move never re-adds usage")
            self.assertEqual(["root"], list(watch.blocks), "same logical session after the move")
            self.assertEqual(1, sum(item.prompt.event_id == "u_new" for item in watch._last_projection.rows))
            self.assertIn(expected, self.rendered(watch._last_projection))

            restarted = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: 4800)
            self.assertIn("Watch total CCost: 0", self.rendered(restarted.initialize().projection))

    def header_cost(self, projection):
        return next(line for line in self.rendered(projection).splitlines() if "Σ" in line)

    def test_session_header_subtotal_follows_rows_without_double_count_across_moves(self):
        with tempfile.TemporaryDirectory() as td:
            source = MutableSource(completed_history())
            config, selection, service, _ = make_service(td, source)
            clock = [4000]
            watch = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: clock[0])
            initial = watch.initialize().projection
            self.assertEqual({}, dict(initial.session_subtotals), "no selected rows in global Watch yet")

            usage = TokenUsage(input=50, output=5)
            source.snapshot = with_prompt(source.snapshot, "new", 4100, usage)
            clock[0] = 4500
            first = watch.poll_once().projection
            amount = ccost_amount(service._load_comparison_catalog().reference_valuation(MODEL, usage))
            self.assertRegex(self.header_cost(first), rf"\| +Σ {re.escape(amount)} \|")
            self.assertIn("Watch total CCost: " + amount, self.rendered(first))
            self.assertEqual(sum((row.prompt.ccost for row in first.rows), Decimal(0)),
                             first.session_subtotals["root"].ccost)

            source.snapshot = moved(source.snapshot, 4600, "moved-to-worktree")
            clock[0] = 4700
            for cycle in (watch.poll_once(), watch.poll_once(force_resync=True), watch.poll_once()):
                self.assertEqual(first.session_subtotals, cycle.projection.session_subtotals)
                self.assertEqual(first.token_mix, cycle.projection.token_mix)
            self.assertEqual(1, self.rendered(watch._last_projection).count("Σ"), "one subtotal after the move")
            self.assertRegex(self.header_cost(watch._last_projection), rf"\| +Σ {re.escape(amount)} \|")

    def test_run_total_counts_requests_once_across_roots_and_repeated_hydration(self):
        usages = {"a": TokenUsage(input=50, output=5), "b": TokenUsage(input=400, output=40), "c": TokenUsage(input=7, output=1)}
        with tempfile.TemporaryDirectory() as td:
            _config, _selection, service, _ = make_service(td, MutableSource(completed_history()))
            valuation = service.token_category_valuation()
        tracker = WatchTokenMix(4000)
        base = completed_history()
        expected = Decimal(0)
        for root, key, at in (("alpha", "a", 4100), ("beta", "b", 4200), ("alpha", "c", 4300)):
            snapshot = with_prompt(base, key, at, usages[key])
            session = replace(snapshot.root, session_id=root)
            messages = tuple(replace(item, session_id=root) for item in snapshot.messages
                             if item.message_id in {f"u_{key}", f"a_{key}"})
            snapshot = replace(snapshot, root=session, sessions=(session,), messages=messages,
                               parts=tuple(part for item in messages for part in item.parts),
                               events=tuple(replace(item, session_id=root) for item in snapshot.events
                                            if item.event_id == f"u_{key}"),
                               invocations=tuple(replace(item, session_id=root) for item in snapshot.invocations
                                                 if item.invocation_id == f"i_{key}"))
            for _ in range(2):
                tracker.observe(snapshot, analyze_snapshot(snapshot, now_ms=9000))
            expected += service._load_comparison_catalog().reference_valuation(MODEL, usages[key])
        total = tracker.project(valuation)
        self.assertEqual(3, total.request_count)
        self.assertEqual(3, total.sample_size)
        self.assertEqual(expected, sum(total.costs))
        self.assertEqual(tuple(sum(getattr(usage, field) for usage in usages.values())
                               for field in ("input", "cache_read", "cache_write", "output")), total.totals)


    @staticmethod
    def rendered(projection):
        stream = io.StringIO()
        WatchRenderer({"timezone": "UTC"}, stream=stream, interactive=False, terminal_width=200).render(projection)
        return stream.getvalue()

    def test_v2_moved_session_keeps_identity_and_usage_and_follows_session_route(self):
        with source_with_current_service() as (source, service, _):
            before = source.load_session_snapshot("ses_current")
            revision = source.get_session_tree_revision("ses_current")
            service.sessions[0] = {**service.sessions[0], "location": {"directory": "/private/worktree"}}
            service.messages["ses_current"].append({
                "id": "msg_moved", "type": "location-switched", "location": {"directory": "/private/worktree"},
                "previous": {"directory": "/private/repo"}, "time": {"created": 5000},
            })
            source.list_sessions()
            self.assertNotEqual(revision, source.get_session_tree_revision("ses_current"), "a move triggers rehydration")
            after = source.load_session_snapshot("ses_current")
            self.assertEqual(before.root.session_id, after.root.session_id)
            self.assertEqual([s.session_id for s in before.sessions], [s.session_id for s in after.sessions])
            self.assertEqual(before.invocations, after.invocations, "historical usage is not duplicated")
            self.assertEqual(before.events, after.events)
            self.assertEqual(len(before.messages), len(after.messages))
            self.assertEqual((ContextBoundary("ses_current", "msg_moved", 5000),), after.context_boundaries)
            self.assertNotIn("/private/", repr(after.context_boundaries))
            message_queries = [parse_qs(urlsplit(path).query) for path, _ in service.requests
                               if urlsplit(path).path.endswith("/message")]
            self.assertTrue(message_queries)
            self.assertFalse(any("directory" in query for query in message_queries), "session-ID route, not location")
            tracker = WatchTokenMix(0)
            for snapshot in (before, after, before, after):
                tracker.observe(snapshot, analyze_snapshot(snapshot, now_ms=9000))
            self.assertEqual(1, tracker.project().request_count)


class NextIctxLabelTests(unittest.TestCase):
    def test_watch_and_report_label_the_range_as_next_ictx_ccost(self):
        item = replace(prompt(PriceWarningSeverity.APPROACHING, "[Approaching price threshold >272.0K]"),
                       watch_next_context_cached_ccost=Decimal("0.3"), watch_next_context_fresh_ccost=Decimal("3"))
        stream = io.StringIO()
        WatchRenderer({"timezone": "UTC"}, stream=stream, interactive=False).render(watch_projection(item))
        self.assertIn("*1 Next Ictx: Approaching price threshold >272.0K (Next Ictx CCost 0.3–3)", stream.getvalue())
        projection = report_projection(item)
        block = replace(projection.prompt_blocks[0], next_context_cached_ccost=Decimal("0.3"),
                        next_context_fresh_ccost=Decimal("3"))
        stream = io.StringIO()
        ReportRenderer({"timezone": "UTC"}, stream=stream, color_enabled=False, terminal_width=160).render(
            replace(projection, prompt_blocks=(block,)))
        self.assertIn("(Next Ictx CCost 0.3–3)", stream.getvalue())
        self.assertNotIn("(0.3", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
