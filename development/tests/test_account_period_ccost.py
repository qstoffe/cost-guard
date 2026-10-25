"""Shared account-period scopes, provenance, incremental reuse and Watch geometry."""
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import tempfile
import re
import unittest
from unittest.mock import patch

from development.tests.fixtures.accounts import account
from development.tests.fixtures.report_runtime import FakePricingProvider
from development.tests.fixtures.session_snapshots import make_snapshot
from development.tests.fixtures.watch_runtime import MutableSource, make_service
from development.tests.fixtures.synthetic_month import SyntheticMonthSource, make_root_snapshot
from src.analysis.causal import trace_entries
from src.analysis.period_ccost import PeriodCCostIndex, quota_window
from src.analysis.timezones import local_day_start_ms, local_month_start_ms
from src.domain import ModelRef, QuotaComponent, TokenUsage
from src.domain.acquisition import AcquisitionMetrics
from src.presentation.accounts import account_ccost_lines, capacity_lines
from src.presentation.terminal import AnsiStyler
from src.reports.accounts import account_projections, WatchAccountProjection

D = Decimal
HOUR = 3_600_000
NOW = int(datetime(2026, 10, 25, 12, tzinfo=timezone.utc).timestamp() * 1000)
DAY = local_day_start_ms("Europe/Stockholm", now_ms=NOW)
MONTH = local_month_start_ms("Europe/Stockholm", now_ms=NOW)


def strip_ansi(value):
    return re.sub(r"\x1b\[[0-9;]*m", "", value)


def request(name, when, *, provider="claude-code", amount=1_000_000, ref=None, model="gpt-test"):
    return replace(trace_entries(make_snapshot())[0], session_id="root", message_id=name, step_part_id=None,
                   completed_at_ms=when, model=ModelRef(provider, model), tokens=TokenUsage(input=amount),
                   account_ref=ref)


def subscription(provider="claude-code", identity="one"):
    return replace(account(provider, identity=identity), quotas=(
        QuotaComponent("5-hour", "rolling", remaining_fraction=D(1), duration_seconds=18_000, window_active=False),
        QuotaComponent("weekly", "rolling", remaining_fraction=D("0.57"), duration_seconds=604_800,
                       reset_at_ms=NOW + HOUR),))


def project(accounts, entries, *, watch=False):
    return account_projections(accounts, entries, FakePricingProvider().catalog, now_ms=NOW,
                               today_start_ms=DAY, month_start_ms=MONTH, timezone_id="Europe/Stockholm", watch=watch)


