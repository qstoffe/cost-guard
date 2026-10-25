"""Copilot residuals require native monthly, fully acquired and priced evidence."""
from dataclasses import replace
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import tempfile
import unittest
from unittest.mock import patch

from development.tests.fixtures.accounts import account
from development.tests.fixtures.quota_rendering import quotas, report_text, watch_text
from development.tests.fixtures.report_runtime import FakePricingProvider
from development.tests.fixtures.session_snapshots import make_snapshot
from development.tests.fixtures.synthetic_month import SyntheticMonthSource, make_root_snapshot
from development.tests.fixtures.watch_runtime import make_service
from src.accounts.base import normalize_quota
from src.accounts.github_copilot import convert_entitlement_payload, convert_internal_user_payload
from src.analysis.causal import trace_entries
from src.analysis.period_ccost import history_start, monthly_quota_window
from src.analysis.timezones import local_day_start_ms, local_month_start_ms
from src.domain import ModelRef, QuotaComponent, TokenUsage
from src.presentation.accounts import account_ccost_lines
from src.reports.accounts import account_projections

D = Decimal


def timestamp(year, month, day=1, hour=0):
    return int(datetime(year, month, day, hour, tzinfo=timezone.utc).timestamp() * 1000)


START = timestamp(2026, 10)
RESET = timestamp(2026, 11)
NOW = timestamp(2026, 10, 25, 12)


def copilot(used="850", identity="one"):
    return replace(account("github-copilot", identity=identity, plan="Pro+"), fetched_at_ms=NOW, quotas=(
        QuotaComponent("Monthly", "fixed", used=None if used is None else D(used), limit=D(7000),
                       unit="AI credits", reset_at_ms=RESET),))


def request(name, *, when=NOW, amount=6_200_000, provider="github-copilot", ref=None, model="gpt-test"):
    return replace(trace_entries(make_snapshot())[0], message_id=name, step_part_id=None,
                   completed_at_ms=when, model=ModelRef(provider, model), tokens=TokenUsage(input=amount),
                   account_ref=ref)


def project(accounts, entries=(), *, now=NOW, zone="Europe/Stockholm", acquired=START, watch=False):
    return account_projections(accounts, entries, FakePricingProvider().catalog, now_ms=now,
                               today_start_ms=local_day_start_ms(zone, now_ms=now),
                               month_start_ms=local_month_start_ms(zone, now_ms=now), timezone_id=zone,
                               observed_start_ms=acquired, watch=watch)


