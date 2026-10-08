"""Account-level BLOCKED ownership/deduplication and responsive compact Watch accounts."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
import re
import unittest

from development.tests.test_quota_presentation import NOW, quotas, report_text, rolling, watch_text
from src.accounts.base import normalize_quota
from src.accounts.github_copilot import convert_entitlement_payload
from src.accounts.openai_subscription import convert_usage_payload
from src.domain import AccountRef, AccountUsageStatus, QuotaComponent
from src.presentation.accounts import blocked_explained, capacity_lines
from src.presentation.terminal import AnsiStyler
from src.reports.models import AccountProjection

D = Decimal
ANSI = re.compile(r"\x1b\[[0-9;]*m")
BAR = re.compile(r"[█░]{10}")


def openai(five_hour_used=100, weekly_used=31, *, allowed=False):
    payload = {"plan_type": "plus", "rate_limit": {
        "allowed": allowed, "limit_reached": not allowed,
        "primary_window": {"used_percent": five_hour_used, "limit_window_seconds": 18_000, "reset_after_seconds": 3300},
        "secondary_window": {"used_percent": weekly_used, "limit_window_seconds": 604_800, "reset_after_seconds": 432_300}}}
    snapshot = normalize_quota(convert_usage_payload(payload, fetched_at_ms=NOW),
                               AccountRef("test", "openai", source_account="plus"), "OpenAI")
    return AccountProjection(snapshot, "OpenAI Plus")


def with_quotas(row, *items, status=AccountUsageStatus.BLOCKED):
    return replace(row, account=replace(row.account, status=status, quotas=items))


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
            self.assertIn("60%", text)
            self.assertEqual(1, len(re.findall(r"\bBLOCKED\b", text)), "positive quota cannot explain the pause")


class BlockedDeduplicationTests(unittest.TestCase):
    def test_exhausted_five_hour_explains_block_without_any_blocked_text(self):
        row = openai()
        watch = watch_text(quotas(row), width=160)
        lines = [line for line in watch.splitlines() if line.startswith("OpenAI Plus")]
        self.assertEqual(1, len(lines))
        self.assertRegex(lines[0], r"5h +░{10} +0% · Reset@\d\d:\d\d \| Week ███████░░░  69% · Reset@\w+ \d\d:\d\d$")
        report = report_text(quotas(row))
        for text in (watch, report):
            self.assertNotIn("BLOCKED", text)
        self.assertIn("Reset in 55min", report)

    def test_unexplained_or_unknown_blocks_keep_exactly_one_account_warning(self):
        cases = {
            "positive": (QuotaComponent("5-hour", remaining_fraction=D("0.4")),
                         QuotaComponent("weekly", remaining_fraction=D("0.69"))),
            "rounded zero": (QuotaComponent("5-hour", remaining_fraction=D("0.004")),),
            "unknown": (QuotaComponent("5-hour"), QuotaComponent("weekly", remaining_fraction=D("0.69"))),
            "expired": (QuotaComponent("5-hour", remaining_fraction=D(0), reset_at_ms=NOW - 1),),
            "not started": (QuotaComponent("5-hour", remaining_fraction=D(0), window_active=False),),
            "model scoped": (QuotaComponent("Fable", remaining_fraction=D(0), scope="model"),),
            "no quotas": (),
        }
        for name, items in cases.items():
            row = with_quotas(rolling(), *items)
            with self.subTest(name):
                self.assertFalse(blocked_explained(row.account, now_ms=NOW))
                for text in (watch_text(quotas(row), width=160), report_text(quotas(row))):
                    self.assertEqual(1, len(re.findall(r"\bBLOCKED\b", text)), text)
        rounded = watch_text(quotas(with_quotas(rolling(), *cases["rounded zero"])), width=160)
        self.assertIn("  0%", rounded)

    def test_component_block_without_account_block_keeps_its_own_indicator(self):
        row = with_quotas(rolling(), QuotaComponent("5-hour", remaining_fraction=D("0.4")),
                          QuotaComponent("Fable", remaining_fraction=D(0), scope="model", status=AccountUsageStatus.BLOCKED),
                          status=AccountUsageStatus.AVAILABLE)
        self.assertIn("Fable ░░░░░░░░░░   0% · BLOCKED", watch_text(quotas(row), width=160))

    def test_available_account_has_no_blocked_warning(self):
        for row in (openai(40, 31, allowed=True), rolling()):
            for text in (watch_text(quotas(row), width=160), report_text(quotas(row))):
                self.assertNotIn("BLOCKED", text)


class ResponsiveLayoutTests(unittest.TestCase):
    def test_split_at_pipe_with_aligned_indented_continuation(self):
        lines = [line for line in watch_text(quotas(openai()), width=70).splitlines() if BAR.search(line)]
        self.assertEqual(2, len(lines))
        self.assertTrue(lines[0].startswith("OpenAI Plus   5h "))
        self.assertTrue(lines[1].startswith(" " * 14 + "Week "))
        self.assertEqual(1, len({BAR.search(line).start() for line in lines}))
        self.assertIn("Reset@", lines[1])
        self.assertNotIn("|", "".join(lines))

    def test_oversized_component_wraps_alone_with_values_and_styles_intact(self):
        long = "Extremely long provider-defined model quota window name"
        row = with_quotas(rolling(), QuotaComponent("5-hour", remaining_fraction=D("0.4"), reset_at_ms=NOW + 3_600_000),
                          QuotaComponent(long, remaining_fraction=D("0.25"), reset_at_ms=NOW + 7_200_000),
                          status=AccountUsageStatus.AVAILABLE)
        styler = AnsiStyler({"dailyCostFilled": {"ansi256": 70}, "dailyCostEmpty": {"ansi256": 240}}, enabled=True)
        lines = capacity_lines(row, styler, "UTC", width=60, now_ms=NOW, watch=True, primary_label_width=4)
        visible = [ANSI.sub("", line) for line in lines]
        self.assertTrue(visible[0].startswith("OpenAI Plus   5h "))
        self.assertTrue(all(line.startswith(" " * 14) for line in visible[1:]))
        self.assertTrue(all(len(line) <= 60 for line in visible))
        joined = " ".join(line.strip() for line in visible)
        for value in (long, "40%", "25%", "Reset@21:00", "Reset@22:00", "███░░░░░░░"):
            self.assertIn(value, joined)
        for line in lines:
            self.assertEqual(line.count("\x1b[0m"), len(re.findall(r"\x1b\[(?!0m)[0-9;]*m", line)))

    def test_compact_fit_alignment_and_protected_neighbors(self):
        copilot = with_quotas(rolling("c", "GitHub Copilot Pro+"), QuotaComponent("Month", remaining_fraction=D("0.91")),
                              status=AccountUsageStatus.AVAILABLE)
        claude = rolling("b", "Claude Code Max")
        rows = (openai(), copilot, claude)
        text = watch_text(quotas(*rows), width=240)
        bars = [line for line in text.splitlines() if BAR.search(line)]
        self.assertEqual(3, len(bars), "one row per account")
        self.assertEqual(1, len({BAR.search(line).start() for line in bars}))
        self.assertNotIn("BLOCKED", text)
        recovering = capacity_lines(claude, AnsiStyler({}, enabled=False), "UTC", width=240, now_ms=NOW,
                                    watch=True, recovering=True)
        self.assertEqual(1, len(recovering))
        self.assertIn("STALE / RECONNECTING", recovering[0])
        narrow = capacity_lines(claude, AnsiStyler({}, enabled=False), "UTC", width=40, now_ms=NOW,
                                watch=True, recovering=True)
        self.assertEqual("Claude Code Max", narrow[0], "genuinely narrow keeps the verbose fallback")
        self.assertIn("  STALE / RECONNECTING", narrow)


if __name__ == "__main__":
    unittest.main()
