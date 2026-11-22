"""Evidence-qualified child invocation windows and prompt cost attribution.

Tool metadata identifies a candidate, never an unrelated session. Native output
wrappers are a fallback only on actual assistant task/subagent tool results.
All traversal stays inside the already acquired snapshot; no history is fetched.
"""
from bisect import bisect_left, bisect_right
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
import re

from src.domain import EventKind, MessageRole, NormalizedMessage, NormalizedPart, SessionSnapshot, TerminalOutcome

from .billing import ProviderScope, provider_matches
from .child_inference import OPEN_END, PROMPT_KINDS, inferred_children, source_identity, source_member
from .models import TraceEntry
from .prompt_index import prompt_owners
from .valuation import physical_usage_key

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
    declared = set()
    for metadata in (state.get("metadata"), part.data.get("metadata")):
        if isinstance(metadata, Mapping):
            for key in ("sessionID", "sessionId"):
                if key in metadata:
                    value = metadata[key]
                    if not isinstance(value, str) or not _ID.fullmatch(value):
                        return ""
                    declared.add(value)
    if declared:
        return next(iter(declared)) if len(declared) == 1 else ""
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
    timing_only: bool = False
    inferred_path: bool = False
    excluded_ids: tuple[str, ...] = ()
    bound_continuations: bool = False
    stale_at: int = 0


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
    terminal = message.termination
    failed_at = (terminal.completed_at_ms if terminal and terminal.outcome is not TerminalOutcome.SUCCESS
                 else message.completed_at_ms if message.error_name else None)
    stale_at = failed_at if not background and not end and failed_at is not None and failed_at > start else 0
    return ChildScope(child.session_id, start, OPEN_END if background or not end else end,
                      background, stale_at=stale_at)