class CopilotUnaccountedUsageTests(unittest.TestCase):
    def test_signed_residual_uses_unrounded_canonical_deduplicated_value(self):
        for native, amount, expected, display in (
            ("850", 6_200_000, "230", "+230"), ("500", 5_250_000, "-25", "-25"),
            ("620.15", 6_200_000, "0.15", "+0.2"), ("619.85", 6_200_000, "-0.15", "-0.2"),
            ("620.01", 6_200_000, "0.01", "+<0.1"), ("619.99", 6_200_000, "-0.01", "-<0.1"),
            ("657.2", 6_200_000, "37.2", "+38"), ("0", 0, "0", "0"),
        ):
            with self.subTest(native=native):
                entry = request("one", amount=amount)
                row = project((copilot(native),), (entry, replace(entry, session_id="fork")))[0]
                self.assertEqual(D(expected), row.unaccounted_usage)
                self.assertEqual("Unaccounted usage: " + display, account_ccost_lines(row)[-1])

    def test_unknown_evidence_always_keeps_row_and_existing_partial_ccost(self):
        native = copilot()
        cases = (
            (copilot(None), (request("known"),), START),
            (replace(native, quotas=()), (), START),
            (replace(native, quotas=(replace(native.quotas[0], reset_at_ms=None),)), (), START),
            (replace(native, quotas=(replace(native.quotas[0], reset_at_ms=NOW),)), (), START),
            (replace(native, quotas=(replace(native.quotas[0], reset_at_ms=RESET + 1),)), (), START),
            (replace(native, availability="stale"), (), START),
            (native, (request("known"),), START + 1),
            (native, (request("known"),), None),
            (native, (request("unknown", model="not-priced"),), START),
            (native, (request("known"), request("unknown", model="not-priced")), START),
        )
        for snapshot, entries, acquired in cases:
            with self.subTest(snapshot=snapshot, acquired=acquired):
                row = project((snapshot,), entries, acquired=acquired)[0]
                self.assertIsNone(row.unaccounted_usage)
                self.assertEqual("Unaccounted usage: —", account_ccost_lines(row)[-1])
        partial = project((native,), cases[-1][1])[0]
        self.assertFalse(dict(partial.ccost_scopes)["this month"].complete)
        self.assertIn("CCost this month: 620", account_ccost_lines(partial))

    def test_fully_acquired_empty_period_is_zero_not_missing_history(self):
        row = project((copilot("0"),))[0]
        self.assertEqual(D(0), row.unaccounted_usage)
        self.assertEqual("Unaccounted usage: 0", account_ccost_lines(row)[-1])
        self.assertIsNone(project((copilot("0"),), acquired=None)[0].unaccounted_usage)

    def test_provider_alias_publisher_independence_and_account_separation(self):
        one, two = copilot(), copilot("500", identity="two")
        entries = (request("one", ref=one.ref, provider="github-copilot-enterprise"),
                   request("two", ref=two.ref, amount=5_250_000),
                   request("direct", provider="openai"))
        rows = project((one, two), entries)
        self.assertEqual([D(230), D(-25)], [row.unaccounted_usage for row in rows])
        ambiguous = project((one, two), (*entries, request("unassigned")))
        self.assertTrue(all(row.unaccounted_usage is None for row in ambiguous))
        removed = copilot(identity="removed")
        single = project((one,), (request("unknown"), request("other", ref=removed.ref)))[0]
        self.assertEqual(D(230), single.unaccounted_usage)
        alias = replace(one, ref=replace(one.ref, provider_id="github-copilot-enterprise"))
        self.assertEqual(D(230), project((alias,), (request("alias"),))[0].unaccounted_usage)

    def test_native_utc_month_is_independent_of_local_month_and_dst(self):
        for zone, now, early, local_total in (
            ("Europe/Stockholm", NOW, START - 1, D(1240)),  # autumn DST day
            ("America/Los_Angeles", timestamp(2026, 10, 2), START + 1, D(620)),
        ):
            with self.subTest(zone=zone):
                entries = (request("boundary", when=early), request("inside", when=now))
                # A synthetic west-of-UTC zone keeps this model-free on Windows
                # without tzdata; Stockholm above exercises real DST independently.
                context = (patch("src.analysis.timezones.ZoneInfo", return_value=timezone(timedelta(hours=-7)))
                           if zone == "America/Los_Angeles" else nullcontext())
                with context:
                    row = project((copilot(),), entries, now=now, zone=zone)[0]
                expected = D(230) if zone == "Europe/Stockholm" else D(-390)
                self.assertEqual(expected, row.unaccounted_usage)
                self.assertEqual(local_total, dict(row.ccost_scopes)["this month"].known_ccost)
        march = replace(copilot().quotas[0], reset_at_ms=timestamp(2026, 4))
        self.assertEqual((timestamp(2026, 3), timestamp(2026, 3, 29, 12) + 1),
                         monthly_quota_window(march, timestamp(2026, 3, 29, 12)))
        january = replace(march, reset_at_ms=timestamp(2027, 1))
        self.assertEqual(timestamp(2026, 12), monthly_quota_window(january, timestamp(2026, 12, 20))[0])

    def test_only_supported_native_months_are_used(self):
        component = copilot().quotas[0]
        for changes in ({"period": "rolling"}, {"scope": "model"}, {"model_id": "gpt-test"},
                        {"origin": "estimated"}, {"window_active": False}, {"label": "Week"},
                        {"reset_at_ms": timestamp(2026, 12)}, {"reset_at_ms": timestamp(2026, 10)}):
            with self.subTest(changes=changes):
                self.assertIsNone(monthly_quota_window(replace(component, **changes), NOW))

    def test_existing_provider_evidence_flows_through_without_usage_inference(self):
        for converter, payload in (
            (convert_entitlement_payload, {"quotas": {"premiumInteractionsQuota": {"creditsUsed": "850", "total": 7000}}}),
            (convert_internal_user_payload, {"quota_snapshots": {"premium_interactions": {"credits_used": "850", "entitlement": 7000}}}),
        ):
            with self.subTest(converter=converter.__name__):
                snapshot = converter({**payload, "quota_reset_date_utc": "2026-11-01T00:00:00Z"}, fetched_at_ms=NOW)
                native = normalize_quota(snapshot, copilot().ref, "GitHub Copilot")
                self.assertEqual(D(230), project((native,), (request("one"),))[0].unaccounted_usage)
        percent = convert_internal_user_payload({"quota_reset_date": "2026-11-01", "quota_snapshots": {
            "premium_interactions": {"percent_remaining": 50, "entitlement": 7000}}}, fetched_at_ms=NOW)
        native = normalize_quota(percent, copilot().ref, "GitHub Copilot")
        self.assertIsNone(project((native,), ())[0].unaccounted_usage)

    def test_report_adds_exactly_one_row_per_copilot_account_but_watch_does_not(self):
        native = copilot()
        row = project((native,), (request("one"),))[0]
        text = report_text(replace(quotas(row), now_ms=NOW))
        self.assertEqual(1, text.count("Unaccounted usage: +230"))
        self.assertIn("CCost this month: 620", text)
        self.assertNotIn("Unaccounted usage", watch_text(replace(quotas(row), now_ms=NOW), width=160))
        non_copilot = project((account("openai"),))[0]
        self.assertFalse(any("Unaccounted" in line for line in account_ccost_lines(non_copilot)))
        self.assertIsNone(project((native,), (request("one"),), watch=True)[0].unaccounted_usage)

    @patch("src.analysis.timezones.ZoneInfo", return_value=timezone(timedelta(hours=-7)))
    def test_only_normal_report_extends_history_to_native_start(self, _zone):
        now = timestamp(2026, 10, 2)
        day = local_day_start_ms("America/Los_Angeles", now_ms=now)
        self.assertEqual(day, history_start((copilot(),), day, now))
        self.assertEqual(START, history_start((copilot(),), day, now, include_copilot_month=True))
        source = SyntheticMonthSource(0, 1, month_start_ms=START)
        source.snapshots = {"root-0000": make_root_snapshot(0, 1, month_start_ms=START + 60_000)}
        with tempfile.TemporaryDirectory() as directory:
            _, _, service, _ = make_service(directory, source, now_ms=now)
            service.config["timezone"] = "America/Los_Angeles"
            self.addCleanup(service.close_accounts)
            roots, activity = service._ordered_roots(service.session_catalog())
            row = service._account_history((copilot(),), roots, activity).accounts[0]
            self.assertEqual(D(0), dict(row.ccost_scopes)["this month"].known_ccost)
            self.assertIsNotNone(row.unaccounted_usage)
            self.assertLess(row.unaccounted_usage, D(850))


if __name__ == "__main__":
    unittest.main()
