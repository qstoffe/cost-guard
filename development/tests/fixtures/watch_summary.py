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
from src.analysis.quota_pace import QuotaPace, quota_pace
from src.analysis.token_mix import TokenMix
from src.analysis.valuation import ComparisonCost
from src.analysis.session_cost import SessionCost
from src.domain import AccountRef, AccountUsageStatus as Status, QuotaComponent
from src.reports.watch_context import WatchContextGuidance
from src.reports.models import QuotaPeriodProjection
from src.reports.prompt_costs import PromptCostPart
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
        has_additional_model=True, linked_agent_count=2,
        ccost=D(33), incoming_context_ccost=D(11), extra_ccost=D(22), calls=4,
        cost_parts=(
            PromptCostPart('root', 0, 'fixture', 'main-model', 'high', 'Main Model', 'High',
                2, D(25), 2, True, (D(8), D(2), D(1), D(14))),
            PromptCostPart('child', 1, 'fixture', 'child-model', 'low', 'Child Model', 'Low',
                1, D(8), 1, True, (D(3), D(1), D(0), D(4)),
                prompt_ids=(('fixture', 'child', 'child-prompt'),), prompts_complete=True),
            PromptCostPart('nested', 2, 'fixture', 'child-model', 'low', 'Child Model', 'Low',
                1, D(0), 1, True, (D(0), D(0), D(0), D(0)),
                prompt_ids=(('fixture', 'nested', 'nested-prompt'),), prompts_complete=True)))
    guidance = WatchContextGuidance("prompt", 120000, "[Price threshold >100.0K exceeded]",
        PriceWarningSeverity.EXCEEDED, D("2.4"), D(2), D(12))
    tool = ToolObservation(tool_counts=(("shell", 2), ("read", 1)), failed_count=1,
        running_tool="shell", running_ms=41000, background_kinds=("subagent",), background_ms=55000,
        skills=(SkillObservation("custom-skill", 1),))
    card = WatchCard("root", "Synthetic active session", "prompt", (WatchRow("root", "Session", item, "▶", tool),),
        state="observed", session_context=guidance,
        session_cost=SessionCost(ComparisonCost(D("4582.125"), 2000, 2000), True, True,
            main_ccost=D(4000), subagent_ccost=D("582.125")), session_cost_state="observed",
        observed_at_ms=NOW)
    history = replace(card, session_id="past", title="Synthetic earlier session", focal_id="",
        rows=(WatchRow("past", "Earlier", replace(item, in_progress=False, completed_at_ms=NOW - 1000)),),
        session_context=replace(guidance, severity=PriceWarningSeverity.APPROACHING,
            text="[Approaching price threshold >100.0K]", multiplier=None))
    mix = TokenMix((5000, 3000, 1000, 1000), (50, 30, 10, 10), 37, 100,
        (D(15), D(3), D(4), D(12)), 100, 10000)
    daily = DailyUsage(NOW - 3600000, NOW, ComparisonCost(D(34), 100, 100), mix, 37, True)
    return WatchProjection("Watch", "Synthetic", (), now_ms=NOW,
        quota=replace(quotas, accounts=tuple(accounts)), active_cards=(card,), history_cards=(history,),
        cards_state="observed", history_state="observed", daily_usage=daily, daily_state="observed")


def authoritative_allowances(frame):
    """External provider usage differs from local cost; two independent native mappings."""
    base = frame.quota.accounts[0]
    primary = QuotaComponent('Monthly', 'fixed', used=D(3000), remaining=D(7000), limit=D(10000),
        unit='AI credits', reset_at_ms=frame.now_ms + 6 * 86400000, primary=True)
    secondary = QuotaComponent('Model allowance', 'fixed', used=D(3), remaining=D(7), limit=D(10),
        unit='requests', scope='model', model_id='synthetic-model', reference_ccost_capacity=D(2000),
        reset_at_ms=frame.now_ms + 2 * 86400000)
    quotas = (primary, secondary)
    periods = tuple(QuotaPeriodProjection(q, ComparisonCost(D(cost), 1, 1),
        quota_pace(q, now_ms=frame.now_ms, timezone_id='UTC', workday_calendar='SE'))
        for q, cost in zip(quotas, (450, 999)))
    item = replace(base, account=replace(base.account, quotas=quotas), quota_periods=periods)
    return replace(frame, quota=replace(frame.quota, accounts=(item,)))


