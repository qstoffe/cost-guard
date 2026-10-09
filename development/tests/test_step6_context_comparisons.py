from __future__ import annotations

import unittest
from dataclasses import replace
from decimal import Decimal

from development.tests.test_analysis_core import make_snapshot, message, part
from src.analysis.comparisons import (
    model_comparison_rows, model_timeline_name,
)
from src.analysis.context import (
    build_context_timeline, context_composition, estimate_next_context,
    input_context_above_price_threshold, next_context_warning_state,
)
from src.analysis.core import analyze_snapshot
from src.domain import MessageRole, ModelPricing, ModelRef, PricingTier, TokenUsage
from src.pricing.catalog import PricingCatalog
from src.reports.models import PromptProjection
from src.reports.prompts import _coherent_watch_deltas


def catalog() -> PricingCatalog:
    def model(name: str, display: str, i: str, c: str, o: str) -> ModelPricing:
        tier = PricingTier(per_million_input=Decimal(i), per_million_cache_read=Decimal(c), per_million_output=Decimal(o))
        return ModelPricing(ModelRef("github-copilot", name, display), "USD", Decimal(i), Decimal(c), None, Decimal(o), (tier,), {"publisher":"Test"})
    return PricingCatalog((model("gpt-test", "GPT Test", "1", "0.1", "4"), model("claude-test", "Claude Test", "2", "0.2", "6")))


class ContextEngineTests(unittest.TestCase):
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
        class Epochs:
            def crossed(self, session_id, start, end):
                assert session_id == "root"
                return any(start <= boundary < end for boundary in crossed)
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

    def test_location_move_suppresses_cross_epoch_delta_and_restarts_chain(self):
        rows = (self.row(1, 1000, 24_000, 16_000),
                self.row(2, 2000, 220_000, 59_000),
                self.row(3, 3000, 231_000, 11_000))
        fixed = self.aligned(rows, crossed=(1600,))
        self.assertEqual([16_000, None, 11_000],
                         [row.watch_delta_context_tokens for row in fixed])

    def test_unknown_root_anchor_suppresses_delta_but_subtasks_do_not_reset(self):
        rows = (self.row(1, 1000, 24_000, 16_000),
                self.row(2, 1500, None, None, event_id="subtask"),
                self.row(3, 2000, 220_000, 59_000),
                self.row(4, 2500, None, 2_000),
                self.row(5, 3000, 231_000, 11_000))
        fixed = self.aligned(rows, subtasks=frozenset({"subtask"}))
        self.assertEqual([16_000, None, 196_000, None, None],
                         [row.watch_delta_context_tokens for row in fixed])


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
