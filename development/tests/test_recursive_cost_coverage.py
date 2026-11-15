"""Physical recursive calls reconcile; unknown acquisition is not zero spending."""
from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from development.tests.fixtures.compact_reports import report_service
from development.tests.fixtures.pricing_catalog import catalog, threshold_catalog
from development.tests.fixtures.recursive_costs import recursive_source
from development.tests.fixtures.subagent_sessions import incident_source
from src.analysis import analyze_snapshot
from src.analysis.cache import AnalysisDependencies, _bundle_from_dict, _bundle_to_dict
from src.analysis.causal import trace_entries
from src.analysis.period_ccost import PeriodCCostIndex, combined_cost
from src.analysis.session_cost import reconcile_session_cost
from src.analysis.token_mix import priced_token_mix
from src.analysis.valuation import comparison_cost, unique_usage
from src.application.live_projection import project_live
from src.application.projection import block as export_block, project
from src.cache import CacheDatabase, CacheRepository
from src.domain import TokenUsage, ModelRef
from src.reports.prompts import build_prompt_block
from src.reports.models import ReportKind, ReportProjection
from src.reports.sampling import AnalyzedRoot
from src.reports.session_summary import ALGORITHM, NAMESPACE, session_summary, summary_key
from src.watch.models import WatchCard, WatchProjection, WatchRow