def estimated_allowances(frame, used=D(613)):
    """Independent raw parent/rates and a shorter secondary window for browser help."""
    base = frame.quota.accounts[0]
    primary = QuotaComponent('Monthly', 'fixed', used=D(10), remaining=D(90), limit=D(100),
        unit='messages', reset_at_ms=frame.now_ms + 9 * 86400000, primary=True)
    secondary = QuotaComponent('5-hour', 'rolling', remaining_fraction=D('.9'), duration_seconds=18000,
        reset_at_ms=frame.now_ms + 3600000)
    periods = (QuotaPeriodProjection(primary, ComparisonCost(used, 1, 1), QuotaPace('Monthly', 'messages', D(10), 9, 3, D(30))),
        QuotaPeriodProjection(secondary, ComparisonCost(D('61.3'), 1, 1), None))
    item = replace(base, account=replace(base.account, ref=AccountRef('fixture', 'other', account_id='estimate'),
        quotas=(primary, secondary), primary_quota_label='Monthly'), quota_periods=periods)
    return replace(frame, quota=replace(frame.quota, accounts=(item,)))


def many_cost_groups(frame):
    """Thirty distinct synthetic groups through the real bounded cost exporter."""
    card = frame.active_cards[0]
    row = card.rows[0]
    original = row.prompt.cost_parts[0]
    parts = tuple(replace(original, agent=index, session_id=f"agent-{index}",
        variant=f"effort-{index}", effort=f"Effort {index}") for index in range(30))
    prompt = replace(row.prompt, cost_parts=parts, linked_agent_count=29,
        calls=60, ccost=D(750), incoming_context_ccost=D(8), extra_ccost=D(742))
    return replace(frame, active_cards=(replace(card, rows=(replace(row, prompt=prompt),)),))


def secondary_estimates(frame, phase):
    """Three independent native windows with partial→complete→reset browser updates."""
    base = frame.quota.accounts[0]
    primary = QuotaComponent('5-hour', 'rolling', remaining_fraction=D('.8'), duration_seconds=18000,
        reset_at_ms=frame.now_ms + 3600000, primary=True)
    weekly = QuotaComponent('Weekly', 'rolling', remaining_fraction=D('.9301') if phase == 'raw' else D('.93'),
        duration_seconds=604800, reset_at_ms=frame.now_ms + 86400000)
    later = QuotaComponent('Model daily', 'rolling', scope='model', model_id='synthetic-model',
        remaining_fraction=D('.5'), duration_seconds=86400, reset_at_ms=frame.now_ms + 3600000)
    if phase == 'reset':
        weekly = replace(weekly, remaining_fraction=D(1), reset_at_ms=weekly.reset_at_ms + 604800000)
    quotas = (primary, weekly, later)
    costs = (ComparisonCost(D(200), 1, 1), ComparisonCost(D(1020), 3, 3 if phase == 'complete' else 2), ComparisonCost(D(40), 2, 1))
    periods = tuple(QuotaPeriodProjection(q, None if phase in {'history', 'reset'} and q is weekly else cost, None)
        for q, cost in zip(quotas, costs))
    note = ('CCost Weekly: waiting for complete period history.',) if phase == 'history' else ()
    item = replace(base, account=replace(base.account, ref=AccountRef('fixture', 'claude-code', account_id='secondary'),
        quotas=quotas, primary_quota_label='5-hour', provider_label='Claude Code', plan='Pro'),
        label='Claude Code Pro', quota_periods=periods, ccost_notes=note, ccost_estimated_scopes=('Weekly',))
    return replace(frame, quota=replace(frame.quota, accounts=(item,)))


def same_model_groups(frame):
    """Single-model linked work must still export actual main/child effort help."""
    card = frame.active_cards[0]
    row = card.rows[0]
    parts = tuple(replace(part, model_id='main-model', model='Main Model') for part in row.prompt.cost_parts)
    return replace(frame, active_cards=(replace(card, rows=(replace(row, prompt=replace(row.prompt, cost_parts=parts)),)),))
