"""Evidence-qualified child invocation windows shared by accounting and activity.

Tool metadata identifies a candidate, never an unrelated session. Native output
wrappers are a fallback only on actual assistant task/subagent tool results.
All traversal stays inside the already acquired snapshot; no history is fetched.
"""
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
import re

from src.domain import EventKind, MessageRole, NormalizedMessage, NormalizedPart, SessionSnapshot

from .billing import ProviderScope, provider_matches
from .models import TraceEntry

OPEN_END = 2**63 - 1
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,255}\Z")
_WRAPPERS = {
    "task": re.compile(r'\s*<task\s+id="([^"]+)"\s*>[\s\S]*</task>\s*\Z'),
    "subagent": re.compile(r'\s*<subagent\s+sessionID="([^"]+)"\s*>[\s\S]*</subagent>\s*\Z'),
}


def child_session_id(part: NormalizedPart) -> str:
    """Prefer structured state, rejecting malformed authority instead of guessing."""
    name = str(part.data.get("tool") or part.data.get("name") or "").lower()
    if part.kind != "tool" or name not in _WRAPPERS:
        return ""
    state = part.data.get("state")
    state = state if isinstance(state, Mapping) else {}
    for metadata in (state.get("metadata"), part.data.get("metadata")):
        if isinstance(metadata, Mapping):
            for key in ("sessionID", "sessionId"):
                if key in metadata:
                    value = metadata[key]
                    return value if isinstance(value, str) and _ID.fullmatch(value) else ""
    output = state.get("output")
    match = _WRAPPERS[name].fullmatch(output) if isinstance(output, str) else None
    return match[1] if match and _ID.fullmatch(match[1]) else ""


def part_time(part: NormalizedPart) -> tuple[int, int]:
    start, end = part.created_at_ms, part.updated_at_ms
    state = part.data.get("state")
    if isinstance(state, Mapping):
        timing = state.get("time")
        if isinstance(timing, Mapping):
            try:
                start, end = int(timing.get("start") or start), int(timing.get("end") or end)
            except (TypeError, ValueError, OverflowError):
                return 0, 0
        if str(state.get("status", "")).lower() in {"pending", "streaming", "running"}:
            end = 0
    return int(start or 0), int(end or 0)


@dataclass(frozen=True)
class ChildScope:
    session_id: str
    start_ms: int
    end_ms: int
    background: bool = False
    continuing_ids: tuple[str, ...] = ()
    invocation_end_ms: int = OPEN_END
    owner_id: str = ""


def _candidate(part, message, sessions):
    child = sessions.get(child_session_id(part))
    if (child is None or child.parent_session_id != message.session_id or child.session_id == message.session_id
            or part.session_id != message.session_id or part.message_id != message.message_id):
        return None
    start, end = part_time(part)
    if (start <= 0 or start < message.created_at_ms or (end and end <= start)
            or (end and child.created_at_ms > end)):
        return None
    state = part.data.get("state")
    state = state if isinstance(state, Mapping) else {}
    inputs = state.get("input")
    background = any(isinstance(value, Mapping) and value.get("background") is True
                     for value in (state.get("metadata"), part.data.get("metadata"), inputs))
    return ChildScope(child.session_id, start, OPEN_END if background or not end else end, background)


