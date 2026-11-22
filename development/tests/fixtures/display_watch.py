"""Synthetic common Watch/Mini observations, without real account or source data."""
from decimal import Decimal

from src.analysis.session_cost import SessionCost
from src.analysis.valuation import ComparisonCost
from src.domain import AccountRef, AccountSnapshot, QuotaComponent
from src.reports.models import PromptProjection
from src.reports.watch_context import WatchContextGuidance
from src.watch.models import WatchCard, WatchProjection, WatchRow


def running_frame(now):
    prompt = PromptProjection(now - 2_000, 1, "Prompt", "private transcript sample", "Model medium",
        Decimal("0.125"), False, False, 2, 817, None, None, (12, 34, 5, 49), in_progress=True, event_id="prompt-1",
        watch_model="Model", watch_effort="medium", duration_ms=2000, watch_delta_context_tokens=-44)
    session_cost = SessionCost(
        ComparisonCost(Decimal("1.25000001"), observed_requests=4, priced_requests=4), True, True)
    card = WatchCard("root", "Observed title", prompt.event_id, (WatchRow("root", "Observed title", prompt),),
        state="observed", session_context=WatchContextGuidance("root", 773, context_scope="fixture"),
        session_cost=session_cost, session_cost_state="observed",
        observed_at_ms=now, invocation_verified=True)
    return WatchProjection("Watch", "fixture", (), now_ms=now, active_cards=(card,), cards_state="observed")


def native_account(now):
    return AccountSnapshot(
        AccountRef("private-provider-instance", "test-provider", "private-account-id"),
        now, "Fixture", plan="Pro",
        quotas=(QuotaComponent("Primary window", used=Decimal("1"), limit=Decimal("4"),
                               reset_at_ms=now + 20_000, primary=True, reference_ccost_capacity=Decimal("98765")),),
        observations={"private-provider-payload": "not exported"})
