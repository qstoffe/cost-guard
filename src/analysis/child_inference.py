"""Conservative, snapshot-only timing inference between logical prompts."""
from bisect import bisect_left, bisect_right
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass

from src.domain import EventKind, MessageRole

OPEN_END = 2**63 - 1
PROMPT_KINDS = {EventKind.USER_PROMPT, EventKind.SUBTASK}
_SHELL_ACTIVITIES = {"shell", "bash", "functions.shell", "functions.bash"}


def source_identity(provenance):
    return provenance.source_type, provenance.source_generation, provenance.source_instance


def source_member(item, source):
    return (source_identity(item.provenance) == source
        and item.provenance.source_session_id in (None, item.session_id))


def _terminal(message):
    if message.termination:
        return message.termination.completed_at_ms
    if message.error_name or message.finish_reason not in (None, "tool-calls"):
        return message.completed_at_ms or message.created_at_ms
    return 0


def _declared_background(part, state):
    return any(isinstance(value, Mapping) and value.get("background") is True
               for value in (state.get("input"), state.get("metadata"), part.data.get("metadata")))


def _background_index(snapshot):
    exact, approximate = defaultdict(set), defaultdict(set)
    for activity in snapshot.background:
        owner = (activity.session_id, activity.owner_message_id)
        if activity.tool_part_id:
            exact[(*owner, "part", activity.tool_part_id)].add(activity)
        if activity.tool_call_id:
            exact[(*owner, "call", activity.tool_call_id)].add(activity)
        if not activity.tool_part_id and not activity.tool_call_id:
            approximate[(*owner, activity.started_at_ms)].add(activity)
    return exact, approximate


def _background_end(message, part, start, activities, weak_match):
    exact, approximate = activities
    owner = (message.session_id, message.message_id)
    call = part.data.get("callID")
    matches = exact[(*owner, "part", part.part_id)]
    if isinstance(call, str) and call:
        matches = matches | exact[(*owner, "call", call)]
    is_exact = bool(matches)
    if not is_exact and weak_match:
        matches = approximate[(*owner, start)]
    if len(matches) != 1:
        return OPEN_END
    activity = next(iter(matches))
    if is_exact and activity.kind in _SHELL_ACTIVITIES:
        return 0  # Source-qualified shell work cannot be a subagent launch.
    end = activity.ended_at_ms
    return end if not activity.running and end is not None and end >= start > 0 else OPEN_END


def _attempt_ends(message, source, verified_parts, activities, part_time):
    """Observed work and unresolved overlap are different boundaries."""
    terminal = _terminal(message)
    observed = max(message.created_at_ms, terminal, message.completed_at_ms or 0)
    foreground = 0 if terminal or message.completed_at_ms else message.created_at_ms
    asynchronous = 0
    tools = []
    for part in message.parts:
        state = part.data.get("state")
        if (part.kind != "tool" or not isinstance(state, Mapping) or part.session_id != message.session_id
                or part.message_id != message.message_id or not source_member(part, source)):
            continue
        if (part.session_id, part.part_id) in verified_parts:
            continue  # Its work is addressed by the direct invocation evidence.
        start, end = part_time(part)
        tools.append((part, state, start, end))
    start_counts = defaultdict(int)
    for _, _, start, _ in tools:
        start_counts[start] += 1
    for part, state, start, end in tools:
        declared_background = _declared_background(part, state)
        background_end = _background_end(message, part, start, activities, start_counts[start] == 1)
        if background_end == 0:
            continue
        if end >= start > 0:
            observed = max(observed, end)
        pending = str(state.get("status", "")).lower() in {"pending", "streaming", "running"}
        if declared_background:
            # Tool completion may be just the launch acknowledgement. Where an
            # async launch cannot be bound or verified finished, do not guess.
            asynchronous = max(asynchronous, background_end)
        elif pending and not terminal:
            foreground = max(foreground, start or message.created_at_ms)
    return observed, foreground, asynchronous


