"""Whole-session selected effort is independent of primary model and cost."""
from dataclasses import replace
from decimal import Decimal
import unittest
from unittest.mock import patch

from development.tests.fixtures.compact_reports import report_service
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from src.application.projection import project
from src.application.session_catalog import SessionCatalog, ordered
from src.domain import ModelRef, TokenUsage
from src.domain.effort import DefaultEffort
from src.reports.models import ReportKind, ReportProjection, SessionUsageRow
from src.reports.session_summary import ALGORITHM, NAMESPACE, session_summary, summary_key
from src.watch.observers import observe_catalog


class SessionEffortTests(unittest.TestCase):
    def setUp(self):
        self.source = SyntheticMonthSource(1, 1, month_start_ms=1000)
        snapshot = self.source.snapshots["root-0000"]
        self.source.snapshots["root-0000"] = replace(snapshot, complete=True)
        self.service = report_service(self, self.source, now_ms=100_000)
        self.item = self.service._analyze(snapshot.root, detail=True)
        self.entry = replace(self.item.bundle.trace_entries[0], selected_effort="default",
                             model=ModelRef("openai", "gpt-6.1-sol"))

    def row(self, entries, **changes):
        bundle = replace(self.item.bundle, trace_entries=tuple(entries), **changes)
        return self.service._session_rows((replace(self.item, bundle=bundle),))[0]

    def test_one_selection_across_models_default_and_explicit_are_not_effective_guesses(self):
        default = self.row((self.entry,))
        explicit = self.row((replace(self.entry, selected_effort="high"),))
        same_effort = self.row((replace(self.entry, selected_effort="high"),
            replace(self.entry, selected_effort="high", model=ModelRef("other", "other-model"), message_id="other")))
        self.assertEqual((default.effort, default.effort_key), ("Default", "default"))
        self.assertEqual((explicit.effort, explicit.effort_key), ("High", "high"))
        self.assertEqual(same_effort.effort, "High")
        self.assertTrue(same_effort.multiple_models)
        exported = project(ReportProjection(ReportKind.SESSIONS, "Sessions", "OpenCode",
            session_usage=(default,)), "UTC").to_json()["session_usage"][0]
        self.assertEqual(exported["effort"], "Default")
        self.assertIn("openai/gpt-6.1-sol: default (medium)*", exported["effort_help"])
        self.assertIn("Defaults may change", exported["effort_help"])
        self.assertNotIn("*", exported["display"]["model_help"])
        self.assertNotIn("trace_entries", exported)

    def test_default_and_explicit_high_remain_multiple_even_when_default_request_is_high(self):
        selected_default = replace(self.entry, variant="high")
        mixed = self.row((selected_default, replace(self.entry, selected_effort="high", message_id="second")))
        self.assertEqual((mixed.effort, mixed.effort_key), ("Multiple efforts", "multiple"))
        self.assertFalse(mixed.multiple_models)
        self.assertEqual({part.evidence.selected for part in mixed.effort_contributors}, {"default", "high"})
        report = ReportProjection(ReportKind.SESSIONS, "Sessions", "OpenCode", session_usage=(mixed,))
        help_text = project(report, "UTC").to_json()["session_usage"][0]["effort_help"]
        self.assertIn("default (high)*", help_text)
        self.assertIn("Observed in the recorded request", help_text)
        self.assertIn("openai/gpt-6.1-sol: high", help_text)

    def test_child_compaction_unknown_and_failed_saved_selection_have_honest_coverage(self):
        child = replace(self.entry, selected_effort="low", session_id="child", message_id="child-response",
                        model=ModelRef("anthropic", "claude-sonnet-5-5"))
        row = self.row((self.entry, child))
        self.assertEqual(row.effort, "Multiple efforts")
        self.assertEqual({(part.provider, part.model) for part in row.effort_contributors},
                         {("openai", "gpt-6.1-sol"), ("anthropic", "claude-sonnet-5-5")})
        compaction = replace(child, summary=True, selected_effort=None, variant=None)
        self.assertEqual(self.row((self.entry, compaction)).effort, "N/A")
        failed = replace(self.entry, selected_effort="xhigh", tokens=TokenUsage(), error_name="aborted",
                         message_id="failed-attempt", invocation_id="failed-attempt")
        self.assertEqual(self.row((failed,)).effort, "N/A")
        self.assertEqual(self.row((self.entry, failed)).effort, "Default")
        pending = self.row((), prompts=(replace(self.item.bundle.prompts[0], in_progress=True),))
        self.assertTrue(pending.effort_pending)
        self.assertEqual(pending.effort, "N/A")

    def test_effort_sort_selected_levels_ties_mixed_and_unknown_last_both_directions(self):
        rows = tuple(SessionUsageRow(key, key, "Model", False, Decimal(0), 1, effort_key=effort)
            for key, effort in (("a", "high"), ("b", "default"), ("c", "low"), ("d", None),
                                ("e", "multiple"), ("f", "high")))
        self.assertEqual([row.session_id for row in ordered(rows, "effort", 1)], ["c", "a", "f", "b", "e", "d"])
        self.assertEqual([row.session_id for row in ordered(rows, "effort", -1)], ["e", "b", "a", "f", "c", "d"])

    def test_breakdown_bound_retains_exact_selected_scalar_and_partial_source_is_unqualified(self):
        many = self.row(tuple(replace(self.entry, model=ModelRef("provider", f"model-{index}"),
                                     selected_effort="high", message_id=f"response-{index}") for index in range(40)))
        self.assertEqual(many.effort, "High")
        self.assertEqual(len(many.effort_contributors), 24)
        self.assertFalse(many.effort_details_complete)
        partial = replace(self.item, snapshot=replace(self.item.snapshot, complete=False))
        self.assertFalse(self.service._session_rows((partial,))[0].effort_qualified)

    def test_versioned_cache_roundtrip_rejects_missing_corrupt_and_old_effort_fields(self):
        root = self.item.session
        revision = self.item.bundle.source_revision
        original, _ = session_summary(self.service, root, revision)
        key = summary_key(self.service, root)
        cached = self.service.cache_repository.get(NAMESPACE, key)
        self.assertEqual(original.effort, "Default")
        with patch.object(self.service, "_analyze", side_effect=AssertionError("warm hydration")):
            self.assertEqual(session_summary(self.service, root, revision)[0], original)
        missing = dict(cached.payload)
        missing.pop("effort")
        corrupt = dict(cached.payload, effort="High")
        malformed = dict(cached.payload, effort_contributors=[{"provider": "p"}])
        for values, version in ((missing, ALGORITHM), (corrupt, ALGORITHM), (malformed, ALGORITHM),
                                (cached.payload, "session-summary-4")):
            self.service.cache_repository.put(NAMESPACE, key, values, source_revision=revision,
                                               algorithm_version=version)
            with patch.object(self.service, "_analyze", wraps=self.service._analyze) as analyze:
                rebuilt, _ = session_summary(self.service, root, revision)
            self.assertEqual(analyze.call_count, 1)
            self.assertEqual(rebuilt, original)

    def test_source_default_change_revalidates_in_memory_and_cached_effort_without_history_change(self):
        catalog = SessionCatalog(clock_ms=lambda: 100_000)
        catalog.observe(observe_catalog(self.source, include_archived_revisions=True))
        first = catalog.page(sort="effort")
        observed = DefaultEffort("synthetic-location", "gpt-6.1-sol", "gpt-6.1-sol",
            "@opencode/ai/providers/openai", "low", "source-catalog", "catalog-1")

        def analyze(*_args, **_kwargs):
            entry = replace(self.entry, model=replace(self.entry.model, effort_default=observed))
            return replace(self.item, bundle=replace(self.item.bundle, trace_entries=(entry,)))

        def current(models):
            return all(model.effort_default.signature == observed.signature for model in models)

        with patch.object(self.source, "model_identities_current", side_effect=current, create=True), \
                patch.object(self.service, "_analyze", side_effect=analyze) as hydration:
            catalog.tick(self.service)
            initial = catalog.page(token=first["token"], sort="effort")
            self.assertIn("default (low)*", initial["view"]["session_usage"][0]["effort_help"])
            catalog.tick(self.service)
            self.assertEqual(hydration.call_count, 1, "unchanged source default reuses the scalar")

            observed = replace(observed, level="high", signature="catalog-2")
            catalog.observe(observe_catalog(self.source, include_archived_revisions=True))
            catalog.tick(self.service)
            updated = catalog.page(token=first["token"], sort="effort")

        row = updated["view"]["session_usage"][0]
        self.assertEqual(hydration.call_count, 2, "only the dependent root is rebuilt")
        self.assertEqual(row["effort"], "Default")
        self.assertIn("default (high)*", row["effort_help"])
        self.assertNotIn("default (low)*", row["effort_help"])
        self.assertFalse(updated["pending_sort"])


if __name__ == "__main__":
    unittest.main()
