"""Current subagent usage joins the initiating prompt, never a session residual."""
from decimal import Decimal as D
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import io
import tempfile
import unittest

from development.tests.fixtures.pricing_catalog import catalog, threshold_catalog
from development.tests.fixtures.session_snapshots import make_snapshot
from development.tests.fixtures.subagent_sessions import assistant, incident_source, link, user
from development.tests.fixtures.watch_runtime import MutableSource
from src.analysis import analyze_snapshot
from src.analysis.cache import AnalysisDependencies, DerivedAnalysisCache, analyze_with_cache
from src.analysis.causal import trace_entries
from src.analysis.session_cost import reconcile_session_cost
from src.analysis.valuation import comparison_cost
from src.application.live_projection import project_live
from src.application.projection import block as export_block
from src.cache import CacheDatabase, CacheRepository
from src.domain import ModelRef, TokenUsage
from src.presentation import ReportRenderer
from src.reports.models import ReportKind, ReportProjection
from src.reports.prompt_rows import PromptRowProjector
from src.reports.prompts import build_prompt_block
from src.watch.models import WatchCard, WatchProjection, WatchRow
from src.watch.tools import observe_tools


class SubagentAttributionTests(unittest.TestCase):
    def test_native_incident_includes_child_once_after_canonical_loading(self):
        with incident_source() as (source, _server):
            snapshot = source.load_session_snapshot("ses_current")
        prices = catalog()
        bundle = analyze_snapshot(snapshot, now_ms=20_000)
        self.assertEqual(1, len(bundle.prompts))
        record = bundle.prompts[0]
        row = PromptRowProjector(snapshot=snapshot, bundle=bundle, catalog=prices, config={}).prompt(record)
        total = comparison_cost(trace_entries(snapshot), prices.reference_valuation)

        self.assertEqual(3, record.model_calls)
        self.assertEqual(("ses_current_child",), record.linked_session_ids)
        self.assertEqual(D(224), row.ccost)  # main 2*(10+1+10+40), child 20+2+20+60
        self.assertEqual(total.ccost, row.ccost)
        self.assertEqual((D(21), D(203)), (row.incoming_context_ccost, row.extra_ccost))
        self.assertEqual(row.ccost, row.incoming_context_ccost + row.extra_ccost)
        self.assertEqual((D(122), D(102)), tuple(p.known_ccost for p in row.cost_parts))
        self.assertEqual(("high", "low"), tuple(p.variant for p in row.cost_parts))
        self.assertEqual(1, row.linked_agent_count)
        self.assertEqual((25, 25, 25, 25), row.token_mix_percent)
        self.assertEqual((("subagent", 1),), observe_tools(snapshot, "u1").tool_counts)

    def project(self, snapshot, prices=None):
        prices = prices or catalog()
        bundle = analyze_snapshot(snapshot, now_ms=20_000)
        block = build_prompt_block(session_id=snapshot.root.session_id, title="Synthetic", bundle=bundle,
            snapshot=snapshot, catalog=prices, config={}, snapshot_running_metrics=True)
        return bundle, block

    def test_report_cli_full_web_and_mini_share_corrected_cost_calls_models_and_mix(self):
        with incident_source() as (source, _server):
            snapshot = source.load_session_snapshot("ses_current")
        _, block = self.project(snapshot)
        row = block.rows[0]
        wire = export_block(block, details=True).to_json()
        card = WatchCard("ses_current", "Synthetic", "u1", (WatchRow("ses_current", "Synthetic", row),), "observed")
        live = project_live(WatchProjection("Watch", "Synthetic", (), now_ms=20_000,
            active_cards=(card,), history_cards=(replace(card, focal_id=""),))).to_json()
        for prompt in (wire["rows"][0], live["active_cards"][0]["rows"][0]["prompt"],
                       live["history_cards"][0]["rows"][0]["prompt"]):
            self.assertEqual((D(224), 3), (D(prompt["ccost"]), prompt["calls"]))
            self.assertTrue(prompt["has_additional_model"])
            self.assertEqual([25, 25, 25, 25], prompt["token_mix_percent"])
        displayed = live["active_cards"][0]["rows"][0]["prompt"]
        self.assertIn("Subagent 1 — Claude Test · Low", displayed["display"]["cost_detail_help"])
        self.assertIn("github-copilot/claude-test", displayed["display"]["model_detail_help"])
        self.assertIn("$2.24", displayed["display_units"]["usd"]["cost_detail_help"])
        stream = io.StringIO()
        ReportRenderer({}, stream=stream, color_enabled=False, terminal_width=180).render(
            ReportProjection(ReportKind.SESSION, "Synthetic", "v2", prompt_blocks=(block,)))
        self.assertIn("224", stream.getvalue())
        self.assertIn("*", stream.getvalue())
        self.assertEqual((D(224), 3), (block.total_ccost, block.total_calls))

    def test_multiple_nested_overlapping_and_duplicate_links_union_real_request_identities(self):
        with incident_source() as (source, server):
            duplicate = deepcopy(server.messages["ses_current"][1]["content"][0])
            overlapping = link(start=3250)
            overlapping.update(id="overlap", callID="overlap-call")
            sibling = link(child="ses_sibling", start=3250)
            sibling.update(id="sibling", callID="sibling-call")
            server.messages["ses_current"][1]["content"].extend((duplicate, overlapping, sibling))
            nested = link(child="ses_nested", start=3450, end=3700)
            server.messages["ses_current_child"][1]["content"] = [nested]
            template = server.sessions[1]
            server.sessions.extend(({**template, "id": "ses_sibling"},
                                    {**template, "id": "ses_nested", "parentID": "ses_current_child"}))
            server.messages["ses_sibling"] = [user("su", 3300), assistant("sa", 3400, 3800, model="claude-test")]
            server.messages["ses_nested"] = [user("nu", 3500), assistant("na", 3550, 3600)]
            snapshot = source.load_session_snapshot("ses_current")
        bundle, block = self.project(snapshot)
        record = bundle.prompts[0]
        self.assertEqual(5, record.model_calls)
        self.assertEqual(3, len(record.linked_session_ids))
        self.assertEqual(D(387), block.total_ccost)
        self.assertEqual(5, len({(entry.session_id, entry.message_id) for entry in record.entries}))
        self.assertEqual(block.total_ccost, comparison_cost(trace_entries(snapshot), catalog().reference_valuation).ccost)
        self.assertEqual(4, observe_tools(snapshot, "u1").tool_count)

    def test_background_child_belongs_to_initiator_across_new_prompt_and_late_completion(self):
        with incident_source(background=True, end=3250) as (source, server):
            server.messages["ses_current"].insert(2, user("u2", 3500))
            server.messages["ses_current_child"][1]["time"]["completed"] = 4800
            # Replayed launch data in a newer prompt cannot steal the old call.
            server.messages["ses_current"][4]["content"] = [link(background=True, end=3250)]
            snapshot = source.load_session_snapshot("ses_current")
        bundle, block = self.project(snapshot)
        self.assertEqual({"u1": 2, "u2": 1}, {record.prompt_id: record.model_calls for record in bundle.prompts})
        first, second = bundle.prompts
        self.assertEqual(("ses_current_child",), first.linked_session_ids)
        self.assertEqual((), second.linked_session_ids)
        self.assertEqual(1800, first.execution_duration_ms)
        self.assertEqual(4800, first.terminal_time_ms)
        self.assertEqual((D(163), D(61)), tuple(row.ccost for row in block.rows))

    def test_nested_background_child_can_finish_after_its_foreground_parent_returns(self):
        with incident_source() as (source, server):
            server.sessions.append({**server.sessions[1], "id": "ses_nested", "parentID": "ses_current_child"})
            server.messages["ses_current_child"][1]["content"] = [link(
                child="ses_nested", start=3450, end=3500, background=True)]
            server.messages["ses_nested"] = [user("nu", 3500), assistant("na", 4200, 4400)]
            snapshot = source.load_session_snapshot("ses_current")
        bundle, block = self.project(snapshot)
        self.assertEqual((4, 2, D(285)),
            (bundle.prompts[0].model_calls, len(bundle.prompts[0].linked_session_ids), block.total_ccost))
        self.assertEqual(block.total_ccost, comparison_cost(trace_entries(snapshot), catalog().reference_valuation).ccost)

    def test_running_children_created_during_prompt_then_terminal_updates_duration(self):
        with incident_source(end=0) as (source, server):
            server.sessions[1]["time"]["created"] = 3300
            server.active = {"ses_current_child": {"type": "running"}}
            server.messages["ses_current"] = server.messages["ses_current"][:2]
            server.messages["ses_current_child"][1] = assistant("ca", 3400, None, model="claude-test")
            running = source.load_session_snapshot("ses_current")
            record = analyze_snapshot(running, now_ms=4700).prompts[0]
            self.assertTrue(record.in_progress)
            self.assertFalse(analyze_snapshot(running, now_ms=4700).cacheable)
            self.assertEqual(1700, record.execution_duration_ms)
            server.active = {}
            server.sessions[1]["time"]["updated"] = 5200
            server.messages["ses_current_child"][1] = assistant("ca", 3400, 5000, model="claude-test")
            server.messages["ses_current"][1]["content"] = [link(end=5200)]
            server.messages["ses_current"].extend((user("notice", 5300, "done", "synthetic"),
                                                  assistant("a2", 5400, 5500)))
            finished = source.load_session_snapshot("ses_current")
        record = analyze_snapshot(finished, now_ms=20_000).prompts[0]
        self.assertFalse(record.in_progress)
        self.assertTrue(record.completed_successfully)
        self.assertEqual((3, 2500, 5500), (record.model_calls, record.execution_duration_ms, record.terminal_time_ms))

    def test_reusing_a_background_child_opens_a_new_window_without_cross_prompt_charges(self):
        with incident_source(background=True, end=3250) as (source, server):
            server.messages["ses_current"].extend((user("u2", 4900),
                assistant("b1", 5000, 6100, content=[{**link(start=5100, end=6000),
                    "id": "new-link", "callID": "new-call"}])))
            server.messages["ses_current_child"].extend((user("cu2", 5200),
                assistant("ca2", 5300, 5500, model="claude-test")))
            snapshot = source.load_session_snapshot("ses_current")
        bundle, block = self.project(snapshot)
        self.assertEqual((3, 2), tuple(record.model_calls for record in bundle.prompts))
        self.assertEqual((D(224), D(163)), tuple(row.ccost for row in block.rows))
        assigned = [(entry.session_id, entry.message_id) for record in bundle.prompts for entry in record.entries]
        self.assertEqual(len(assigned), len(set(assigned)))

    def test_cache_algorithm_and_late_source_revision_rebuild_both_views_without_residuals(self):
        with incident_source() as (source, _server):
            snapshot = source.load_session_snapshot("ses_current")
        early = replace(snapshot, invocations=tuple(i for i in snapshot.invocations if i.session_id == "ses_current"),
            source_revision="early")
        source = MutableSource(early)
        deps = AnalysisDependencies("cfg", "price")
        with tempfile.TemporaryDirectory() as directory:
            database = CacheDatabase(Path(directory)); database.initialize()
            repo = CacheRepository(database)
            cache = DerivedAnalysisCache(repo)
            analyze_with_cache(source, early.root, cache, AnalysisDependencies("cfg", "price", "v78-analysis-15-linked-agent-evidence"), analyze_snapshot)
            rebuilt = analyze_with_cache(source, early.root, cache, deps, analyze_snapshot)
            self.assertFalse(rebuilt.cache_hit)
            before = reconcile_session_cost(repo, early, catalog())
            source.snapshot = replace(snapshot, source_revision="late")
            after = analyze_with_cache(source, snapshot.root, cache, deps, analyze_snapshot)
            total = reconcile_session_cost(repo, source.snapshot, catalog())
            repeated = analyze_with_cache(source, snapshot.root, cache, deps, analyze_snapshot)
            self.assertFalse(after.cache_hit)
            self.assertTrue(repeated.cache_hit)
            self.assertEqual((2, 3), (rebuilt.bundle.prompts[0].model_calls, after.bundle.prompts[0].model_calls))
            self.assertEqual((D(122), D(224), 1), (before.total.ccost, total.total.ccost, total.valued_requests))
            self.assertEqual(after.bundle, repeated.bundle)

    def test_zero_unknown_and_partial_children_keep_honest_reference_coverage_and_billing(self):
        with incident_source() as (source, _server):
            snapshot = source.load_session_snapshot("ses_current")
        for kind in ("zero", "unpriced", "partial"):
            invocations = []
            for invocation in snapshot.invocations:
                if invocation.session_id == "ses_current_child":
                    changes = {"tokens": TokenUsage()} if kind == "zero" else (
                        {"model": ModelRef("github-copilot", "unpriced")} if kind == "unpriced" else
                        {"tokens": replace(invocation.tokens, known_fields=("input",))})
                    invocation = replace(invocation, **changes)
                invocations.append(invocation)
            changed = replace(snapshot, invocations=tuple(invocations))
            _, block = self.project(changed)
            row = block.rows[0]
            with self.subTest(kind=kind):
                self.assertEqual((3, 1), (row.calls, row.linked_agent_count))
                self.assertEqual(kind == "unpriced", row.unresolved_cost)
                self.assertEqual(kind != "partial", row.token_mix_percent is not None)
                self.assertIsNone(row.billed_cost)  # native zero is not reference billing
                self.assertEqual(D(122) if kind in {"zero", "unpriced"} else D(224), row.ccost)

    def test_child_uses_its_own_price_tier_even_when_it_shares_the_parent_model(self):
        with incident_source() as (source, _server):
            snapshot = source.load_session_snapshot("ses_current")
        invocations = tuple(replace(i, model=ModelRef("github-copilot", "gpt-test"),
            tokens=TokenUsage(input=100001, output=1000)) if i.session_id == "ses_current_child" else i
            for i in snapshot.invocations)
        _, block = self.project(replace(snapshot, invocations=invocations), threshold_catalog())
        row = block.rows[0]
        self.assertEqual((D(244), D("20.8002"), D("264.8002")), (row.main_ccost, row.subagent_ccost, row.ccost))
        self.assertEqual(("high", "low"), tuple(p.variant for p in row.cost_parts))

    def test_child_usage_without_a_recorded_parent_request_is_not_dropped_or_relabelled(self):
        with incident_source() as (source, _server):
            snapshot = source.load_session_snapshot("ses_current")
        child_only = replace(snapshot, invocations=tuple(i for i in snapshot.invocations if i.session_id != "ses_current"))
        bundle, block = self.project(child_only)
        record = bundle.prompts[0]
        self.assertEqual((1, 0, "gpt-test"), (record.model_calls, record.root_entry_count, record.main_model_id))
        self.assertEqual((D(0), D(102)), (block.rows[0].main_ccost, block.rows[0].subagent_ccost))

    def test_legitimate_unallocatable_and_compaction_residuals_are_not_assigned_to_prompt(self):
        with incident_source() as (source, server):
            server.messages["ses_current_child"].append(assistant("unassigned", 6000, 6200, model="claude-test"))
            snapshot = source.load_session_snapshot("ses_current")
        _, block = self.project(snapshot)
        self.assertEqual(D(224), block.rows[0].ccost)
        self.assertEqual(D(326), comparison_cost(trace_entries(snapshot), catalog().reference_valuation).ccost)
        legacy = make_snapshot()
        bundle, block = self.project(legacy)
        prompt_cost = sum(row.ccost for row in block.rows if not row.is_compaction)
        compact_cost = sum(row.ccost for row in block.rows if row.is_compaction)
        self.assertGreater(compact_cost, 0)
        self.assertEqual(block.total_ccost, prompt_cost + compact_cost)


if __name__ == "__main__":
    unittest.main()
