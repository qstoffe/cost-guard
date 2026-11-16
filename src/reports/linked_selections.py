"""Display-only selections inside canonical child invocation windows."""
from dataclasses import replace
from src.analysis.child_links import ChildLinkIndex
from src.analysis.effort import prompt_replies
from src.domain import ModelRef
from .model_details import executed
from .prompt_selection import selection_name


def selection_index(snapshot, revision):
    if snapshot is None or snapshot.source_revision != revision:
        return None
    identity = lambda provenance: (provenance.source_type, provenance.source_generation, provenance.source_instance)
    source = identity(snapshot.root.provenance)
    # Same IDs from another source generation/instance are not child evidence.
    snapshot = replace(snapshot,
        sessions=tuple(session for session in snapshot.sessions if identity(session.provenance) == source),
        messages=tuple(replace(message, parts=tuple(part for part in message.parts if identity(part.provenance) == source))
            for message in snapshot.messages if identity(message.provenance) == source),
        events=tuple(event for event in snapshot.events if identity(event.provenance) == source))
    replies = prompt_replies(snapshot)
    children = ChildLinkIndex(snapshot)
    events = {(event.session_id, event.event_id): event for event in snapshot.events
              if identity(event.provenance) == source}
    users = {(message.session_id, message.message_id): message for message in snapshot.messages
              if identity(message.provenance) == source and message.role.value == "user"}
    return replies, children, events, users


def linked_selections(snapshot, records, catalog, revision, *, index=None):
    index = index if index is not None else selection_index(snapshot, revision)
    if index is None:
        return ()
    replies, children, events, users = index
    lines = []
    for record in records:
        messages = replies.get((record.session_id, record.prompt_id), ())
        scopes = children.scopes(messages)
        for scope in scopes:
            event = events.get((scope.session_id, scope.owner_id))
            if event is None or any(entry.session_id == scope.session_id and executed(entry)
                                    for entry in record.entries):
                continue
            allowed = {(message.session_id, message.message_id) for message in children.messages((scope,))}
            matches = [message for message in replies.get((event.session_id, event.event_id), ())
                       if (message.session_id, message.message_id) in allowed
                       and message.model.provider and message.model.recorded_model]
            latest = max(matches, key=lambda message: (message.created_at_ms, message.message_id), default=None)
            user = users.get((event.session_id, event.event_id))
            selected = latest or user
            model = selected.model if selected and selected.model else ModelRef(
                event.metadata.get("provider_id", ""), event.metadata.get("model_id", ""))
            variant = selected.variant if selected and selected.variant else event.metadata.get("variant", "")
            name = selection_name(model, catalog)
            if not model.provider or not model.recorded_model or any(
                    not isinstance(text, str) or len(text) > limit or text and not text.isprintable()
                    for text, limit in ((model.provider, 128), (model.recorded_model, 256), (name, 256), (variant, 64))):
                continue
            line = f"{model.provider}/{name}"
            if variant:
                line += f" · {variant.capitalize()}"
            if name != model.recorded_model:
                qualifier = "catalog estimate; " if model.resolution else ""
                line += f" ({qualifier}recorded {model.provider}/{model.recorded_model})"
            state = next((agent.state for agent in record.agent_coverage if agent.session_id == scope.session_id), "")
            line += {
                "not-executed": " — No request recorded in complete child history.",
                "pending": " — Pending; usage/cost unknown.",
                "acquisition-pending": " — Partial source; usage/cost unknown.",
            }.get(state, " — Execution/inference and usage/cost unverified.")
            if len(line) <= 768 and line not in lines:
                lines.append(line)
            if len(lines) >= 24:
                return tuple(lines)
    return tuple(lines)
