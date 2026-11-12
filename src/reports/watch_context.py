"""Card-owned current continuation guidance, separate from historical row facts."""
from dataclasses import dataclass, replace
from decimal import Decimal

from src.analysis.context import PriceWarningSeverity
from src.analysis.session_context import session_context_observation


@dataclass(frozen=True, slots=True)
class WatchContextGuidance:
    owner_id: str
    tokens: int | None
    text: str = ""
    severity: PriceWarningSeverity = PriceWarningSeverity.NONE
    multiplier: Decimal | None = None
    cached_ccost: Decimal | None = None
    fresh_ccost: Decimal | None = None
    model_id: str = ''
    price_threshold: int = 0
    price_basis: object = None
    guidance_signature: str = ''
    guidance_state: str = 'ready'
    source_epoch: str = ''
    guidance_sample_at_ms: int | None = None
    context_state: str = 'ready-current'
    context_scope: str = ''
    context_epoch: str = ''
    context_provider: str = ''
    context_model: str = ''
    context_anchor: str = ''
    context_at_ms: int = 0


def card_context(projector, session_id, threshold_multiplier, *, defer_guidance=False,
                 guidance_signature='', source_epoch=''):
    record = max((item for item in projector.bundle.prompts
        if item.session_id == session_id and item.prompt_kind != "subtask"),
        key=lambda item: (item.prompt_time_ms, item.prompt_id), default=None)
    observation = session_context_observation(projector.snapshot, projector.bundle, record,
        projector.catalog, projector.epochs, source_epoch=source_epoch)
    state = observation.value
    warning = projector.warning(state.next_tokens, state.model_id)
    multiplier = (threshold_multiplier(state.model_id, warning.price_threshold)
                  if warning.price_threshold and threshold_multiplier is not None and not defer_guidance else None)
    return WatchContextGuidance(record.prompt_id if record else '', state.next_tokens, warning.text, warning.price_severity,
        multiplier, state.cached_ccost, state.fresh_ccost, state.model_id, warning.price_threshold,
        state.price_basis, guidance_signature, 'pending' if defer_guidance and warning.price_threshold else 'ready',
        source_epoch, context_state=observation.status, context_scope=observation.scope,
        context_epoch=observation.epoch, context_provider=observation.provider,
        context_model=observation.model, context_anchor=observation.anchor_id,
        context_at_ms=state.last_activity_ms)


def retain_session_context(current, previous, snapshot=None):
    """Carry only pending same-source/epoch tokens; never carry price guidance."""
    if current is None and previous is not None:
        current = replace(previous, tokens=None, context_state='pending', text='',
            severity=PriceWarningSeverity.NONE, multiplier=None, cached_ccost=None, fresh_ccost=None,
            model_id='', price_threshold=0, price_basis=None, guidance_state='ready')
    if (current is None or previous is None or current.context_state != 'pending'
            or previous.tokens is None or not current.context_scope
            or (current.tokens is not None and current.context_at_ms >= previous.context_at_ms)
            or (current.context_scope, current.context_epoch) != (previous.context_scope, previous.context_epoch)
            or (current.context_provider and previous.context_provider and current.context_provider != previous.context_provider)
            or (current.context_model and previous.context_model and current.context_model != previous.context_model)):
        return current
    active = next((item for item in snapshot.active_contexts if item.session_id == snapshot.root.session_id), None) if snapshot else None
    if active is not None and previous.context_anchor not in active.message_ids:
        return replace(current, context_state='invalidated')
    return replace(current, tokens=previous.tokens, context_anchor=previous.context_anchor,
        context_at_ms=previous.context_at_ms,
        context_provider=current.context_provider or previous.context_provider,
        context_model=current.context_model or previous.context_model,
        text='', severity=PriceWarningSeverity.NONE, multiplier=None, cached_ccost=None,
        fresh_ccost=None, model_id='', price_threshold=0, price_basis=None, guidance_state='ready')
