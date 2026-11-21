"""Synthetic common Watch/Mini observations, without real account or source data."""
from decimal import Decimal
from types import SimpleNamespace

from src.analysis.valuation import ComparisonCost
from src.reports.models import PromptProjection
from src.watch.models import WatchCard, WatchProjection, WatchRow


def running_frame(now):
    prompt = PromptProjection(now - 2_000, 1, "Prompt", "private transcript sample", "Model medium",
        Decimal("0.125"), False, False, 2, 817, None, None, (12, 34, 5, 49), in_progress=True, event_id="prompt-1",
        watch_model="Model", watch_effort="medium", duration_ms=2000, watch_delta_context_tokens=-44)
    session_cost = SimpleNamespace(
        total=ComparisonCost(Decimal("1.25000001"), observed_requests=4, priced_requests=4), source_complete=True)
    card = WatchCard("root", "Observed title", prompt.event_id, (WatchRow("root", "Observed title", prompt),),
        state="observed", session_context=SimpleNamespace(tokens=773), session_cost=session_cost,
        observed_at_ms=now, invocation_verified=True)
    return WatchProjection("Watch", "fixture", (), now_ms=now, active_cards=(card,), cards_state="observed")
