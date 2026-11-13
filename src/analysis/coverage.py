"""Source-qualified request coverage, independent of prices or inferred spend."""
from dataclasses import dataclass
from collections import defaultdict

from src.domain import MessageRole


@dataclass(frozen=True, slots=True)
class AgentCoverage:
    session_id: str
    state: str


def unrepresented_usage(messages, entries):
    represented = {(entry.session_id, entry.message_id) for entry in entries}
    return any(message.role is MessageRole.ASSISTANT
        and (message.session_id, message.message_id) not in represented
        and (message.tokens is not None and message.tokens.total > 0
             or message.tokens is None and any(part.kind in {"text", "reasoning"} and part.data.get("text")
                 for part in message.parts))
        for message in messages)


def child_coverage(snapshot, session_ids, messages, entries):
    sessions = {session.session_id: session for session in snapshot.sessions}
    by_message, by_entry = defaultdict(list), defaultdict(list)
    for message in messages:
        by_message[message.session_id].append(message)
    for entry in entries:
        by_entry[entry.session_id].append(entry)
    result = []
    for identity in session_ids:
        own_messages, own_entries = by_message[identity], by_entry[identity]
        if not snapshot.complete:
            state = "acquisition-pending"
        elif unrepresented_usage(own_messages, own_entries):
            state = "usage-unavailable"
        elif own_entries:
            state = "usage-observed"
        elif not any(message.role is MessageRole.ASSISTANT for message in own_messages) and sessions[identity].active is False:
            state = "not-executed"
        elif sessions[identity].active is True:
            state = "pending"
        else:
            state = "usage-unavailable"
        result.append(AgentCoverage(identity, state))
    return tuple(result)


def coverage_complete(agents):
    return all(agent.state in {"usage-observed", "not-executed"} for agent in agents)


def snapshot_coverage_complete(snapshot, entries):
    children = tuple(session.session_id for session in snapshot.sessions
                     if session.session_id != snapshot.root.session_id)
    return (snapshot.complete and not unrepresented_usage(snapshot.messages, entries)
        and coverage_complete(child_coverage(snapshot, children, snapshot.messages, entries)))
