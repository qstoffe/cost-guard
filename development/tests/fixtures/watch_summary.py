"""Synthetic Watch daily/account/context states shared by VM and visual checks."""
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal as D

from development.tests.fixtures.account_views import account_report, NOW
from development.tests.fixtures.warning_projections import warning_prompt
from src.accounts.base import normalize_quota
from src.accounts.openai_subscription import convert_usage_payload
from src.analysis.context import PriceWarningSeverity
from src.analysis.daily_usage import DailyUsage
from src.analysis.quota_pace import quota_pace
from src.analysis.token_mix import TokenMix
from src.analysis.valuation import ComparisonCost
from src.analysis.session_cost import SessionCost
from src.domain import AccountRef, AccountUsageStatus as Status, QuotaComponent
from src.reports.watch_context import WatchContextGuidance
from src.reports.models import QuotaPeriodProjection
from src.watch.models import SkillObservation, ToolObservation, WatchCard, WatchProjection, WatchRow


def summary_watch():
    quotas = account_report().accounts_quotas
    base = quotas.accounts[0]
    monthly = replace(base.account.quotas[0], remaining_fraction=D("0.91648"), used=D(2088), limit=D(25000),
        remaining=D(22912), unit="AI credits",
        reset_at_ms=int(datetime(2026, 11, 1, tzinfo=timezone.utc).timestamp() * 1000))
    five = QuotaComponent("5-hour", "rolling", remaining_fraction=D("0.75"), duration_seconds=18000,
        reset_at_ms=NOW + 3600000)
    weekly = QuotaComponent("Weekly", "rolling", used=D(100), limit=D(100), unit="requests",
        remaining_fraction=D(0), duration_seconds=604800,
        reset_at_ms=NOW + 86400000, status=Status.BLOCKED)
    accounts = []
    for index, (provider, label, windows) in enumerate((
        ("github-copilot", "GitHub Copilot Pro", (monthly,)),
        ("anthropic", "Claude Max · Personal research and development subscription with a long distinguishing title", (five, weekly)),
        ("anthropic", "Claude Max · Work", (replace(five, remaining_fraction=D("0.00001")), weekly)),
        ("other", "Other · Source-confirmed Unlimited", (QuotaComponent("Weekly", unlimited=True, primary=True),)),
        ("anthropic", "Claude Pro · Primary temporarily missing", (weekly,)),
    )):
        native = replace(base.account, ref=AccountRef("fixture", provider, account_id=str(index)),
            provider_label=label, plan=None, quotas=windows, billing=(), warnings=(), status=Status.UNKNOWN,
            primary_quota_label="5-hour" if provider == "anthropic" else None)
        periods = tuple(QuotaPeriodProjection(quota, ComparisonCost(D(1814) if quota is monthly else D(840) if quota is weekly else D(420), 2, 2),
            quota_pace(quota, now_ms=NOW, timezone_id="UTC", workday_calendar="SE")) for quota in windows)
        accounts.append(replace(base, account=native, label=label, quota_periods=periods,
            ccost_scopes=(("today", ComparisonCost(D("12.5"), 2, 2)),),
            ccost_estimated_scopes=("today",),
             ccost_notes=("CCost today: configured local calendar day; provider-attributed estimate; not verified account/billing attribution.",)))
    native = normalize_quota(convert_usage_payload({"plan_type": "pro_lite", "rate_limit": {
        "primary_window": {"limit_window_seconds": 604800, "used_percent": 42, "reset_after_seconds": 86400}}},
        fetched_at_ms=NOW), AccountRef("fixture", "openai", account_id="weekly"), "OpenAI Pro Lite")
    accounts.append(replace(base, account=native, label="OpenAI Pro Lite",
        quota_periods=(QuotaPeriodProjection(native.quotas[0], None, None),)))
    item = replace(warning_prompt(PriceWarningSeverity.EXCEEDED), event_id="prompt", in_progress=True,
        watch_model="Model", watch_effort="High", prompt_number=37,
        preview="Keep completed literally\nhttps://example.test/" + "long" * 200,
        has_additional_model=True)
    guidance = WatchContextGuidance("prompt", 120000, "[Price threshold >100.0K exceeded]",
        PriceWarningSeverity.EXCEEDED, D("2.4"), D(2), D(12))
    tool = ToolObservation(tool_counts=(("shell", 2), ("read", 1)), failed_count=1,
        running_tool="shell", running_ms=41000, background_kinds=("subagent",), background_ms=55000,
        skills=(SkillObservation("custom-skill", 1),))
    card = WatchCard("root", "Synthetic active session", "prompt", (WatchRow("root", "Session", item, "▶", tool),),
        state="observed", context_warning=guidance, session_context=guidance,
        session_cost=SessionCost(ComparisonCost(D("4582.125"), 2000, 2000), True, True), session_cost_state="observed")
    history = replace(card, session_id="past", title="Synthetic earlier session", focal_id="",
        rows=(WatchRow("past", "Earlier", replace(item, in_progress=False)),),
        context_warning=replace(guidance, severity=PriceWarningSeverity.APPROACHING,
             text="[Approaching price threshold >100.0K]", multiplier=None))
    history = replace(history, session_context=history.context_warning)
    mix = TokenMix((5000, 3000, 1000, 1000), (50, 30, 10, 10), 37, 100,
        (D(15), D(3), D(4), D(12)), 100, 10000)
    daily = DailyUsage(NOW - 3600000, NOW, ComparisonCost(D(34), 100, 100), mix, 37, True)
    return WatchProjection("Watch", "Synthetic", (), now_ms=NOW,
        quota=replace(quotas, accounts=tuple(accounts)), active_cards=(card,), history_cards=(history,),
        cards_state="observed", history_state="observed", daily_usage=daily, daily_state="observed")
