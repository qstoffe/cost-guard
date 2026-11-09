"""Model/effort groups preserve canonical role scopes, evidence, tiers and updates."""
from dataclasses import replace
from decimal import Decimal as D
import unittest

from development.tests.fixtures.pricing_catalog import catalog, threshold_catalog
from development.tests.fixtures.session_snapshots import make_uncompacted_snapshot, part, prov, MODEL
from src.analysis import analyze_snapshot
from src.analysis.cache import AnalysisDependencies, _bundle_from_dict, _bundle_to_dict
from src.application.live_projection import project_live
from src.domain import EventKind, ModelInvocation, ModelRef, NormalizedEvent, TokenUsage
from src.numbers import ccost_amount
from src.reports.prompt_rows import PromptRowProjector
from src.watch.models import WatchCard, WatchProjection, WatchRow


class PromptCostDetailTests(unittest.TestCase):
    def project(self, snapshot, prices=None, prompt_id="u_sub"):
        prices = prices or catalog()
        bundle = analyze_snapshot(snapshot, now_ms=4000)
        record = next(item for item in bundle.prompts if item.prompt_id == prompt_id)
        return PromptRowProjector(snapshot=snapshot, bundle=bundle, catalog=prices,
            config={}, snapshot_running_metrics=True).prompt(record)

    def wire(self, row):
        card = WatchCard("root", "Synthetic", row.event_id,
            (WatchRow("root", "Synthetic", row),), "observed")
        return project_live(WatchProjection("Watch", "Synthetic", (), now_ms=4000,
            active_cards=(card,), history_cards=(replace(card, focal_id=""),))).to_json()

    def test_exact_categories_use_each_request_model_effort_and_preserve_both_tables(self):
        snapshot = make_uncompacted_snapshot()
        invocations = tuple(replace(item, tokens=TokenUsage(input=100000, cache_read=200000,
            cache_write=300000, output=400000, reasoning=100000), variant="high")
            if item.session_id == "root" else replace(item, model=ModelRef("github-copilot", "claude-test"),
                variant="low", tokens=TokenUsage(input=100000, cache_read=200000, cache_write=300000, output=400000))
            for item in snapshot.invocations)

        row = self.project(replace(snapshot, invocations=invocations))
        wire = self.wire(row)

        # Reference Credits are 100x USD; cache writes fall back to input price.
        self.assertEqual(1, row.linked_agent_count)
        self.assertEqual(("root", "child"), tuple(item.session_id for item in row.cost_parts))
        self.assertEqual((D(20), D(4), D(60), D(400)), row.cost_parts[0].categories)
        self.assertEqual((D(20), D(4), D(60), D(240)), row.cost_parts[1].categories)
        self.assertEqual(("high", "low"), tuple(item.variant for item in row.cost_parts))
        self.assertEqual(row.ccost, sum(item.known_ccost for item in row.cost_parts))
        for kind in ("active_cards", "history_cards"):
            prompt = wire[kind][0]["rows"][0]["prompt"]
            self.assertIn("Main prompt — GPT Test · High", prompt["display"]["cost_detail_help"])
            self.assertIn("Subagents — Claude Test · Low (1 agent)", prompt["display"]["cost_detail_help"])
            self.assertIn("• Cached input: $0.04", prompt["display_units"]["usd"]["cost_detail_help"])
            self.assertIn("github-copilot/claude-test", prompt["display"]["model_detail_help"])
            self.assertEqual(str(row.ccost), prompt["ccost"])

    def test_model_switch_without_subagents_has_detail_but_never_participation_marker(self):
        snapshot = make_uncompacted_snapshot()
        invocations = tuple(replace(item, model=ModelRef("github-copilot", "claude-test"),
            variant="low") if item.invocation_id == "i_syn" else item
            for item in snapshot.invocations if item.session_id == "root")
        messages = tuple(replace(item, parts=()) if item.message_id == "a_sub" else item for item in snapshot.messages)

        row = self.project(replace(snapshot, invocations=invocations, messages=messages))

        self.assertEqual(0, row.linked_agent_count)
        self.assertEqual((0, 0), tuple(item.agent for item in row.cost_parts))
        help_text = self.wire(row)["active_cards"][0]["rows"][0]["prompt"]["display"]["model_detail_help"]
        self.assertIn("Claude Test · Low", help_text)
        self.assertNotIn("*", help_text)
        cost_help = self.wire(row)["active_cards"][0]["rows"][0]["prompt"]["display"]["cost_detail_help"]
        self.assertIn("Total CCost: " + ccost_amount(row.ccost), cost_help)
        self.assertIn("Total Calls: " + str(row.calls),
            self.wire(row)["active_cards"][0]["rows"][0]["prompt"]["display"]["calls_help"])

    def test_same_model_and_link_without_usage_still_prove_participation_and_survive_cache(self):
        snapshot = make_uncompacted_snapshot()
        bundle = analyze_snapshot(snapshot, now_ms=4000)
        decoded = _bundle_from_dict(_bundle_to_dict(bundle, AnalysisDependencies("c", "p")))
        record = next(item for item in decoded.prompts if item.prompt_id == "u_sub")
        self.assertEqual(("child",), record.linked_session_ids)
        row = self.project(snapshot)
        self.assertEqual(1, row.linked_agent_count)
        without_usage = replace(snapshot, invocations=tuple(i for i in snapshot.invocations if i.session_id == "root"))
        waiting = self.project(without_usage)
        self.assertEqual(1, waiting.linked_agent_count)
        displayed = self.wire(waiting)["active_cards"][0]["rows"][0]["prompt"]["display"]
        self.assertIn("1 linked subagent(s) have no recorded request usage", displayed["model_detail_help"])
        self.assertIn("1 linked subagent(s) have no recorded request usage", displayed["cost_detail_help"])
        self.assertIn("incomplete request evidence", displayed["calls_help"])
        self.assertIn("Subagents — GPT Test", self.wire(row)["active_cards"][0]["rows"][0]["prompt"]["display"]["model_detail_help"])
        self.assertEqual("cu", record.entries[-1].logical_prompt_id)

    def test_partial_telemetry_and_unpriced_agents_never_manufacture_category_zeroes(self):
        snapshot = make_uncompacted_snapshot()
        invocations = tuple(replace(item, model=ModelRef("github-copilot", "unpriced")) if item.session_id == "child" else
            replace(item, tokens=TokenUsage(input=100, known_fields=("input",))) for item in snapshot.invocations)

        row = self.project(replace(snapshot, invocations=invocations))
        help_text = self.wire(row)["active_cards"][0]["rows"][0]["prompt"]["display"]["cost_detail_help"]

        self.assertTrue(row.unresolved_cost)
        self.assertEqual((None,) * 4, row.cost_parts[0].categories)
        self.assertEqual(0, row.cost_parts[1].priced_requests)
        self.assertNotIn("• Output: 0", help_text)
        self.assertIn("Some category amounts are unavailable", help_text)
        self.assertIn("Reference price data cannot currently be checked", help_text)
        self.assertNotIn("has no listed reference price", help_text)
        self.assertIn("Total CCost: ?", help_text)

    def test_tiers_and_live_corrections_reconcile_unrounded_not_displayed_shares(self):
        snapshot = make_uncompacted_snapshot(running=True)
        for count in (100000, 100001, 100000):
            invocations = tuple(replace(item, tokens=TokenUsage(input=count, output=1000))
                if item.invocation_id == "i_next" else item for item in snapshot.invocations)
            row = self.project(replace(snapshot, invocations=invocations), threshold_catalog(), "u_next")
            expected = (D(10), D(0), D(0), D(".4")) if count == 100000 else (D("20.0002"), D(0), D(0), D(".8"))
            self.assertEqual(expected, row.cost_parts[0].categories)
            self.assertEqual(row.ccost, sum(expected))
            self.assertEqual(row.ccost, row.incoming_context_ccost + row.extra_ccost)

    def test_concurrent_and_nested_links_keep_distinct_sessions_and_own_efforts(self):
        snapshot = make_uncompacted_snapshot()
        direct = part("other-task", "a_sub", "root", "tool", {"tool": "subagent", "state": {
            "time": {"start": 1200, "end": 1450}, "metadata": {"sessionID": "other"}}}, 1200)
        nested = part("nested-task", "ca", "child", "tool", {"tool": "subagent", "state": {
            "time": {"start": 1250, "end": 1390}, "metadata": {"sessionID": "nested"}}}, 1250)
        messages = tuple(replace(m, parts=(*m.parts, direct)) if m.message_id == "a_sub" else
            replace(m, parts=(*m.parts, nested)) if m.message_id == "ca" else m for m in snapshot.messages)
        requests = tuple(ModelInvocation(sid, sid, 1300, MODEL, TokenUsage(input=100, output=10),
            prov(sid, sid), completed_at_ms=1350, variant="low") for sid in ("other", "nested"))
        sessions = (*snapshot.sessions, replace(snapshot.sessions[1], session_id="other"),
            replace(snapshot.sessions[1], session_id="nested", parent_session_id="child"))

        row = self.project(replace(snapshot, sessions=sessions, messages=messages, invocations=(*snapshot.invocations, *requests)))

        self.assertEqual(3, row.linked_agent_count)
        by_session = {item.session_id: item for item in row.cost_parts}
        self.assertEqual({"root", "child", "other", "nested"}, set(by_session))
        self.assertEqual(("low", "low"), (by_session["other"].variant, by_session["nested"].variant))
        self.assertEqual(row.ccost, sum(item.known_ccost for item in row.cost_parts))
        self.assertEqual(row.calls, sum(item.calls for item in row.cost_parts))
        displayed = self.wire(row)["active_cards"][0]["rows"][0]["prompt"]
        groups = displayed["cost_detail"]["parts"]
        combined = next(group for group in groups if group["variant"] == "low")
        self.assertEqual(("subagents", 2, 2), (combined["role"], combined["agent_count"], combined["calls"]))
        # Two physical requests, each (100 input * 1 + 10 output * 4) / 10000 Credits.
        self.assertEqual(D(".028"), D(combined["known_ccost"]))
        self.assertEqual((D(".02"), D(0), D(0), D(".008")), tuple(D(value) for value in combined["categories"]))
        self.assertIn("Subagents — GPT Test · Low (2 agents): 2", displayed["display"]["calls_help"])
        self.assertIn("Subagents — GPT Test · Low (2 agents)", displayed["display"]["model_detail_help"])
        self.assertFalse(combined["prompts_complete"], "unparented requests cannot establish prompt boundaries")
        self.assertEqual(0, combined["prompt_count"])

    def test_one_linked_agent_with_multiple_efforts_has_distinct_group_subtotals(self):
        snapshot = make_uncompacted_snapshot()
        extra = ModelInvocation("extra", "child", 1300, ModelRef("github-copilot", "claude-test"),
            TokenUsage(input=100000), prov("extra", "child"), completed_at_ms=1350, variant="high")

        row = self.project(replace(snapshot, invocations=(*snapshot.invocations, extra)))
        child_parts = tuple(part for part in row.cost_parts if part.session_id == "child")
        text = self.wire(row)["active_cards"][0]["rows"][0]["prompt"]["display"]["cost_detail_help"]

        self.assertEqual(1, row.linked_agent_count)
        self.assertEqual((1, 1), tuple(part.agent for part in child_parts))
        self.assertEqual(D(20), next(part.known_ccost for part in child_parts if part.model_id == "claude-test"))
        self.assertIn("Subagents — Claude Test · High (1 agent)", text)
        self.assertNotIn("Subagent 1", text)
        self.assertEqual(row.ccost, sum(part.known_ccost for part in row.cost_parts))

    def test_bounded_export_preserves_honest_omitted_count_and_subtotal(self):
        row = self.project(make_uncompacted_snapshot())
        original = row.cost_parts[0]
        parts = tuple(replace(original, session_id=str(i), agent=i, variant=str(i)) for i in range(30))
        row = replace(row, cost_parts=parts, ccost=sum(p.known_ccost for p in parts),
            calls=sum(p.calls for p in parts), linked_agent_count=29)

        prompt = self.wire(row)["active_cards"][0]["rows"][0]["prompt"]

        self.assertEqual(24, len(prompt["cost_detail"]["parts"]))
        self.assertEqual(6, prompt["cost_detail"]["omitted_parts"])
        self.assertEqual(original.known_ccost * 6, D(prompt["cost_detail"]["omitted_ccost"]))
        self.assertIn("6 additional role/model/effort groups not shown", prompt["display"]["cost_detail_help"])
        self.assertEqual(original.calls * 6, prompt["cost_detail"]["omitted_calls"])
        self.assertIn(f"not shown: {original.calls * 6} calls", prompt["display"]["calls_help"])

        same = replace(row, cost_parts=tuple(replace(p, variant=None) for p in parts))
        detail = self.wire(same)["active_cards"][0]["rows"][0]["prompt"]["cost_detail"]
        self.assertEqual((2, 0, 29), (len(detail["parts"]), detail["omitted_parts"], detail["parts"][1]["agent_count"]))

    def test_provider_identity_zero_calls_and_missing_category_data_stay_honest(self):
        row = self.project(make_uncompacted_snapshot())
        original = row.cost_parts[0]
        unknown = replace(original, session_id="another", agent=2, provider_id="another-provider",
            categories=(None, D(0), D(0), D(1)), known_ccost=D(1))
        row = replace(row, cost_parts=(*row.cost_parts, unknown), linked_agent_count=2)
        displayed = self.wire(row)["active_cards"][0]["rows"][0]["prompt"]["display"]
        self.assertIn("another-provider/gpt-test", displayed["model_detail_help"])
        self.assertIn("[another-provider/gpt-test]", displayed["cost_detail_help"])
        self.assertIn("• Input: N/A", displayed["cost_detail_help"])
        self.assertIn("incomplete request evidence", displayed["calls_help"])
        empty = self.wire(replace(row, calls=0, ccost=D(0), cost_parts=(), linked_agent_count=0))
        self.assertEqual("", empty["active_cards"][0]["rows"][0]["prompt"]["display"]["calls_help"])
        unrecorded = replace(unknown, provider_id="", model_id="", model="")
        missing = self.wire(replace(row, cost_parts=(*row.cost_parts[:2], unrecorded)))
        tokens = missing["active_cards"][0]["rows"][0]["prompt"]["display"]
        self.assertIn("Unrecorded model", tokens["model_detail_help"])
        self.assertNotIn("another-provider", tokens["model_detail_help"])
        self.assertIn("Unrecorded model", tokens["cost_detail_help"])

    def test_distinct_request_price_tiers_never_pool_their_rates(self):
        snapshot = make_uncompacted_snapshot()
        requests = tuple(replace(item, tokens=TokenUsage(input=100001 if item.invocation_id == "i_syn" else 100000,
            output=1000)) for item in snapshot.invocations)
        row = self.project(replace(snapshot, invocations=requests), threshold_catalog())
        main = [part for part in row.cost_parts if not part.agent]
        self.assertEqual(2, len(main))
        self.assertNotEqual(main[0].price_tier, main[1].price_tier)
        self.assertEqual(D("41.6002"), row.ccost)
        displayed = self.wire(row)["active_cards"][0]["rows"][0]["prompt"]["display"]
        for key in ("model_detail_help", "cost_detail_help"):
            self.assertNotIn("input tokens", displayed[key])
            self.assertNotIn("Default (", displayed[key])
        self.assertIn("input tokens", displayed["calls_help"], "Calls help is outside the requested copy change")

    def test_distinct_child_prompts_not_requests_or_agents_and_private_ids_stay_server_side(self):
        snapshot = make_uncompacted_snapshot()
        second = NormalizedEvent("cu2", "child", EventKind.USER_PROMPT, 1300, prov("child", "cu2"), "private prompt")
        requests = tuple(replace(snapshot.invocations[1], invocation_id=f"child-{index}",
            message_id=f"reply-{index}", step_part_id=f"step-{index}",
            initiating_event_id=parent, completed_at_ms=when)
            for index, (parent, when) in enumerate((("cu", 1250), ("cu", 1260), ("cu2", 1400))))

        row = self.project(replace(snapshot, events=(*snapshot.events, second, second),
            invocations=tuple(i for i in snapshot.invocations if i.session_id == "root") + requests))
        wire = self.wire(row)["active_cards"][0]["rows"][0]["prompt"]
        group = next(part for part in wire["cost_detail"]["parts"] if part["role"] == "subagents")

        self.assertEqual((1, 3, 2, True), tuple(group[key] for key in ("agent_count", "calls", "prompt_count", "prompts_complete")))
        help_text = wire["display"]["cost_detail_help"]
        self.assertEqual(1, help_text.count("Number of prompts:"))
        self.assertIn("(1 agent)\n• Number of prompts: 2\n• Input:", help_text)
        self.assertIn("• Number of prompts: 2\n• Input: $", wire["display_units"]["usd"]["cost_detail_help"])
        self.assertNotIn("prompt_ids", str(wire))
        self.assertNotIn("cu2", str(wire))
        self.assertNotIn("private prompt", str(wire))

    def test_one_prompt_across_effort_and_price_tiers_counts_once_in_each_group(self):
        snapshot = make_uncompacted_snapshot()
        child = snapshot.invocations[1]
        requests = tuple(replace(child, invocation_id=f"child-{index}", step_part_id=f"step-{index}",
            tokens=TokenUsage(input=count, output=1000), variant=effort)
            for index, (count, effort) in enumerate(((100000, "low"), (100001, "low"), (100001, "high"), (100000, "low"))))

        row = self.project(replace(snapshot,
            invocations=tuple(i for i in snapshot.invocations if i.session_id == "root") + requests), threshold_catalog())
        groups = self.wire(row)["active_cards"][0]["rows"][0]["prompt"]["cost_detail"]["parts"]
        children = [group for group in groups if group["role"] == "subagents"]

        self.assertEqual(3, len(children))
        self.assertEqual([1, 1, 1], [group["prompt_count"] for group in children])
        self.assertTrue(all(group["prompts_complete"] for group in children))
        self.assertEqual([2, 1, 1], [group["calls"] for group in children])

    def test_nested_sessions_with_same_prompt_id_have_distinct_canonical_owners(self):
        snapshot = make_uncompacted_snapshot()
        nested = part("nested-task", "ca", "child", "tool", {"tool": "subagent", "state": {
            "time": {"start": 1250, "end": 1390}, "metadata": {"sessionID": "nested"}}}, 1250)
        messages = tuple(replace(m, parts=(*m.parts, nested)) if m.message_id == "ca" else m for m in snapshot.messages)
        event = NormalizedEvent("cu", "nested", EventKind.USER_PROMPT, 1260, prov("nested", "cu"))
        request = replace(snapshot.invocations[1], session_id="nested", invocation_id="nested-request",
            message_id="nested-reply", created_at_ms=1300, completed_at_ms=1380)

        row = self.project(replace(snapshot, messages=messages, events=(*snapshot.events, event),
            sessions=(*snapshot.sessions, replace(snapshot.sessions[1], session_id="nested", parent_session_id="child")),
            invocations=(*snapshot.invocations, request)))
        group = self.wire(row)["active_cards"][0]["rows"][0]["prompt"]["cost_detail"]["parts"][1]

        self.assertEqual((2, 2, True), (group["agent_count"], group["prompt_count"], group["prompts_complete"]))

    def test_missing_and_ambiguous_prompt_boundaries_qualify_observed_count(self):
        snapshot = make_uncompacted_snapshot()
        extra = replace(snapshot.invocations[1], invocation_id="unknown", message_id="unknown-reply", initiating_event_id=None)
        row = self.project(replace(snapshot, invocations=(*snapshot.invocations, extra)))
        text = self.wire(row)["active_cards"][0]["rows"][0]["prompt"]["display"]["cost_detail_help"]
        self.assertIn("Number of prompts: at least 1 observed (incomplete boundaries)", text)
        missing = self.project(replace(snapshot, events=tuple(e for e in snapshot.events if e.session_id != "child")))
        self.assertIn("Number of prompts: N/A", self.wire(missing)["active_cards"][0]["rows"][0]["prompt"]["display"]["cost_detail_help"])

        # Two simultaneous prompts cannot safely own the same synthetic continuation.
        first = NormalizedEvent("first", "child", EventKind.SUBTASK, 1210, prov("child", "first"))
        second = replace(first, event_id="second")
        continuation = replace(first, event_id="continuation", kind=EventKind.SYNTHETIC_CONTINUATION, created_at_ms=1220)
        ambiguous = self.project(replace(snapshot, events=(*snapshot.events, first, second, continuation),
            invocations=tuple(replace(i, initiating_event_id="continuation") if i.session_id == "child" else i for i in snapshot.invocations)))
        self.assertIn("Number of prompts: N/A", self.wire(ambiguous)["active_cards"][0]["rows"][0]["prompt"]["display"]["cost_detail_help"])

    def test_child_synthetic_continuation_resolves_to_one_prompt_not_another_call(self):
        snapshot = make_uncompacted_snapshot()
        event = NormalizedEvent("notice", "child", EventKind.BACKGROUND_COMPLETION, 1250, prov("child", "notice"))
        extra = replace(snapshot.invocations[1], invocation_id="continued", message_id="continued-reply",
            initiating_event_id="notice", completed_at_ms=1420)
        row = self.project(replace(snapshot, events=(*snapshot.events, event), invocations=(*snapshot.invocations, extra)))
        group = self.wire(row)["active_cards"][0]["rows"][0]["prompt"]["cost_detail"]["parts"][1]
        self.assertEqual((2, 1, True), (group["calls"], group["prompt_count"], group["prompts_complete"]))


if __name__ == "__main__":
    unittest.main()
