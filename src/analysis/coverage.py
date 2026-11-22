"""Source-qualified request coverage, independent of prices or inferred spend."""
from dataclasses import dataclass
from collections import defaultdict

from src.domain import MessageRole


@dataclass(frozen=True, slots=True)
class AgentCoverage:
    session_id: str
    state: str
    attribution: str = "verified"


def unrepresented_usage(messages, entries):
    represented = {(entry.session_id, entry.message_id) for entry in entries}
    return any(message.role is MessageRole.ASSISTANT
        and (message.session_id, message.message_id) not in represented
        and (message.tokens is not None and message.tokens.total > 0
             or message.tokens is None and any(part.kind in {"text", "reasoning"} and part.data.get("text")
                 for part in message.parts))
        for message in messages)


def _turn_state(messages, entries):
    if unrepresented_usage(messages, entries):
        return "usage-unavailable"
    assistants = [message for message in messages if message.role is MessageRole.ASSISTANT and not message.summary]
    if not assistants and any(message.termination for message in messages):
        return "not-executed"
    latest = max(assistants, key=lambda item: (item.created_at_ms, item.message_id), default=None)
    if latest and latest.completed_at_ms is None and not latest.termination and not latest.error_name:
        return "pending"
    return "usage-observed" if entries else "usage-unavailable"


def child_coverage(snapshot, session_ids, messages, entries, *, attribution=None, turns=()):
    sessions = {session.session_id: session for session in snapshot.sessions}
    by_message, by_entry = defaultdict(list), defaultdict(list)
    for message in messages:
        by_message[message.session_id].append(message)
    for entry in entries:
        by_entry[entry.session_id].append(entry)
    turn_states = defaultdict(set)
    for session, turn_messages, turn_entries in turns:
        turn_states[session].add(_turn_state(turn_messages, turn_entries))
    result = []
    for identity in session_ids:
        own_messages, own_entries = by_message[identity], by_entry[identity]
        basis = attribution.get(identity, "verified") if attribution else "verified"
        # A reused session's current activity is not evidence about the
        # execution or completeness of a specific timing-attributed turn.
        active = sessions[identity].active if basis == "verified" else None
        if not snapshot.complete:
            state = "acquisition-pending"
        elif unrepresented_usage(own_messages, own_entries):
            state = "usage-unavailable"
        elif "usage-unavailable" in turn_states[identity]:
            state = "usage-unavailable"
        elif "pending" in turn_states[identity]:
            state = "pending"
        elif own_entries:
            state = "usage-observed"
        elif turn_states[identity] == {"not-executed"} and basis == "inferred":
            state = "not-executed"
        elif not any(message.role is MessageRole.ASSISTANT for message in own_messages) and active is False:
            state = "not-executed"
        elif active is True:
            state = "pending"
        else:
            state = "usage-unavailable"
        result.append(AgentCoverage(identity, state, basis))
    return tuple(result)


def coverage_complete(agents):
    return all(agent.state in {"usage-observed", "not-executed"} for agent in agents)


def snapshot_coverage_complete(snapshot, entries):
    children = tuple(session.session_id for session in snapshot.sessions
                     if session.session_id != snapshot.root.session_id)
    return (snapshot.complete and not unrepresented_usage(snapshot.messages, entries)
        and coverage_complete(child_coverage(snapshot, children, snapshot.messages, entries)))