class ChildLinkIndex:
    """One snapshot's physical calls, validated ancestry and bounded descendants."""

    def __init__(self, snapshot: SessionSnapshot):
        self.messages_by_session = defaultdict(list)
        self.links_by_message = defaultdict(list)
        sessions = {session.session_id: session for session in snapshot.sessions}
        turns = defaultdict(list)
        for event in snapshot.events:
            if event.kind in {EventKind.USER_PROMPT, EventKind.SUBTASK, EventKind.COMPACTION}:
                turns[event.session_id].append(event)
        calls = {}
        for message in snapshot.messages:
            if message.role is MessageRole.USER and message.termination is not None:
                self.messages_by_session[message.session_id].append(message)
            if message.role is not MessageRole.ASSISTANT:
                continue
            self.messages_by_session[message.session_id].append(message)
            for part in message.parts:
                start, _ = part_time(part)
                if (part.kind != "tool" or part.session_id != message.session_id or part.message_id != message.message_id
                        or (start > 0 and start < message.created_at_ms)):
                    continue
                call = part.data.get("callID")
                has_call = isinstance(call, str) and bool(call)
                key = (part.session_id, "call" if has_call else "part", call if has_call else part.part_id)
                rank = (part.updated_at_ms, -message.created_at_ms)
                if key not in calls or rank > calls[key][0]:
                    calls[key] = (rank, message, part)
        qualified = [(message.message_id, scope) for _, message, part in calls.values()
                     if (scope := _candidate(part, message, sessions)) is not None
                     and scope.session_id != snapshot.root.session_id]
        starts = defaultdict(set)
        for _, scope in qualified:
            starts[scope.session_id].add(scope.start_ms)
        for mid, scope in qualified:
            # A later invocation of the same child is a new causal window, even
            # when an earlier background launch has no terminal timestamp.
            end = min((at for at in starts[scope.session_id] if at > scope.start_ms), default=OPEN_END)
            owned_turns = sorted((item for item in turns[scope.session_id]
                if scope.start_ms <= item.created_at_ms < min(end, scope.end_ms)),
                key=lambda item: (item.created_at_ms, item.event_id))
            if not owned_turns and scope.start_ms <= sessions[scope.session_id].created_at_ms < scope.end_ms:
                # A freshly created child may enqueue its first user turn only
                # after the asynchronous launch acknowledgement has returned.
                owned_turns = sorted((item for item in turns[scope.session_id]
                    if scope.start_ms <= item.created_at_ms < end),
                    key=lambda item: (item.created_at_ms, item.event_id))[:1]
            if owned_turns:
                # Independent child prompts close the live ownership window too.
                end = min(end, min((item.created_at_ms for item in turns[scope.session_id]
                    if item.created_at_ms >= scope.end_ms and item.created_at_ms > owned_turns[0].created_at_ms),
                    default=OPEN_END))
            scope = replace(scope, end_ms=min(end, scope.end_ms), invocation_end_ms=end,
                owner_id=owned_turns[0].event_id if owned_turns else "")
            # A tool's return/abort ends its launch window, not an assistant
            # already executing inside it. Bind that physical attempt before
            # extending, so an unrelated later child request stays unallocated.
            messages = self.messages_by_session.get(scope.session_id, ())
            crossing = {message.parent_message_id for message in messages
                if scope.start_ms <= message.created_at_ms < scope.end_ms
                and message.parent_message_id
                and (message.completed_at_ms is None or message.completed_at_ms > scope.end_ms
                     or message.finish_reason == "tool-calls")}
            if owned_turns:
                owner = owned_turns[0].event_id
                if not any(message.parent_message_id == owner and message.created_at_ms < scope.end_ms
                           for message in messages):
                    crossing.add(owner)  # Launch acknowledged before the first assistant.
            continuing = tuple(message.message_id for message in messages
                if (message.parent_message_id in crossing or
                    message.role is MessageRole.USER and message.termination is not None
                    and owned_turns and message.message_id == owned_turns[0].event_id)
                and scope.start_ms <= message.created_at_ms < end)
            self.links_by_message[mid].append(replace(scope, continuing_ids=continuing))

    def messages(self, scopes: Sequence[ChildScope]) -> list[NormalizedMessage]:
        result = {}
        for scope in scopes:
            for message in self.messages_by_session.get(scope.session_id, ()):
                continuing = message.message_id in scope.continuing_ids
                upper = scope.invocation_end_ms if continuing else scope.end_ms
                if (scope.start_ms <= message.created_at_ms < upper
                        and (continuing or message.completed_at_ms is None or message.completed_at_ms <= upper)):
                    key = (message.session_id, message.message_id)
                    parts = {part.part_id: part for part in result[key].parts} if key in result else {}
                    for part in message.parts:
                        start, end = part_time(part)
                        if scope.start_ms <= start < upper and (continuing or not end or end <= upper):
                            parts[part.part_id] = part
                    result[key] = replace(message, parts=tuple(parts.values()))
        return list(result.values())

    def scopes(self, messages: Sequence[NormalizedMessage]) -> tuple[ChildScope, ...]:
        pending = [(message, 0, OPEN_END) for message in messages]
        found = set()
        while pending:
            message, lower, upper = pending.pop()
            for link in self.links_by_message.get(message.message_id, ()):
                # A background descendant can outlive its foreground parent,
                # but its launch must still originate inside that parent's window.
                scope = replace(link, end_ms=link.end_ms if link.background else min(link.end_ms, upper))
                if scope.start_ms < lower or scope.start_ms >= upper or scope.end_ms <= scope.start_ms or scope in found:
                    continue
                found.add(scope)
                pending.extend((child, scope.start_ms,
                    scope.invocation_end_ms if child.message_id in scope.continuing_ids else scope.end_ms)
                    for child in self.messages((scope,)))
        return tuple(sorted(found, key=lambda scope: (scope.start_ms, scope.session_id, scope.end_ms)))


def scoped_entries(snapshot: SessionSnapshot, entries: Sequence[TraceEntry], scopes: Sequence[ChildScope],
                   provider: ProviderScope) -> list[TraceEntry]:
    """Union physical request identities, not token/cost fingerprints or residuals."""
    by_session = defaultdict(list)
    for scope in scopes:
        by_session[scope.session_id].append(scope)
    result = {}
    for entry in entries:
        if not provider_matches(entry.model.provider, provider):
            continue
        invocation = snapshot.invocations[entry.sort_order]
        if any(invocation.created_at_ms >= scope.start_ms
                and (entry.message_id in scope.continuing_ids and invocation.created_at_ms < scope.invocation_end_ms
                     or scope.start_ms <= entry.completed_at_ms <= scope.end_ms)
               for scope in by_session.get(entry.session_id, ())):
            identity = (entry.source_instance, entry.session_id, invocation.invocation_id)
            result[identity] = entry
    return list(result.values())
