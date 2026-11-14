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
from src.cache import CacheDatabase, CacheRepository
from src.domain.effort import EffortEvidence
from src.reports.prompt_costs import PromptCostPart
from src.reports.prompts import build_prompt_block
from src.watch.models import WatchCard, WatchProjection, WatchRow


class MiniTooltipTests(unittest.TestCase):
    def help_text(self, display):
        return "\n\n".join(f"{label}: {model}\n{label} CCost: {amount}"
            for (label, model), amount in zip(display["mini_cost_models"], display["mini_cost_amounts"]))

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
        self.assertEqual(5, prompt["display"]["cost_detail_help"].count("• Number of prompts:"))
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
                self.assertIn("Sub Agent 1:", text)
                self.assertIn("CCost: ", text)
                self.assertIn(" Credits" if unit == "credits" else "$", text)
        self.assertIn("Session Model 1:", self.help_text(total["display"]))
        self.assertIsNone(total["duration_ms"], "cost capture has no canonical session duration")

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
        self.assertIn("CCost: 1.0 Credits", text)
        self.assertIn("— default (high)", text)
        self.assertIn("CCost: 0 Credits", text)
        self.assertIn("CCost: 0.5 Credits", text)
        self.assertNotIn("\n\nMain Model CCost", text, "group lines must be consecutive")

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
