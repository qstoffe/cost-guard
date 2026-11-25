"""Shared quota reset times, billing evidence and price coverage."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import json
import tempfile
import unittest

from development.tests.fixtures.package_copy import make_package
from development.tests.fixtures.quota_rendering import NOW, rolling
from development.tests.fixtures.session_snapshots import make_snapshot
from development.tests.fixtures.report_runtime import FakePricingProvider
from development.tests.fixtures.watch_runtime import MutableSource, make_service
from src.analysis.causal import trace_entries
from src.config import load_configuration
from src.domain import CostDisposition
from src.display import format_reset
from src.reports import ReportRequest
from src.reports.accounts import account_projections
from src.reports.models import ReportKind

D = Decimal


class FormattingTests(unittest.TestCase):
    def test_exact_reset_boundaries_and_compact_targets(self):
        cases = (
            (23 * 3_600_000 + 59 * 60_000, "Reset in 1439min, 19:59", "Reset@19:59"),
            (24 * 3_600_000, "Reset in 24h, Thursday 20:00", "Reset@Thursday 20:00"),
            (6 * 86_400_000 + 23 * 3_600_000 + 59 * 60_000, "Reset in 167h, Wednesday 19:59", "Reset@Wednesday 19:59"),
            (7 * 86_400_000, "Reset at 2026-10-07 20:00", "Reset@2026-10-07 20:00"),
        )
        for remaining, verbose, compact in cases:
            with self.subTest(remaining=remaining):
                self.assertEqual(verbose, format_reset(NOW + remaining, "UTC", now_ms=NOW))
                self.assertEqual(compact, format_reset(NOW + remaining, "UTC", now_ms=NOW, compact=True))

    def test_minutes_floor_and_invalid_or_expired_timestamps_are_safe(self):
        self.assertEqual("Reset in 5min, 20:05", format_reset(NOW + 359_999, "UTC", now_ms=NOW))
        self.assertEqual("Reset in 0min, 20:00", format_reset(NOW + 59_999, "UTC", now_ms=NOW))
        for value in (NOW - 1, NOW):
            self.assertEqual("Reset expired", format_reset(value, "UTC", now_ms=NOW))
        for value in (None, "broken", True, -1, 0, float("nan"), float("inf"), 10**1000):
            self.assertEqual("Reset unknown", format_reset(value, "UTC", now_ms=NOW))

    def test_local_targets_and_dst_do_not_change_elapsed_time_tier(self):
        self.assertEqual("Reset in 126min, 00:06", format_reset(NOW + 126 * 60_000, "Europe/Stockholm", now_ms=NOW))
        before_dst = int(datetime(2026, 10, 24, 12, tzinfo=timezone.utc).timestamp() * 1000)
        self.assertEqual("Reset in 24h, Sunday 13:00", format_reset(before_dst + 86_400_000, "Europe/Stockholm", now_ms=before_dst))


class VisibilityTests(unittest.TestCase):
    def test_subscription_inclusion_is_not_account_billing_evidence(self):
        snapshot = rolling().account
        entry = replace(trace_entries(make_snapshot())[0], account_ref=snapshot.ref,
                        model=replace(trace_entries(make_snapshot())[0].model, provider="openai"),
                        completed_at_ms=NOW, reported_cost=D(0), cost_disposition=CostDisposition.INCLUDED_SUBSCRIPTION)
        def project(value):
            return account_projections((snapshot,), (value,), FakePricingProvider().catalog,
                                       now_ms=NOW, today_start_ms=0, month_start_ms=0)[0]
        self.assertIsNone(project(entry).billed_today)
        self.assertEqual(D("3.72"), project(replace(entry, reported_cost=D("3.72"))).billed_today)
        self.assertEqual(D(0), project(replace(entry, cost_disposition=CostDisposition.BILLED)).billed_today)

    def test_deprecated_budget_is_absent_from_defaults_and_ignored_in_old_configs(self):
        for value in (20000, None, "obsolete"):
            with tempfile.TemporaryDirectory() as td:
                package = make_package(td)
                (package / "config/user-config.jsonc").write_text(json.dumps({"monthlyAiCredits": value}))
                config = load_configuration(package)
                self.assertNotIn("monthlyAiCredits", config.values)
                self.assertEqual("auto", config.open_code_source)


class CoverageTests(unittest.TestCase):
    def test_service_retains_fallback_diagnostics_and_warns_for_unpriced_reported_calls(self):
        with tempfile.TemporaryDirectory() as td:
            snapshot = make_snapshot()
            invocations = tuple(replace(i, cost=replace(i.cost, amount=D(0))) for i in snapshot.invocations)
            source = MutableSource(replace(snapshot, invocations=invocations))
            _, _, service, _ = make_service(td, source, now_ms=4000)
            report = service.build(ReportRequest())
            self.assertFalse(any("WARNING" in note for note in report.notes))
            stats = report.pricing_diagnostics
            self.assertGreater(stats["current_price_fallback_requests"], 0)
            self.assertGreater(stats["reference_price_requests"], 0)
            self.assertEqual(stats["observed_requests"], stats["priced_requests"])
            self.assertIn("reference_catalog_retrieved_at_ms", stats)
            subscription = replace(snapshot, invocations=tuple(replace(i, cost=replace(i.cost, amount=D(0)),
                                    cost_disposition=CostDisposition.INCLUDED_SUBSCRIPTION) for i in snapshot.invocations),
                                   source_revision="subscription")
            source.snapshot = subscription
            service.invalidate_roots(("root",))
            report = service.build(ReportRequest())
            stats = report.pricing_diagnostics
            self.assertFalse(any("WARNING" in note for note in report.notes))
            self.assertGreater(stats["reference_price_requests"], 0)
        with tempfile.TemporaryDirectory() as td:
            missing = replace(snapshot.invocations[1], model=replace(snapshot.invocations[1].model, model="no-reference-price"))
            source = MutableSource(replace(snapshot, invocations=snapshot.invocations[:1] + (missing,) + snapshot.invocations[2:]))
            _, _, service, _ = make_service(td, source, now_ms=4000)
            report = service.build(ReportRequest())
            self.assertFalse(report.notes, "Compact dashboard has no historical CCost totals to warn about")
            report = service.build(ReportRequest(ReportKind.SESSION, session_id="root"))
            self.assertTrue(any("CCost totals are incomplete" in note for note in report.notes))


if __name__ == "__main__":
    unittest.main()