@dataclass(frozen=True)
class Timing:
    events: tuple
    starts: tuple[int, ...]
    prior_ends: tuple[int, ...]
    ownerless: tuple[int, ...]
    settled_ownerless: tuple[int, ...]

    def previous_overlap(self, position, at):
        index = bisect_right(self.ownerless, at)
        return self.prior_ends[position] >= at or bool(index and self.settled_ownerless[index - 1] >= at)


def _event_clocks(snapshot, sessions, source):
    events, events_by_key, compactions, uncertain = defaultdict(list), {}, defaultdict(list), set()
    for event in snapshot.events:
        session = sessions.get(event.session_id)
        if session is None or event.kind not in PROMPT_KINDS | {EventKind.COMPACTION}:
            continue
        if not source_member(event, source) or not 0 < session.created_at_ms <= event.created_at_ms:
            uncertain.add(event.session_id)
            continue
        key = (event.session_id, event.event_id)
        if key in events_by_key:
            previous = events_by_key[key]
            if (event.kind, event.created_at_ms) != (previous.kind, previous.created_at_ms):
                uncertain.add(event.session_id)
            continue  # Repeated observations of the same event are not separate turns.
        events_by_key[key] = event
        if event.kind is EventKind.COMPACTION:
            compactions[event.session_id].append(event.created_at_ms)
        else:
            events[event.session_id].append(event)
    return events, events_by_key, compactions, uncertain


def _attempt_clocks(snapshot, sessions, source, owners, events_by_key, verified_parts, part_time, uncertain):
    activities = _background_index(snapshot)
    attempts, ownerless, boundaries = defaultdict(list), defaultdict(list), defaultdict(list)
    resumed = defaultdict(list)
    for event in snapshot.events:
        key = (event.session_id, event.event_id)
        owner = owners.get(key)
        if owner and owner != event.event_id and source_member(event, source):
            resumed[(event.session_id, owner)].append(event.created_at_ms)
    for message in snapshot.messages:
        sid = message.session_id
        if sid not in sessions or not source_member(message, source):
            continue
        event_id = message.message_id if message.role is MessageRole.USER else message.parent_message_id
        owner = owners.get((sid, event_id))
        event = events_by_key.get((sid, owner))
        terminal = _terminal(message)
        if ((event is not None and message.created_at_ms < event.created_at_ms)
                or (message.completed_at_ms is not None and message.completed_at_ms < message.created_at_ms)
                or (terminal and terminal < message.created_at_ms)):
            uncertain.add(sid)
        if message.role is not MessageRole.ASSISTANT and not message.termination:
            continue
        observed, foreground, asynchronous = _attempt_ends(message, source, verified_parts, activities, part_time)
        if event is None:
            ownerless[sid].append((message.created_at_ms, observed, foreground, asynchronous))
            continue
        attempts[(sid, owner)].append((message.created_at_ms, observed, foreground, asynchronous, terminal))
        if message.role is MessageRole.ASSISTANT:
            boundaries[sid].append((event.created_at_ms, message.created_at_ms))
    for invocation in snapshot.invocations:
        sid = invocation.session_id
        if sid not in sessions or not source_member(invocation, source):
            continue
        owner = owners.get((sid, invocation.initiating_event_id))
        if ((event := events_by_key.get((sid, owner))) is not None and invocation.created_at_ms < event.created_at_ms
                or invocation.completed_at_ms is not None and invocation.completed_at_ms < invocation.created_at_ms):
            uncertain.add(sid)
    return attempts, ownerless, boundaries, resumed


