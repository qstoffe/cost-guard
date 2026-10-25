from __future__ import annotations

import unittest
from dataclasses import replace
from decimal import Decimal

from development.tests.fixtures.session_snapshots import (
    MODEL, make_native_v2_compaction_snapshot, make_snapshot, make_uncompacted_snapshot, message, part, prov,
)
from development.tests.fixtures.pricing_catalog import catalog
from src.analysis.comparisons import (
    model_comparison_rows, model_timeline_name,
)
from src.analysis.context import (
    ContextEpochs, build_context_timeline, context_composition, estimate_next_context, watch_context_state,
    input_context_above_price_threshold, next_context_warning_state,
)
from src.analysis.core import analyze_snapshot
from src.domain import (
    ActiveContext, ContextBoundary, EventKind, MessageRole, ModelInvocation, ModelPricing, ModelRef,
    NormalizedEvent, PricingTier, TokenUsage,
)
from src.pricing.catalog import PricingCatalog
from src.reports.models import PromptProjection
from src.reports.prompts import build_prompt_block
from src.reports.prompts import _coherent_watch_deltas


class ContextEngineTests(unittest.TestCase):
    @staticmethod
    def replacement_snapshot(requests, *, active_context=True):
        snapshot = make_uncompacted_snapshot()
        invocations = []
        messages = list(snapshot.messages)
        for index, (input_tokens, output_tokens) in enumerate(requests, start=1):
            if index == 1:
                invocations.append(replace(
                    next(item for item in snapshot.invocations if item.invocation_id == "i_next"),
                    tokens=TokenUsage(input=input_tokens, output=output_tokens),
                ))
                continue
            started = 2300 + index * 100
            completed = started + 100
            message_id = f"a_follow_{index}"
            messages.append(message(message_id, "root", role=MessageRole.ASSISTANT, created=started,
                                  parent="u_next", completed=completed,
                                  model=MODEL, finish="stop"))
            invocations.append(ModelInvocation(
                f"i_follow_{index}", "root", started, MODEL,
                TokenUsage(input=input_tokens, output=output_tokens), prov("root", f"i_follow_{index}"),
                completed_at_ms=completed, initiating_event_id="u_next", message_id=message_id,
            ))
        replaced_invocations = tuple(
            item for item in snapshot.invocations if item.invocation_id != "i_next"
        ) + tuple(invocations)
        active_contexts = (ActiveContext("root", tuple(item.message_id for item in messages)),) if active_context else ()
        return replace(snapshot, messages=tuple(messages), invocations=replaced_invocations,
                       parts=tuple(part for item in messages for part in item.parts),
                       active_contexts=active_contexts)

    def test_next_ictx_cost_range_is_cache_agnostic_and_stable(self) -> None:
        bundle = analyze_snapshot(make_snapshot(), now_ms=4000)
        record = next(item for item in bundle.prompts if item.prompt_id == "u_next")
        estimate = estimate_next_context(record, catalog())
        self.assertEqual(34, estimate.tokens)
        self.assertLess(estimate.cached_ccost, estimate.fresh_ccost)

    def test_next_ictx_warning_state_matches_price_threshold_semantics(self) -> None:
        base = PricingTier(max_input_tokens=100_000, per_million_input=Decimal("1"), per_million_cache_read=Decimal("0.1"), per_million_output=Decimal("4"))
        long = PricingTier(min_input_tokens=100_001, per_million_input=Decimal("2"), per_million_cache_read=Decimal("0.2"), per_million_output=Decimal("8"))
        priced = ModelPricing(ModelRef("github-copilot", "gpt-5.6", "GPT-5.6"), "USD", tiers=(base, long), metadata={"publisher":"OpenAI"})
        prices = PricingCatalog((priced,))
        approaching = next_context_warning_state(
            tokens=80_000, model_id="gpt-5.6", catalog=prices, price_approach_percent=75,
        )
        self.assertTrue(approaching.price_approaching)
        self.assertFalse(approaching.hard_warning)
        self.assertIn("Approaching price threshold", approaching.text)
        crossed = next_context_warning_state(
            tokens=100_001, model_id="gpt-5.6", catalog=prices, price_approach_percent=75,
        )
        self.assertTrue(crossed.price_exceeded)
        self.assertTrue(crossed.hard_warning)
        self.assertTrue(input_context_above_price_threshold(100_001, "gpt-5.6", prices))
        self.assertIn(">100.0K", crossed.text)

    def test_context_composition_scales_sources_to_actual_request_ictx(self) -> None:
        snapshot = make_snapshot(); bundle = analyze_snapshot(snapshot, now_ms=4000)
        record = next(item for item in bundle.prompts if item.prompt_id == "u_next")
        composition = context_composition(snapshot, record)
        self.assertTrue(composition.complete)
        self.assertEqual(record.last_root_entry.request_input_approx, composition.target_tokens)
        self.assertEqual(composition.target_tokens, sum(item.tokens for item in composition.sources))
        self.assertTrue(composition.category_totals)

    def test_temporary_request_uses_active_history_for_next_context_not_usage_accounting(self) -> None:
        snapshot = self.replacement_snapshot(((5, 4),))
        bundle = analyze_snapshot(snapshot, now_ms=5000)
        record = next(item for item in bundle.prompts if item.prompt_id == "u_next")
        estimate = estimate_next_context(record, catalog(), epochs=ContextEpochs(snapshot, bundle))

        self.assertEqual(18, estimate.tokens)
        self.assertEqual(1, record.model_calls)
        self.assertEqual((5, 4), (record.input_tokens, record.output_tokens))

        no_active_history = replace(snapshot, active_contexts=())
        unknown_bundle = analyze_snapshot(no_active_history, now_ms=5000)
        unknown_record = next(item for item in unknown_bundle.prompts if item.prompt_id == "u_next")
        unknown = estimate_next_context(unknown_record, catalog(), epochs=ContextEpochs(no_active_history, unknown_bundle))
        self.assertIsNone(unknown.tokens, "an unproven request-local decrease remains explicitly unknown")
        self.assertEqual(record.cost, unknown_record.cost)
        self.assertEqual(record.model_calls, unknown_record.model_calls)
        self.assertEqual(record.total_token_volume, unknown_record.total_token_volume)
        active_block = build_prompt_block(session_id="root", title="Root", bundle=bundle, snapshot=snapshot,
                                          catalog=catalog(), config={})
        unknown_block = build_prompt_block(session_id="root", title="Root", bundle=unknown_bundle,
                                           snapshot=no_active_history, catalog=catalog(), config={})
        active_row = next(row for row in active_block.rows if row.event_id == "u_next")
        unknown_row = next(row for row in unknown_block.rows if row.event_id == "u_next")
        self.assertEqual(18, active_row.next_context_tokens)
        self.assertEqual(18, active_row.watch_next_context_tokens)
        self.assertIsNone(unknown_row.next_context_tokens)
        self.assertIsNone(unknown_row.watch_next_context_tokens)
        self.assertEqual(active_row.ccost, unknown_row.ccost)
        self.assertEqual(active_row.calls, unknown_row.calls)
        self.assertEqual(active_block.total_mix_text, unknown_block.total_mix_text)

    def test_multiple_temporary_requests_reanchor_when_normal_request_returns(self) -> None:
        snapshot = self.replacement_snapshot(((5, 4), (2, 1), (19, 2)))
        bundle = analyze_snapshot(snapshot, now_ms=5000)
        record = next(item for item in bundle.prompts if item.prompt_id == "u_next")
        estimate = estimate_next_context(record, catalog(), epochs=ContextEpochs(snapshot, bundle))

        self.assertEqual(21, estimate.tokens)
        self.assertEqual(3, record.model_calls)
        self.assertEqual((26, 7), (record.input_tokens, record.output_tokens))

    def test_12_and_7_request_histories_keep_tiny_final_requests_accounted(self) -> None:
        for count in (12, 7):
            regular_inputs = tuple((13 + index, 1) for index in range(1, count))
            requests = (*regular_inputs, (1, 1))
            with self.subTest(requests=count):
                snapshot = self.replacement_snapshot(requests)
                bundle = analyze_snapshot(snapshot, now_ms=10000)
                record = next(item for item in bundle.prompts if item.prompt_id == "u_next")
                estimate = estimate_next_context(record, catalog(), epochs=ContextEpochs(snapshot, bundle))

                self.assertEqual(count, record.model_calls)
                self.assertEqual(1, record.last_root_entry.request_input_approx)
                self.assertEqual(1, record.input_tokens - sum(value for value, _ in regular_inputs))
                self.assertEqual(count, record.output_tokens)
                self.assertEqual(14 + count, estimate.tokens)

    def test_model_switch_and_missing_usage_do_not_borrow_an_incompatible_anchor(self) -> None:
        switched = self.replacement_snapshot(((5, 4),))
        alternate = ModelRef("github-copilot", "other-model")
        switched = replace(
            switched,
            invocations=tuple(replace(item, model=alternate) if item.invocation_id == "i_next" else item
                              for item in switched.invocations),
            messages=tuple(replace(item, model=alternate) if item.message_id == "a_next" else item
                           for item in switched.messages),
        )
        switched_bundle = analyze_snapshot(switched, now_ms=5000)
        switched_record = next(item for item in switched_bundle.prompts if item.prompt_id == "u_next")
        switched_estimate = estimate_next_context(
            switched_record, catalog(), epochs=ContextEpochs(switched, switched_bundle),
        )
        self.assertEqual(9, switched_estimate.tokens)

        missing = self.replacement_snapshot(((0, 4),))
        missing_bundle = analyze_snapshot(missing, now_ms=5000)
        missing_record = next(item for item in missing_bundle.prompts if item.prompt_id == "u_next")
        missing_estimate = estimate_next_context(missing_record, catalog(), epochs=ContextEpochs(missing, missing_bundle))
        self.assertIsNone(missing_estimate.tokens)

        missing_output = self.replacement_snapshot(((5, 4),))
        missing_output = replace(missing_output, invocations=tuple(
            replace(item, tokens=TokenUsage(input=5, known_fields=("input",)))
            if item.invocation_id == "i_next" else item for item in missing_output.invocations
        ))
        output_bundle = analyze_snapshot(missing_output, now_ms=5000)
        output_record = next(item for item in output_bundle.prompts if item.prompt_id == "u_next")
        output_estimate = estimate_next_context(
            output_record, catalog(), epochs=ContextEpochs(missing_output, output_bundle),
        )
        self.assertIsNone(output_estimate.tokens, "missing output context is not treated as zero growth")

    def test_native_agent_selection_boundary_reanchors_same_model_history(self) -> None:
        snapshot = self.replacement_snapshot(((5, 4),))
        snapshot = replace(snapshot, context_boundaries=(ContextBoundary("root", "agent-change", 2050),))
        bundle = analyze_snapshot(snapshot, now_ms=5000)
        record = next(item for item in bundle.prompts if item.prompt_id == "u_next")
        estimate = estimate_next_context(record, catalog(), epochs=ContextEpochs(snapshot, bundle))

        self.assertEqual(9, estimate.tokens)

    def test_aborted_temporary_request_keeps_supported_continuing_context_in_watch(self) -> None:
        snapshot = self.replacement_snapshot(((5, 4),))
        bundle = analyze_snapshot(snapshot, now_ms=5000)
        record = next(item for item in bundle.prompts if item.prompt_id == "u_next")
        epochs = ContextEpochs(snapshot, bundle)
        for terminal in (replace(record, aborted=True), replace(record, in_progress=True)):
            with self.subTest(aborted=terminal.aborted, in_progress=terminal.in_progress):
                state = watch_context_state(snapshot, bundle, terminal, catalog(), epochs)
                self.assertEqual(18, state.next_tokens)

    def test_undo_and_redo_select_active_context_without_dropping_historical_usage(self) -> None:
        snapshot = make_uncompacted_snapshot()
        prefix_ids = ("u_sub", "a_sub", "u_syn", "a_syn")
        reverted = replace(snapshot, active_contexts=(ActiveContext("root", prefix_ids),))
        bundle = analyze_snapshot(reverted, now_ms=5000)
        block = build_prompt_block(session_id="root", title="Root", bundle=bundle, snapshot=reverted,
                                  catalog=catalog(), config={})

        self.assertEqual(13, block.next_context_tokens)
        self.assertEqual(sum(item.model_calls for item in bundle.prompts), block.total_calls)
        undone_row = next(row for row in block.rows if row.event_id == "u_next")
        self.assertEqual(1, undone_row.calls, "reverted model requests remain visible and accounted")

        restored = replace(snapshot, active_contexts=(ActiveContext(
            "root", tuple(item.message_id for item in snapshot.messages if item.session_id == "root"),
        ),))
        restored_bundle = analyze_snapshot(restored, now_ms=5000)
        restored_block = build_prompt_block(session_id="root", title="Root", bundle=restored_bundle,
                                            snapshot=restored, catalog=catalog(), config={})
        self.assertEqual(34, restored_block.next_context_tokens)
        self.assertEqual(block.total_calls, restored_block.total_calls)

    def test_prompt_after_history_revert_starts_from_its_own_incoming_context(self) -> None:
        snapshot = make_uncompacted_snapshot()
        user_part = part("p_after", "u_after", "root", "text", {"text": "again"}, 4000)
        user = message("u_after", "root", MessageRole.USER, 4000, parts=(user_part,))
        assistant = message("a_after", "root", MessageRole.ASSISTANT, 4100, parent="u_after",
                            completed=4300, model=MODEL, finish="stop")
        event = NormalizedEvent("u_after", "root", EventKind.USER_PROMPT, 4000, prov("root", "u_after"), "again")
        invocation = ModelInvocation(
            "i_after", "root", 4100, MODEL, TokenUsage(input=14, output=4), prov("root", "i_after"),
            completed_at_ms=4300, initiating_event_id="u_after", message_id="a_after",
        )
        messages = (*snapshot.messages, user, assistant)
        active_ids = tuple(item.message_id for item in messages
                           if item.session_id == "root" and item.message_id not in {"u_next", "a_next"})
        reverted_then_prompted = replace(
            snapshot, messages=messages, parts=(*snapshot.parts, user_part),
            events=(*snapshot.events, event), invocations=(*snapshot.invocations, invocation),
            active_contexts=(ActiveContext("root", active_ids),),
        )
        bundle = analyze_snapshot(reverted_then_prompted, now_ms=5000)
        state = next(item for item in build_context_timeline(reverted_then_prompted, bundle, catalog())
                     if item.event_id == "u_after")

        self.assertEqual(18, state.next_tokens)
        self.assertEqual(4, state.delta_tokens, "the undo reduction is not charged to the new prompt")

    def test_reverted_history_before_compaction_keeps_compaction_as_the_shrink_event(self) -> None:
        snapshot = make_native_v2_compaction_snapshot()
        reverted_before_compaction = replace(
            snapshot, active_contexts=(ActiveContext("root", ("u_comp", "u_next", "a_next")),),
        )
        bundle = analyze_snapshot(reverted_before_compaction, now_ms=5000)
        states = build_context_timeline(reverted_before_compaction, bundle, catalog())
        compact = next(item for item in states if item.event_id == "u_comp")
        following = next(item for item in states if item.event_id == "u_next")

        self.assertLess(compact.delta_tokens, 0)
        self.assertGreater(following.delta_tokens, 0)

    def test_temporary_request_after_compaction_uses_the_compacted_context_baseline(self) -> None:
        snapshot = make_native_v2_compaction_snapshot()
        messages = []
        for item in snapshot.messages:
            if item.message_id == "u_comp":
                compact_part = replace(item.parts[0], data={
                    "auto": True, "summary": "x" * 4_000, "recent": None,
                    "model": {"providerID": MODEL.provider, "id": MODEL.model},
                })
                item = replace(item, model=MODEL, parts=(compact_part,))
            messages.append(item)
        invocations = tuple(
            replace(item, tokens=TokenUsage(input=5, output=4)) if item.invocation_id == "i_next" else item
            for item in snapshot.invocations
        )
        snapshot = replace(snapshot, messages=tuple(messages),
                           parts=tuple(part for item in messages for part in item.parts),
                           invocations=invocations,
                           active_contexts=(ActiveContext("root", ("u_comp", "u_next", "a_next")),))
        bundle = analyze_snapshot(snapshot, now_ms=5000)
        record = next(item for item in bundle.prompts if item.prompt_id == "u_next")
        estimate = estimate_next_context(record, catalog(), epochs=ContextEpochs(snapshot, bundle))

        self.assertEqual(1006, estimate.tokens)

    def test_temporary_request_before_compaction_does_not_hide_compaction_shrink(self) -> None:
        snapshot = make_snapshot()
        summary_part = part("sum-text", "a_comp", "root", "text", {"text": "summary"}, 3200)
        messages = tuple(
            replace(item, parts=(summary_part,)) if item.message_id == "a_comp" else item
            for item in snapshot.messages
        )
        snapshot = replace(
            snapshot, messages=messages, parts=tuple(part for item in messages for part in item.parts),
            invocations=tuple(
                replace(item, tokens=TokenUsage(input=5, output=4)) if item.invocation_id == "i_next" else item
                for item in snapshot.invocations
            ),
            active_contexts=(ActiveContext("root", tuple(item.message_id for item in messages
                                                            if item.session_id == "root")),),
        )
        bundle = analyze_snapshot(snapshot, now_ms=5000)
        record = next(item for item in bundle.prompts if item.prompt_id == "u_next")
        estimate = estimate_next_context(record, catalog(), epochs=ContextEpochs(snapshot, bundle))
        compact = next(item for item in build_context_timeline(snapshot, bundle, catalog())
                       if item.event_kind == "compaction")

        self.assertEqual(18, estimate.tokens)
        self.assertLess(compact.delta_tokens, 0)

    def test_separate_child_context_cannot_replace_its_parent_session_anchor(self) -> None:
        snapshot = make_uncompacted_snapshot()
        root_ids = tuple(item.message_id for item in snapshot.messages if item.session_id == "root")
        child_ids = tuple(item.message_id for item in snapshot.messages if item.session_id == "child")
        scoped = replace(snapshot, active_contexts=(ActiveContext("root", root_ids),
                                                     ActiveContext("child", child_ids)))
        large_child = replace(scoped, invocations=tuple(
            replace(item, tokens=TokenUsage(input=999_000, output=500))
            if item.invocation_id == "i_child" else item for item in scoped.invocations
        ))
        scoped_bundle = analyze_snapshot(scoped, now_ms=5000)
        large_bundle = analyze_snapshot(large_child, now_ms=5000)
        scoped_record = next(item for item in scoped_bundle.prompts if item.prompt_id == "u_next")
        large_record = next(item for item in large_bundle.prompts if item.prompt_id == "u_next")

        self.assertEqual(estimate_next_context(scoped_record, catalog(), epochs=ContextEpochs(scoped, scoped_bundle)).tokens,
                         estimate_next_context(large_record, catalog(), epochs=ContextEpochs(large_child, large_bundle)).tokens)

    def test_compaction_timeline_uses_post_compaction_summary_not_incoming_request(self) -> None:
        snapshot = make_snapshot()
        summary_part = part("sum-text", "a_comp", "root", "text", {"text":"compact summary"}, 3200)
        messages = tuple(
            replace(item, parts=(summary_part,)) if item.message_id == "a_comp" else item
            for item in snapshot.messages
        )
        snapshot = replace(snapshot, messages=messages, parts=tuple(p for m in messages for p in m.parts))
        bundle = analyze_snapshot(snapshot, now_ms=4000)
        states = build_context_timeline(snapshot, bundle, catalog())
        compact = next(state for state in states if state.event_kind == "compaction")
        self.assertEqual(45, compact.incoming_tokens)
        self.assertEqual(4, compact.next_tokens)
        self.assertNotEqual(compact.incoming_tokens, compact.next_tokens)
        self.assertLess(compact.delta_tokens, 0)



