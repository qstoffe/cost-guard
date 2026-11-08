"""Aggregate canonical focal prompts at the same observation as Web cards."""
from decimal import Decimal

from .models import RunningPrompts, WatchCard


def running_prompts(cards: tuple[WatchCard, ...], state: str) -> RunningPrompts:
    if any(row.prompt.execution_unverified for card in cards for row in card.rows):
        return RunningPrompts(state="unverified")
    prompts = {(card.session_id, row.prompt.event_id): row.prompt
        for card in cards for row in card.rows
        if row.prompt.event_id == card.focal_id and row.prompt.in_progress and not row.prompt.is_compaction}
    complete = state == "observed"
    if not prompts and not complete:
        return RunningPrompts(state=state)
    return RunningPrompts(count=len(prompts),
        ccost=sum((row.ccost for row in prompts.values()), Decimal(0)),
        duration_ms=max((row.duration_ms for row in prompts.values() if row.duration_ms is not None), default=None),
        complete=complete,
        unresolved_cost=not complete or any(row.unresolved_cost for row in prompts.values()),
        cost_estimated=any(row.cost_estimated for row in prompts.values()), state=state)
