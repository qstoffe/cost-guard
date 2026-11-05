"""Card-owned current continuation guidance, separate from historical row facts."""
from dataclasses import dataclass
from decimal import Decimal

from src.analysis.context import PriceWarningSeverity, session_watch_context


@dataclass(frozen=True, slots=True)
class WatchContextGuidance:
    owner_id: str
    tokens: int | None
    text: str = ""
    severity: PriceWarningSeverity = PriceWarningSeverity.NONE
    multiplier: Decimal | None = None
    cached_ccost: Decimal | None = None
    fresh_ccost: Decimal | None = None


def card_context(projector, session_id, threshold_multiplier):
    record = max((item for item in projector.bundle.prompts
        if item.session_id == session_id and item.prompt_kind != "subtask"),
        key=lambda item: (item.prompt_time_ms, item.prompt_id), default=None)
    if record is None:
        return None
    state = session_watch_context(projector.snapshot, projector.bundle, record, projector.catalog, projector.epochs)
    warning = projector.warning(state.next_tokens, state.model_id)
    multiplier = (threshold_multiplier(state.model_id, warning.price_threshold)
                  if warning.price_threshold and threshold_multiplier is not None else None)
    return WatchContextGuidance(record.prompt_id, state.next_tokens, warning.text, warning.price_severity,
        multiplier, state.cached_ccost, state.fresh_ccost)