def _timelines(events, attempts, ownerless, boundaries):
    timelines, latest_ends = {}, {}
    for sid, prompts in events.items():
        ordered = sorted(prompts, key=lambda item: item.created_at_ms)
        starts = tuple(item.created_at_ms for item in ordered)
        # Later assistant starts settle abandoned *foreground* observations,
        # not async launches or observed long-running tools. Compute suffix
        # minima once for sessions with many sequential prompts.
        points = sorted(boundaries[sid])
        owners = [prompt_start for prompt_start, _ in points]
        suffix = [OPEN_END] * (len(points) + 1)
        for index in range(len(points) - 1, -1, -1):
            suffix[index] = min(suffix[index + 1], points[index][1])
        observed_starts = sorted(at for _, at in points)
        prior_ends, end = [], 0
        unresolved, unresolved_ends, unresolved_end = [], [], 0
        for start, observed, foreground, asynchronous in sorted(ownerless[sid]):
            index = bisect_right(observed_starts, start)
            settled = observed_starts[index] if index < len(observed_starts) else OPEN_END
            unresolved_end = max(unresolved_end, observed, asynchronous, settled if foreground else 0)
            unresolved.append(start)
            unresolved_ends.append(unresolved_end)
        for event in ordered:
            key = (sid, event.event_id)
            prior_ends.append(end)
            rows = attempts[key]
            observed = max((row[1] for row in rows), default=0)
            newest = max((row[0] for row in rows), default=0)
            current = [row for row in rows if row[0] == newest]
            terminal = min((row[4] for row in current), default=0)
            latest_ends[key] = (terminal, observed, any(row[2] for row in current))
            replacement = suffix[bisect_right(owners, event.created_at_ms)]
            end = max(end, observed, max((row[3] for row in rows), default=0),
                      replacement if any(row[2] for row in rows) and not terminal else 0)
        timelines[sid] = Timing(tuple(ordered), starts, tuple(prior_ends), tuple(unresolved), tuple(unresolved_ends))
    return timelines, latest_ends


def inferred_children(snapshot, sessions, owners, claimed, fenced, verified_parts, part_time):
    """Map parent prompt keys to independently qualified child prompt events."""
    result = defaultdict(list)
    source = source_identity(snapshot.root.provenance)
    if not snapshot.complete or not all(source):
        return result
    events, events_by_key, compactions, uncertain = _event_clocks(snapshot, sessions, source)
    attempts, ownerless, boundaries, resumed = _attempt_clocks(
        snapshot, sessions, source, owners, events_by_key, verified_parts, part_time, uncertain)
    timelines, latest_ends = _timelines(events, attempts, ownerless, boundaries)
    for times in (*compactions.values(), *resumed.values()):
        times.sort()

    for child_id, child_timing in timelines.items():
        child = sessions[child_id]
        parent = sessions.get(child.parent_session_id)
        if (parent is None or parent.session_id not in timelines or child_id in uncertain
                or parent.session_id in uncertain or child.created_at_ms < parent.created_at_ms):
            continue
        parent_timing = timelines[parent.session_id]
        compact = compactions[parent.session_id]
        child_starts, starts = child_timing.starts, parent_timing.starts
        for index, event in enumerate(child_timing.events):
            key, at = (child_id, event.event_id), event.created_at_ms
            if key in claimed or key in fenced or child_timing.previous_overlap(index, at):
                continue
            if ((index and child_starts[index - 1] == at)
                    or (index + 1 < len(child_starts) and child_starts[index + 1] == at)):
                continue
            next_index = bisect_left(starts, at)
            if not next_index or (next_index < len(starts) and starts[next_index] == at):
                continue
            pos = next_index - 1
            if (pos and starts[pos - 1] == starts[pos]) or parent_timing.previous_overlap(pos, at):
                continue
            parent_key = (parent.session_id, parent_timing.events[pos].event_id)
            compact_pos = bisect_right(compact, at) - 1
            if compact_pos >= 0 and compact[compact_pos] >= starts[pos]:
                continuations = resumed[parent_key]
                resume_pos = bisect_left(continuations, at) - 1
                if resume_pos < 0 or continuations[resume_pos] <= compact[compact_pos]:
                    continue
            if next_index == len(starts):
                terminal, observed, unfinished = latest_ends[parent_key]
                if (terminal and at >= terminal or not terminal and parent.active is not True
                        and not unfinished and at >= observed):
                    continue
            result[parent_key].append(event)
    return result