class ChildLinkIndex:
    """One snapshot's physical calls, validated ancestry and bounded descendants."""

    def __init__(self, snapshot: SessionSnapshot):
        self.messages_by_session = defaultdict(list)
        self.links_by_message = defaultdict(list)
        self.source = source_identity(snapshot.root.provenance)
        sessions = _tree_sessions(snapshot, self.source)
        self.owners = prompt_owners(snapshot, event_filter=lambda event: (
            event.session_id in sessions and source_member(event, self.source)))
        turn_observations = defaultdict(dict)
        for event in snapshot.events:
            if (event.session_id in sessions and source_member(event, self.source)
                    and event.kind in PROMPT_KINDS | {EventKind.COMPACTION}):
                turn_observations[event.session_id].setdefault(event.event_id, event)
        turns = {sid: tuple(values.values()) for sid, values in turn_observations.items()}
        self.turns = turns
        self.messages_by_prompt = defaultdict(list)
        calls = defaultdict(list)
        for message in snapshot.messages:
            if message.session_id not in sessions or not source_member(message, self.source):
                continue
            event_id = message.message_id if message.role is MessageRole.USER else message.parent_message_id
            if owner := self.owners.get((message.session_id, event_id)):
                self.messages_by_prompt[(message.session_id, owner)].append(message)
            if message.role is MessageRole.USER and message.termination is not None:
                self.messages_by_session[message.session_id].append(message)
            if message.role is not MessageRole.ASSISTANT:
                continue
            self.messages_by_session[message.session_id].append(message)
            for part in message.parts:
                if (part.kind != "tool" or not source_member(part, self.source)
                        or part.session_id != message.session_id or part.message_id != message.message_id):
                    continue
                call = part.data.get("callID")
                has_call = isinstance(call, str) and bool(call)
                key = (part.session_id, "call" if has_call else "part", call if has_call else part.part_id)
                rank = (part.updated_at_ms, -message.created_at_ms)
                calls[key].append((rank, message, part))
        qualified, fences, verified_parts = _resolved_launches(calls.values(), sessions)
        starts = defaultdict(set)
        requests = defaultdict(list)
        for invocation in snapshot.invocations:
            if invocation.session_id in sessions and source_member(invocation, self.source):
                requests[invocation.session_id].append(invocation)
        for _, scope in qualified:
            starts[scope.session_id].add(scope.start_ms)
        starts = {session: sorted(times) for session, times in starts.items()}
        for items in requests.values():
            items.sort(key=lambda item: item.created_at_ms)
        request_starts = {session: [item.created_at_ms for item in items] for session, items in requests.items()}
        candidates, bindings, claims = [], defaultdict(set), defaultdict(set)
        for parent, scope in qualified:
            # A later invocation of the same child is a new causal window, even
            # when an earlier background launch has no terminal timestamp.
            times = starts[scope.session_id]
            index = bisect_right(times, scope.start_ms)
            end = times[index] if index < len(times) else OPEN_END
            child_turns = turns.get(scope.session_id, ())
            if scope.stale_at:
                if any(turn.kind in PROMPT_KINDS and scope.start_ms <= turn.created_at_ms < min(end, scope.stale_at)
                       for turn in child_turns):
                    end = min(end, min((turn.created_at_ms for turn in child_turns if turn.kind in PROMPT_KINDS
                                        and turn.created_at_ms >= scope.stale_at), default=OPEN_END))
                else:
                    end = min(end, scope.stale_at)
            owned_turns = sorted((item for item in child_turns
                if scope.start_ms <= item.created_at_ms < min(end, scope.end_ms)),
                key=lambda item: (item.created_at_ms, item.event_id))
            if (not owned_turns and not scope.stale_at
                    and scope.start_ms <= sessions[scope.session_id].created_at_ms < scope.end_ms):
                # A freshly created child may enqueue its first user turn only
                # after the asynchronous launch acknowledgement has returned.
                owned_turns = sorted((item for item in child_turns
                    if scope.start_ms <= item.created_at_ms < end),
                    key=lambda item: (item.created_at_ms, item.event_id))[:1]
            prompt_turns = [item for item in owned_turns if item.kind in PROMPT_KINDS]
            if scope.background and prompt_turns:
                # A native launch owns its first turn, not the remainder of a
                # reused conversation. Already bound replies may finish later.
                later_turn = next((turn for turn in prompt_turns if turn.created_at_ms > prompt_turns[0].created_at_ms), None)
                if later_turn:
                    end = min(end, later_turn.created_at_ms)
                owned_turns = [item for item in owned_turns if item.created_at_ms < end]
            if owned_turns:
                # Independent child prompts close the live ownership window too.
                end = min(end, min((item.created_at_ms for item in child_turns
                    if item.created_at_ms >= scope.end_ms and item.created_at_ms > owned_turns[0].created_at_ms),
                    default=OPEN_END))
            first_turn = next((item for item in owned_turns if item.kind in PROMPT_KINDS), None)
            scope = replace(scope, end_ms=min(end, scope.end_ms), invocation_end_ms=end,
                owner_id=first_turn.event_id if first_turn else "",
                bound_continuations=bool(scope.background or scope.stale_at) and first_turn is not None)
            # A tool's return/abort ends its launch window, not an assistant
            # already executing inside it. Bind that physical attempt before
            # extending, so an unrelated later child request stays unallocated.
            messages = self.messages_by_session.get(scope.session_id, ())
            crossing = {message.parent_message_id for message in messages
                if scope.start_ms <= message.created_at_ms < scope.end_ms
                and message.parent_message_id
                and (message.completed_at_ms is None or message.completed_at_ms > scope.end_ms
                     or message.finish_reason == "tool-calls")}
            if first_turn:
                owner = first_turn.event_id
                if not any(message.parent_message_id == owner and message.created_at_ms < scope.end_ms
                           for message in messages):
                    crossing.add(owner)  # Launch acknowledged before the first assistant.
            continuing = tuple(message.message_id for message in messages
                if (message.parent_message_id in crossing or
                    message.role is MessageRole.USER and message.termination is not None
                    and first_turn and message.message_id == first_turn.event_id)
                and scope.start_ms <= message.created_at_ms < end)
            scope = replace(scope, continuing_ids=continuing)
            parent_key = (parent.session_id, self.owners.get((parent.session_id, parent.parent_message_id),
                                                            parent.parent_message_id or parent.message_id))
            # Explicit windows reserve the entire logical child turn from
            # inference, even when only some of its physical attempts qualify.
            bound = {(scope.session_id, turn.event_id) for turn in owned_turns if turn.kind in PROMPT_KINDS}
            for key in bound:
                bindings[key].add(parent_key)
            child_keys = set(bound)
            for message in messages:
                owner = self._message_owner(message)
                if owner and _contains_message(scope, message, owner):
                    child_keys.add((scope.session_id, owner))
            # Reserve qualified physical invocations even when a retry started
            # inside the explicit window for a turn whose start was outside it.
            times = request_starts.get(scope.session_id, ())
            for invocation in requests[scope.session_id][bisect_left(times, scope.start_ms):bisect_left(times, end)]:
                if _within_window(scope, invocation.message_id, invocation.created_at_ms,
                                  invocation.completed_at_ms or invocation.created_at_ms):
                    owner = self.owners.get((scope.session_id, invocation.initiating_event_id))
                    if owner:
                        child_keys.add((scope.session_id, owner))
            for key in child_keys:
                claims[key].add(parent_key)
            candidates.append((parent, scope, bound, child_keys))
        owners = {key: next(iter(possible)) for key, claimants in claims.items()
                  if len(possible := bindings.get(key, claimants)) == 1}
        for parent, scope, bound, keys in candidates:
            parent_key = (parent.session_id, self.owners.get((parent.session_id, parent.parent_message_id),
                                                            parent.parent_message_id or parent.message_id))
            excluded = {key for key in keys if owners.get(key) != parent_key}
            if bound and keys <= excluded:
                continue
            self.links_by_message[(parent.session_id, parent.message_id)].append(
                replace(scope, excluded_ids=tuple(sorted(key[1] for key in excluded))))
        fenced = set()
        for child, launch_times in fences.items():
            # A rejected launch cannot establish a new window. Fence the first
            # turn at/after each launch and any turn already spanning it.
            child_turns = sorted(turns.get(child, ()), key=lambda item: item.created_at_ms)
            for start in launch_times:
                following = next((turn for turn in child_turns if turn.created_at_ms >= start), None)
                preceding = next((turn for turn in reversed(child_turns) if turn.created_at_ms < start), None)
                if following:
                    fenced.add((child, following.event_id))
                if preceding and _spans_launch(self.messages_by_prompt[(child, preceding.event_id)], start):
                    fenced.add((child, preceding.event_id))
        self.inferred = inferred_children(
            snapshot, sessions, self.owners, claims, fenced, verified_parts, part_time)

    def _message_owner(self, message):
        event_id = message.message_id if message.role is MessageRole.USER else message.parent_message_id
        return self.owners.get((message.session_id, event_id))

    def messages(self, scopes: Sequence[ChildScope]) -> list[NormalizedMessage]:
        result = {}
        for scope in scopes:
            candidates = (self.messages_by_prompt.get((scope.session_id, scope.owner_id), ())
                          if scope.timing_only else self.messages_by_session.get(scope.session_id, ()))
            for message in candidates:
                owner = self._message_owner(message)
                if not _contains_message(scope, message, owner):
                    continue
                if scope.timing_only:
                    result[(message.session_id, message.message_id)] = message
                    continue
                continuing = message.message_id in scope.continuing_ids
                upper = _message_upper(scope, owner, continuing)
                key = (message.session_id, message.message_id)
                parts = {part.part_id: part for part in result[key].parts} if key in result else {}
                for part in message.parts:
                    start, end = part_time(part)
                    if scope.start_ms <= start < upper and (continuing or not end or end <= upper):
                        parts[part.part_id] = part
                result[key] = replace(message, parts=tuple(parts.values()))
        return list(result.values())

    def scopes(self, messages: Sequence[NormalizedMessage], *,
               prompt: tuple[str, str] | None = None) -> tuple[ChildScope, ...]:
        """Only explicit lifecycle scopes unless a logical cost prompt is supplied."""
        pending = [(message, 0, OPEN_END, False) for message in messages]
        found = set()
        logical = [(prompt, 0, OPEN_END)] if prompt else []
        while pending or logical:
            if logical:
                key, lower, upper = logical.pop()
                for event in self.inferred.get(key, ()):
                    if lower <= event.created_at_ms < upper:
                        scope = ChildScope(event.session_id, event.created_at_ms, OPEN_END,
                                           owner_id=event.event_id, timing_only=True, inferred_path=True)
                        if scope not in found:
                            found.add(scope)
                            pending.extend((child, scope.start_ms, OPEN_END, True) for child in self.messages((scope,)))
                            logical.append(((scope.session_id, scope.owner_id), scope.start_ms, OPEN_END))
                continue
            message, lower, upper, inferred_path = pending.pop()
            for link in self.links_by_message.get((message.session_id, message.message_id), ()):
                # A background descendant can outlive its foreground parent,
                # but its launch must still originate inside that parent's window.
                scope = replace(link, end_ms=link.end_ms if link.background else min(link.end_ms, upper),
                                inferred_path=inferred_path)
                if scope.start_ms < lower or scope.start_ms >= upper or scope.end_ms <= scope.start_ms or scope in found:
                    continue
                found.add(scope)
                pending.extend((child, scope.start_ms,
                    _message_upper(scope, self._message_owner(child), child.message_id in scope.continuing_ids),
                    inferred_path)
                    for child in self.messages((scope,)))
                if prompt:
                    logical.extend(((scope.session_id, event.event_id), scope.start_ms, scope.invocation_end_ms)
                        for event in self.turns.get(scope.session_id, ())
                        if event.kind in PROMPT_KINDS and event.event_id not in scope.excluded_ids
                        and (event.event_id == scope.owner_id or scope.start_ms <= event.created_at_ms < scope.end_ms))
        return tuple(sorted(found, key=lambda scope: (
            scope.start_ms, scope.session_id, scope.end_ms, scope.owner_id, not scope.inferred_path)))


