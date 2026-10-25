"""Synthetic alternating-effort history: past estimates versus future anchor safety."""
from dataclasses import replace
import tempfile
import unittest

from development.tests.fixtures.pricing_catalog import catalog, threshold_catalog
from development.tests.fixtures.session_snapshots import MODEL, make_native_v2_compaction_snapshot, make_uncompacted_snapshot, message, part, prov
from development.tests.fixtures.watch_runtime import MutableSource, make_service
from src.analysis import analyze_snapshot
from src.analysis.context import ContextEpochs, estimate_event_context, estimate_next_context
from src.domain import ActiveContext, ContextBoundary, EventKind, MessageRole, ModelInvocation, NormalizedEvent, TokenUsage
from src.reports.prompts import build_prompt_block
from src.sources.opencode_v2_wire import selection_boundaries
from src.watch import WatchCoordinator


def alternating_history(count=5, *, after_switch=True, switch8_at=8900):
    """No real export: terminal totals and call counts, with invented regular growth."""
    base = make_uncompacted_snapshot()
    messages, events, requests, boundaries = [], [], [], []
    for number, calls, terminal, effort in ((5, 2, 51000, ""), (6, 1, 51481, ""),
                                           (7, 17, 99813, "max"), (8, 1, 100088, ""),
                                           (9, 5, 142934, "max"))[:count]:
        start = number * 1000
        user_id = f"u{number}"
        text = part(f"p{number}", user_id, "root", "text", {"text": "next"}, start)
        messages.append(message(user_id, "root", MessageRole.USER, start, parts=(text,)))
        events.append(NormalizedEvent(user_id, "root", EventKind.USER_PROMPT, start, prov("root", user_id), "next"))
        for call in range(calls):
            at = start + 100 + call * 20
            mid = f"a{number}_{call}"
            usage = TokenUsage(input=terminal - 100 - (calls - call - 1) * 150, output=100)
            messages.append(replace(message(mid, "root", MessageRole.ASSISTANT, at, parent=user_id,
                                            completed=at + 10, model=MODEL,
                                            finish="stop" if call == calls - 1 else "tool-calls"), tokens=usage, variant=effort))
            requests.append(ModelInvocation(mid, "root", at, MODEL, usage, prov("root", mid),
                                            completed_at_ms=at + 10, initiating_event_id=user_id,
                                            message_id=mid, variant=effort))
        if number in (6, 7, 8) and (number < 4 + count or after_switch):
            boundary_at = switch8_at if number == 8 else start + 900
            boundaries.extend(selection_boundaries(({
                "type": "model-switched", "id": f"switch{number}", "time": {"created": boundary_at},
            },), session_id="root"))
    return replace(base, sessions=(base.root,), messages=tuple(messages),
                   parts=tuple(p for m in messages for p in m.parts), events=tuple(events),
                   invocations=tuple(requests), context_boundaries=tuple(boundaries),
                   active_contexts=(ActiveContext("root", tuple(m.message_id for m in messages)),),
                   source_revision=f"alternating-{count}-{after_switch}-{switch8_at}")


def project(snapshot, prices=None):
    bundle = analyze_snapshot(snapshot, now_ms=20000)
    block = build_prompt_block(session_id="root", title="Synthetic", bundle=bundle, snapshot=snapshot,
                               catalog=prices or catalog(), config={})
    return bundle, block


