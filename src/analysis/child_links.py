"""Evidence-qualified child invocation windows shared by accounting and activity.

Tool metadata identifies a candidate, never an unrelated session. Native output
wrappers are a fallback only on actual assistant task/subagent tool results.
All traversal stays inside the already acquired snapshot; no history is fetched.
"""
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
import re

from src.domain import MessageRole, NormalizedMessage, NormalizedPart, SessionSnapshot

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
        calls = {}
        for message in snapshot.messages:
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
            self.links_by_message[mid].append(replace(scope, end_ms=min(end, scope.end_ms)))

    def messages(self, scopes: Sequence[ChildScope]) -> list[NormalizedMessage]:
        result = {}
        for scope in scopes:
            for message in self.messages_by_session.get(scope.session_id, ()):
                if (scope.start_ms <= message.created_at_ms < scope.end_ms
                        and (message.completed_at_ms is None or message.completed_at_ms <= scope.end_ms)):
                    key = (message.session_id, message.message_id)
                    parts = {part.part_id: part for part in result[key].parts} if key in result else {}
                    for part in message.parts:
                        start, end = part_time(part)
                        if scope.start_ms <= start < scope.end_ms and (not end or end <= scope.end_ms):
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
                pending.extend((child, scope.start_ms, scope.end_ms) for child in self.messages((scope,)))
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
               and scope.start_ms <= entry.completed_at_ms <= scope.end_ms
               for scope in by_session.get(entry.session_id, ())):
            identity = (entry.source_instance, entry.session_id, invocation.invocation_id)
            result[identity] = entry
    return list(result.values())
