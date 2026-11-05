"""Per-agent category costs preserve canonical scopes, evidence, tiers and updates."""
from dataclasses import replace
from decimal import Decimal as D
import unittest

from development.tests.fixtures.pricing_catalog import catalog, threshold_catalog
from development.tests.fixtures.session_snapshots import make_uncompacted_snapshot, part, prov, MODEL
from src.analysis import analyze_snapshot
from src.analysis.cache import AnalysisDependencies, _bundle_from_dict, _bundle_to_dict
from src.application.live_projection import project_live
from src.domain import ModelInvocation, ModelRef, TokenUsage
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
            self.assertIn("Subagent 1 — Claude Test · Low", prompt["display"]["cost_detail_help"])
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
        self.assertIn("Main prompt total: " + ccost_amount(row.ccost), cost_help)

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
        self.assertIn("1 linked subagent(s) have no recorded request usage",
            self.wire(waiting)["active_cards"][0]["rows"][0]["prompt"]["display"]["model_detail_help"])

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
        self.assertIn("no reference price", help_text)
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
        direct = part("other-task", "a_sub", "root", "tool", {"tool": "task", "state": {
            "time": {"start": 1200, "end": 1450}, "metadata": {"sessionId": "other"}}}, 1200)
        nested = part("nested-task", "ca", "child", "tool", {"tool": "task", "state": {
            "time": {"start": 1250, "end": 1390}, "metadata": {"sessionId": "nested"}}}, 1250)
        messages = tuple(replace(m, parts=(*m.parts, direct)) if m.message_id == "a_sub" else
            replace(m, parts=(*m.parts, nested)) if m.message_id == "ca" else m for m in snapshot.messages)
        requests = tuple(ModelInvocation(sid, sid, 1300, MODEL, TokenUsage(input=100, output=10),
            prov(sid, sid), completed_at_ms=1350, variant=effort) for sid, effort in (("other", "low"), ("nested", "high")))
        sessions = (*snapshot.sessions, replace(snapshot.sessions[1], session_id="other"),
            replace(snapshot.sessions[1], session_id="nested", parent_session_id="child"))

        row = self.project(replace(snapshot, sessions=sessions, messages=messages, invocations=(*snapshot.invocations, *requests)))

        self.assertEqual(3, row.linked_agent_count)
        by_session = {item.session_id: item for item in row.cost_parts}
        self.assertEqual({"root", "child", "other", "nested"}, set(by_session))
        self.assertEqual(("low", "high"), (by_session["other"].variant, by_session["nested"].variant))
        self.assertEqual(row.ccost, sum(item.known_ccost for item in row.cost_parts))
        self.assertEqual(row.calls, sum(item.calls for item in row.cost_parts))

    def test_one_linked_agent_with_multiple_efforts_has_group_and_agent_subtotals(self):
        snapshot = make_uncompacted_snapshot()
        extra = ModelInvocation("extra", "child", 1300, ModelRef("github-copilot", "claude-test"),
            TokenUsage(input=100000), prov("extra", "child"), completed_at_ms=1350, variant="high")

        row = self.project(replace(snapshot, invocations=(*snapshot.invocations, extra)))
        child_parts = tuple(part for part in row.cost_parts if part.session_id == "child")
        text = self.wire(row)["active_cards"][0]["rows"][0]["prompt"]["display"]["cost_detail_help"]

        self.assertEqual(1, row.linked_agent_count)
        self.assertEqual((1, 1), tuple(part.agent for part in child_parts))
        self.assertEqual(D(20), next(part.known_ccost for part in child_parts if part.model_id == "claude-test"))
        self.assertIn("Subagent 1 — Claude Test · High", text)
        self.assertIn("Subagent 1 total: " + ccost_amount(sum(part.known_ccost for part in child_parts)), text)
        self.assertEqual(row.ccost, sum(part.known_ccost for part in row.cost_parts))

    def test_bounded_export_preserves_honest_omitted_count_and_subtotal(self):
        row = self.project(make_uncompacted_snapshot())
        original = row.cost_parts[0]
        parts = tuple(replace(original, session_id=str(i), agent=i) for i in range(30))
        row = replace(row, cost_parts=parts, ccost=sum(p.known_ccost for p in parts), linked_agent_count=29)

        prompt = self.wire(row)["active_cards"][0]["rows"][0]["prompt"]

        self.assertEqual(24, len(prompt["cost_detail"]["parts"]))
        self.assertEqual(6, prompt["cost_detail"]["omitted_parts"])
        self.assertEqual(original.known_ccost * 6, D(prompt["cost_detail"]["omitted_ccost"]))
        self.assertIn("6 additional agent/model groups not shown", prompt["display"]["cost_detail_help"])
        self.assertEqual(original.calls * 6, prompt["cost_detail"]["omitted_calls"])
        self.assertIn(f"not shown: {original.calls * 6} calls", prompt["display"]["calls_help"])


if __name__ == "__main__":
    unittest.main()
