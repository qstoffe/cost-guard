"""Attempt-qualified descendant execution, independent of the parent outcome."""
from collections.abc import Mapping

from src.domain import EventKind, MessageRole
from .child_links import OPEN_END, part_time


def running_tool(message, terminal_at=0):
    terminal = max(terminal_at, message.termination.completed_at_ms if message.termination else
        message.completed_at_ms if message.error_name else 0)
    return any(part.kind == "tool" and isinstance(state := part.data.get("state"), Mapping)
        and str(state.get("status", "")).lower() in {"pending", "streaming", "running"}
        and (not terminal or part_time(part)[0] > terminal) for part in message.parts)


def descendant_activity(snapshot, children, scopes):
    """Return positive activity and process-local uncertainty, never cached truth.

    Closed launches need an owned child turn/crossing assistant or a newly
    created child. Open invocations retain their existing native-status support.
    A later independent child turn or invocation cannot lend its active flag.
    """
    sessions = {session.session_id: session for session in snapshot.sessions}
    by_session = {}
    for message in snapshot.messages:
        by_session.setdefault(message.session_id, []).append(message)
    active = unverified = False
    for scope in scopes:
        session = sessions[scope.session_id]
        messages = children.messages((scope,))
        latest = max(messages, key=lambda item: (item.created_at_ms, item.message_id), default=None)
        all_messages = by_session.get(scope.session_id, ())
        last = max(all_messages, key=lambda item: (item.created_at_ms, item.message_id), default=None)
        owners = {message.message_id for message in all_messages if message.role is MessageRole.USER
            and (scope.start_ms <= message.created_at_ms < scope.end_ms or message.message_id == scope.owner_id)}
        turns = sorted({event.created_at_ms for event in snapshot.events
            if event.session_id == scope.session_id and event.kind in {EventKind.USER_PROMPT, EventKind.SUBTASK}
            and event.created_at_ms >= scope.start_ms})
        qualified = (scope.end_ms == OPEN_END or bool(latest) or bool(owners)
            or scope.start_ms <= session.created_at_ms < scope.end_ms)
        displaced = last is not None and last not in messages and last.message_id not in owners
        if scope.background and len(turns) > 1 and last and last.created_at_ms >= turns[1]:
            displaced = True  # Open-ended accounting is not proof of current invocation ownership.
        # A later invocation wins even if no new child message has arrived yet.
        if not qualified or displaced or scope.invocation_end_ms != OPEN_END:
            continue
        terminal = latest and (latest.termination or latest.error_name or
            latest.completed_at_ms is not None and latest.finish_reason not in {None, "tool-calls"})
        terminal_at = (latest.termination.completed_at_ms if latest.termination else latest.completed_at_ms or 0) if terminal else 0
        tools = any(running_tool(message, terminal_at) for message in messages)
        background = any(item.running and item.owner_message_id in {m.message_id for m in messages}
            for item in snapshot.background)
        if tools or background:
            active = True
        elif not terminal and session.active is True:
            active = True
        elif not terminal and latest and latest.completed_at_ms is None:
            if snapshot.complete and session.active is False:
                unverified = True
            else:
                active = True  # Preserve supported message fallback, not native inactivity.
        elif latest is None and owners and session.active is not True:
            unverified = True  # An observed launch without an execution/end is not success.
    return active, unverified
