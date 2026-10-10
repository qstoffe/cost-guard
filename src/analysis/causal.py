"""Prompt boundaries and causal attribution over canonical session snapshots."""
from __future__ import annotations

import json
import math
import re
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace

from src.domain import (
    BackgroundActivity, CostDisposition, EventKind, MessageRole, NormalizedMessage, NormalizedPart, SessionSnapshot,
    TerminalOutcome,
)

from .billing import CostEstimator, ProviderScope, measure_prompt_billing, provider_matches
from .models import PromptRecord, PromptReference, TraceEntry

TRACKED_PROVIDER_DEFAULT = "github-copilot"
TOOL_CALLS_CONTINUATION_GRACE_MS = 60_000
_LOCAL_TOOL_NAMES = frozenset({
    "bash", "shell", "read", "grep", "glob", "edit", "write", "patch",
    "apply_patch", "ls", "lsp", "skill", "todoread", "todowrite",
})
_TASK_OUTPUT_ID = re.compile(r'<task\s+id="([^"]+)"')


def trace_entries(
    snapshot: SessionSnapshot, *, subscription_providers: frozenset[str] = frozenset()
) -> tuple[TraceEntry, ...]:
    result: list[TraceEntry] = []
    for order, invocation in enumerate(snapshot.invocations):
        reported = invocation.cost.amount if invocation.cost is not None else 0
        disposition = invocation.cost_disposition
        if reported > 0:
            disposition = CostDisposition.BILLED
        elif disposition is CostDisposition.UNKNOWN and invocation.model.provider in subscription_providers:
            disposition = CostDisposition.INCLUDED_SUBSCRIPTION
        result.append(TraceEntry(
            session_id=invocation.session_id,
            parent_event_id=invocation.initiating_event_id,
            message_id=invocation.message_id,
            step_part_id=invocation.step_part_id,
            completed_at_ms=invocation.completed_at_ms or invocation.created_at_ms,
            sort_order=order,
            model=invocation.model,
            variant=invocation.variant,
            tokens=invocation.tokens,
            reported_cost=reported,
            summary=invocation.summary,
            finish_reason=invocation.finish_reason,
            error_name=invocation.error_name,
            cost_disposition=disposition,
            source_instance=invocation.provenance.source_instance,
            account_ref=invocation.account_ref,
        ))
    return tuple(sorted(result, key=lambda item: (item.completed_at_ms, item.sort_order)))


def _visible_prompt_events(snapshot: SessionSnapshot) -> list:
    return sorted(
        (
            event for event in snapshot.events
            if event.session_id == snapshot.root.session_id
            and event.kind in {EventKind.USER_PROMPT, EventKind.SUBTASK}
        ),
        key=lambda event: (event.created_at_ms, event.event_id),
    )


def active_compaction_event(snapshot: SessionSnapshot):
    """Return the live final root event when it is an unfinished compaction."""
    events = sorted(
        (event for event in snapshot.events if event.session_id == snapshot.root.session_id
         and event.kind in {EventKind.USER_PROMPT, EventKind.SUBTASK, EventKind.COMPACTION}),
        key=lambda event: (event.created_at_ms, event.event_id),
    )
    if snapshot.root.active is not True or not events or events[-1].kind is not EventKind.COMPACTION:
        return None
    event = events[-1]
    message = next((item for item in snapshot.messages if item.message_id == event.event_id), None)
    part = next((item for item in message.parts if item.kind == "compaction"), None) if message else None
    if part is not None:
        status = str(part.data.get("status") or "").lower()
        if status in {"failed", "error", "cancelled", "aborted"}:
            return None
        if status == "completed" and (part.data.get("summary") or part.data.get("recent")):
            return None
    if any(
        item.role is MessageRole.ASSISTANT and item.parent_message_id == event.event_id
        and item.summary and item.finish_reason and not item.error_name
        for item in snapshot.messages
    ):
        return None
    return event