class WatchContextDeltaRegressionTests(unittest.TestCase):
    """The displayed delta must reconcile with adjacent Next Ictx anchors."""

    @staticmethod
    def row(number: int, at: int, next_tokens: int | None, delta: int | None = None,
            *, compact: bool = False, event_id: str | None = None) -> PromptProjection:
        return PromptProjection(
            at_ms=at, prompt_number=number, event_id=event_id or f"event-{number}",
            label="/compact" if compact else "prompt", preview="", model_effort="GPT-6 Luna",
            ccost=Decimal("3"), cost_estimated=False, unresolved_cost=False, calls=2,
            incoming_context_tokens=None, incoming_context_ccost=None, extra_ccost=None,
            token_mix_percent=None, is_compaction=compact,
            delta_context_tokens=delta, next_context_tokens=next_tokens,
            watch_delta_context_tokens=delta, watch_next_context_tokens=next_tokens,
        )

    @staticmethod
    def aligned(rows, *, crossed=(), subtasks=frozenset()):
        by_id = {row.event_id: row for row in rows}
        class Epochs:
            def comparable_events(self, previous_id, current_id):
                start, end = by_id[previous_id].at_ms, by_id[current_id].at_ms + 1
                return not any(start <= boundary < end for boundary in crossed)
        return _coherent_watch_deltas(
            list(rows), epochs=Epochs(), session_id="root", subtask_ids=subtasks,
        )

    def test_24k_to_220k_is_plus_196k_not_internal_59k(self):
        rows = (self.row(1, 1000, 24_000, 16_000),
                self.row(2, 2000, 220_000, 59_000),
                self.row(3, 3000, 231_000, 11_000))
        fixed = self.aligned(rows)
        self.assertEqual([16_000, 196_000, 11_000],
                         [row.watch_delta_context_tokens for row in fixed])
        self.assertEqual([24_000, 220_000, 231_000],
                         [row.watch_next_context_tokens for row in fixed])
        self.assertEqual([16_000, 59_000, 11_000],
                         [row.delta_context_tokens for row in fixed],
                         "ordinary-report context fields must not change")
        self.assertEqual([Decimal("3")] * 3, [row.ccost for row in fixed])

    def test_unexplained_shrink_is_unknown_and_next_prompt_reanchors(self):
        rows = (self.row(7, 1000, 52_000, 1_000),
                self.row(8, 2000, 36_000, -16_000),
                self.row(9, 3000, 45_000, 9_000))
        fixed = self.aligned(rows)
        self.assertEqual([1_000, None, 9_000],
                         [item.watch_delta_context_tokens for item in fixed])
        self.assertEqual([52_000, 36_000, 45_000],
                         [item.watch_next_context_tokens for item in fixed])
        self.assertEqual(-16_000, fixed[1].delta_context_tokens,
                         "historical report delta must remain unchanged")
        self.assertEqual([Decimal("3")] * 3, [item.ccost for item in fixed])

    def test_first_event_unexplained_negative_is_unknown(self):
        fixed = self.aligned((
            self.row(8, 2000, 36_000, -16_000),
            self.row(9, 3000, 45_000, 9_000),
        ))
        self.assertEqual([None, 9_000],
                         [item.watch_delta_context_tokens for item in fixed])

    def test_zero_and_positive_deltas_remain(self):
        fixed = self.aligned((
            self.row(1, 1000, 52_000, 1_000),
            self.row(2, 2000, 52_000, 0),
            self.row(3, 3000, 54_000, 2_000),
        ))
        self.assertEqual([1_000, 0, 2_000],
                         [item.watch_delta_context_tokens for item in fixed])

    def test_compaction_checkpoint_becomes_the_next_comparable_baseline(self):
        rows = (self.row(1, 1000, 220_000, 100_000),
                self.row(2, 1500, 12_000, -208_000, compact=True),
                self.row(3, 2000, 17_000, 1_000))
        fixed = self.aligned(rows)
        self.assertEqual([100_000, -208_000, 5_000],
                         [row.watch_delta_context_tokens for row in fixed])

    def test_missing_compaction_result_suppresses_unprovable_delta(self):
        rows = (self.row(1, 1000, 220_000, 100_000),
                self.row(2, 1500, None, None, compact=True),
                self.row(3, 2000, 17_000, 1_000))
        self.assertIsNone(self.aligned(rows)[-1].watch_delta_context_tokens)

    def test_location_move_never_compares_across_epochs_and_keeps_new_epoch_estimate(self):
        rows = (self.row(1, 1000, 24_000, 16_000),
                self.row(2, 2000, 220_000, 59_000),
                self.row(3, 3000, 231_000, 11_000))
        fixed = self.aligned(rows, crossed=(1600,))
        self.assertEqual([16_000, 59_000, 11_000],
                         [row.watch_delta_context_tokens for row in fixed],
                         "the epoch-aware estimate starts at the new epoch's first request")
        shrink = self.aligned((self.row(1, 1000, 224_000, 16_000),
                               self.row(2, 2000, 20_000, -4_000)), crossed=(1600,))
        self.assertIsNone(shrink[1].watch_delta_context_tokens)

    def test_forked_session_rows_never_replace_the_parent_delta_anchor(self):
        class SessionEpochs:
            sessions = {"event-1": "root", "event-2": "fork", "event-3": "root"}

            def session_for_event(self, event_id):
                return self.sessions[event_id]

            def comparable_events(self, _previous_id, _current_id):
                return True

        rows = [self.row(1, 1000, 100, 10), self.row(2, 1500, 5, 5), self.row(3, 2000, 120, 999)]
        fixed = _coherent_watch_deltas(rows, epochs=SessionEpochs(), session_id="root", subtask_ids=frozenset())

        self.assertEqual([10, 5, 20], [item.watch_delta_context_tokens for item in fixed])

    def test_unknown_root_anchor_keeps_own_estimate_and_subtasks_do_not_reset(self):
        rows = (self.row(1, 1000, 24_000, 16_000),
                self.row(2, 1500, None, None, event_id="subtask"),
                self.row(3, 2000, 220_000, 59_000),
                self.row(4, 2500, None, 2_000),
                self.row(5, 3000, 231_000, 11_000))
        fixed = self.aligned(rows, subtasks=frozenset({"subtask"}))
        self.assertEqual([16_000, None, 196_000, None, 11_000],
                         [row.watch_delta_context_tokens for row in fixed],
                         "a failed/unanchored prompt must not erase its successor's own delta")