def scoped_entries(snapshot: SessionSnapshot, index, scopes: Sequence[ChildScope],
                   provider: ProviderScope) -> list[TraceEntry]:
    """Union physical request identities, not token/cost fingerprints or residuals."""
    source = source_identity(snapshot.root.provenance)
    result = {}
    for scope in scopes:
        candidates = (index.child_prompt_entries.get((scope.session_id, scope.owner_id), ()) if scope.timing_only
                      else index.child_session_entries.get(scope.session_id, ()))
        for entry in candidates:
            if not provider_matches(entry.model.provider, provider):
                continue
            invocation = snapshot.invocations[entry.sort_order]
            if not source_member(invocation, source) or entry.completed_at_ms < invocation.created_at_ms:
                continue
            if _contains_request(scope, entry, invocation):
                result[physical_usage_key(entry) or entry.sort_order] = entry
    return sorted(result.values(), key=lambda item: (item.completed_at_ms, item.sort_order))


def _contains_request(scope, entry, invocation):
    if entry.logical_prompt_id in scope.excluded_ids:
        return False
    if scope.timing_only:
        return (entry.logical_prompt_id == scope.owner_id and invocation.created_at_ms >= scope.start_ms
                and not invocation.summary)
    if scope.bound_continuations and entry.logical_prompt_id == scope.owner_id:
        return invocation.created_at_ms >= scope.start_ms
    return _within_window(scope, entry.message_id, invocation.created_at_ms, entry.completed_at_ms)


