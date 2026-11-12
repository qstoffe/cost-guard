"""Current session continuation observations, never prompt-local Ictx or delta.

Missing new-request telemetry is pending. Only source evidence retires a usable
anchor; terminal status and independent history-publication lifetimes do not.
"""
from dataclasses import dataclass, replace
from hashlib import sha256

from src.domain import EventKind
from .context import WatchContextState, session_watch_context


@dataclass(frozen=True, slots=True)
class SessionContextObservation:
    value: WatchContextState
    status: str
    scope: str
    epoch: str
    provider: str = ''
    model: str = ''
    anchor_id: str = ''


def _digest(value):
    return sha256(repr(value).encode('utf-8')).hexdigest()[:24]


def _state(snapshot, bundle, record, catalog, epochs):
    # A failure flag retires prompt-local metrics, not valid session history.
    return session_watch_context(snapshot, bundle,
        replace(record, watch_error=False) if record.watch_error else record, catalog, epochs)


def session_context_observation(snapshot, bundle, record, catalog, epochs, *, source_epoch=''):
    """Resolve from already acquired canonical evidence, including fresh launches.

    Search the analyzed root, not the bounded card-row slice. A fallback is a
    verified continuation anchor, not an arbitrary historical prompt value.
    """
    root = snapshot.root
    provenance = root.provenance
    scope = _digest((provenance.source_type, provenance.source_generation,
        provenance.source_instance, root.session_id, root.created_at_ms, source_epoch))
    boundaries = tuple((item.at_ms, item.kind, item.boundary_id) for item in snapshot.context_boundaries
        if item.session_id == root.session_id)
    compactions = tuple({(item.created_at_ms, item.user_message_id) for item in bundle.compactions
        if item.session_id == root.session_id} | {(item.created_at_ms, item.event_id) for item in snapshot.events
        if item.session_id == root.session_id and item.kind is EventKind.COMPACTION})
    epoch = _digest((sorted(boundaries), sorted(compactions)))
    provider = record.main_provider_id if record else ''
    model = record.main_model_id if record else ''
    def observation(value, status, anchor=''):
        return SessionContextObservation(value, status, scope, epoch, provider, model, anchor)
    empty = WatchContextState(None, None)
    if record is None:
        return observation(empty, 'invalidated' if snapshot.complete else 'pending')
    state = _state(snapshot, bundle, record, catalog, epochs)
    if state.next_tokens is not None:
        if any(at > state.last_activity_ms for at, _ in compactions):
            return observation(empty, 'invalidated')
        return observation(state, 'ready-current', record.last_root_entry.message_id
            if record.last_root_entry else record.prompt_id)
    if epochs.active_prompt(record) is False:
        return observation(empty, 'invalidated')
    candidates = sorted((item for item in bundle.prompts
        if item.session_id == root.session_id and item.prompt_kind != 'subtask'
        and (item.prompt_time_ms, item.prompt_id) < (record.prompt_time_ms, record.prompt_id)),
        key=lambda item: (item.prompt_time_ms, item.prompt_id), reverse=True)
    for prior in candidates:
        entry = prior.last_root_entry
        if entry is None:
            continue
        if (epochs.active_entry(entry) is False or epochs.retired(root.session_id, entry.completed_at_ms)
                or any(at >= entry.completed_at_ms for at, _ in compactions)
                or (provider and provider != entry.model.provider) or (model and model != entry.model.model)):
            return observation(empty, 'invalidated')
        previous = _state(snapshot, bundle, prior, catalog, epochs)
        if previous.next_tokens is not None and epochs.active_entry(entry) is True:
            # Price/model warnings require the current selector, not the prior one.
            return replace(observation(WatchContextState(previous.next_tokens, None,
                model_id=model, last_activity_ms=previous.last_activity_ms), 'pending', entry.message_id),
                provider=provider or entry.model.provider, model=model or entry.model.model)
    if boundaries or compactions:
        return observation(empty, 'invalidated')
    return observation(empty, 'pending')