class ComparisonTests(unittest.TestCase):
    def test_model_comparison_reprices_same_observed_mix_and_orders_relative_cost(self) -> None:
        bundle = analyze_snapshot(make_snapshot(), now_ms=4000)
        rows = model_comparison_rows(bundle.prompts, catalog())
        self.assertEqual(["Claude Test", "GPT Test"], [row.model_name for row in rows])
        self.assertGreater(rows[0].relative_to_lowest, Decimal("1"))
        self.assertEqual(Decimal("1"), rows[1].relative_to_lowest)
        self.assertGreaterEqual(rows[0].estimated_ccost, rows[1].estimated_ccost)

    def test_model_comparison_keeps_all_catalog_models_without_month_sample(self) -> None:
        rows = model_comparison_rows((), catalog())
        self.assertEqual(["Claude Test", "GPT Test"], [row.model_name for row in rows])
        self.assertTrue(all(row.relative_to_lowest is None for row in rows))
        self.assertTrue(all(row.estimated_ccost is None for row in rows))


    def test_model_timeline_name_never_guesses_default_effort(self) -> None:
        tier = PricingTier(per_million_input=Decimal("1"), per_million_cache_read=Decimal("0.1"), per_million_output=Decimal("4"))
        prices = PricingCatalog((ModelPricing(ModelRef("github-copilot", "gpt-5.6", "GPT-5.6"), "USD", tiers=(tier,), metadata={"publisher":"OpenAI"}),))
        self.assertEqual("GPT-5.6 (Default)", model_timeline_name(prices, "gpt-5.6", "github-copilot", ""))
        self.assertEqual("GPT-5.6 (XHigh)", model_timeline_name(prices, "gpt-5.6", "github-copilot", "xhigh"))
        self.assertTrue(model_timeline_name(prices, "gpt-5.6-pro", "github-copilot", "default").endswith(" (Default)"))



if __name__ == "__main__":
    unittest.main()
