"""Selection, metering and clocks remain independent across the same child link."""
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from development.tests.fixtures.scripted_parent import scripted_parent, catalog, FixtureCatalog
from development.tests.fixtures.claude_alias import service as make_service
from src.analysis import analyze_snapshot
from src.analysis.session_activity import activity_fields
from src.application.display import with_display
from src.application.live_projection import card_row
from src.application.projection import project, prompt
from src.application.session_epoch_page import ordered
from src.reports.models import ReportProjection, ReportKind, SessionUsageRow
from src.reports.prompt_rows import PromptRowProjector
from src.reports.sampling import AnalyzedRoot
from src.reports.session_summary import session_summary
from src.analysis.session_cost import reconcile_session_cost
from src.sources.opencode_v2_model_identity import DesktopModelCatalog


class ScriptedParentTests(unittest.TestCase):
    def project(self, saved):
        service = make_service(self, snapshots=(saved,))
        service.source.model_identities_current = DesktopModelCatalog(lambda: FixtureCatalog()).current
        service.pricing_provider.catalog = catalog()
        item = service._analyze(saved.root, detail=True)
        row = service._session_rows((item,), catalog_models=True)[0]
        projector = PromptRowProjector(snapshot=saved, bundle=item.bundle, catalog=catalog(), config={})
        parent = next(projector.prompt(record) for record in item.bundle.prompts if record.session_id == "root")
        wire = with_display(prompt(parent, details=True)).to_json()
        session = project(ReportProjection(ReportKind.SESSIONS, "Sessions", "OpenCode", session_usage=(row,)), "UTC").to_json()["session_usage"][0]
        return service, item, row, parent, wire, session

    def test_selected_child_is_not_a_call_contributor_or_replacement_main_model(self):
        service, _, row, parent, wire, session = self.project(scripted_parent())

        self.assertEqual(("Scripted", True, False, ("fixture/scripted",)),
            (row.model, row.has_model_details, row.multiple_models, row.contributor_models))
        self.assertEqual((1, Decimal(0), 1, 1), (parent.calls, parent.ccost, parent.linked_agent_count, len(parent.cost_parts)))
        self.assertIsNone(parent.incoming_context_tokens)
        self.assertEqual(Decimal(0), parent.billed_cost)  # Observed fixture amount, not a child bill.
        for text in (wire["model_display_help"], session["model_display_help"], session["model_help"]):
            self.assertIn("Local scripted fixture", text)
            self.assertIn("claude-agent/Claude Opus 5.5 · Max", text)
            self.assertIn("recorded claude-agent/opus", text)
            self.assertIn("Execution/inference and usage/cost unverified", text)
            self.assertNotIn("gpt-6-luna", text)
        for text in (wire["model_display_help"], session["model_help"]):
            self.assertIn("Selected/attempted subagents", text)
        main, agents = session["model_display_help"].split("\n\n")
        self.assertTrue(main.startswith("Session Models:\n"))
        self.assertTrue(agents.startswith("Sub Agents:\nNo executed subagent model is verified."))
        self.assertIn("Selected/attempted: claude-agent/", agents)
        self.assertNotIn("• ", agents, "a selection is not an executed subagent request")
        mini = with_display(card_row(SimpleNamespace(prompt=parent, tool=None, marker=""), 200_000)).to_json()
        self.assertEqual(wire["model_display_help"], mini["prompt"]["model_display_help"])
        self.assertIn("not a proven zero upstream bill", mini["prompt"]["display"]["mini_cost_coverage_help"])
        self.assertIn("not a proven zero upstream bill", session["display"]["mini_cost_coverage_help"])
        cost = reconcile_session_cost(service.cache_repository, scripted_parent(), catalog())
        self.assertEqual(1, cost.unverified_agent_count)

    def test_positive_zero_failed_and_explicit_nonexecution_keep_distinct_coverage(self):
        for state, calls, contributors, missing in (
            ("positive", 2, 2, 0), ("zero", 2, 2, 0), ("failed", 1, 1, 1), ("not-executed", 1, 1, 0)):
            with self.subTest(state=state):
                _, _, row, parent, wire, session = self.project(scripted_parent(child_state=state))
                self.assertEqual((calls, contributors, missing),
                    (parent.calls, len(row.contributor_models), row.unverified_agent_count))
                self.assertEqual(state in {"positive", "zero"}, bool(row.subagent_models))
                self.assertEqual(state in {"failed", "not-executed"}, bool(row.linked_model_selections))
                self.assertEqual(state == "positive", parent.ccost > 0)
                if state == "not-executed":
                    self.assertIn("No request recorded in complete child history", wire["model_display_help"])

    def test_missing_partial_and_stale_selection_are_neutral(self):
        for saved in (scripted_parent(selection=False), scripted_parent(complete=False)):
            _, item, row, parent, wire, _ = self.project(saved)
            if saved.complete:
                self.assertEqual((), row.linked_model_selections)
                self.assertIn("model unknown", wire["model_display_help"])
            else:
                self.assertIn("Partial source", wire["model_display_help"])
            stale = replace(item, bundle=replace(item.bundle, source_revision="other"))
            stale_row = self.project(saved)[0]._session_rows((stale,), catalog_models=True)[0]
            self.assertEqual((), stale_row.linked_model_selections)

    def test_unrelated_ancestry_and_later_reused_child_selection_cannot_leak(self):
        saved = scripted_parent()
        foreign = replace(saved.sessions[1], parent_session_id="elsewhere")
        unrelated = replace(saved, sessions=(saved.root, foreign), source_revision="foreign")
        self.assertEqual((), self.project(unrelated)[2].linked_model_selections)
        late = replace(saved.events[1], event_id="late", created_at_ms=500_000,
            metadata=dict(provider_id="wrong", model_id="later", variant="high"))
        reused = replace(saved, events=(*saved.events, late), source_revision="reuse")
        row = self.project(reused)[2]
        self.assertEqual(1, len(row.linked_model_selections))
        self.assertNotIn("wrong", row.linked_model_selections[0])

    def test_terminal_unverified_start_is_visible_without_fabricating_a_finish(self):
        for finished in (False, True):
            saved = scripted_parent(finished=finished, child_state="zero")
            item = AnalyzedRoot(saved.root, analyze_snapshot(saved, now_ms=200_000), False, saved)

            values = activity_fields(item)

            self.assertEqual(2000, values["prompt_started_ms"])
            self.assertEqual(122_030 if finished else None, values["last_activity_ms"])
            self.assertFalse(values["running"])
            self.assertLess(values["activity_latest_ms"], saved.root.updated_at_ms)

    def test_start_fallback_sort_keeps_running_first_unknown_last_and_id_ties(self):
        base = SessionUsageRow("old", "old", "Scripted", False, Decimal(0), 1, last_activity_ms=1000)
        rows = (base, replace(base, session_id="b", last_activity_ms=None, prompt_started_ms=2000),
            replace(base, session_id="a", last_activity_ms=None, prompt_started_ms=2000),
            replace(base, session_id="unknown", last_activity_ms=None),
            replace(base, session_id="live", running=True, prompt_started_ms=500))

        self.assertEqual(["live", "a", "b", "old", "unknown"], [r.session_id for r in ordered(rows, "activity", -1)])
        self.assertEqual(["live", "old", "a", "b", "unknown"], [r.session_id for r in ordered(rows, "activity", 1)])

    def test_scalar_cache_reuses_selection_then_replaces_it_after_source_revision(self):
        saved = scripted_parent()
        service, _, _, _, _, _ = self.project(saved)
        first, _ = session_summary(service, saved.root, saved.source_revision)
        with patch.object(service, "_analyze", side_effect=AssertionError("warm hydration")):
            cached, _ = session_summary(service, saved.root, saved.source_revision)
        self.assertEqual(first, cached)
        service.source.snapshots["root"] = scripted_parent(selection=False)
        current, _ = session_summary(service, saved.root, service.source.snapshots["root"].source_revision)
        self.assertEqual((), current.linked_model_selections)

    def test_same_native_start_converts_to_local_minute_across_midnight_and_dst(self):
        for utc, local in (("2026-11-15T23:38:00+00:00", "2026-11-16 00:38"),
                           ("2026-03-29T00:59:00+00:00", "2026-03-29 01:59"),
                           ("2026-03-29T01:00:00+00:00", "2026-03-29 03:00"),
                           ("2026-10-25T00:30:00+00:00", "2026-10-25 02:30"),
                           ("2026-10-25T01:30:00+00:00", "2026-10-25 02:30")):
            saved = scripted_parent(start=int(datetime.fromisoformat(utc).timestamp() * 1000))
            _, item, _, parent, _, _ = self.project(saved)
            activity = activity_fields(item)
            mini = with_display(prompt(parent), "Europe/Stockholm").to_json()
            self.assertEqual(saved.events[0].created_at_ms, activity["prompt_started_ms"])
            self.assertEqual(activity["prompt_started_ms"], mini["at_ms"])
            self.assertEqual(local, mini["display"]["date_time"])


if __name__ == "__main__":
    unittest.main()