class HistoricalContextTests(unittest.TestCase):
    def test_alternating_history_is_stable_at_every_stage_and_current_anchor_reestablishes(self):
        totals = (51000, 51481, 99813, 100088, 142934)
        # Comparable retained history permits exact subtraction, not screenshot rounding.
        deltas = (250, 481, 48332, 275, 42846)
        for count in range(1, 6):
            before = alternating_history(count, after_switch=False)
            after = alternating_history(count)
            for snapshot in (before, after):
                with self.subTest(count=count, after=snapshot is after):
                    bundle, block = project(snapshot)
                    self.assertEqual(totals[:count], tuple(row.next_context_tokens for row in block.rows))
                    self.assertEqual(totals[:count], tuple(row.watch_next_context_tokens for row in block.rows))
                    self.assertEqual(deltas[:count], tuple(row.delta_context_tokens for row in block.rows))
                    self.assertEqual(deltas[:count], tuple(row.watch_delta_context_tokens for row in block.rows))
                    epochs = ContextEpochs(snapshot, bundle)
                    latest = bundle.prompts[-1]
                    self.assertEqual(totals[count - 1], estimate_event_context(latest, catalog(), epochs=epochs).tokens)
                    current = estimate_next_context(latest, catalog(), epochs=epochs).tokens
                    self.assertEqual(None if snapshot is after and count in (2, 3, 4) else totals[count - 1], current)
                    self.assertEqual(current, block.next_context_tokens)
            old_bundle, new_bundle = project(before)[0], project(after)[0]
            self.assertEqual(replace(old_bundle, source_revision=new_bundle.source_revision), new_bundle,
                             "boundaries cannot change accounting or lifecycle")

    def test_retirement_asymmetry_depends_on_selected_anchor_time_not_effort_name(self):
        for switch_at, expected in ((8900, True), (8105, False)):
            snapshot = alternating_history(switch8_at=switch_at)
            bundle, block = project(snapshot)
            epochs = ContextEpochs(snapshot, bundle)
            # The old projection discarded a historical row exactly when this predicate was true.
            completions = sorted(entry.completed_at_ms for entry in bundle.trace_entries)
            retired = []
            for item in bundle.prompts:
                anchor = item.last_root_entry.completed_at_ms
                following = next((at for at in completions if at > anchor), None)
                retired.append(epochs.crossed("root", anchor, following + 1 if following is not None else None))
            self.assertEqual([False, True, True, expected, False], retired)
            self.assertEqual((51481, 99813, 100088), tuple(row.watch_next_context_tokens for row in block.rows[1:4]))

    def test_missing_history_reset_removed_history_and_missing_usage_do_not_invent_continuity(self):
        base = alternating_history()
        no_history = replace(base, active_contexts=())
        incomplete = replace(base, active_contexts=(ActiveContext("root", tuple(
            m.message_id for m in base.messages if m.message_id != "a5_0")),))
        reset = replace(base, context_boundaries=tuple(replace(b, kind="reset") for b in base.context_boundaries))
        for snapshot in (no_history, incomplete, reset):
            _, block = project(snapshot)
            self.assertEqual(99813, block.rows[2].next_context_tokens)
            self.assertEqual(2500, block.rows[2].watch_delta_context_tokens,
                             "no cross-epoch subtraction; use this prompt's own complete request baseline")
        for fields in (("input",), ("input", "output"), ("cache_read", "cache_write", "output")):
            missing = replace(base, invocations=tuple(replace(i, tokens=TokenUsage(input=i.tokens.input,
                              known_fields=fields)) if i.message_id == "a6_0" else i for i in base.invocations))
            _, block = project(missing)
            self.assertIsNone(block.rows[1].next_context_tokens)
            self.assertIsNone(block.rows[1].watch_next_context_tokens)

    def test_historical_large_context_never_revives_a_current_price_warning(self):
        snapshot = alternating_history()
        _, before = project(snapshot, threshold_catalog())
        boundary = ContextBoundary("root", "later-selection", 9900, "model-selection")
        after = replace(snapshot, context_boundaries=(*snapshot.context_boundaries, boundary))
        _, block = project(after, threshold_catalog())
        self.assertIn("exceeded", before.next_context_warning)
        self.assertEqual(142934, block.rows[-1].next_context_tokens)
        self.assertEqual(142934, block.rows[-1].watch_next_context_tokens)
        self.assertIsNone(block.next_context_tokens)
        self.assertEqual("", block.next_context_warning)
        self.assertEqual("", block.rows[-1].next_context_warning)
        self.assertEqual("", block.rows[-1].watch_next_context_warning)

    def test_watch_refresh_resync_preserves_rows_totals_and_mix(self):
        with tempfile.TemporaryDirectory() as directory:
            source = MutableSource(alternating_history(2, after_switch=False))
            config, selection, service, _ = make_service(directory, source)
            clock = [6500]
            watch = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: clock[0])
            watch.initialize()
            source.snapshot = alternating_history()
            clock[0] = 10000
            first = watch.poll_once().projection
            expected = watch.blocks["root"]
            self.assertEqual((51000, 51481, 99813, 100088, 142934),
                             tuple(row.watch_next_context_tokens for row in expected.rows))
            for cycle in (watch.poll_once(), watch.poll_once(force_resync=True), watch.poll_once()):
                self.assertEqual(expected, watch.blocks["root"])
                self.assertEqual(first.token_mix, cycle.projection.token_mix)
                self.assertEqual(first.today_total, cycle.projection.today_total)

    def test_compaction_and_undo_keep_history_but_never_revive_retired_current_context(self):
        compacted = make_native_v2_compaction_snapshot()
        before_bundle, before = project(compacted)
        moved = replace(compacted, context_boundaries=(ContextBoundary("root", "move", 4000),))
        after_bundle, after = project(moved)
        self.assertEqual([row.next_context_tokens for row in before.rows], [row.next_context_tokens for row in after.rows])
        self.assertEqual([row.watch_delta_context_tokens for row in before.rows],
                         [row.watch_delta_context_tokens for row in after.rows])
        self.assertLess(next(row for row in after.rows if row.is_compaction).delta_context_tokens, 0)
        self.assertIsNone(after.next_context_tokens)
        self.assertEqual(before_bundle, after_bundle)

        restored = alternating_history()
        undone = replace(restored, active_contexts=(ActiveContext("root", tuple(
            m.message_id for m in restored.messages if m.created_at_ms < 8000)),))
        _, undo_block = project(undone)
        _, redo_block = project(restored)
        for left, right in zip(undo_block.rows, redo_block.rows):
            self.assertEqual(left.next_context_tokens, right.next_context_tokens)
            self.assertEqual(left.calls, right.calls)
            self.assertEqual(left.ccost, right.ccost)
            self.assertEqual(left.token_mix_percent, right.token_mix_percent)
        self.assertIsNone(undo_block.rows[-1].watch_delta_context_tokens)
        self.assertIsNone(undo_block.next_context_tokens, "later boundaries still retire the restored older anchor")
        self.assertEqual(142934, redo_block.next_context_tokens)
        old_prefix = replace(restored, active_contexts=(ActiveContext("root", tuple(
            m.message_id for m in restored.messages if m.created_at_ms < 6000)),))
        _, prefix_block = project(old_prefix)
        self.assertIsNone(prefix_block.next_context_tokens,
                          "a later undone request cannot hide the later switch from an older restored anchor")


if __name__ == "__main__":
    unittest.main()
