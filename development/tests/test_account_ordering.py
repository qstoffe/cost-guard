"""Stable capacity/name/account ordering for shared report and Watch projections."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
import itertools
from types import SimpleNamespace
import unittest

from development.fixtures.pricing_catalog import catalog
from src.accounts.acquisition import _failure
from src.accounts.base import normalize_quota
from src.accounts.discovery import AccountCandidate
from src.accounts.github_copilot import convert_internal_user_payload
from src.domain import AccountRef, AccountSnapshot, AccountUsageStatus, QuotaComponent
from src.reports.accounts import account_projections


class AccountOrderingTests(unittest.TestCase):
    def test_credit_class_survives_failed_acquisition_with_known_plan_and_label(self):
        provider = SimpleNamespace(provider_id="github-copilot", capacity_kind="credit")
        candidate = AccountCandidate(0, provider, None)
        ref = AccountRef("s", provider.provider_id, "c")
        known = normalize_quota(convert_internal_user_payload({
            "copilot_plan": "individual_pro", "quota_snapshots": {
                "premium_interactions": {"entitlement": 7000, "credits_used": 5}}}),
            ref, "GitHub Copilot", capacity_kind=provider.capacity_kind)
        known = replace(known, status=AccountUsageStatus.BLOCKED, warnings=("Previously blocked",))

        failed, = _failure(candidate, (known,), "s", 10, timeout=True)
        first_failure, = _failure(candidate, (), "s", 10, timeout=True)

        self.assertEqual("credit", known.capacity_kind)
        self.assertEqual("credit", failed.capacity_kind)
        self.assertEqual("credit", first_failure.capacity_kind)
        self.assertEqual(known.provider_label, failed.provider_label)
        self.assertEqual(known.plan, failed.plan)
        self.assertEqual(known.key, failed.key)
        self.assertEqual("error", failed.availability)
        self.assertFalse(failed.quotas)
        self.assertEqual(AccountUsageStatus.UNKNOWN, failed.status)
        self.assertFalse(failed.warnings)

    def test_capacity_then_name_then_identity_ignore_input_order_and_remaining(self):
        accounts = (
            AccountSnapshot(AccountRef("source", "copilot", "b"), 1, "GitHub Copilot", "Pro+", capacity_kind="credit"),
            AccountSnapshot(AccountRef("source", "openai", "o"), 1, "OpenAI", "Plus"),
            AccountSnapshot(AccountRef("source", "claude", "c"), 1, "Claude Code", "Pro"),
            AccountSnapshot(AccountRef("source", "copilot", "a"), 1, "GitHub Copilot", "Pro+", capacity_kind="credit"),
            AccountSnapshot(AccountRef("source", "api", "d"), 1, "DeepSeek", capacity_kind="credit"),
        )
        expected = ("d", "a", "b", "c", "o")
        for permutation in itertools.permutations(accounts):
            for fraction in (Decimal(0), Decimal(1)):
                changed = tuple(replace(account, quotas=(QuotaComponent("quota", remaining_fraction=fraction),))
                                for account in permutation)

                result = account_projections(changed, (), catalog(), now_ms=10, today_start_ms=0, month_start_ms=0)

                self.assertEqual(expected, tuple(row.account.ref.account_id for row in result))
                self.assertEqual("GitHub Copilot Pro+ · account 1", result[1].label)
                self.assertEqual("GitHub Copilot Pro+ · account 2", result[2].label)

    def test_error_or_partial_observation_keeps_capacity_group(self):
        credit = AccountSnapshot(AccountRef("s", "credits", "c"), 1, "Zulu", capacity_kind="credit")
        usage = AccountSnapshot(AccountRef("s", "usage", "u"), 1, "Alpha")
        for availability in ("available", "partial", "stale", "error", "unavailable"):
            changed = replace(credit, availability=availability, quotas=())

            result = account_projections((usage, changed), (), catalog(), now_ms=10, today_start_ms=0, month_start_ms=0)

            self.assertEqual(("c", "u"), tuple(row.account.ref.account_id for row in result))


if __name__ == "__main__":
    unittest.main()
