"""Reuse qualified live card metrics without waiting for the history lane."""
from dataclasses import replace


def with_live_metrics(running, frame):
    if not running or frame is None:
        return running
    # Both sides must prove the same focal prompt and capture. A card retained
    # during an outage, a different concurrent prompt or a neighboring source
    # observation cannot decorate a current Sessions row.
    matches = {(row.session_id, row.prompt_id, row.started_ms, row.observed_ms): row for row in running}
    metrics = {}
    for card in frame.active_cards:
        if not card.focal_id or card.invocation_verified is not True:
            continue
        prompt = next((row.prompt for row in card.rows if row.prompt.event_id == card.focal_id), None)
        if not prompt or not prompt.in_progress or prompt.execution_unverified:
            continue
        item = matches.get((card.session_id, prompt.event_id, prompt.at_ms, card.observed_at_ms))
        if item is None:
            continue
        cost = card.session_cost
        context = card.session_context
        ccost = (cost.total.known_ccost if card.session_cost_state == "observed"
                 and cost is not None and cost.source_complete and cost.total.complete else None)
        invalidated = context is not None and context.context_state == "invalidated"
        tokens = context.tokens if context is not None and not invalidated else None
        metrics[item.session_id] = replace(item, ccost=ccost, context_tokens=tokens, context_invalidated=invalidated)
    return tuple(metrics.get(row.session_id, row) for row in running)
