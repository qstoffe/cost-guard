"""Reason-specific CCost explanations preserve valuation, scope and snapshot evidence."""
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from development.tests.fixtures.pricing_catalog import catalog
from development.tests.fixtures.session_snapshots import make_uncompacted_snapshot
from src.analysis import analyze_snapshot
from src.analysis.session_cost import reconcile_session_cost
from src.application.display import with_display
from src.application.live_projection import project_live
from src.application.projection import comparison
from src.application.reference_cost import issue_records, unavailable_help
from src.cache.database import CacheDatabase
from src.cache.repository import CacheRepository
from src.domain import ModelRef, TokenUsage
from src.domain.reference_cost import ReferenceCostIssue, bounded_issues
from src.reports.prompt_rows import PromptRowProjector
from src.watch.models import WatchCard, WatchProjection, WatchRow


class CCostUnavailableTests(unittest.TestCase):
    def prices(self):
        return replace(catalog(), retrieved_at_ms=1000, source_revision="acquired-copilot")

    def row(self, prices, *, child="claude-sonnet-4", main="claude-sonnet-4", tokens=None):
        source = make_uncompacted_snapshot()
        snapshot = replace(source, invocations=tuple(replace(item,
            model=ModelRef("github-copilot", child if item.session_id == "child" else main),
            tokens=tokens if tokens is not None else item.tokens) for item in source.invocations))
        bundle = analyze_snapshot(snapshot, now_ms=4000)
        prompt = next(item for item in bundle.prompts if item.prompt_id == "u_sub")
        return snapshot, PromptRowProjector(snapshot=snapshot, bundle=bundle, catalog=prices,
            config={}, snapshot_running_metrics=True).prompt(prompt)

    def wire(self, row):
        card = WatchCard("root", "Synthetic", row.event_id, (WatchRow("root", "Synthetic", row),), "observed")
        return project_live(WatchProjection("Watch", "Synthetic", (), now_ms=4000,
            active_cards=(card,), history_cards=(replace(card, focal_id=""),))).to_json()

    def test_acquired_catalog_absence_names_sonnet_without_changing_na_or_units(self):
        _, row = self.row(self.prices())

        wire = self.wire(row)

        self.assertEqual(Decimal(0), row.ccost)
        self.assertTrue(row.unresolved_cost)
        for kind in ("active_cards", "history_cards"):
            display = wire[kind][0]["rows"][0]["prompt"]["display"]
            self.assertEqual("N/A", display["ccost"])
            self.assertIn("Claude Sonnet 4 has no listed reference price in the available GitHub Copilot", display["ccost_unavailable_help"])
            self.assertIn("N/A does not mean zero", display["ccost_unavailable_help"])
            self.assertIn("Claude Sonnet 4", display["cost_detail_help"])

    def test_identity_missing_rate_usage_and_catalog_are_not_list_absence(self):
        prices = self.prices()
        model = ModelRef("test", "gpt-test")
        missing_rate = replace(prices.models[0], tiers=(replace(prices.models[0].tiers[0], per_million_output=None),))
        cases = ((prices, ModelRef("test", "sonnet"), TokenUsage(input=100), "identity"),
            (replace(prices, models=(prices.models[0], prices.models[0])), model, TokenUsage(input=100), "identity"),
            (replace(prices, models=(missing_rate,)), model, TokenUsage(input=100), "rate"),
            (prices, model, TokenUsage(input=100, known_fields=("input",)), "usage"),
            (replace(prices, reference_stale=True), ModelRef("test", "claude-sonnet-4"), TokenUsage(input=100), "catalog"),
            (catalog(), ModelRef("test", "claude-sonnet-4"), TokenUsage(input=100), "catalog"))
        for current, identity, tokens, expected in cases:
            with self.subTest(expected=expected):
                issue = current.reference_issue(identity, tokens)
                text = unavailable_help(issue_records((issue,)))
                self.assertEqual(expected, issue.reason)
                self.assertNotIn("has no listed", text)
                if expected == "usage":
                    self.assertIn("cached input, cache write, output", text)
                if expected == "rate":
                    self.assertIn("output", text)

    def test_actual_contributors_not_main_model_and_positive_partial_stays_partial(self):
        _, mixed = self.row(self.prices(), main="gpt-test")
        _, unpriced = self.row(self.prices(), main="claude-opus-4")

        mixed_wire = self.wire(mixed)["active_cards"][0]["rows"][0]["prompt"]
        help_text = self.wire(unpriced)["active_cards"][0]["rows"][0]["prompt"]["display"]["ccost_unavailable_help"]

        self.assertGreater(mixed.ccost, 0)
        self.assertRegex(mixed_wire["display"]["ccost"], r"^[<\d]")
        self.assertTrue(mixed_wire["unresolved_cost"])
        self.assertEqual((ReferenceCostIssue("model_absent", "Claude Sonnet 4"),), mixed.comparison_cost.unavailable)
        self.assertIn("Claude Opus 4", help_text)
        self.assertIn("Claude Sonnet 4", help_text)

    def test_refresh_and_retained_session_reconcile_reason_without_persisting_diagnostics(self):
        prices = self.prices()
        snapshot, row = self.row(prices)
        snapshot = replace(snapshot, complete=True)
        # Disposable cache; the same unchanged source is reconciled twice.
        with tempfile.TemporaryDirectory() as directory:
            database = CacheDatabase(Path(directory))
            database.initialize()
            repository = CacheRepository(database)
            first = reconcile_session_cost(repository, snapshot, prices)
            retained = reconcile_session_cost(repository, snapshot, prices)
            stale = reconcile_session_cost(repository, snapshot, replace(prices, reference_stale=True))

        self.assertEqual(first.total.unavailable, retained.total.unavailable)
        self.assertEqual(0, retained.valued_requests)
        self.assertEqual("catalog", stale.total.unavailable[0].reason)
        self.assertEqual(first.total.known_ccost, stale.total.known_ccost)
        frozen = with_display(comparison(row.comparison_cost)).to_json()
        self.assertIn("Claude Sonnet 4", frozen["display"]["ccost_unavailable_help"])

    def test_verified_zero_known_cost_and_fallback_have_no_fabricated_missing_model(self):
        _, zero = self.row(self.prices(), tokens=TokenUsage())
        _, known = self.row(self.prices(), main="gpt-test", child="gpt-test")

        self.assertEqual("0", self.wire(zero)["active_cards"][0]["rows"][0]["prompt"]["display"]["ccost"])
        self.assertEqual((), zero.comparison_cost.unavailable)
        self.assertFalse(known.unresolved_cost)
        self.assertEqual((), known.comparison_cost.unavailable)
        self.assertIn("available model pricing and usage", unavailable_help(()))
        self.assertEqual("unknown", self.prices().reference_issue(ModelRef("test", "gpt-test"), TokenUsage(input=1)).reason)

    def test_reason_summary_is_bounded_deterministic_and_does_not_export_arbitrary_identity(self):
        issues = [ReferenceCostIssue("model_absent", f"Model {index}") for index in range(20)]
        self.assertEqual(bounded_issues(issues), bounded_issues(reversed(issues)))
        self.assertEqual(6, len(bounded_issues(issues)))
        self.assertEqual(ReferenceCostIssue("unknown"), bounded_issues(issues)[-1])
        issue = self.prices().reference_issue(ModelRef("test", "private/path\nsecret"), TokenUsage(input=10))
        self.assertEqual(ReferenceCostIssue("identity"), issue)


if __name__ == "__main__":
    unittest.main()
