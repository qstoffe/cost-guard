"""Executed main model, role help and disposable scalar migration regressions."""
from dataclasses import replace
from decimal import Decimal
import unittest
from unittest.mock import patch

from development.tests.fixtures.compact_reports import report_service
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from development.tests.fixtures.claude_alias import desktop_service, snapshot as alias_snapshot
from src.application.projection import project
from src.application.session_catalog import ordered
from src.domain import ModelRef, TokenUsage
from src.reports.models import ReportKind, ReportProjection, SessionUsageRow
from src.reports.session_summary import ALGORITHM, NAMESPACE, session_summary, summary_key


class SessionModelTests(unittest.TestCase):
    def setUp(self):
        self.source = SyntheticMonthSource(1, 2, month_start_ms=1000)
        saved = self.source.snapshots["root-0000"]
        self.source.snapshots[saved.root.session_id] = replace(saved, complete=True)
        self.service = report_service(self, self.source, now_ms=100_000)
        self.item = self.service._analyze(saved.root, detail=True)
        self.entry = self.item.bundle.trace_entries[0]

    def row(self, main, children=(), *, saved=False, snapshot=True, partial=False, extra=()):
        prompts, entries = [], []
        for index, model in enumerate(main):
            entry = replace(self.entry, model=ModelRef("provider", model), message_id=f"main-{index}",
                            completed_at_ms=100 + index, reported_cost=Decimal(100 if index == 0 else 1))
            entries.append(entry)
            prompts.append(replace(self.item.bundle.prompts[0], prompt_id=f"prompt-{index}",
                prompt_time_ms=index, entries=(entry,), main_model_id=model))
        for index, model in enumerate(children):
            entries.append(replace(self.entry, model=ModelRef("provider", model), session_id="child",
                message_id=f"child-{index}", completed_at_ms=1000 + index))
        if saved:
            prompts.append(replace(self.item.bundle.prompts[0], prompt_id="pending", prompt_time_ms=100,
                entries=(), main_model_id="never-used", in_progress=True))
        root = self.item.session
        child = replace(root, session_id="child", parent_session_id=root.session_id)
        source = replace(self.item.snapshot, sessions=(root, child), complete=not partial) if snapshot else None
        if not snapshot:
            prompts = [replace(p, linked_session_ids=("child",)) for p in prompts]
        bundle = replace(self.item.bundle, trace_entries=tuple(entries) + tuple(extra), prompts=tuple(prompts))
        item = replace(self.item, bundle=bundle, snapshot=source)
        return self.service._session_rows((item,), catalog_models=True)[0]

    def wire(self, row):
        return project(ReportProjection(ReportKind.SESSIONS, "Sessions", "OpenCode",
            session_usage=(row,)), "UTC").to_json()["session_usage"][0]

    def test_required_matrix_latest_used_main_not_cost_or_last_child(self):
        cases = (
            (("A",), (), "Claude Test", False, ("A",), ()),
            (("A", "B"), (), "B", True, ("A", "B"), ()),
            (("A",), ("C",), "Claude Test", True, ("A",), ("C",)),
            (("A", "B"), ("B", "C"), "B", True, ("A", "B"), ("B", "C")),
            (("A",), ("A",), "Claude Test", False, ("A",), ("A",)),
            ((), ("C",), "N/A", False, (), ("C",)),
        )
        for main, children, name, mixed, expected_main, expected_child in cases:
            with self.subTest(main=main, children=children):
                row = self.row(main, children)
                wire = self.wire(row)
                self.assertEqual((name, mixed), (row.model, row.multiple_models))
                self.assertEqual(expected_main, tuple(p.model for p in row.main_models))
                self.assertEqual(expected_child, tuple(p.model for p in row.subagent_models))
                help_text = wire["display"]["model_help"]
                self.assertEqual(bool(main), "Main models used in session" in help_text)
                self.assertEqual(bool(children), "Sub-agents used in session" in help_text)
                if main and children:
                    self.assertIn("\n\nSub-agents used in session\n• ", help_text)
                self.assertNotIn("trace_entries", wire)

    def test_pending_saved_unknown_and_failed_zero_selection_do_not_replace_used_model(self):
        pending = self.row(("A",), ("C",), saved=True)
        self.assertEqual(("Claude Test", True, False), (pending.model, pending.multiple_models, pending.contributor_models_complete))
        self.assertIn("Observed so far", self.wire(pending)["display"]["model_help"])
        empty = self.row((), ("C",), saved=True)
        self.assertEqual(("N/A", True), (empty.model, empty.model_pending))
        failed = replace(self.entry, model=ModelRef("p", "unexecuted"), tokens=TokenUsage(),
                         reported_cost=Decimal(0), error_name="provider-error", message_id="failed")
        self.assertFalse(self.row(("A",), extra=(failed,)).multiple_models)
        unknown = replace(self.entry, model=ModelRef("", ""), message_id="unknown")
        self.assertFalse(self.row(("A",), extra=(unknown,)).contributor_models_complete)

    def test_compaction_and_unrelated_root_cannot_be_the_representative(self):
        compact = replace(self.entry, summary=True, model=ModelRef("p", "compact"),
                          message_id="compact", completed_at_ms=9000)
        foreign = replace(self.entry, session_id="unrelated-root", model=ModelRef("p", "foreign"),
                          message_id="foreign")
        row = self.row(("A", "B"), extra=(compact, foreign))
        self.assertEqual("B", row.model)
        self.assertEqual(("A", "B", "compact"), tuple(p.model for p in row.main_models))
        self.assertNotIn("p/foreign", row.contributor_models)
        self.assertFalse(row.contributor_models_complete)

    def test_dedup_provider_identity_and_recorded_alias_not_effective_pricing_identity(self):
        other = replace(self.entry, model=ModelRef("other", "A"), message_id="other")
        row = self.row(("A", "A"), extra=(other, other))
        self.assertTrue(row.multiple_models)
        self.assertEqual(("provider/A", "other/A"), tuple(f"{p.provider}/{p.model}" for p in row.main_models))
        self.assertIn("• other/A", self.wire(row)["display"]["model_help"])

    def test_partial_compact_running_and_truncated_evidence_remain_qualified(self):
        for options in (dict(partial=True), dict(snapshot=False), dict(saved=True)):
            row = self.row(("A",), ("C",), **options)
            self.assertFalse(row.contributor_models_complete)
            self.assertIn("Observed so far", self.wire(row)["display"]["model_help"])
        many = self.row(tuple(f"m{i}" for i in range(70)))
        self.assertEqual("m69", many.model)
        self.assertEqual(64, len(many.main_models))
        self.assertFalse(many.contributor_models_complete)

    def test_resolved_alias_raw_identity_and_default_effort_survive_role_help(self):
        service = desktop_service(self, (alias_snapshot(),))
        root = service.source.list_sessions()[0]
        item = service._analyze(root, detail=True)
        entry = item.bundle.trace_entries[0]
        pinned = replace(entry, model=ModelRef("claude-agent", "claude-sonnet-5-5"), message_id="pinned")
        item = replace(item, bundle=replace(item.bundle, trace_entries=(entry, pinned)))
        row = service._session_rows((item,), catalog_models=True)[0]
        text = self.wire(row)["display"]["model_help"]
        self.assertTrue(row.multiple_models)
        self.assertIn("• claude-agent/sonnet", text)
        self.assertIn("• claude-agent/claude-sonnet-5-5", text)
        self.assertIn("Catalog modelID: claude-sonnet-5-5", text)
        self.assertIn("historic executed version unconfirmed", text)
        self.assertNotIn("*", text)

    def test_sort_ignores_star_and_keeps_unknown_last_and_id_ties_both_directions(self):
        rows = tuple(SessionUsageRow(key, key, model, mixed, Decimal(0), 1)
            for key, model, mixed in (("b", "Alpha", True), ("a", "Alpha", False),
                                     ("c", "Zulu", False), ("d", "N/A", True)))
        self.assertEqual(["a", "b", "c", "d"], [r.session_id for r in ordered(rows, "model", 1)])
        self.assertEqual(["c", "a", "b", "d"], [r.session_id for r in ordered(rows, "model", -1)])

    def test_old_missing_and_malformed_role_cache_is_rehydrated_and_revision_updates_together(self):
        root, revision = self.item.session, self.item.bundle.source_revision
        original, _ = session_summary(self.service, root, revision)
        key = summary_key(self.service, root)
        cached = self.service.cache_repository.get(NAMESPACE, key)
        with patch.object(self.service, "_analyze", side_effect=AssertionError("warm hydration")):
            self.assertEqual(original, session_summary(self.service, root, revision)[0])
        missing = dict(cached.payload)
        missing.pop("main_models")
        malformed = dict(cached.payload, main_models=[{"provider": "p"}])
        wrong_star = dict(cached.payload, multiple_models=not cached.payload["multiple_models"])
        for payload, algorithm in ((cached.payload, "session-summary-5"), (missing, ALGORITHM),
                                   (malformed, ALGORITHM), (wrong_star, ALGORITHM)):
            self.service.cache_repository.put(NAMESPACE, key, payload, source_revision=revision, algorithm_version=algorithm)
            with patch.object(self.service, "_analyze", wraps=self.service._analyze) as analyze:
                self.assertEqual(original, session_summary(self.service, root, revision)[0])
            self.assertEqual(1, analyze.call_count)
        updated = replace(self.item.snapshot, source_revision="new-model",
            invocations=tuple(replace(i, model=ModelRef("other", "New")) for i in self.item.snapshot.invocations))
        self.source.snapshots[root.session_id] = updated
        current, actual = session_summary(self.service, root, "new-model")
        self.assertEqual(("new-model", "New"), (actual, current.model))
        self.assertIn("• other/New", self.wire(current)["display"]["model_help"])
        self.assertNotIn("github-copilot/gpt-test", self.wire(current)["display"]["model_help"])


if __name__ == "__main__":
    unittest.main()