class AccountPeriodCCostTests(unittest.TestCase):
    def test_month_is_calendar_history_not_sum_of_overlapping_windows(self):
        monthly = replace(subscription("github-copilot"), quotas=(QuotaComponent("Month", "monthly"),))
        entries = tuple(request(name, when, provider=provider) for provider in ("claude-code", "github-copilot")
                        for name, when in ((provider + "old", MONTH - 1), (provider + "month", MONTH),
                                           (provider + "week", NOW - 2 * 86_400_000),
                                           (provider + "hour", NOW - HOUR)))
        claude, copilot = sorted(project((subscription(), monthly), entries), key=lambda row: row.account.ref.provider_id)
        scopes = dict(claude.ccost_scopes)
        self.assertEqual(D(300), scopes["this month"].ccost)
        self.assertEqual(D(100), scopes["today"].ccost)
        self.assertEqual(D(100), scopes["5-hour"].ccost)
        self.assertEqual(D(200), scopes["weekly"].ccost)
        self.assertEqual(scopes["this month"].ccost, dict(copilot.ccost_scopes)["this month"].ccost)
        self.assertNotIn("this month", dict(project((subscription(),), entries, watch=True)[0].ccost_scopes))
        report = "\n".join(account_ccost_lines(claude))
        self.assertIn("CCost this month: 300", report)
        self.assertIn("trailing lookback", report)
        self.assertIn("native reset window", report)
        self.assertIn("not verified account/billing attribution", report)

    def test_provider_is_request_source_not_publisher_and_direct_api_stays_separate(self):
        entries = (request("gpt-via-copilot", NOW, provider="github-copilot-enterprise"),
                   request("direct-anthropic", NOW, provider="anthropic"),
                   request("codex-alias", NOW, provider="openai-codex"))
        rows = project((subscription(), subscription("github-copilot"), subscription("openai")), entries)
        values = {row.account.ref.provider_id: dict(row.ccost_scopes)["today"] for row in rows}
        self.assertIsNone(values["claude-code"])
        self.assertEqual(D(100), values["github-copilot"].ccost)
        self.assertEqual(D(100), values["openai"].ccost)

    def test_two_accounts_never_duplicate_unassigned_usage_and_provider_total_is_explained_once(self):
        one, two = subscription(identity="one"), subscription(identity="two")
        proven = request("proven", NOW, ref=one.ref)
        rows = project((one, two), (proven,))
        self.assertEqual(D(100), dict(rows[0].ccost_scopes)["today"].ccost)
        self.assertIsNone(dict(rows[1].ccost_scopes)["today"])
        rows = project((one, two), (proven, request("unknown", NOW)))
        self.assertTrue(all(dict(row.ccost_scopes)["today"] is None for row in rows))
        notes = "\n".join(note for row in rows for note in row.ccost_notes)
        self.assertEqual(1, notes.count("Provider-only CCost today: 200"))
        self.assertIn("multiple compatible accounts", notes)
        text = "\n".join(capacity_lines(rows[0], AnsiStyler({}, enabled=False), "UTC", width=240, now_ms=NOW, watch=True))
        self.assertIn("CCost: account unknown", text)
        self.assertNotIn("(200)", text)

    def test_single_account_estimate_excludes_history_proven_to_another_account(self):
        current, removed = subscription(), subscription(identity="removed")
        row = project((current,), (request("unknown", NOW), request("other", NOW, ref=removed.ref)))[0]
        self.assertEqual(D(100), dict(row.ccost_scopes)["today"].ccost)

    def test_partial_pricing_dedup_and_model_scopes_match_canonical_valuation(self):
        known = request("known", NOW)
        clone = replace(known, session_id="fork")
        unknown = request("unknown", NOW, model="unpriced")
        row = project((subscription(),), (known, clone, unknown))[0]
        value = dict(row.ccost_scopes)["today"]
        self.assertEqual((D(100), 2, 1), (value.known_ccost, value.observed_requests, value.priced_requests))
        self.assertIn("CCost today: ?100", account_ccost_lines(row))
        scoped = replace(subscription(), quotas=(replace(subscription().quotas[1], scope="model", model_id="claude-test"),))
        self.assertIsNone(dict(project((scoped,), (known,))[0].ccost_scopes)["weekly"])

    def test_window_requires_a_valid_anchor_or_explicit_not_started(self):
        component = subscription().quotas[1]
        self.assertIsNone(quota_window(replace(component, reset_at_ms=None), NOW))
        self.assertIsNone(quota_window(replace(component, reset_at_ms=NOW), NOW))
        self.assertIsNone(quota_window(replace(component, reset_at_ms=NOW + 8 * 86_400_000), NOW))
        self.assertEqual(NOW - 5 * HOUR, quota_window(subscription().quotas[0], NOW)[0])

    def test_local_month_boundary_uses_stockholm_midnight_across_dst(self):
        self.assertEqual(int(datetime(2026, 9, 30, 22, tzinfo=timezone.utc).timestamp() * 1000), MONTH)
        self.assertEqual(14 * HOUR, NOW - DAY)  # 25-hour autumn day, not a fixed UTC day

    def test_watch_percentage_parentheses_and_daily_placement_preserve_width_and_status(self):
        row = project((subscription(),), (request("one", NOW),), watch=True)[0]
        for width in (35, 65, 120, 240):
            for color in (False, True):
                lines = capacity_lines(row, AnsiStyler({}, enabled=color), "UTC", width=width, now_ms=NOW, watch=True)
                text = "\n".join(strip_ansi(line) for line in lines)
                self.assertIn("100% (100)", text)
                self.assertIn("57% (100)", text)
                self.assertIn("not started", " ".join(text.split()))
                self.assertTrue(all(len(strip_ansi(line)) <= width for line in lines))
                self.assertNotIn("this month", text)
        native = replace(subscription("github-copilot"), quotas=(QuotaComponent("Month", "fixed", remaining=D(2483),
                         limit=D(7000), remaining_fraction=D("0.35"), unit="AI credits", reset_at_ms=NOW + 5 * 86_400_000),))
        monthly = project((native,), (request("copilot", NOW, provider="github-copilot"),), watch=True)[0]
        text = "\n".join(capacity_lines(monthly, AnsiStyler({}, enabled=False), "UTC", width=240, now_ms=NOW, watch=True))
        self.assertIn("2483/7000 · Today: 100 · Remaining:", text)
        no_percent = replace(row, account=replace(row.account, quotas=(replace(row.account.quotas[0], remaining_fraction=None),)))
        text = "\n".join(capacity_lines(no_percent, AnsiStyler({}, enabled=False), "UTC", width=240, now_ms=NOW, watch=True))
        self.assertIn("N/A · CCost: 100", text)
        self.assertNotIn("█", text)

    def test_prefix_queries_and_quota_updates_never_revalue_unchanged_history(self):
        entries = (request("one", NOW),)
        catalog = FakePricingProvider().catalog
        index = PeriodCCostIndex(entries, catalog.reference_valuation)
        self.assertEqual(D(100), index.cost("claude-code", "provider", DAY, NOW + 1).ccost)
        projector = WatchAccountProjection(AcquisitionMetrics())
        options = dict(now_ms=NOW, day_start_ms=DAY, month_start_ms=MONTH, timezone_id="UTC", workday_calendar="")
        first = projector.project((subscription(),), entries, catalog, **options)[0]
        with patch("src.analysis.period_ccost.comparison_cost", side_effect=AssertionError("revaluation")):
            second = projector.project((replace(subscription(), fetched_at_ms=NOW + 1),), entries, catalog, **options)[0]
        self.assertEqual(first.accounts[0].ccost_scopes, second.accounts[0].ccost_scopes)

    def test_watch_expands_history_for_week_then_retains_deleted_observations_without_month_scan(self):
        with tempfile.TemporaryDirectory() as directory:
            source = MutableSource(make_snapshot())
            _, _, service, _ = make_service(directory, source, now_ms=4000)
            self.addCleanup(service.close_accounts)
            native = subscription("github-copilot")
            native = replace(native, quotas=(replace(native.quotas[1], reset_at_ms=5000),))
            service.project_watch_accounts((native,))
            roots = service.watch_history_candidates(service.session_catalog())
            service.watch_history_batch(roots)
            service.publish_watch_history()
            first = service.project_watch_accounts((native,))[0].accounts[0]
            self.assertGreater(dict(first.ccost_scopes)["weekly"].observed_requests, 0)
            source.snapshot = replace(source.snapshot, sessions=(), source_revision="deleted")
            service.watch_history_candidates(())
            service.publish_watch_history()
            after = service.project_watch_accounts((native,))[0].accounts[0]
            self.assertEqual(first.ccost_scopes, after.ccost_scopes)
            self.assertNotIn("this month", dict(after.ccost_scopes))

    def test_watch_week_and_report_month_acquire_independent_available_history_scopes(self):
        source = SyntheticMonthSource(0, 1, month_start_ms=MONTH)
        source.snapshots = {f"root-{index:04d}": make_root_snapshot(index, 1, month_start_ms=when - index * 60_000)
                            for index, when in enumerate((MONTH, NOW - 2 * 86_400_000, NOW - HOUR))}
        native = replace(subscription("github-copilot"), quotas=(subscription("github-copilot").quotas[1],))
        with tempfile.TemporaryDirectory() as directory:
            _, _, service, _ = make_service(directory, source, now_ms=NOW)
            service.config["timezone"] = "Europe/Stockholm"
            self.addCleanup(service.close_accounts)
            service.project_watch_accounts((native,))
            roots = service.watch_history_candidates(service.session_catalog())
            self.assertEqual({"root-0001", "root-0002"}, {root.session_id for root in roots})
            service.watch_history_batch(roots)
            service.publish_watch_history()
            watch_row = service.project_watch_accounts((native,))[0].accounts[0]
            self.assertEqual(2, dict(watch_row.ccost_scopes)["weekly"].observed_requests)
            ordered, activity = service._ordered_roots(service.session_catalog())
            report_row = service._account_history((native,), ordered, activity).accounts[0]
            self.assertEqual(3, dict(report_row.ccost_scopes)["this month"].observed_requests)
            self.assertEqual(dict(watch_row.ccost_scopes)["weekly"], dict(report_row.ccost_scopes)["weekly"])
            self.assertEqual(dict(watch_row.ccost_scopes)["today"], dict(report_row.ccost_scopes)["today"])


if __name__ == "__main__":
    unittest.main()