def prompt_references(snapshot: SessionSnapshot, *, since_ms: int = 0) -> tuple[PromptReference, ...]:
    entries = trace_entries(snapshot)
    parent_ids = {entry.parent_event_id for entry in entries if entry.parent_event_id}
    messages = {message.message_id: message for message in snapshot.messages}
    refs: list[PromptReference] = []
    order = {
        event.event_id: index + 1
        for index, event in enumerate(sorted(
            (item for item in snapshot.events if item.session_id == snapshot.root.session_id
             and item.kind in {EventKind.USER_PROMPT, EventKind.SUBTASK, EventKind.COMPACTION}),
            key=lambda item: (item.created_at_ms, item.event_id),
        ))
    }
    visible_events = _visible_prompt_events(snapshot)
    for event in visible_events:
        if event.created_at_ms < since_ms:
            continue
        message = messages.get(event.event_id)
        assistant_messages = [
            item for item in snapshot.messages
            if item.session_id == snapshot.root.session_id
            and item.role is MessageRole.ASSISTANT
            and item.parent_message_id == event.event_id
        ]
        latest_visible = event is visible_events[-1]
        window = prompt_parent_ids(snapshot, event.event_id, event.created_at_ms,
                                   subtask=event.kind is EventKind.SUBTASK)
        has_error_or_live = (
            any(item.termination or item.error_name or item.completed_at_ms is None for item in assistant_messages)
            or bool(snapshot.root.active is True and latest_visible)
        )
        if not window & parent_ids and not has_error_or_live:
            continue
        refs.append(PromptReference(
            session_id=snapshot.root.session_id,
            prompt_id=event.event_id,
            prompt_time_ms=event.created_at_ms,
            prompt_number=order[event.event_id],
            prompt_kind="subtask" if event.kind is EventKind.SUBTASK else "prompt",
            prompt_text=event.text or "",
            model_id=event.metadata.get("model_id", ""),
            provider_id=event.metadata.get("provider_id", ""),
            variant=event.metadata.get("variant", ""),
        ))
    return tuple(refs)


def prompt_parent_ids(snapshot: SessionSnapshot, prompt_id: str, prompt_time_ms: int, *, subtask: bool) -> set[str]:
    """Events whose assistant work continues one logical root prompt.

    Background-completion notices and other invisible synthetic user messages
    (for example subagent-completion notices injected while work continues)
    resume the prompt current at that time, so work after them stays on that
    prompt's row; subtasks also own synthetic task-summary continuations.
    Each event falls in exactly one prompt window.
    """
    kinds = {EventKind.BACKGROUND_COMPLETION, EventKind.OTHER} | (
        {EventKind.SYNTHETIC_CONTINUATION} if subtask else set())
    next_visible = min(
        (event.created_at_ms for event in _visible_prompt_events(snapshot) if event.created_at_ms > prompt_time_ms),
        default=2**63 - 1,
    )
    return {prompt_id} | {
        event.event_id for event in snapshot.events
        if event.session_id == snapshot.root.session_id and event.kind in kinds
        and prompt_time_ms < event.created_at_ms < next_visible
    }


def _synthetic_parent_ids(snapshot: SessionSnapshot, ref: PromptReference) -> set[str]:
    return prompt_parent_ids(snapshot, ref.prompt_id, ref.prompt_time_ms, subtask=ref.prompt_kind == "subtask")


def _outstanding_background(
    snapshot: SessionSnapshot, messages: Sequence[NormalizedMessage], *, superseded: bool,
) -> tuple[BackgroundActivity, ...]:
    """Running background work the current prompt is still waiting on.

    Completion resumes the conversation inside the newest prompt, so work an
    earlier prompt started hands its wait over to that prompt; a superseded
    prompt never waits on background work.
    """
    if superseded:
        return ()
    sessions = {snapshot.root.session_id} | _prompt_child_ids(messages)
    return tuple(item for item in snapshot.background if item.running and item.session_id in sessions)


def _is_aborted_message(message: NormalizedMessage) -> bool:
    return message.error_name in {"AbortedError", "AbortError", "MessageAbortedError"}