def _message_upper(scope, owner, continuing):
    if scope.bound_continuations and owner == scope.owner_id:
        return OPEN_END
    return scope.invocation_end_ms if continuing else scope.end_ms


def _contains_message(scope, message, owner):
    if owner in scope.excluded_ids or message.created_at_ms < scope.start_ms:
        return False
    if scope.timing_only:
        return owner == scope.owner_id
    continuing = message.message_id in scope.continuing_ids
    upper = _message_upper(scope, owner, continuing)
    return (message.created_at_ms < upper and
            (continuing or message.completed_at_ms is None or message.completed_at_ms <= upper))


def _spans_launch(messages, start):
    return any(message.role is MessageRole.ASSISTANT and message.created_at_ms <= start
               and (message.completed_at_ms is None or message.completed_at_ms >= start) for message in messages)


def _within_window(scope, message_id, start, end):
    return (scope.start_ms <= start < scope.invocation_end_ms
            and (message_id in scope.continuing_ids or start <= end <= scope.end_ms))


def _malformed_native_link(part):
    name = str(part.data.get("tool") or part.data.get("name") or "").lower()
    if name not in _WRAPPERS:
        return False
    state = part.data.get("state")
    state = state if isinstance(state, Mapping) else {}
    return not child_session_id(part) and any(
        isinstance(metadata, Mapping) and ("sessionID" in metadata or "sessionId" in metadata)
        for metadata in (state.get("metadata"), part.data.get("metadata")))


def _resolved_launches(calls, sessions):
    """Use the latest physical observation; contradictory links fence timing."""
    qualified, fences, verified_parts = [], defaultdict(set), set()
    children = defaultdict(set)
    for session in sessions.values():
        children[session.parent_session_id].add(session.session_id)
    for observations in calls:
        possible = [item for item in observations if not (0 < part_time(item[2])[0] < item[1].created_at_ms)]
        scope = None
        if possible:
            rank, message, part = max(possible, key=lambda item: item[0])
            current = [(item, observed) for seen, item, observed in possible if seen == rank]
            evidence = {(item.message_id, _candidate(observed, item, sessions)) for item, observed in current}
            if len(evidence) == 1:
                scope = _candidate(part, message, sessions)
        if scope is not None:
            qualified.append((message, scope))
            verified_parts.update((observed.session_id, observed.part_id) for _, _, observed in observations)
        for _, observed_message, observed in observations:
            child = child_session_id(observed)
            start = part_time(observed)[0] or observed_message.created_at_ms
            siblings = children[observed_message.session_id]
            if child in siblings and (scope is None or scope.session_id != child):
                fences[child].add(start)
            elif scope is None and _malformed_native_link(observed):
                for sibling in siblings:
                    fences[sibling].add(start)
    return qualified, fences, verified_parts


def _tree_sessions(snapshot, source):
    qualified, conflicts, by_parent = {}, set(), defaultdict(list)
    for session in snapshot.sessions:
        if session.session_id != snapshot.root.session_id and source_member(session, source):
            prior = qualified.setdefault(session.session_id, session)
            if prior.parent_session_id != session.parent_session_id or prior.created_at_ms != session.created_at_ms:
                conflicts.add(session.session_id)
    for session in qualified.values():
        if session.session_id not in conflicts:
            by_parent[session.parent_session_id].append(session)
    found, pending = {}, [snapshot.root]
    while pending:
        session = pending.pop()
        if session.session_id not in found:
            found[session.session_id] = session
            pending.extend(by_parent[session.session_id])
    return found
