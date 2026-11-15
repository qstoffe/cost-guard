"""Independent root/prompt marker truth table without altering cost/model counts."""
from dataclasses import replace
from decimal import Decimal
import unittest

from development.tests.fixtures.compact_reports import report_service
from development.tests.fixtures.model_details import model_details_snapshot
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from src.application.projection import project
from src.application.session_catalog import retain_pending_metrics
from src.domain import ModelRef, TokenUsage
from src.reports.model_details import has_model_details
from src.reports.models import ReportKind, ReportProjection


class ModelDetailsTests(unittest.TestCase):
    def test_native_v2_linked_sol_children_share_the_cross_view_marker_without_inventing_models(self):
        from development.tests.fixtures.model_subagent_history import native_tree, PRICES, NOW
        from development.tests.fixtures.watch_runtime import MutableSource
        for effort in ("high", "max"):
            with self.subTest(child_effort=effort):
                snapshot = native_tree(child_effort=effort)
                service = report_service(self, MutableSource(snapshot), now_ms=NOW)
                service.pricing_provider.catalog = PRICES
                item = service._analyze(snapshot.root, detail=True)

                summary = service._session_rows((item,), catalog_models=True)[0]
                block = service._prompt_block(item)

                self.assertFalse(summary.multiple_models)
                self.assertTrue(summary.has_model_details)
                self.assertEqual(1, summary.linked_agent_count)
                self.assertTrue(block.rows[0].has_model_details)
                self.assertEqual(1, block.rows[0].linked_agent_count)
                self.assertEqual({"ses_current_child"}, set(item.bundle.prompts[0].linked_session_ids))

    def test_cross_view_truth_table_uses_normalized_causal_child_and_prompt_scopes(self):
        cases = (
            ("one", False, False, False, False),
            ("child-same", True, True, False, False),
            ("child-effort", True, True, False, False),
            ("child-model", True, True, False, True),
            ("main-models", True, True, False, True),
            ("main-efforts", True, True, False, False),
            ("separate-efforts", True, False, False, False),
            ("running-child", True, True, False, False),
            ("unknown-main", True, True, False, False),
        )
        for case, root_marker, first_marker, next_marker, multiple_models in cases:
            with self.subTest(case=case):
                snapshot = model_details_snapshot(case)
                source = SyntheticMonthSource(0, 0, month_start_ms=1000)
                source.snapshots = {"root": snapshot}
                service = report_service(self, source, now_ms=4000)
                item = service._analyze(snapshot.root, detail=True)

                summary = service._session_rows((item,), catalog_models=True)[0]
                block = service._prompt_block(item)
                wire = project(ReportProjection(ReportKind.SESSION, "Session", "Synthetic",
                    session_usage=(summary,), prompt_blocks=(block,)), "UTC", prompt_details=True).to_json()

                self.assertEqual(root_marker, summary.has_model_details)
                self.assertEqual(multiple_models, summary.multiple_models)
                prompts = {row.event_id: row for row in block.rows}
                self.assertEqual(first_marker, prompts["u_sub"].has_model_details)
                if "u_next" in prompts:
                    self.assertEqual(next_marker, prompts["u_next"].has_model_details)
                self.assertEqual(root_marker, wire["session_usage"][0]["has_model_details"])
                details = wire["prompt_blocks"][0]["rows"][0]
                self.assertEqual(first_marker, details["has_model_details"])
                help_text = details["display"]["model_detail_help"]
                if case in {"child-same", "child-effort", "child-model"}:
                    self.assertIn("Subagent 1", help_text)
                    self.assertIn("Main prompt", help_text)
                    self.assertIn("High", help_text)
                if case in {"child-effort", "main-efforts"}:
                    self.assertIn("Max", help_text)
                if case == "unknown-main":
                    self.assertEqual("N/A", summary.model)
                self.assertEqual(sum((row.ccost for row in block.rows), Decimal(0)), block.total_ccost)

    def test_selected_effort_not_vendor_defaults_saved_choices_or_duplicate_failed_usage(self):
        snapshot = model_details_snapshot("one")
        source = SyntheticMonthSource(0, 0, month_start_ms=1000)
        source.snapshots = {"root": snapshot}
        service = report_service(self, source, now_ms=4000)
        entry = service._analyze(snapshot.root, detail=True).bundle.trace_entries[0]
        first = replace(entry, selected_effort="High")
        same = replace(first, selected_effort="high", message_id="second")
        default = replace(first, selected_effort="Default", variant="medium")
        omitted = replace(first, selected_effort="", variant="medium", message_id="omitted")
        explicit = replace(first, selected_effort="medium", message_id="explicit")
        failed = replace(first, selected_effort="max", error_name="failed", tokens=TokenUsage(),
                         reported_cost=Decimal(0), message_id="failed", invocation_id="failed")
        alias = replace(first, model=replace(first.model, display_name="Other pretty alias"), message_id="alias")

        self.assertFalse(has_model_details((first, same, alias, failed, failed)))
        self.assertFalse(has_model_details((default, omitted)))
        self.assertTrue(has_model_details((default, explicit)))
        self.assertTrue(has_model_details((replace(first, model=ModelRef("other", "gpt-test"),
                                                  message_id="other"), first)))

    def test_last_good_indicator_is_retained_only_until_a_qualified_correction(self):
        source = SyntheticMonthSource(0, 0, month_start_ms=1000)
        snapshot = model_details_snapshot("child-same")
        source.snapshots = {"root": snapshot}
        service = report_service(self, source, now_ms=4000)
        item = service._analyze(snapshot.root, detail=True)
        previous = service._session_rows((item,), catalog_models=True)[0]
        missing = replace(previous, has_model_details=False, linked_agent_count=0, subagent_models=(),
                          contributor_models_complete=False)

        retained = retain_pending_metrics(missing, previous)
        corrected = retain_pending_metrics(replace(missing, contributor_models_complete=True), previous)

        self.assertTrue(retained.has_model_details)
        self.assertEqual(previous.subagent_models, retained.subagent_models)
        self.assertFalse(corrected.has_model_details)
