"""Mini presentation consumes the same physical request values, never new pricing."""
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path
import tempfile
import unittest

from development.tests.fixtures.pricing_catalog import catalog
from development.tests.fixtures.recursive_costs import recursive_source
from src.analysis import analyze_snapshot
from src.analysis.session_cost import reconcile_session_cost
from src.application.contracts import record
from src.application.display import with_display, web_quota_reset
from src.application.live_projection import project_live
from src.application.mini_costs import mini_groups
from src.application.projection import block as project_block
from src.cache import CacheDatabase, CacheRepository
from src.domain.effort import EffortEvidence
from src.reports.prompt_costs import PromptCostPart
from src.reports.prompts import build_prompt_block
from src.watch.models import WatchCard, WatchProjection, WatchRow


class MiniTooltipTests(unittest.TestCase):
    def help_text(self, display):
        return display.get("session_cost_help", display.get("cost_detail_help"))

    def test_recursive_prompt_and_whole_session_groups_use_all_unrounded_requests_once(self):
        with recursive_source() as (source, _server):
            snapshot = source.load_session_snapshot("ses_current")
        prices = catalog()
        bundle = analyze_snapshot(snapshot, tracked_provider=None, now_ms=20_000)
        block = build_prompt_block(session_id=snapshot.root.session_id, title="Synthetic",
            bundle=bundle, snapshot=snapshot, catalog=prices, config={}, snapshot_running_metrics=True)
        with tempfile.TemporaryDirectory() as directory:
            database = CacheDatabase(Path(directory))
            database.initialize()
            repository = CacheRepository(database)
            cold = reconcile_session_cost(repository, snapshot, prices)
            warm = reconcile_session_cost(repository, snapshot, prices)
        card = WatchCard("ses_current", "Synthetic", "u1",
            (WatchRow("ses_current", "Synthetic", block.rows[0]),), "observed",
            session_cost=warm, session_cost_state="observed")
        wire = project_live(WatchProjection("Watch", "Synthetic", (), now_ms=20_000,
            active_cards=(card,))).to_json()["active_cards"][0]

        self.assertEqual(0, warm.valued_requests)
        self.assertEqual(cold.groups, warm.groups)
        self.assertEqual(D(672), sum(group.known_ccost for group in warm.groups))
        prompt, total = wire["rows"][0]["prompt"], wire["session_summary"]["cost"]
        prompt_groups = [dict(group.fields) for group in mini_groups(block.rows[0].cost_parts)]
        self.assertEqual(D(509), sum(D(group["known_ccost"]) for group in prompt_groups))
        # Five individual descendants collapse to three provider/model/effort
        # combinations. The Full Watch identity breakdown stays individual.
        self.assertEqual(5, sum(part["role"] == "subagents" for part in prompt["cost_detail"]["parts"]))
        self.assertLess(len(prompt_groups), len(prompt["cost_detail"]["parts"]))
        for value in (prompt, total):
            self.assertNotIn("mini_cost_groups", value, "presentation inputs must not duplicate wire costs")
            self.assertNotIn("mini_missing_agents", value)
            self.assertNotIn("mini_session_cost", value)
            for unit in ("credits", "usd"):
                overlay = value.get("display_units", {}).get(unit, {})
                self.assertNotIn("mini_cost_models", overlay, "unit-invariant labels must be shared")
                text = self.help_text({**value["display"], **overlay})
                self.assertNotRegex(text, r"Calls:|Effort:|Linked subagents|Total CCost|ses_")
                self.assertIn("Sub Agents:\n• ", text)
                self.assertNotRegex(text, r"CCost:|Partial cost coverage|Subtotal:|Model \d")
                self.assertIn(" Credits" if unit == "credits" else "$", text)
        self.assertIn("Session Models:\n• ", self.help_text(total["display"]))
        self.assertIsNone(total["duration_ms"], "cost capture has no canonical session duration")
        detail = with_display(project_block(block, details=True)).to_json()
        self.assertEqual(total["display"]["session_cost_help"], detail["display"]["session_cost_help"])
        self.assertEqual(prompt["display"]["cost_detail_help"], detail["rows"][0]["display"]["cost_detail_help"])
        self.assertEqual(D(672), sum(group.known_ccost for group in block.cost_groups))
        self.assertNotEqual(prompt["display"]["cost_detail_help"], total["display"]["session_cost_help"])
        for value in (detail, *detail["rows"]):
            text = str(value["display"]) + str(value.get("display_units"))
            self.assertNotRegex(text, r"Partial cost coverage|Partial pricing/usage|Amounts are independently rounded")

    def test_sum_before_rounding_preserves_effort_provider_version_and_partial_unknown(self):
        base = PromptCostPart("root", 0, "provider", "model-v1", "high", "", "high",
            1, D(".49"), 1, True, (D(0),) * 4, selected_models=("model-v1",),
            effort_evidence=(EffortEvidence("high"),))
        parts = (base, replace(base, agent=1), replace(base, agent=2),
            replace(base, agent=3, model_id="model-v2", selected_models=("model-v2",), complete=False),
            replace(base, agent=4, provider_id="other", priced_requests=0, known_ccost=D(0), complete=False),
            replace(base, agent=5, effort="", effort_evidence=(EffortEvidence("", "high", "request"),)))
        grouped = mini_groups(parts)
        groups = [group.to_json() for group in grouped]
        dto = with_display(record(mini_cost_groups=grouped)).to_json()
        shared = next(group for group in groups if group["subagent"] and
            group["model"] == "provider/model-v1" and group["effort"] == "high")
        self.assertEqual("0.98", shared["known_ccost"])
        self.assertEqual(5, len(groups))
        text = self.help_text(dto["display"])
        self.assertIn("— (1.0 Credits)", text)
        self.assertIn("— default (high)", text)
        self.assertIn("• other/model-v1 — high — (N/A)", text)
        self.assertIn("— (0.5 Credits)", text)
        self.assertNotIn("CCost:", text)

    def test_exact_sections_units_zero_and_missing_slots_preserve_raw_qualifications(self):
        base = PromptCostPart("root", 0, "provider", "a", "high", "", "High",
            1, D("125"), 1, True, (D(0),) * 4)
        parts = (base, replace(base, model_id="b", effort="Default (High)", known_ccost=D(14)),
            replace(base, session_id="child1", agent=1, model_id="c", effort="Medium", known_ccost=D(28)),
            replace(base, session_id="child2", agent=2, model_id="c", effort="Medium", known_ccost=D(2)),
            replace(base, agent=3, model_id="c", effort="Low", known_ccost=D(0)),
            replace(base, agent=4, provider_id="", model_id="", effort="", known_ccost=D(0),
                priced_requests=0, complete=False))
        grouped = mini_groups(parts)

        wire = with_display(record(mini_cost_groups=grouped, mini_missing_agents=2)).to_json()

        self.assertEqual("Session Models:\n• provider/a — High — (125 Credits)\n"
            "• provider/b — Default (High) — (14 Credits)\n\nSub Agents:\n"
            "• N/A — N/A — (N/A)\n• provider/c — Low — (0 Credits)\n"
            "• provider/c — Medium — (30 Credits)",
            wire["display"]["cost_detail_help"])
        self.assertIn("• provider/c — Medium — ($0.30)", wire["display_units"]["usd"]["cost_detail_help"])
        self.assertEqual(D(169), sum(D(group.to_json()["known_ccost"]) for group in grouped))
        unknown = next(group.to_json() for group in grouped if group.to_json()["model"] == "N/A")
        self.assertFalse(unknown["complete"])

    def test_mini_reset_uses_one_local_calendar_without_changing_full_watch(self):
        def ms(value):
            return int(datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp() * 1000)
        now = ms("2026-03-28T20:00:00")
        for deadline, qualification in (
                ("2026-03-28T21:00:00", "22:00 today"),
                ("2026-03-29T01:00:00", "03:00 tomorrow"),
                ("2026-03-30T01:00:00", "03:00 Monday"),
                ("2026-04-04T20:00:00", "22:00 Saturday"),
                ("2026-04-04T20:00:01", "22:00 2026-04-04")):
            values = {"reset_at_ms": ms(deadline)}
            mini = web_quota_reset(values, "Europe/Stockholm", now, mini=True)
            self.assertTrue(mini.startswith("in "))
            self.assertTrue(mini.endswith(" · " + qualification))
            self.assertNotIn("Reset", mini)
            self.assertTrue(web_quota_reset(values, "Europe/Stockholm", now).startswith("Reset "))
        for values, expected in (({}, "N/A"), ({"reset_at_ms": float("nan")}, "N/A"),
                ({"window_active": False}, "Window not started"),
                ({"reset_at_ms": now}, "Reset expired")):
            self.assertEqual(expected, web_quota_reset(values, "Europe/Stockholm", now, mini=True))


if __name__ == "__main__":
    unittest.main()
