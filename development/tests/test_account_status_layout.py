"""Account-level BLOCKED ownership/deduplication and responsive compact Watch accounts."""
from __future__ import annotations

from decimal import Decimal
import re
import unittest

from development.tests.fixtures.quota_rendering import NOW, quotas, report_text, watch_text
from src.accounts.base import normalize_quota
from src.accounts.github_copilot import convert_entitlement_payload
from src.accounts.openai_subscription import convert_usage_payload
from src.domain import AccountRef, AccountUsageStatus
from src.presentation.accounts import blocked_explained
from src.reports.models import AccountProjection

D = Decimal


def openai(five_hour_used=100, weekly_used=31, *, allowed=False):
    payload = {"plan_type": "plus", "rate_limit": {
        "allowed": allowed, "limit_reached": not allowed,
        "primary_window": {"used_percent": five_hour_used, "limit_window_seconds": 18_000, "reset_after_seconds": 3300},
        "secondary_window": {"used_percent": weekly_used, "limit_window_seconds": 604_800, "reset_after_seconds": 432_300}}}
    snapshot = normalize_quota(convert_usage_payload(payload, fetched_at_ms=NOW),
                               AccountRef("test", "openai", source_account="plus"), "OpenAI")
    return AccountProjection(snapshot, "OpenAI Plus")


class StatusOwnershipTests(unittest.TestCase):
    def test_openai_account_block_stays_on_account_not_on_each_window(self):
        row = openai()
        self.assertIs(AccountUsageStatus.BLOCKED, row.account.status)
        self.assertEqual({AccountUsageStatus.UNKNOWN}, {item.status for item in row.account.quotas})
        self.assertEqual((D(0), D("0.69")), tuple(item.remaining_fraction for item in row.account.quotas))
        self.assertTrue(blocked_explained(row.account, now_ms=NOW))

    def test_copilot_has_quota_remains_window_evidence_and_paused_warning(self):
        snapshot = convert_entitlement_payload({"quotas": {"premiumInteractionsQuota": {
            "hasQuota": False, "total": 300, "creditsUsed": 120}}}, fetched_at_ms=NOW)
        row = AccountProjection(normalize_quota(snapshot, AccountRef("test", "github-copilot", source_account="c"),
                                                "GitHub Copilot"), "GitHub Copilot Pro")
        self.assertIs(AccountUsageStatus.BLOCKED, row.account.quotas[0].status)
        for text in (watch_text(quotas(row), width=160), report_text(quotas(row))):
            self.assertIn("COPILOT PAUSED", text)
            self.assertIn("40% used", text)
            self.assertEqual(1, len(re.findall(r"\bBLOCKED\b", text)), "positive quota cannot explain the pause")


if __name__ == "__main__":
    unittest.main()