def _latest_assistant(messages: Sequence[NormalizedMessage]) -> NormalizedMessage | None:
    values = sorted(messages, key=lambda item: (
        item.created_at_ms,
        bool(item.completed_at_ms is not None and item.finish_reason not in {None, "tool-calls"} and not item.error_name),
        item.completed_at_ms or 0, item.message_id,
    ))
    return values[-1] if values else None


def _assistant_in_progress(
    messages: Sequence[NormalizedMessage], *, now_ms: int, continuation_superseded: bool,
    active_work: bool = False,
) -> bool:
    latest = _latest_assistant(messages)
    if active_work and not continuation_superseded:
        return True
    if latest is None or latest.termination or latest.error_name:
        return False
    if latest.completed_at_ms is None:
        return True
    if latest.finish_reason != "tool-calls" or continuation_superseded:
        return False
    return latest.completed_at_ms >= now_ms - TOOL_CALLS_CONTINUATION_GRACE_MS


def _part_is_running(part: NormalizedPart) -> bool:
    if part.kind != "tool":
        return False
    state = part.data.get("state")
    return isinstance(state, Mapping) and str(state.get("status", "")).lower() in {
        "pending", "streaming", "running",
    }


def _prompt_child_ids(messages: Sequence[NormalizedMessage]) -> set[str]:
    return {
        child_id
        for message in messages
        for part in message.parts
        if (child_id := _task_child_session_id(part))
    }


def _prompt_has_active_work(
    snapshot: SessionSnapshot,
    messages: Sequence[NormalizedMessage],
    *,
    continuation_superseded: bool,
) -> bool:
    if continuation_superseded:
        return False
    if snapshot.root.active is True:
        return True
    latest = _latest_assistant(messages)
    terminal_at = latest.termination.completed_at_ms if latest and latest.termination else 0
    if any(_part_is_running(part) and (not terminal_at or max(
        part.created_at_ms, part.updated_at_ms, _part_time(part)[0]) > terminal_at)
        for message in messages for part in message.parts):
        return True
    child_ids = _prompt_child_ids(messages)
    return any(session.session_id in child_ids and session.active is True for session in snapshot.sessions)


def _prompt_activity_end(
    snapshot: SessionSnapshot,
    messages: Sequence[NormalizedMessage],
    *,
    fallback: int,
) -> int:
    values = [fallback]
    child_ids = _prompt_child_ids(messages)
    for message in messages:
        values.append(message.completed_at_ms or message.created_at_ms)
        if message.termination:
            values.append(message.termination.completed_at_ms)
        values.extend(part.updated_at_ms or part.created_at_ms for part in message.parts)
    values.extend(
        session.updated_at_ms for session in snapshot.sessions if session.session_id in child_ids
    )
    # Background work the prompt started is part of its wall-clock lifetime.
    owners = {message.message_id for message in messages}
    values.extend(item.ended_at_ms for item in snapshot.background
                  if item.owner_message_id in owners and item.ended_at_ms)
    return max(values)


def _message_approx_context_tokens(message: NormalizedMessage | None) -> int:
    if message is None:
        return 0
    total = 0
    if message.role is MessageRole.USER:
        for part in message.parts:
            data = part.data
            if part.kind == "text" and not bool(data.get("ignored", False)):
                total += math.ceil(len(str(data.get("text", ""))) / 4)
            elif part.kind == "file":
                label = f"{data.get('filename', 'file')} {data.get('mime', '')}"
                total += max(4, math.ceil(len(label) / 4))
            elif part.kind == "compaction":
                total += math.ceil(len("What did we do so far?") / 4)
    return total


def _part_time(part: NormalizedPart) -> tuple[int, int]:
    start = int(part.created_at_ms or 0)
    end = int(part.updated_at_ms or 0)
    state = part.data.get("state")
    if isinstance(state, Mapping):
        state_time = state.get("time")
        if isinstance(state_time, Mapping):
            try:
                start = int(state_time.get("start") or start)
                end = int(state_time.get("end") or end)
            except (TypeError, ValueError):
                pass
        if str(state.get("status", "")).lower() in {"pending", "streaming", "running"}:
            end = 0
    return start, end


