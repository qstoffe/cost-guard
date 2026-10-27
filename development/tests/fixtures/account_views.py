"""Equivalent Normal CLI/Web account states, without private provider payloads."""
from dataclasses import replace
from decimal import Decimal as D

from src.analysis.quota_pace import QuotaPace
from src.analysis.valuation import ComparisonCost
from src.domain import AccountRef, AccountSnapshot, AccountUsageStatus as Status, BillingComponent, QuotaComponent
from src.reports.models import AccountProjection, AccountsQuotasProjection, ReportKind, ReportProjection

NOW = 1_793_052_000_000


def account_report():
    quota = QuotaComponent("Monthly", period="fixed", used=D("10.123456789"), limit=D("100"),
        remaining=D("89.876543211"), remaining_fraction=D("0.89876543211"), unit="AI credits",
        reset_at_ms=NOW + 2 * 86_400_000, remaining_money=D("8.9876543211"), limit_money=D("10"), status=Status.AVAILABLE)
    native = AccountSnapshot(AccountRef("synthetic", "github-copilot", account_id="test"), NOW,
        "GitHub Copilot", plan="Pro", quotas=(quota, QuotaComponent("5-hour", period="rolling",
            remaining_fraction=D("0.643219"), duration_seconds=18_000, reset_at_ms=NOW + 126 * 60_000)), status=Status.AVAILABLE,
        billing=(BillingComponent("Extra usage", D("1.23456789"), "USD", "month", "spend", "active"),),
        reason="PRIVATE reason", observations={"token": "PRIVATE token"})
    base = AccountProjection(native, "Available account", billed_today=D("0"), billed_month=D("1.23456789"),
        ccost_scopes=(("today", ComparisonCost(D("1.23456789"))), ("this month", ComparisonCost(D("12.3456789")))),
        pace=(QuotaPace("Monthly", "AI credits", D("29.958847737"), 3, 0, None),), unaccounted_usage=D("-0.123456"))
    accounts = [base]
    for label, state, availability, quotas, reason in (
        ("Blocked", Status.BLOCKED, "available", (replace(quota, used=D(100), remaining=D(0), remaining_fraction=D(0), remaining_money=D(0), status=Status.BLOCKED),), None),
        ("Unlimited", Status.AVAILABLE, "available", (replace(quota, unlimited=True, remaining=None, remaining_fraction=None, limit=None,
            remaining_money=None, limit_money=None),), None),
        ("Missing", Status.UNKNOWN, "unavailable", (), "auth_failure"),
        ("Partial", Status.UNKNOWN, "partial", (replace(quota, remaining=None, remaining_fraction=None, used=None, limit=None,
            remaining_money=None, limit_money=None, reset_at_ms=None, window_active=False, status=Status.UNKNOWN),), None),
        ("Rate limited", Status.UNKNOWN, "error", (), "rate_limited"),
        ("Recovering", Status.UNKNOWN, "stale", (replace(quota, status=Status.UNKNOWN),), "transport_failure"),
    ):
        snapshot = replace(native, ref=AccountRef("synthetic", "openai", account_id=label), quotas=quotas, billing=(),
            status=state, availability=availability, warnings=("PRIVATE warning",), observations={"parser_reason": reason})
        accounts.append(AccountProjection(snapshot, label, ccost_scopes=(("today", ComparisonCost(D(0), observed_requests=2, priced_requests=0)),),
            ccost_account_unknown=True, ccost_notes=("Attribution incomplete",)))
    return ReportProjection(ReportKind.NORMAL, "Accounts", "Synthetic", accounts_quotas=AccountsQuotasProjection(
        ComparisonCost(D("999")), ComparisonCost(D("9999")), tuple(accounts), now_ms=NOW))