class RecursiveCostCoverageTests(unittest.TestCase):
    def project(self, snapshot):
        prices = catalog()
        bundle = analyze_snapshot(snapshot, tracked_provider=None, now_ms=20_000)
        block = build_prompt_block(session_id=snapshot.root.session_id, title="Synthetic", bundle=bundle,
            snapshot=snapshot, catalog=prices, config={}, snapshot_running_metrics=True)
        return bundle, block

    def test_recursive_siblings_late_great_grandchild_and_outside_bucket_reconcile_all_consumers(self):
        with recursive_source() as (source, _server):
            snapshot = source.load_session_snapshot("ses_current")
        bundle, block = self.project(snapshot)
        # Independent request oracle: root 3*61, child 2*102, sibling 102,
        # other-provider sibling 61, grandchild 61, great-grandchild 61.
        expected = D(672)
        self.assertEqual((D(509), D(61)), tuple(row.ccost for row in block.rows))
        self.assertEqual((expected, 9, D(102), 1), (block.total_ccost, block.total_calls, block.other_ccost, block.other_calls))
        self.assertEqual((D(183), D(489)), (block.total_main_ccost, block.total_subagent_ccost))
        first = bundle.prompts[0]
        self.assertEqual((7, 5), (len(first.entries), len(first.linked_session_ids)))
        self.assertTrue(first.usage_coverage_complete)
        canonical = unique_usage(bundle.trace_entries + bundle.trace_entries)
        self.assertEqual(9, len(canonical))
        self.assertEqual(expected, comparison_cost(canonical, catalog().reference_valuation).ccost)
        mix = priced_token_mix(((entry.model, entry.tokens) for entry in canonical), catalog().reference_category_valuation)
        self.assertEqual(expected, sum(mix.costs))
        period = PeriodCCostIndex(canonical, catalog().reference_valuation)
        self.assertEqual(expected, sum(period.cost(provider, "provider", 0, 20_000).known_ccost
            for provider in ("github-copilot", "openai")))
        # Another capture of one child cannot multiply the same physical call.
        child = next(entry for entry in canonical if entry.session_id == "ses_current_child")
        self.assertEqual(9, len(unique_usage((*canonical, replace(child, root_session_id=child.session_id)))))
        decoded = _bundle_from_dict(_bundle_to_dict(bundle, AnalysisDependencies("c", "p")))
        self.assertEqual(bundle, decoded)
        with tempfile.TemporaryDirectory() as directory:
            database = CacheDatabase(Path(directory)); database.initialize()
            repository = CacheRepository(database)
            cold = reconcile_session_cost(repository, snapshot, catalog())
            warm = reconcile_session_cost(repository, snapshot, catalog())
            self.assertEqual((expected, 9, True), (cold.total.ccost, cold.checked_requests, cold.source_complete))
            self.assertEqual((expected, 0), (warm.total.ccost, warm.valued_requests))
        card = WatchCard("ses_current", "Synthetic", "u1", (WatchRow("ses_current", "Synthetic", block.rows[0]),), "observed")
        live = project_live(WatchProjection("Watch", "Synthetic", (), now_ms=20_000,
            active_cards=(card,), history_cards=(replace(card, focal_id=""),))).to_json()
        for lane in ("active_cards", "history_cards"):
            prompt = live[lane][0]["rows"][0]["prompt"]
            self.assertEqual(D(509), D(prompt["ccost"]))
            for unit in ("credits", "usd"):
                display = {**prompt["display"], **prompt["display_units"][unit]}
                help_text = display["cost_detail_help"]
                self.assertEqual(4, help_text.count("• "))
                self.assertIn("Sub Agents", [label for label, _model in display["mini_cost_models"]])
                self.assertNotRegex(help_text, r"Subagent \d|Partial cost coverage|CCost:")
                self.assertNotIn("mini_cost_detail_help", display)
                self.assertNotIn("ses_", help_text)
                self.assertNotIn("Linked subagents participated", help_text)
            groups = prompt["cost_detail"]["parts"]
            self.assertEqual(6, len(groups))
            self.assertEqual(D(509), sum(D(part["known_ccost"]) for part in groups))
        exported = export_block(block, details=True).to_json()
        self.assertEqual(expected, D(exported["total_ccost"]))

    def test_sessions_scalar_cache_preserves_recursive_role_totals_and_rejects_corruption(self):
        with recursive_source() as (source, _server):
            snapshot = source.load_session_snapshot("ses_current")
            bundle, block = self.project(snapshot)
            item = AnalyzedRoot(snapshot.root, bundle, False, snapshot)
            service = report_service(self, source, now_ms=20_000)
            with patch.object(service, "_load_catalog", return_value=catalog()), \
                    patch.object(service, "_load_comparison_catalog", return_value=catalog()), \
                    patch.object(service, "_analyze", return_value=item) as hydration:
                cold, revision = session_summary(service, snapshot.root, snapshot.source_revision)
                warm, _revision = session_summary(service, snapshot.root, revision)
                self.assertEqual(1, hydration.call_count)
                self.assertEqual(cold, warm)
                self.assertEqual((D(672), D(183), D(489), True),
                    (warm.ccost, warm.main_ccost, warm.subagent_ccost, warm.complete))
                cost = reconcile_session_cost(service.cache_repository, snapshot, catalog())
                card = WatchCard("ses_current", "Synthetic", "u1",
                    (WatchRow("ses_current", "Synthetic", block.rows[0]),), "observed",
                    session_cost=cost, session_duration_ms=warm.duration_ms)
                mini = project_live(WatchProjection("Watch", "Synthetic", (), now_ms=20_000,
                    active_cards=(card,))).to_json()["active_cards"][0]["session_summary"]
                sessions = project(ReportProjection(ReportKind.SESSIONS, "Sessions", "Synthetic",
                    session_usage=(warm,))).to_json()["session_usage"][0]
                self.assertEqual(D(672), sum(group.known_ccost for group in warm.cost_groups))
                self.assertEqual(warm.duration_ms, mini["duration_ms"])
                self.assertIsNotNone(warm.duration_ms)
                for name in ("mini_cost_models", "mini_cost_amounts"):
                    self.assertEqual(mini["cost"]["display"][name], sessions["display"][name])
                self.assertNotIn("mini_cost_groups", sessions)
                key = summary_key(service, snapshot.root)
                cached = service.cache_repository.get(NAMESPACE, key)
                service.cache_repository.put(NAMESPACE, key, dict(cached.payload, subagent_ccost="0"),
                    source_revision=revision, algorithm_version=ALGORITHM)
                rebuilt, _revision = session_summary(service, snapshot.root, revision)
                self.assertEqual(2, hydration.call_count)
                self.assertEqual(cold, rebuilt)
                for groups in ([], [dict(cached.payload["cost_groups"][0], known_ccost="-1")],
                        [dict(cached.payload["cost_groups"][0], selected_models=[42])]):
                    with self.subTest(groups=groups):
                        service.cache_repository.put(NAMESPACE, key, dict(cached.payload, cost_groups=groups),
                            source_revision=revision, algorithm_version=ALGORITHM)
                        before = hydration.call_count
                        repaired, _revision = session_summary(service, snapshot.root, revision)
                        self.assertEqual(before + 1, hydration.call_count)
                        self.assertEqual(cold, repaired)

    def test_response_without_tokens_is_observed_unpriced_call_not_a_zero_or_lost_child(self):
        with incident_source() as (source, server):
            del server.messages["ses_current_child"][1]["tokens"]
            snapshot = source.load_session_snapshot("ses_current")
        bundle, block = self.project(snapshot)
        self.assertEqual((3, D(122), True), (block.rows[0].calls, block.rows[0].ccost, block.rows[0].unresolved_cost))
        self.assertEqual((3, 2, False), (block.rows[0].comparison_cost.observed_requests,
            block.rows[0].comparison_cost.priced_requests, block.comparison_cost_complete))
        child = next(entry for entry in bundle.trace_entries if entry.session_id != "ses_current")
        self.assertEqual((), child.tokens.known_fields)
        self.assertFalse(comparison_cost((child,), catalog().reference_valuation).complete)
        self.assertIn("usage", {issue.reason for issue in block.rows[0].comparison_cost.unavailable})

    def test_empty_inactive_child_partial_acquisition_pending_and_missing_usage_are_distinct(self):
        with incident_source() as (source, server):
            server.messages["ses_current_child"] = []
            empty = source.load_session_snapshot("ses_current")
        for kind, changed, expected_state, complete in (
            ("no execution", empty, "not-executed", True),
            ("partial index", replace(empty, complete=False), "acquisition-pending", False),
            ("running", replace(empty, sessions=tuple(replace(session, active=True)
                if session.parent_session_id else session for session in empty.sessions)), "pending", False),
            ("unknown", replace(empty, sessions=tuple(replace(session, active=None)
                if session.parent_session_id else session for session in empty.sessions)), "usage-unavailable", False)):
            with self.subTest(kind=kind):
                bundle, block = self.project(changed)
                self.assertEqual(expected_state, bundle.prompts[0].agent_coverage[0].state)
                self.assertEqual(complete, block.comparison_cost_complete)
                self.assertEqual(D(122), block.total_ccost)
                self.assertEqual(not complete, block.rows[0].unresolved_cost)

    def test_recorded_zero_missing_tokens_unknown_model_and_late_repair_never_infer_spend(self):
        with incident_source() as (source, _server):
            snapshot = source.load_session_snapshot("ses_current")
        for usage, complete, child_cost in ((TokenUsage(), True, D(0)),
                (TokenUsage(known_fields=()), False, D(0)),
                (TokenUsage(input=1, known_fields=("input",)), False, D(".0002"))):
            changed = replace(snapshot, invocations=tuple(replace(request, tokens=usage)
                if request.session_id != "ses_current" else request for request in snapshot.invocations))
            _, block = self.project(changed)
            self.assertEqual((D(122) + child_cost, complete), (block.total_ccost, block.comparison_cost_complete))
        repaired = replace(snapshot, source_revision="later-observation")
        _, block = self.project(repaired)
        self.assertEqual((D(224), True), (block.total_ccost, block.comparison_cost_complete))

    def test_partial_known_subtotal_survives_cache_period_mix_and_later_repair(self):
        with incident_source() as (source, _server):
            snapshot = source.load_session_snapshot("ses_current")
        partial = replace(snapshot, source_revision="partial-counters", invocations=tuple(
            replace(request, tokens=replace(request.tokens, known_fields=("input",)))
            if request.session_id != snapshot.root.session_id else request for request in snapshot.invocations))
        bundle, block = self.project(partial)
        prices = catalog()
        cost = comparison_cost(bundle.trace_entries, prices.reference_valuation)
        period = PeriodCCostIndex(bundle.trace_entries, prices.reference_valuation).cost("github-copilot", "provider", 0, 20_000)
        mix = priced_token_mix(((entry.model, entry.tokens) for entry in bundle.trace_entries), prices.reference_category_valuation)
        self.assertEqual((D(142), False, 3), (cost.known_ccost, cost.complete, cost.priced_requests))
        self.assertEqual((D(142), False), (block.total_ccost, block.comparison_cost_complete))
        self.assertEqual((D(142), False), (period.known_ccost, period.complete))
        self.assertFalse(combined_cost((period,)).complete)
        self.assertEqual((D(142), False), (sum(mix.costs), mix.cost_complete))
        with tempfile.TemporaryDirectory() as directory:
            database = CacheDatabase(Path(directory)); database.initialize()
            repository = CacheRepository(database)
            for _ in range(2):
                cached = reconcile_session_cost(repository, partial, prices)
                self.assertEqual((D(142), False), (cached.total.known_ccost, cached.total.complete))
                self.assertEqual((D(122), D(20)), (cached.main_ccost, cached.subagent_ccost))
            repaired = reconcile_session_cost(repository, replace(snapshot, source_revision="complete-counters"), prices)
            self.assertEqual((D(224), True, 1), (repaired.total.known_ccost, repaired.total.complete, repaired.valued_requests))
        # Unknown input categories cannot select a tier. Unknown placeholder
        # numbers must never influence even a fixed-tier known-category subtotal.
        usage = TokenUsage(input=1, output=999_999, known_fields=("input",))
        self.assertEqual(D(".0001"), prices.reference_valuation(ModelRef("openai", "gpt-test"), usage))
        self.assertIsNone(threshold_catalog().reference_valuation(ModelRef("openai", "gpt-test"), usage))

    def test_repeated_physical_capture_prefers_complete_and_later_corrected_usage(self):
        with recursive_source() as (source, _server):
            entries = trace_entries(source.load_session_snapshot("ses_current"))
        child = next(entry for entry in entries if entry.session_id == "ses_current_child")
        revised = replace(child, tokens=TokenUsage(input=200_000))
        partial = replace(child, tokens=TokenUsage(known_fields=()))

        canonical = unique_usage((*entries, revised, partial))

        self.assertEqual(9, len(canonical))
        observed = next(entry for entry in canonical if entry.invocation_id == child.invocation_id
            and entry.session_id == child.session_id)
        self.assertEqual(revised.tokens, observed.tokens)


if __name__ == "__main__":
    unittest.main()