def _tool_name(part: NormalizedPart) -> str:
    return str(part.data.get("tool") or part.data.get("name") or "").lower()


def _task_child_session_id(part: NormalizedPart) -> str:
    if part.kind != "tool" or _tool_name(part) != "task":
        return ""
    state = part.data.get("state")
    if isinstance(state, Mapping):
        metadata = state.get("metadata")
        if isinstance(metadata, Mapping) and metadata.get("sessionId"):
            return str(metadata["sessionId"])
    metadata = part.data.get("metadata")
    if isinstance(metadata, Mapping) and metadata.get("sessionId"):
        return str(metadata["sessionId"])
    output = str(state.get("output", "")) if isinstance(state, Mapping) else ""
    match = _TASK_OUTPUT_ID.search(output)
    return match.group(1) if match else ""


def _task_invocations(
    messages: Sequence[NormalizedMessage], range_start: int, range_end: int, allow_open_ended: bool
) -> list[tuple[str, int, int]]:
    result: list[tuple[str, int, int]] = []
    for message in messages:
        for part in message.parts:
            child_id = _task_child_session_id(part)
            if not child_id:
                continue
            start, raw_end = _part_time(part)
            if start <= 0 or (range_end > 0 and start >= range_end):
                continue
            if raw_end > start:
                end = raw_end
                if end <= range_start:
                    continue
            elif allow_open_ended:
                end = range_end if range_end > start else 2**63 - 1
            else:
                continue
            state = part.data.get("state")
            metadata = state.get("metadata") if isinstance(state, Mapping) else None
            if isinstance(metadata, Mapping) and bool(metadata.get("background", False)):
                end = 2**63 - 1
            result.append((child_id, start, end))
    return result


def _local_intervals(messages: Sequence[NormalizedMessage], start_ms: int, end_ms: int) -> list[tuple[int, int]]:
    values: list[tuple[int, int]] = []
    for message in messages:
        for part in message.parts:
            if part.kind != "tool" or _tool_name(part) not in _LOCAL_TOOL_NAMES:
                continue
            start, end = _part_time(part)
            if start <= 0 or end <= start or end <= start_ms or (end_ms > 0 and start >= end_ms):
                continue
            values.append((start, end))
    return values


def _measure_interval_union(intervals: Iterable[tuple[int, int]], start_ms: int, end_ms: int) -> int:
    if end_ms <= start_ms:
        return 0
    clipped = sorted(
        (max(start_ms, start), min(end_ms, end))
        for start, end in intervals
        if min(end_ms, end) > max(start_ms, start)
    )
    if not clipped:
        return 0
    total = 0
    current_start, current_end = clipped[0]
    for start, end in clipped[1:]:
        if start <= current_end:
            current_end = max(current_end, end)
        else:
            total += current_end - current_start
            current_start, current_end = start, end
    return total + current_end - current_start


def _child_work(
    snapshot: SessionSnapshot,
    all_entries: Sequence[TraceEntry],
    session_id: str,
    range_start: int,
    range_end: int,
    visited: set[tuple[str, int, int]],
    allow_open_ended: bool,
    tracked_provider: ProviderScope,
) -> tuple[list[TraceEntry], list[tuple[int, int]]]:
    key = (session_id, range_start, range_end)
    if not session_id or key in visited:
        return [], []
    visited.add(key)
    entries = [
        entry for entry in all_entries
        if entry.session_id == session_id
        and provider_matches(entry.model.provider, tracked_provider)
        and entry.completed_at_ms >= range_start
        and (range_end in (0, 2**63 - 1) or entry.completed_at_ms <= range_end)
    ]
    messages = [
        message for message in snapshot.messages
        if message.session_id == session_id and message.role is MessageRole.ASSISTANT
    ]
    local = _local_intervals(messages, range_start, range_end)
    for child_id, start, end in _task_invocations(messages, range_start, range_end, allow_open_ended):
        nested_end = end
        if range_end not in (0, 2**63 - 1):
            nested_end = min(nested_end, range_end)
        child_entries, child_local = _child_work(
            snapshot, all_entries, child_id, start, nested_end, visited,
            allow_open_ended, tracked_provider,
        )
        entries.extend(child_entries)
        local.extend(child_local)
    return entries, local


