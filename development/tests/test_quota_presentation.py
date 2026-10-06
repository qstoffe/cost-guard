"""v78.19 shared quota language, visibility, responsive layouts and coverage."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import io
import json
from pathlib import Path
import re
import tempfile
import unittest

from development.tests.test_accounts_ccost import account
from development.tests.test_analysis_core import make_snapshot
from development.tests.test_config import make_package
from development.tests.test_step7_reports_cli import FakePricingProvider
from development.tests.test_step8_watch import MutableSource, make_service
from development.tools.collect_diagnostics import _projection_summary
from src.analysis.causal import trace_entries
from src.analysis.models import LocalUsageSummary
from src.analysis.valuation import ComparisonCost
from src.config import load_configuration, read_jsonc
from src.domain import BillingComponent, CostDisposition, QuotaComponent
from src.presentation import ReportRenderer, WatchRenderer
from src.presentation.accounts import capacity_lines, format_quota_bar, format_reset
from src.presentation.terminal import AnsiStyler
from src.reports import ReportRequest
from src.reports.accounts import account_projections
from src.reports.models import AccountProjection, AccountsQuotasProjection, ReportKind, ReportProjection
from src.reports.semantics import aggregate_usage_notes
from src.watch.models import WatchProjection

ROOT = Path(__file__).resolve().parents[2]
D = Decimal
NOW = int(datetime(2026, 9, 30, 20, tzinfo=timezone.utc).timestamp() * 1000)
STYLER = AnsiStyler({}, enabled=False)


def rolling(identity="a", label="OpenAI Plus"):
    snapshot = replace(account(identity=identity), fetched_at_ms=NOW, quotas=(
        QuotaComponent("5-hour", remaining_fraction=D("0.64"), reset_at_ms=NOW + 126 * 60_000, duration_seconds=18_000),
        QuotaComponent("weekly", remaining_fraction=D("0.48"), reset_at_ms=NOW + 74 * 3_600_000, duration_seconds=604_800),
    ))
    return AccountProjection(snapshot, label)


def quotas(*accounts):
    return AccountsQuotasProjection(ComparisonCost(D(999)), ComparisonCost(D(9999)), tuple(accounts),
                                    billed_today=D(88), billed_month=D(888), now_ms=NOW)


def report_text(quota, *, width=160):
    stream = io.StringIO()
    config = read_jsonc(ROOT / "config/default-config.jsonc")
    ReportRenderer(config, stream=stream, color_enabled=False, terminal_width=width)._render_accounts_quotas(
        ReportProjection(ReportKind.NORMAL, "Report", "V2", accounts_quotas=quota))
    return stream.getvalue()


def watch_text(quota, *, width):
    stream = io.StringIO()
    config = read_jsonc(ROOT / "config/default-config.jsonc")
    config["timezone"] = "UTC"
    WatchRenderer(config, stream=stream, interactive=False, terminal_width=width).render(
        WatchProjection("Watch", "V2", (), quota=quota, now_ms=NOW, status="Next refresh: 00:04"))
    return stream.getvalue().split("Token Mix % · 0 prompts · no token data yet", 1)[1].split("\n", 1)[1]


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

    def test_ten_cell_bars_round_consistently_and_preserve_color_segments(self):
        for value, filled in (("0", 0), ("0.2", 2), ("0.64", 6), ("0.75", 8), ("0.9", 9), ("1", 10)):
            bar = format_quota_bar(D(value))
            self.assertEqual("█" * filled + "░" * (10 - filled), "".join(text for text, _ in bar.parts[:2]))
            self.assertEqual("dailyCostFilled", bar.parts[0][1])
            self.assertEqual("dailyCostEmpty", bar.parts[1][1])
            self.assertNotIn("left", str(bar))

    def test_vertical_labels_and_percentage_columns_align_generically(self):
        snapshot = replace(account(), quotas=tuple(QuotaComponent(label, remaining_fraction=D(value))
                           for label, value in (("5-hour", "0.64"), ("weekly", "0.48"), ("Month", "0.9"),
                                                ("Native", "0.2"), ("Credits", "1"))))
        lines = capacity_lines(AccountProjection(snapshot, "Any provider"), STYLER, "UTC", width=120,
                               force_vertical=True, now_ms=NOW)[1:]
        self.assertEqual(1, len({line.index("█") for line in lines}))
        self.assertEqual(1, len({line.index("%") for line in lines}))
        self.assertTrue(all(len(re.search(r"[█░]+", line).group()) == 10 for line in lines))


class VisibilityTests(unittest.TestCase):
    def test_balance_visibility_matches_watch_and_report(self):
        for amount in (D(0), None, D("32.60")):
            row = rolling()
            row = replace(row, account=replace(row.account, billing=(BillingComponent("Extra credits", amount, kind="balance", status="ACTIVE"),)))
            for text in (watch_text(quotas(row), width=180), report_text(quotas(row))):
                self.assertEqual(bool(amount), "Extra credits" in text)
                if amount:
                    self.assertIn("Extra credits $32.60 remaining", text)
        row = rolling()
        row = replace(row, account=replace(row.account, billing=(BillingComponent("Extra credits", D(500), "credits", kind="balance"),
                                                               BillingComponent("Usage credits", D("18.40"), kind="balance"))))
        self.assertIn("Extra credits 500 credits remaining", report_text(quotas(row)))
        self.assertIn("Usage credits $18.40 remaining", watch_text(quotas(row), width=180))
        row = replace(row, account=replace(row.account, billing=(
            BillingComponent("Extra credits", D(500), "AI credits", kind="balance", status="active"),)))
        self.assertIn("Extra credits 500 remaining", watch_text(quotas(row), width=180))
        self.assertNotIn("AI credits", watch_text(quotas(row), width=180))
        self.assertIn("Extra credits 500 AI credits remaining", report_text(quotas(row)))

    def test_sign_in_remedy_appears_once_per_surface(self):
        reason = "Provider sign-in was rejected; sign in again to restore quotas."
        action = "Sign-in rejected; sign in again"
        row = rolling(label="Any provider")
        row = replace(row, account=replace(row.account, quotas=(), availability="unavailable", reason=reason,
                                           observations={"parser_reason": "auth_failure", "user_action": action}))
        watch = watch_text(quotas(row), width=180)
        self.assertIn("Quota unavailable · " + action, watch)
        self.assertNotIn(reason, watch)
        report = report_text(quotas(row))
        self.assertIn(reason, report)
        self.assertNotIn(action, report)
        for availability, observations in (("unavailable", {"parser_reason": "auth_failure"}),
                                           ("error", {"parser_reason": "auth_failure", "user_action": action})):
            other = replace(row, account=replace(row.account, availability=availability, observations=observations))
            self.assertNotIn(action, watch_text(quotas(other), width=180))

    def test_unknown_operational_balance_state_and_native_budgets_remain(self):
        row = rolling()
        row = replace(row, account=replace(row.account, availability="stale", billing=(
            BillingComponent("Credits", None, kind="balance", status="BLOCKED"),
            BillingComponent("Provider budget", D(200), kind="budget"))))
        text = report_text(quotas(row))
        self.assertIn("Credits BLOCKED", text)
        self.assertIn("Provider budget $200.00", text)
        self.assertIn("STALE", text)

    def test_global_and_all_na_rows_disappear_but_known_account_values_remain(self):
        row = replace(rolling(), ccost_scopes=(("5-hour", None), ("weekly", ComparisonCost(D(0), 2, 0))))
        text = report_text(quotas(row))
        for unwanted in ("CCost today:", "CCost month:", "Billed today:", "Billed month:", "CCost:", "configured monthly"):
            self.assertNotIn(unwanted, text)
        row = replace(row, ccost_scopes=(("5-hour", ComparisonCost(D("2.31"), 1, 1)), ("weekly", None)),
                      billed_today=D("3.72"), billed_month=D("48.20"))
        text = report_text(quotas(row))
        self.assertNotIn("CCost:", text)
        self.assertNotIn("Week N/A", text)
        self.assertIn("Billed today: $3.72", text)
        self.assertIn("Billed month: $48.20", text)
        row = replace(row, ccost_scopes=(("today", ComparisonCost(D("3.41"), 1, 1)),), billed_today=None)
        text = report_text(quotas(row))
        self.assertNotIn("CCost today:", text)
        self.assertNotIn("Billed today:", text)

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


class LayoutTests(unittest.TestCase):
    def test_primary_bars_align_for_two_three_and_four_accounts_with_ansi(self):
        month = replace(rolling("c", "GitHub Copilot Pro+"), account=replace(account("github-copilot", "c"), quotas=(
            QuotaComponent("Month", remaining_fraction=D(1)),)))
        custom = replace(rolling("d", "A moderately long subscription label"), account=replace(account(identity="d"), quotas=(
            QuotaComponent("Fortnight", remaining_fraction=D(0)),)))
        for rows in ((month, rolling()), (month, rolling(), rolling("b", "Claude Code Pro")),
                     (month, rolling(), rolling("b", "Claude Code Pro"), custom)):
            text = watch_text(quotas(*rows), width=240)
            lines = [line for line in text.splitlines() if re.search(r"[█░]{10}", line)]
            self.assertEqual(len(rows), len(lines), "one compact row per account")
            self.assertEqual(1, len({re.search(r"[█░]{10}", line).start() for line in lines}))
            report = report_text(quotas(*rows), width=240)
            primary = [line for line in report.splitlines() if line.lstrip().startswith(("Month ", "5h ", "Fortnight "))]
            self.assertEqual(len(rows), len(primary))
            self.assertEqual(1, len({re.search(r"[█░]{10}", line).start() for line in primary}))
        stream = io.StringIO()
        config = {"timezone": "UTC", "colors": {"dailyCostFilled": {"foreground": "Green"}}}
        WatchRenderer(config, stream=stream, interactive=True, terminal_width=240)._render_quota(
            WatchProjection("Watch", "V2", (), quota=quotas(month, rolling()), now_ms=NOW))
        self.assertIn("\x1b[", stream.getvalue())
        visible = re.sub(r"\x1b\[[0-9;]*m", "", stream.getvalue())
        lines = [line for line in visible.splitlines() if "█" in line]
        self.assertEqual(1, len({line.index("█") for line in lines}))

    def test_generic_native_quota_merges_without_a_provider_branch(self):
        row = replace(rolling(), account=replace(rolling().account, quotas=(QuotaComponent(
            "Month", remaining_fraction=D("0.5"), remaining=D(250), limit=D(500), unit="widgets",
            remaining_money=D("2.5"), limit_money=D(5)),)))
        for text in (watch_text(quotas(row), width=160), report_text(quotas(row))):
            self.assertIn("50% · 250/500 widgets", text)
            self.assertNotIn("Native", text)
            self.assertEqual(1, len([line for line in text.splitlines() if "250/500" in line]))
        self.assertNotIn("$", watch_text(quotas(row), width=160))
        self.assertIn("($2.50/$5.00)", report_text(quotas(row)))

    def test_blocked_components_keep_alignment_and_unquantified_balance_keeps_meaning(self):
        from src.domain import AccountUsageStatus
        blocked = replace(rolling("b", "Blocked subscription"), account=replace(rolling("b").account,
            status=AccountUsageStatus.BLOCKED, quotas=(QuotaComponent("Month", remaining_fraction=D(0),
                remaining=D(0), limit=D(500), unit="AI credits", status=AccountUsageStatus.BLOCKED),)))
        text = watch_text(quotas(blocked, rolling()), width=240)
        primary = [line for line in text.splitlines() if re.search(r"[█░]{10}", line)]
        self.assertEqual(1, len({re.search(r"[█░]{10}", line).start() for line in primary}))
        self.assertIn("BLOCKED", text)
        native = replace(rolling(), account=replace(rolling().account, quotas=(QuotaComponent("Balance", remaining=D(50), unit="widgets"),)))
        self.assertIn("50 widgets remaining", watch_text(quotas(native), width=160))

    def test_one_or_two_accounts_compact_when_wide_and_vertical_when_narrow(self):
        for rows in ((rolling(),), (rolling(), rolling("b", "Anthropic Pro"))):
            for width in (45, 100, 300):
                text = watch_text(quotas(*rows), width=width)
                if width >= 100:
                    self.assertIn(" | ", text)
                    self.assertIn("Reset@", text)
                    self.assertEqual(len(rows), sum("█" in line for line in text.splitlines()))
                else:
                    self.assertNotIn(" | ", text)
                    self.assertIn("Reset in", text)
                    for row in rows:
                        self.assertIn(row.label, text.splitlines())
                self.assertTrue(all(len(line) <= width for line in text.splitlines()))

    def test_three_accounts_compact_only_if_each_fits_and_fallback_is_verbose(self):
        copilot = replace(rolling("c", "Copilot Max"), account=replace(account("github-copilot", "c", plan="Max"), quotas=(
            QuotaComponent("Month", remaining_fraction=D("0.91")),)))
        rows = (rolling(), copilot, rolling("b", "Anthropic Pro"))
        wide = watch_text(quotas(*rows), width=240)
        for row in rows:
            line = next(line for line in wide.splitlines() if line.startswith(row.label))
            self.assertIn("%", line)
            self.assertNotIn("left", line)
            self.assertEqual(1, sum(other.label in line for other in rows))
        self.assertIn("Reset@Saturday 22:00", wide)
        self.assertNotIn("Reset in", wide)
        mixed = watch_text(quotas(*rows), width=90)
        self.assertIn("OpenAI Plus", mixed.splitlines())
        self.assertIn("Anthropic Pro", mixed.splitlines())
        self.assertTrue(any(line.startswith("Copilot Max") and "%" in line for line in mixed.splitlines()))
        self.assertIn("Reset in 126min", mixed)
        self.assertTrue(all(len(line) <= 90 for line in mixed.splitlines()))

    def test_report_and_narrow_watch_share_verbose_rolling_components(self):
        row = rolling()
        config = read_jsonc(ROOT / "config/default-config.jsonc")
        stream = io.StringIO()
        config["timezone"] = "UTC"
        ReportRenderer(config, stream=stream, color_enabled=False, terminal_width=160).render(
            ReportProjection(ReportKind.NORMAL, "Report", "V2", accounts_quotas=quotas(row)))
        watch = watch_text(quotas(row), width=60)
        for line in watch.splitlines():
            if "█" in line:
                self.assertIn(line, stream.getvalue())

    def test_long_account_name_does_not_force_other_accounts_vertical(self):
        short = replace(rolling("c", "Copilot Max"), account=replace(account("github-copilot", "c", plan="Max"), quotas=(
            QuotaComponent("Month", remaining_fraction=D("0.91")),)))
        text = watch_text(quotas(rolling("a", "Long account " * 12), short, rolling("b", "Anthropic Pro")), width=120)
        self.assertTrue(any(line.startswith("Copilot Max") and "%" in line for line in text.splitlines()))
        self.assertTrue(all(len(line) <= 120 for line in text.splitlines()))


class CoverageTests(unittest.TestCase):
    def test_successful_fallback_is_silent_and_unpriced_ccost_warns_independently_of_billing(self):
        month = LocalUsageSummary(D(1), 1000, 1, 1037, 1000, 37, 0, D(0))
        self.assertEqual((), aggregate_usage_notes(month, ComparisonCost(D(1), 1000, 1000)))
        notes = aggregate_usage_notes(LocalUsageSummary(D(0), 0, 0, 0, 0, 0, 0, D(0)), ComparisonCost(D(1), 1000, 963))
        self.assertEqual(1, len(notes))
        self.assertIn("37 request(s) could not be assigned CCost", notes[0])

    def test_service_retains_fallback_diagnostics_and_warns_for_unpriced_reported_calls(self):
        with tempfile.TemporaryDirectory() as td:
            snapshot = make_snapshot()
            invocations = tuple(replace(i, cost=replace(i.cost, amount=D(0))) for i in snapshot.invocations)
            source = MutableSource(replace(snapshot, invocations=invocations))
            _, _, service, _ = make_service(td, source, now_ms=4000)
            report = service.build(ReportRequest())
            self.assertFalse(any("WARNING" in note for note in report.notes))
            stats = _projection_summary(report)["pricing"]
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
            stats = _projection_summary(report)["pricing"]
            self.assertFalse(any("WARNING" in note for note in report.notes))
            self.assertGreater(stats["reference_price_requests"], 0)
        with tempfile.TemporaryDirectory() as td:
            missing = replace(snapshot.invocations[1], model=replace(snapshot.invocations[1].model, model="no-reference-price"))
            source = MutableSource(replace(snapshot, invocations=snapshot.invocations[:1] + (missing,) + snapshot.invocations[2:]))
            _, _, service, _ = make_service(td, source, now_ms=4000)
            report = service.build(ReportRequest())
            self.assertFalse(report.notes, "Compact dashboard has no historical CCost totals to warn about")
            from src.reports import ReportKind
            report = service.build(ReportRequest(ReportKind.SESSION, session_id="root"))
            self.assertTrue(any("CCost totals are incomplete" in note for note in report.notes))


if __name__ == "__main__":
    unittest.main()
