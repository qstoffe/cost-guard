"""Compact/on-demand modes, global availability and bounded cross-month samples."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from development.fixtures.synthetic_month import SyntheticMonthSource
from development.tests.test_analysis_core import make_snapshot
from development.tests.test_quota_presentation import quotas, rolling
from development.tests.test_step7_reports_cli import FakePricingProvider, FakeSource
from src.bootstrap import _report_request
from src.cache import CacheDatabase, CacheRepository
from src.cli import CliUsageError, CommandKind, parse_command
from src.config import load_configuration
from src.domain import ModelRef, AccountUsageStatus
from src.presentation import ReportRenderer
from src.reports import ReportKind, ReportProjection, ReportRequest, ReportService
from src.reports.model_comparison import selectable_catalog
from src.sources.model_availability import OpenCodeModelAvailabilitySource
from src.sources.selection import SourceSelection

ROOT = Path(__file__).resolve().parents[2]
START = int(datetime(2026, 9, 30, 23, 50, tzinfo=timezone.utc).timestamp() * 1000)
NOW = START + 2 * 86_400_000


class Availability:
    def __init__(self, ids=("openai/gpt-test",)):
        self.ids = ids
        self.calls = 0

    def available_model_ids(self):
        self.calls += 1
        return self.ids


class ForbiddenAccount:
    provider_id = "github-copilot"

    def __init__(self):
        self.probe_calls = 0

    def probe(self):
        self.probe_calls += 1
        raise AssertionError("This mode must not probe credentials or accounts")

    def get_account_snapshots(self):
        raise AssertionError("This mode must not fetch quotas")


def rendered(report, config=None, *, width=180, color=False):
    stream = io.StringIO()
    ReportRenderer(config or {"timezone": "UTC"}, stream=stream,
                   terminal_width=width, color_enabled=color).render(report)
    return stream.getvalue()


class CompactReportTests(unittest.TestCase):
    def service(self, source=None, *, availability=None, accounts=(), now_ms=NOW):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = CacheDatabase(Path(tmp.name)); db.initialize()
        source = source or FakeSource()
        config = dict(load_configuration(ROOT).values)
        config["timezone"] = "UTC"
        return ReportService(
            selection=SourceSelection(source, "v2", ("Source-wide warning",), source.probe()),
            pricing_provider=FakePricingProvider(), account_provider=None,
            account_providers=accounts, cache_repository=CacheRepository(db),
            config=config, now_ms=now_ms,
            model_availability_source=availability or Availability(),
        )

    def test_cli_primary_shapes_and_request_mapping(self):
        for argv, kind, limit in (([], CommandKind.NORMAL, None),
                                  (["--all-models"], CommandKind.ALL_MODELS, None),
                                  (["--sessions", "10"], CommandKind.SESSIONS, 10),
                                  (["--sessions", "100"], CommandKind.SESSIONS, 100),
                                  (["--sessions", "all"], CommandKind.SESSIONS, None)):
            command = parse_command(argv)
            self.assertEqual(kind, command.kind)
            request = _report_request(command)
            self.assertEqual(kind.value, request.kind.value)
            self.assertEqual(limit, request.session_limit)
        for argv in (("--sessions",), ("--sessions", "0"), ("--sessions", "-1"),
                     ("--sessions", "1.5"), ("--sessions", "10", "--watch"),
                     ("--sessions", "all", "ses_a"), ("--all-models", "ses_a"),
                     ("--all-models", "--watch"), ("--all-models", "--all-models")):
            with self.subTest(argv=argv), self.assertRaises(CliUsageError):
                parse_command(argv)

    def test_default_does_not_build_historical_views_or_range_totals(self):
        service = self.service()
        with patch.object(service, "_prompt_block", side_effect=AssertionError("prompt detail")), \
             patch.object(service, "_range_comparison", side_effect=AssertionError("history totals")), \
             patch.object(service, "_session_rows", side_effect=AssertionError("session usage")):
            report = service.build(ReportRequest())
        self.assertFalse(report.session_usage)
        self.assertFalse(report.prompt_blocks)
        self.assertEqual(["GPT Test"], [row.model for row in report.model_comparison])
        text = rendered(report)
        for omitted in ("Monthly usage", "Today's user prompts", "Daily CCost", "CCost today",
                        "CCost month", "Sample:", "## Model comparison", "## Accounts & quotas",
                        "CCost is reference valuation"):
            self.assertNotIn(omitted, text)
        self.assertLess(text.index("Pricing/cache metadata:"), text.index("| Publisher"))
        self.assertLess(text.index("Relative CCost: Applies Token Mix %"), text.index("| Publisher"))
        self.assertNotIn("Price I/C/W/O is", text)

    def test_all_models_ignores_availability_accounts_and_other_views(self):
        availability = Availability(None)
        account = ForbiddenAccount()
        service = self.service(availability=availability, accounts=(account,))
        with patch.object(service, "_quotas", side_effect=AssertionError("quota")), \
             patch.object(service, "_prompt_block", side_effect=AssertionError("prompts")), \
             patch.object(service, "_session_rows", side_effect=AssertionError("sessions")):
            report = service.build(ReportRequest(ReportKind.ALL_MODELS))
        self.assertEqual(0, availability.calls)
        self.assertEqual(0, account.probe_calls)
        self.assertEqual({"GPT Test", "Claude Test"}, {row.model for row in report.model_comparison})
        self.assertIsNone(report.accounts_quotas)
        self.assertFalse(report.prompt_blocks)
        self.assertNotIn("GitHub Copilot\n", rendered(report))
        self.assertNotIn("available OpenCode models", rendered(report))

    def test_sample_crosses_month_and_stops_before_old_roots(self):
        source = SyntheticMonthSource(12, 20, month_start_ms=START)
        service = self.service(source)
        report = service.build(ReportRequest())
        self.assertEqual(5, source.load_count)
        sample = service._latest_prompts(tuple(service._analyzed.values()))
        self.assertEqual(100, len(sample))
        self.assertLess(sample[-1].prompt_time_ms, START + 10 * 60_000)  # September
        self.assertGreaterEqual(sample[0].prompt_time_ms, START + 10 * 60_000)  # October
        self.assertEqual({f"root-{n:04d}" for n in range(7, 12)}, {p.session_id for p in sample})
        self.assertEqual(100, report.model_comparison_sample_size)
        self.assertNotIn("billing month", rendered(report))
        service.set_now_ms(NOW + 40 * 86_400_000)
        later = service.build(ReportRequest())
        self.assertEqual(report.model_comparison, later.model_comparison)
        self.assertEqual(5, source.load_count, "Stable recent roots reuse derived analysis")
        all_models = service.build(ReportRequest(ReportKind.ALL_MODELS))
        self.assertEqual(report.model_comparison_sample_size, all_models.model_comparison_sample_size)
        self.assertEqual(100, all_models.pricing_diagnostics["relcost_sample_prompts"])

    def test_recently_touched_old_root_does_not_allow_premature_stop_at_100(self):
        source = SyntheticMonthSource(12, 20, month_start_ms=START)
        old = source.snapshots["root-0000"]
        root = replace(old.root, updated_at_ms=NOW)
        source.snapshots[root.session_id] = replace(old, root=root, sessions=(root,))
        service = self.service(source)
        service.build(ReportRequest())
        sample = service._latest_prompts(tuple(service._analyzed.values()))
        self.assertEqual({f"root-{n:04d}" for n in range(7, 12)}, {p.session_id for p in sample})
        self.assertEqual(6, source.load_count)

    def test_fewer_than_100_and_visibility_completion_abort_rules(self):
        service = self.service(FakeSource(make_snapshot(running=True)), now_ms=2_200)
        service.build(ReportRequest())
        roots = tuple(service._analyzed.values())
        expected = tuple(p for item in roots for p in item.bundle.prompts if not p.aborted and not p.in_progress)
        self.assertEqual(set(p.prompt_id for p in expected), set(p.prompt_id for p in service._latest_prompts(roots)))
        self.assertLess(len(expected), 100)
        self.assertTrue(any(p.in_progress for item in roots for p in item.bundle.prompts))
        record = expected[0]
        roots[0].bundle = replace(roots[0].bundle, prompts=(
            replace(record, prompt_id="aborted", aborted=True),
            replace(record, prompt_id="running", in_progress=True),
            replace(record, prompt_id="completed", completed_successfully=True),
        ))
        self.assertEqual(["completed"], [p.prompt_id for p in service._latest_prompts(roots)])

    def test_empty_history_has_catalog_without_relcost(self):
        source = SyntheticMonthSource(0, 0, month_start_ms=START)
        report = self.service(source).build(ReportRequest(ReportKind.ALL_MODELS))
        self.assertEqual(2, len(report.model_comparison))
        self.assertTrue(all(row.relative_cost is None for row in report.model_comparison))

    def test_sessions_limit_all_order_full_cost_and_no_unrelated_runtime(self):
        source = SyntheticMonthSource(12, 20, month_start_ms=START)
        oldest = source.snapshots["root-0000"]
        source.snapshots["root-0000"] = replace(oldest, invocations=tuple(
            replace(i, tokens=replace(i.tokens, input=2_000_000)) for i in oldest.invocations))
        availability = Availability()
        account = ForbiddenAccount()
        service = self.service(source, availability=availability, accounts=(account,))
        with patch.object(service, "_quotas", side_effect=AssertionError("quota")), \
             patch.object(service, "_model_comparison", side_effect=AssertionError("models")), \
             patch.object(service, "_prompt_block", side_effect=AssertionError("detail")):
            report = service.build(ReportRequest(ReportKind.SESSIONS, session_limit=3))
            self.assertEqual(3, source.load_count)
            self.assertEqual(["root-0011", "root-0010", "root-0009"], [r.session_id for r in report.session_usage])
            self.assertEqual([20] * 3, [r.prompt_count for r in report.session_usage])
            october_only = service._range_comparison((service._analyzed["root-0009"],), START + 10 * 60_000)
            self.assertGreater(report.session_usage[-1].ccost, october_only.known_ccost)
            for limit in (100, None):
                all_sessions = service.build(ReportRequest(ReportKind.SESSIONS, session_limit=limit))
                self.assertEqual(12, len(all_sessions.session_usage))
                self.assertEqual("root-0000", all_sessions.session_usage[-1].session_id)
                self.assertGreater(all_sessions.session_usage[-1].ccost, all_sessions.session_usage[0].ccost)
        self.assertEqual(0, availability.calls)
        self.assertEqual(0, account.probe_calls)
        text = rendered(report)
        self.assertIn("Session id", text)
        self.assertNotIn("Total", text)
        self.assertNotIn("Relative CCost", text)
        self.assertNotIn("GitHub Copilot", text)
        self.assertNotIn("CCost today", text)
        self.assertNotIn("CCost month", text)

    def test_deleted_sessions_leave_listing_and_future_sample_even_with_cache(self):
        source = SyntheticMonthSource(2, 20, month_start_ms=START)
        service = self.service(source)
        before = service.build(ReportRequest())
        self.assertEqual(40, before.pricing_diagnostics["relcost_sample_prompts"])
        del source.snapshots["root-0001"]
        after = service.build(ReportRequest())
        self.assertEqual(20, after.pricing_diagnostics["relcost_sample_prompts"])
        sessions = service.build(ReportRequest(ReportKind.SESSIONS))
        self.assertEqual(["root-0000"], [r.session_id for r in sessions.session_usage])

    def test_detail_has_all_explanations_next_context_and_no_other_views(self):
        service = self.service(accounts=(ForbiddenAccount(),))
        report = service.build(ReportRequest(ReportKind.SESSION, session_id="root"))
        text = rendered(report)
        for expected in ("#1", "Next Ictx:", "CCost:", "I/C/W/O %:", "~Ictx:", "~Ictx CCost:", "~Extra CCost:", "not actual billing"):
            self.assertIn(expected, text)
        self.assertNotIn("Relative CCost", text)
        self.assertIsNone(report.accounts_quotas)
        lines = text.splitlines()
        index = next(i for i, line in enumerate(lines) if line.startswith("* Next Ictx:"))
        self.assertTrue(lines[index + 1].startswith("* CCost:"))

    def test_highlights_accounts_warning_placement_and_distinct_theme_roles(self):
        service = self.service()
        prices = service.pricing_provider.catalog
        service.pricing_provider.catalog = replace(prices, models=tuple(replace(m, metadata={
            **dict(m.metadata), "release_date": "2026-10-01", "promotion_active": "true",
            "promotion_expires_ms": str(NOW + 86_400_000), "promotion_discount_percent": "50",
        }) for m in prices.models))
        report = service.build(ReportRequest())
        account = rolling("copilot", "GitHub Copilot Max")
        account = replace(account, account=replace(account.account, status=AccountUsageStatus.BLOCKED,
            warnings=("⚠ COPILOT PAUSED: synthetic account warning",)))
        report = replace(report, accounts_quotas=quotas(account, rolling("openai", "OpenAI Plus")))
        text = rendered(report, width=140)
        lines = text.splitlines()
        new = next(i for i, line in enumerate(lines) if line.startswith("✦ New Models:"))
        self.assertEqual(["", "Accounts Overview"], lines[new + 1:new + 3])
        self.assertEqual("GitHub Copilot Max", lines[new + 4])
        self.assertLess(text.index("Price Promotion:"), text.index("✦ New Models:"))
        self.assertLess(text.index("Source-wide warning"), text.index("Pricing/cache metadata"))
        warning = next(line for line in lines if "COPILOT PAUSED" in line)
        self.assertTrue(warning.startswith("  ⚠"))
        self.assertLess(text.index("GitHub Copilot Max"), text.index("COPILOT PAUSED"))
        self.assertLess(text.index("COPILOT PAUSED"), text.index("OpenAI Plus"))
        self.assertNotIn("Usage Today", text)
        for theme in ("classic", "modus-operandi-tinted"):
            colors = service.config["colorSchemes"][theme]
            self.assertNotEqual(colors["modelComparisonNew"], colors["modelComparisonPromotion"])
        colored = rendered(report, service.config, color=True)
        self.assertIn("\x1b[38;5;118m✦ New Models:\x1b[0m", colored)
        self.assertIn("\x1b[38;5;214m*1 Price Promotion:", colored)


class AvailabilityTests(unittest.TestCase):
    def test_strips_any_provider_and_never_uses_substring_pricing_resolution(self):
        prices = FakePricingProvider().catalog
        sol = replace(prices.models[0], model=ModelRef("github-copilot", "gpt-5.6-sol", "GPT-5.6 Sol"))
        prices = replace(prices, models=(*prices.models, sol))
        for provider in ("openai", "github-copilot", "anthropic", "google", "opencode", "custom-provider"):
            selected, warnings = selectable_catalog(prices, availability_source=Availability((f"{provider}/gpt-5.6-sol",)))
            self.assertEqual((sol,), selected.models)
            self.assertFalse(warnings)
        for value in ("openai/gpt-5.6", "openai/gpt-5.6-sol-extra", "opencode/not-in-catalog"):
            selected, warnings = selectable_catalog(prices, availability_source=Availability((value,)))
            self.assertFalse(selected.models)
            self.assertIn("No available OpenCode models match", warnings[0])
        self.assertIsNotNone(prices.resolve("gpt-5.6-sol-extra"), "Unrelated pricing fallback remains fuzzy")

    def test_global_command_parsing_and_deduplication(self):
        source = OpenCodeModelAvailabilitySource(runner=lambda: (0,
            "status chatter\nopenai/gpt-test\n\x1b[32mgoogle/claude-test\x1b[0m\nopenai/gpt-test\n"))
        self.assertEqual(("openai/gpt-test", "google/claude-test"), source.available_model_ids())
        for code, output in ((1, "openai/gpt-test"), (0, "not a model list")):
            self.assertIsNone(OpenCodeModelAvailabilitySource(runner=lambda: (code, output)).available_model_ids())
        self.assertEqual((), OpenCodeModelAvailabilitySource(runner=lambda: (0, "")).available_model_ids())

    def test_lookup_failure_is_visible_fail_open_but_valid_no_match_is_empty(self):
        prices = FakePricingProvider().catalog
        for source in (None, Availability(None)):
            selected, warnings = selectable_catalog(prices, availability_source=source)
            self.assertEqual(prices, selected)
            self.assertIn("showing full pricing catalog", warnings[0])
        selected, warnings = selectable_catalog(prices, availability_source=Availability(("opencode/unknown",)))
        self.assertFalse(selected.models)
        self.assertNotIn("showing full pricing catalog", warnings[0])
        source = Availability()
        with patch.object(source, "available_model_ids", side_effect=RuntimeError("private failure")):
            selected, warnings = selectable_catalog(prices, availability_source=source)
        self.assertEqual(prices, selected)
        self.assertNotIn("private failure", warnings[0])


if __name__ == "__main__":
    unittest.main()