def _is_completed_compaction_entry(snapshot: SessionSnapshot, entry: TraceEntry | None) -> bool:
    if entry is None or not entry.message_id:
        return False
    messages = {message.message_id: message for message in snapshot.messages}
    message = messages.get(entry.message_id)
    if (
        message is None or message.role is not MessageRole.ASSISTANT or not message.summary
        or not message.finish_reason or message.error_name or not message.parent_message_id
    ):
        return False
    parent = messages.get(message.parent_message_id)
    return bool(parent and parent.role is MessageRole.USER and any(part.kind == "compaction" for part in parent.parts))


def build_prompt_record(
    snapshot: SessionSnapshot,
    ref: PromptReference,
    *,
    tracked_provider: ProviderScope = TRACKED_PROVIDER_DEFAULT,
    estimator: CostEstimator | None = None,
    now_ms: int | None = None,
    subscription_providers: frozenset[str] = frozenset(),
) -> PromptRecord | None:
    now_ms = int(time.time() * 1000) if now_ms is None else now_ms
    parent_ids = _synthetic_parent_ids(snapshot, ref)
    assistant_messages = [
        message for message in snapshot.messages
        if message.session_id == ref.session_id
        and message.role is MessageRole.ASSISTANT
        and message.parent_message_id in parent_ids
    ]
    # Earlier failed attempts remain in the same prompt's history. Only the
    # terminal assistant outcome determines whether the logical prompt aborted.
    latest = _latest_assistant(assistant_messages)
    evidence = latest.termination if latest else None
    explicitly_aborted = bool(evidence.outcome is TerminalOutcome.CANCELLATION if evidence
                              else latest and _is_aborted_message(latest))
    superseded = any(event.created_at_ms > ref.prompt_time_ms for event in _visible_prompt_events(snapshot))
    compacting = active_compaction_event(snapshot)
    superseded = superseded or bool(compacting and compacting.created_at_ms > ref.prompt_time_ms)
    foreground_work = _prompt_has_active_work(
        snapshot, assistant_messages, continuation_superseded=superseded
    )
    background = _outstanding_background(snapshot, assistant_messages, superseded=superseded)

    def running(active_work: bool) -> bool:
        return (not explicitly_aborted or bool(evidence and active_work)) and not bool(
            compacting and compacting.created_at_ms > ref.prompt_time_ms
        ) and _assistant_in_progress(
            assistant_messages, now_ms=now_ms, continuation_superseded=superseded, active_work=active_work,
        )

    in_progress = running(foreground_work or bool(background))
    background_only = in_progress and not running(foreground_work)
    background_fields = dict(
        background_kinds=tuple(item.kind for item in background) if in_progress else (),
        background_started_ms=min((item.started_at_ms for item in background), default=0) if in_progress else 0,
        background_only=background_only,
        abort_reason=((evidence.abort_reason if evidence else "") or (latest.abort_reason if latest else ""))
                     if explicitly_aborted and not in_progress else "",
        ended_after_tool_calls=bool(not in_progress and evidence and evidence.outcome is TerminalOutcome.SUCCESS
                                    and latest and latest.finish_reason == "tool-calls"),
    )

    all_entries = [
        entry for entry in trace_entries(snapshot, subscription_providers=subscription_providers)
        if entry.session_id == ref.session_id and provider_matches(entry.model.provider, tracked_provider)
    ]
    root_entries = sorted(
        (entry for entry in all_entries if entry.parent_event_id in parent_ids),
        key=lambda entry: (entry.completed_at_ms, entry.sort_order),
    )
    prompt_message = next((message for message in snapshot.messages if message.message_id == ref.prompt_id), None)
    prompt_context_approx = _message_approx_context_tokens(prompt_message) or math.ceil(len(ref.prompt_text) / 4)
    previous_before_prompt = None
    for entry in all_entries:
        if entry.request_input_approx <= 0:
            continue
        if entry.completed_at_ms <= ref.prompt_time_ms:
            previous_before_prompt = entry
        else:
            break

    zero_usage_abort = bool(root_entries) and not in_progress and ref.prompt_kind != "subtask" and not any(
        entry.tokens.total > 0 or entry.reported_cost > 0 for entry in root_entries
    )
    evidence = evidence if not in_progress else None
    successful_final = bool(evidence.outcome is TerminalOutcome.SUCCESS if evidence else
                            latest and latest.completed_at_ms is not None
                            and latest.finish_reason not in {None, "tool-calls"} and not latest.error_name)
    terminal_error = bool(evidence.outcome is TerminalOutcome.FAILURE if evidence else latest and latest.error_name)
    # Usage alone cannot override an explicit non-abort terminal failure.
    aborted = (explicitly_aborted and not in_progress) or (zero_usage_abort and not successful_final and not terminal_error)
    watch_error = not aborted and terminal_error
    abort_time = max(
        (message.completed_at_ms or 0 for message in assistant_messages if not explicitly_aborted or _is_aborted_message(message)),
        default=0,
    ) if aborted else 0
    if aborted and evidence:
        abort_time = evidence.completed_at_ms
    terminal_time = 0 if in_progress else _prompt_activity_end(
        snapshot, assistant_messages, fallback=ref.prompt_time_ms
    )

    if not root_entries:
        if not aborted and not in_progress and not watch_error and not evidence:
            return None
        # Before its first completed request a running prompt may already have a
        # request-bound in-flight assistant; never borrow mutable session selection.
        bound = next((m.model for m in reversed(assistant_messages) if m.model is not None and not m.summary), None)
        main_model = ref.model_id or (bound.model if bound else "")
        main_provider = ref.provider_id or (bound.provider if bound else "")
        return PromptRecord(
            session_id=ref.session_id, prompt_id=ref.prompt_id, prompt_time_ms=ref.prompt_time_ms,
            prompt_number=ref.prompt_number, prompt_kind=ref.prompt_kind, prompt_text=ref.prompt_text,
            session_title=snapshot.root.title, main_model_id=main_model, main_provider_id=main_provider,
            main_variant=ref.variant, first_request_time_ms=0, last_request_time_ms=ref.prompt_time_ms,
            terminal_time_ms=abort_time or terminal_time or ref.prompt_time_ms, entries=(), root_entry_count=0,
            cost=0, main_cost=0, subagent_cost=0, breakdown_known=True, has_cost_breakdown=False,
            main_estimated=False, subagent_estimated=False, fallback_requests=0,
            estimated_fallback_requests=0, unresolved_fallback_requests=0, input_tokens=0,
            output_tokens=0, cache_read_tokens=0, cache_write_tokens=0, input_context_tokens=0,
            total_token_volume=0, model_costs={}, prompt_context_tokens_approx=prompt_context_approx,
            previous_entry=previous_before_prompt, pre_prompt_entry=previous_before_prompt,
            previous_entry_is_compaction=_is_completed_compaction_entry(snapshot, previous_before_prompt),
            last_root_entry=None, aborted=aborted, watch_error=watch_error, abort_time_ms=abort_time,
            in_progress=in_progress,
            completed_successfully=successful_final,
            duration_ms=max(0, terminal_time - ref.prompt_time_ms) if evidence else 0,
            **background_fields,
        )

    first, last = root_entries[0], root_entries[-1]
    previous = None
    for entry in all_entries:
        if entry.request_input_approx <= 0:
            continue
        if (entry.completed_at_ms, entry.sort_order) < (first.completed_at_ms, first.sort_order):
            previous = entry
        else:
            break

    prompt_start = ref.prompt_time_ms
    prompt_end = last.completed_at_ms
    if not in_progress and terminal_time <= 0:
        terminal_time = abort_time or prompt_end
    causal_end = now_ms if in_progress else max(prompt_end, terminal_time)
    local_intervals = _local_intervals(assistant_messages, prompt_start, causal_end)
    entries = list(root_entries)
    visited: set[tuple[str, int, int]] = set()
    all_tree_entries = trace_entries(snapshot, subscription_providers=subscription_providers)
    for child_id, start, end in _task_invocations(assistant_messages, prompt_start, causal_end, in_progress):
        child_entries, child_local = _child_work(
            snapshot, all_tree_entries, child_id, start, end, visited, in_progress, tracked_provider
        )
        entries.extend(child_entries)
        local_intervals.extend(child_local)

    billed = measure_prompt_billing(entries, len(root_entries), estimator)
    meaningful_first = first
    last_root_for_next: TraceEntry | None = last
    if ref.prompt_kind == "subtask":
        meaningful = sorted((entry for entry in entries if entry.request_input_approx > 0), key=lambda e: (e.completed_at_ms, e.sort_order))
        if meaningful:
            meaningful_first = meaningful[0]
        nonzero_root = [entry for entry in root_entries if entry.request_input_approx > 0]
        last_root_for_next = nonzero_root[-1] if nonzero_root else None

    main_model = ref.model_id or meaningful_first.model.model
    main_provider = ref.provider_id or meaningful_first.model.provider
    duration = max(0, causal_end - prompt_start)
    local_ms = _measure_interval_union(local_intervals, prompt_start, causal_end)
    output_total = billed.output_tokens
    total_volume = billed.input_tokens + billed.cache_read_tokens + billed.cache_write_tokens + output_total

    return PromptRecord(
        session_id=ref.session_id, prompt_id=ref.prompt_id, prompt_time_ms=ref.prompt_time_ms,
        prompt_number=ref.prompt_number, prompt_kind=ref.prompt_kind, prompt_text=ref.prompt_text,
        session_title=snapshot.root.title, main_model_id=main_model, main_provider_id=main_provider,
        main_variant=ref.variant, first_request_time_ms=meaningful_first.completed_at_ms,
        last_request_time_ms=prompt_end, terminal_time_ms=terminal_time, entries=tuple(entries),
        root_entry_count=len(root_entries), cost=billed.cost, main_cost=billed.main_cost,
        subagent_cost=billed.subagent_cost, breakdown_known=billed.breakdown_known,
        has_cost_breakdown=billed.has_cost_breakdown, main_estimated=billed.main_estimated,
        subagent_estimated=billed.subagent_estimated, fallback_requests=billed.fallback_requests,
        estimated_fallback_requests=billed.estimated_fallback_requests,
        unresolved_fallback_requests=billed.unresolved_fallback_requests, input_tokens=billed.input_tokens,
        output_tokens=output_total, cache_read_tokens=billed.cache_read_tokens,
        cache_write_tokens=billed.cache_write_tokens, input_context_tokens=meaningful_first.request_input_approx,
        total_token_volume=total_volume, model_costs=billed.model_costs, duration_ms=duration,
        local_duration_ms=local_ms, model_wait_ms=max(0, duration - local_ms),
        prompt_context_tokens_approx=prompt_context_approx, previous_entry=previous,
        pre_prompt_entry=previous_before_prompt,
        previous_entry_is_compaction=_is_completed_compaction_entry(snapshot, previous),
        last_root_entry=last_root_for_next, aborted=aborted, watch_error=watch_error,
        abort_time_ms=abort_time, in_progress=in_progress,
        completed_successfully=successful_final,
        **background_fields,
    )


def build_prompt_records(
    snapshot: SessionSnapshot,
    *,
    since_ms: int = 0,
    tracked_provider: ProviderScope = TRACKED_PROVIDER_DEFAULT,
    estimator: CostEstimator | None = None,
    now_ms: int | None = None,
    subscription_providers: frozenset[str] = frozenset(),
) -> tuple[PromptRecord, ...]:
    records = [
        record
        for ref in prompt_references(snapshot, since_ms=since_ms)
        if (record := build_prompt_record(
            snapshot, ref, tracked_provider=tracked_provider, estimator=estimator, now_ms=now_ms,
            subscription_providers=subscription_providers,
        )) is not None
    ]
    return tuple(sorted(records, key=lambda record: (record.prompt_time_ms, record.prompt_number)))
