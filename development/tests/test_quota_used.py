"""Shared used quota, remaining pace and native-unit formatting."""
from dataclasses import replace
from decimal import Decimal as D
import unittest

from development.tests.fixtures.quota_rendering import NOW, quotas, rolling, watch_text, report_text
from src.application.contracts import record, export
from src.application.display import with_display
from src.analysis.quota_pace import quota_pace
from src.display import quota_usage
from src.domain import QuotaComponent
from src.presentation.accounts import quota_parts


class UsedQuotaTests(unittest.TestCase):
    def test_remaining_pace_uses_19392_not_5608_after_bar_inversion(self):
        quota = QuotaComponent("Month", period="fixed", used=D(5608), remaining=D(19392),
            limit=D(25000), unit="AI credits", reset_at_ms=NOW + 4 * 3600_000)
        pace = quota_pace(quota, now_ms=NOW, timezone_id="UTC", workday_calendar="SE")
        self.assertEqual(D(19392), pace.per_day)
        self.assertEqual(D(19392), pace.per_workday)
        row = rolling()
        row = replace(row, account=replace(row.account, quotas=(quota,)), pace=(pace,))
        for text in (report_text(quotas(row)), watch_text(quotas(row), width=160)):
            self.assertIn("22% used", text)
            self.assertIn("19392/day · 19392/workday", text)
            self.assertNotIn("5608/day", text)

    def test_finite_parity_geometry_money_and_separate_remaining_pace(self):
        quota = QuotaComponent("Month", used=D(5608), remaining=D(19392), limit=D(25000),
            remaining_fraction=D("0.77568"), unit="AI credits", remaining_money=D("193.92"), limit_money=D(250))
        row = rolling()
        row = replace(row, account=replace(row.account, quotas=(quota,)))
        for width in (80, 120, 160):
            text = watch_text(quotas(row), width=width)
            self.assertIn("██░░░░░░░░  22% used", text)
            self.assertIn("5608/25000", text)
            self.assertNotIn("19392/25000", text)
            self.assertNotIn("CCost today", text)
            self.assertEqual(1, text.count("used"))
            self.assertTrue(all(len(line) <= width for line in text.splitlines()))
        normal = report_text(quotas(row))
        self.assertIn("5608/25000 AI credits ($56.08/$250.00)", normal)
        self.assertEqual(D("0.77568"), quota.remaining_fraction)
        self.assertEqual(D(19392), quota.remaining)
        dto = export(with_display(record(used=D(5608), remaining=D(19392), limit=D(25000),
            remaining_fraction=D("0.77568"), unit="AI credits", unlimited=False,
            remaining_money=D("193.92"), limit_money=D(250))))
        self.assertEqual("22%", dto["display"]["used_fraction"])
        self.assertEqual("5608/25000 AI credits", dto["display"]["quota_used"])
        self.assertEqual("$56.08", dto["display"]["used_money"])

    def test_unlimited_known_zero_unknown_and_no_denominator(self):
        for used in (None, D(0), D(5608)):
            quota = QuotaComponent("Month", used=used, unlimited=True, unit="AI credits")
            for watch in (True, False):
                text = " ".join(str(part) for part in quota_parts(quota, "UTC", now_ms=NOW, watch=watch, ccost="7"))
                self.assertIn("Unlimited", text)
                self.assertIn("Today: 7", text)
                for invalid in ("%", "█", "░", "/", "remaining", "limit unavailable"):
                    self.assertNotIn(invalid, text)
                if used is not None:
                    self.assertIn(str(used), text)
                    self.assertIn("used", text)
                else:
                    self.assertNotIn("used", text)
        self.assertEqual((None, D(17), None), quota_usage(used=D(17)))
        self.assertEqual((D("0.4"), None, None), quota_usage(remaining_fraction=D("0.6")))
        self.assertEqual((D(1), D(120), None), quota_usage(used=D(120), limit=D(100)))
        self.assertEqual((D(0), D(0), None), quota_usage(used=D(0), limit=D(100)))
        self.assertEqual((None, D(0), None), quota_usage(used=D(0), limit=D(0)))


if __name__ == "__main__":
    unittest.main()
