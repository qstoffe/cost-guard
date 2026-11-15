"""Prompt-event clocks over one acquired tree, independent of modification clocks."""
from collections import defaultdict

from src.domain import EventKind, MessageRole
from src.domain.session_tree import root_by_session

from .child_links import ChildLinkIndex
from .prompt_index import prompt_owners

KINDS = {EventKind.USER_PROMPT, EventKind.SUBTASK, EventKind.COMPACTION}


def source_identity(provenance):
    return provenance.source_type, provenance.source_generation, provenance.source_instance


def activity_fields(item):
    """Latest attributable start or explicit completion; absence needs full history.

    A catalog touch, part rewrite, polling time, and inferred inactivity are not
    prompt events. Child work uses the same bounded causal windows as accounting;
    a later independent turn in a reused child is not the root's activity.
    """
    snapshot = item.snapshot
    if (snapshot is None or snapshot.root.provenance != item.session.provenance
            or snapshot.source_revision != item.bundle.source_revision):
        return dict(last_activity_ms=None, activity_qualified=False)
    identity = source_identity(snapshot.root.provenance)
    mapping = root_by_session(tuple(session for session in snapshot.sessions
                                   if source_identity(session.provenance) == identity))
    messages = [message for message in snapshot.messages
                if source_identity(message.provenance) == identity
                and mapping.get(message.session_id) == snapshot.root.session_id]
    root_messages = [message for message in messages if message.session_id == snapshot.root.session_id]
    children = ChildLinkIndex(snapshot)
    scopes = children.scopes(root_messages)
    child_messages = children.messages(scopes)
    allowed_messages = {(message.session_id, message.message_id)
                        for message in (*root_messages, *child_messages)}
    events = {(event.session_id, event.event_id): event for event in snapshot.events
        if event.kind in KINDS and source_identity(event.provenance) == identity
        and mapping.get(event.session_id) == snapshot.root.session_id and (
            event.session_id == snapshot.root.session_id or any(
                event.session_id == scope.session_id and scope.start_ms <= event.created_at_ms < scope.end_ms
                or event.session_id == scope.session_id and event.event_id == scope.owner_id
                for scope in scopes))}
    owners = prompt_owners(snapshot)
    owners.update({key: key[1] for key, event in events.items() if event.kind is EventKind.COMPACTION})
    attempts = defaultdict(list)
    for message in messages:
        if (message.session_id, message.message_id) not in allowed_messages:
            continue
        parent = message.parent_message_id if message.role is MessageRole.ASSISTANT else message.message_id
        owner = owners.get((message.session_id, parent))
        if (message.session_id, owner) in events:
            attempts[message.session_id, owner].append(message)
    unsettled = {(record.session_id, record.prompt_id) for record in item.bundle.prompts
                 if record.in_progress or record.execution_unverified}
    unsettled.update((record.session_id, record.user_message_id) for record in item.bundle.compactions
                     if record.in_progress)
    values = []
    for key, event in events.items():
        start = event.created_at_ms
        if type(start) is not int or start <= 0:
            continue
        values.append(start)
        latest = max(attempts[key], key=lambda message: (message.created_at_ms, message.message_id), default=None)
        if latest is None or key in unsettled:
            continue
        # Completion belongs to the actual attempt, not its mutable parts or the
        # last request of a still-unfinished tool-calls continuation.
        terminal = (latest.termination.completed_at_ms if latest.termination else
                    latest.completed_at_ms if latest.finish_reason not in (None, "tool-calls") or latest.error_name else None)
        if type(terminal) is int and terminal >= start:
            values.append(terminal)
    return dict(last_activity_ms=max(values, default=None), activity_qualified=snapshot.complete)
