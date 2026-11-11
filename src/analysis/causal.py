"""Prompt boundaries and causal attribution over canonical session snapshots."""
from __future__ import annotations

import math
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from src.domain.progress import observe_work

from src.domain import (
    BackgroundActivity, CostDisposition, EventKind, MessageRole, NormalizedEvent, NormalizedMessage, NormalizedPart,
    SessionSnapshot, TerminalOutcome,
)

from .billing import CostEstimator, ProviderScope, measure_prompt_billing
from .models import PromptRecord, PromptReference, TraceEntry
from .duration import prompt_duration
from .prompt_index import PromptIndex, prompt_owners
from .child_links import ChildLinkIndex, OPEN_END, part_time as _part_time, scoped_entries

TRACKED_PROVIDER_DEFAULT = "github-copilot"
TOOL_CALLS_CONTINUATION_GRACE_MS = 60_000
_LOCAL_TOOL_NAMES = frozenset({
    "bash", "shell", "read", "grep", "glob", "edit", "write", "patch",
    "apply_patch", "ls", "lsp", "skill", "todoread", "todowrite",
})


def trace_entries(
    snapshot: SessionSnapshot, *, subscription_providers: frozenset[str] = frozenset()
) -> tuple[TraceEntry, ...]:
    result: list[TraceEntry] = []
    owners = prompt_owners(snapshot)
    for order, invocation in enumerate(snapshot.invocations):
        observe_work('analyzing', 1)
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
            logical_prompt_id=owners.get((invocation.session_id, invocation.initiating_event_id)),
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


@dataclass(frozen=True, slots=True)
class _RootTimeline:
    """Snapshot-wide inputs shared by every prompt of one analysis pass.

    Deriving them once per prompt made attribution quadratic in long sessions.
    """

    entries: tuple[TraceEntry, ...]
    visible_events: tuple[NormalizedEvent, ...]
    compacting: NormalizedEvent | None
    messages: Mapping[str, NormalizedMessage]
    index: PromptIndex
    children: ChildLinkIndex


def _root_timeline(
    snapshot: SessionSnapshot, subscription_providers: frozenset[str] = frozenset(),
    tracked_provider: ProviderScope = TRACKED_PROVIDER_DEFAULT,
) -> _RootTimeline:
    entries = trace_entries(snapshot, subscription_providers=subscription_providers)
    visible = tuple(_visible_prompt_events(snapshot))
    return _RootTimeline(
        entries=entries,
        visible_events=visible,
        compacting=active_compaction_event(snapshot),
        messages={message.message_id: message for message in snapshot.messages},
        index=PromptIndex(snapshot, entries, visible, tracked_provider),
        children=ChildLinkIndex(snapshot),
    )


def prompt_references(
    snapshot: SessionSnapshot, *, since_ms: int = 0, timeline: _RootTimeline | None = None,
) -> tuple[PromptReference, ...]:
    timeline = timeline or _root_timeline(snapshot)
    parent_ids = {entry.parent_event_id for entry in timeline.entries if entry.parent_event_id}
    messages = timeline.messages
    refs: list[PromptReference] = []
    order = {
        event.event_id: index + 1
        for index, event in enumerate(sorted(
            (item for item in snapshot.events if item.session_id == snapshot.root.session_id
             and item.kind in {EventKind.USER_PROMPT, EventKind.SUBTASK, EventKind.COMPACTION}),
            key=lambda item: (item.created_at_ms, item.event_id),
        ))
    }
    visible_events = timeline.visible_events
    for event in visible_events:
        if event.created_at_ms < since_ms:
            continue
        message = messages.get(event.event_id)
        attempt_messages = timeline.index.attempt_messages(
            timeline.index.windows[event.event_id], messages)
        latest_visible = event is visible_events[-1]
        window = timeline.index.windows[event.event_id]
        has_error_or_live = (
            any(item.termination or item.error_name or item.completed_at_ms is None for item in attempt_messages)
            or bool(snapshot.root.active is True and latest_visible)
        )
        if not window & parent_ids and not has_error_or_live and not timeline.children.scopes(attempt_messages):
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


def prompt_parent_ids(
    snapshot: SessionSnapshot, prompt_id: str, prompt_time_ms: int, *, subtask: bool,
    visible_events: Sequence[NormalizedEvent] | None = None,
) -> set[str]:
    """Events whose assistant work continues one logical root prompt.

    Background-completion notices and other invisible synthetic user messages
    (for example subagent-completion notices injected while work continues)
    resume the prompt current at that time, so work after them stays on that
    prompt's row; subtasks also own synthetic task-summary continuations.
    Each event falls in exactly one prompt window.
    """
    kinds = {EventKind.BACKGROUND_COMPLETION, EventKind.OTHER} | (
        {EventKind.SYNTHETIC_CONTINUATION} if subtask else set())
    visible = _visible_prompt_events(snapshot) if visible_events is None else visible_events
    next_visible = min(
        (event.created_at_ms for event in visible if event.created_at_ms > prompt_time_ms),
        default=2**63 - 1,
    )
    return {prompt_id} | {
        event.event_id for event in snapshot.events
        if event.session_id == snapshot.root.session_id and event.kind in kinds
        and prompt_time_ms < event.created_at_ms < next_visible
    }


def _synthetic_parent_ids(snapshot: SessionSnapshot, ref: PromptReference, timeline: _RootTimeline) -> set[str]:
    return timeline.index.windows.get(ref.prompt_id, {ref.prompt_id})


def _outstanding_background(
    snapshot: SessionSnapshot, child_ids: set[str], *, superseded: bool,
) -> tuple[BackgroundActivity, ...]:
    """Running background work the current prompt is still waiting on.

    Completion resumes the conversation inside the newest prompt, so work an
    earlier prompt started hands its wait over to that prompt; a superseded
    prompt never waits on background work.
    """
    if superseded:
        return ()
    sessions = {snapshot.root.session_id} | child_ids
    return tuple(item for item in snapshot.background if item.running and item.session_id in sessions)


def _is_aborted_message(message: NormalizedMessage) -> bool:
    return message.error_name in {"AbortedError", "AbortError", "MessageAbortedError"}


def _latest_attempt_message(messages: Sequence[NormalizedMessage]) -> NormalizedMessage | None:
    values = sorted(messages, key=lambda item: (
        item.created_at_ms,
        bool(item.completed_at_ms is not None and item.finish_reason not in {None, "tool-calls"} and not item.error_name),
        item.completed_at_ms or 0, item.message_id,
    ))
    return values[-1] if values else None


def _attempt_in_progress(
    messages: Sequence[NormalizedMessage], *, now_ms: int, continuation_superseded: bool,
    active_work: bool = False,
) -> bool:
    latest = _latest_attempt_message(messages)
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


def _prompt_has_active_work(
    snapshot: SessionSnapshot,
    messages: Sequence[NormalizedMessage],
    *,
    continuation_superseded: bool,
    live_child_ids: set[str],
) -> bool:
    if continuation_superseded:
        return False
    if snapshot.root.active is True:
        return True
    latest = _latest_attempt_message(messages)
    terminal_at = latest.termination.completed_at_ms if latest and latest.termination else 0
    if any(_part_is_running(part) and (not terminal_at or max(
        part.created_at_ms, part.updated_at_ms, _part_time(part)[0]) > terminal_at)
        for message in messages for part in message.parts):
        return True
    return any(session.session_id in live_child_ids and session.active is True for session in snapshot.sessions)


def _prompt_activity_end(
    snapshot: SessionSnapshot,
    messages: Sequence[NormalizedMessage],
    *,
    fallback: int,
) -> int:
    values = [fallback]
    for message in messages:
        values.append(message.completed_at_ms or message.created_at_ms)
        if message.termination:
            values.append(message.termination.completed_at_ms)
        values.extend(part.updated_at_ms or part.created_at_ms for part in message.parts)
        values.extend(_part_time(part)[1] for part in message.parts)
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


def _tool_name(part: NormalizedPart) -> str:
    return str(part.data.get("tool") or part.data.get("name") or "").lower()


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


def _is_completed_compaction_entry(messages: Mapping[str, NormalizedMessage], entry: TraceEntry | None) -> bool:
    if entry is None or not entry.message_id:
        return False
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
    timeline: _RootTimeline | None = None,
) -> PromptRecord | None:
    """``timeline`` must derive from the same snapshot and subscription providers."""
    now_ms = int(time.time() * 1000) if now_ms is None else now_ms
    timeline = timeline or _root_timeline(snapshot, subscription_providers, tracked_provider)
    parent_ids = _synthetic_parent_ids(snapshot, ref, timeline)
    attempt_messages = timeline.index.attempt_messages(parent_ids, timeline.messages)
    scopes = timeline.children.scopes(attempt_messages)
    child_ids = {scope.session_id for scope in scopes}
    child_messages = timeline.children.messages(scopes)
    # A continuation may fail before producing an assistant. The newest attempt,
    # not an earlier response or session inactivity, owns the logical outcome.
    latest = _latest_attempt_message(attempt_messages)
    evidence = latest.termination if latest else None
    explicitly_aborted = bool(evidence.outcome is TerminalOutcome.CANCELLATION if evidence
                              else latest and _is_aborted_message(latest))
    superseded = bool(timeline.visible_events and timeline.visible_events[-1].created_at_ms > ref.prompt_time_ms)
    compacting = timeline.compacting
    superseded = superseded or bool(compacting and compacting.created_at_ms > ref.prompt_time_ms)
    foreground_work = _prompt_has_active_work(
        snapshot, (*attempt_messages, *child_messages), continuation_superseded=superseded,
        live_child_ids={scope.session_id for scope in scopes if scope.end_ms == OPEN_END},
    )
    background = _outstanding_background(snapshot, child_ids, superseded=superseded)

    def running(active_work: bool) -> bool:
        return (not explicitly_aborted or bool(evidence and active_work)) and not bool(
            compacting and compacting.created_at_ms > ref.prompt_time_ms
        ) and _attempt_in_progress(
            attempt_messages, now_ms=now_ms, continuation_superseded=superseded, active_work=active_work,
        )

    in_progress = running(foreground_work or bool(background))
    # A negative native observation is process-local, not a persisted end or
    # proof that another server is executing this unfinished request. Do not
    # turn that contradiction into either a live clock or a successful result.
    unverified = bool(in_progress and snapshot.complete and snapshot.root.active is False
        and not superseded and not foreground_work and not background and latest
        and latest.role is MessageRole.ASSISTANT and latest.completed_at_ms is None
        and not latest.termination and not latest.error_name)
    in_progress = in_progress and not unverified
    background_only = in_progress and not running(foreground_work)
    background_fields = dict(
        execution_unverified=unverified,
        background_kinds=tuple(item.kind for item in background) if in_progress else (),
        background_started_ms=min((item.started_at_ms for item in background), default=0) if in_progress else 0,
        background_only=background_only,
        abort_reason=((evidence.abort_reason if evidence else "") or (latest.abort_reason if latest else ""))
                     if explicitly_aborted and not in_progress else "",
        ended_after_tool_calls=bool(not in_progress and evidence and evidence.outcome is TerminalOutcome.SUCCESS
                                    and latest and latest.finish_reason == "tool-calls"),
    )

    root_entries = sorted(
        (entry for parent in parent_ids for entry in timeline.index.entries.get(parent, ())),
        key=lambda entry: (entry.completed_at_ms, entry.sort_order),
    )
    child_entries = scoped_entries(snapshot, timeline.entries, scopes, tracked_provider) if scopes else []
    prompt_message = timeline.messages.get(ref.prompt_id)
    prompt_context_approx = _message_approx_context_tokens(prompt_message) or math.ceil(len(ref.prompt_text) / 4)
    previous_before_prompt = timeline.index.before_prompt(ref.prompt_time_ms)

    zero_usage_abort = bool(root_entries) and not in_progress and not unverified and ref.prompt_kind != "subtask" and not any(
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
        (message.completed_at_ms or 0 for message in attempt_messages if not explicitly_aborted or _is_aborted_message(message)),
        default=0,
    ) if aborted else 0
    if aborted and evidence:
        abort_time = evidence.completed_at_ms
    terminal_time = 0 if in_progress or unverified else _prompt_activity_end(
        snapshot, (*attempt_messages, *child_messages), fallback=ref.prompt_time_ms
    )

    if not root_entries and not child_entries:
        if not aborted and not in_progress and not unverified and not watch_error and not evidence:
            return None
        # Before its first completed request a running prompt may already have a
        # request-bound in-flight assistant; never borrow mutable session selection.
        bound = next((m.model for m in reversed(attempt_messages) if m.model is not None and not m.summary), None)
        main_model = ref.model_id or (bound.model if bound else "")
        main_provider = ref.provider_id or (bound.provider if bound else "")
        return PromptRecord(
            session_id=ref.session_id, prompt_id=ref.prompt_id, prompt_time_ms=ref.prompt_time_ms,
            prompt_number=ref.prompt_number, prompt_kind=ref.prompt_kind, prompt_text=ref.prompt_text,
            session_title=snapshot.root.title, main_model_id=main_model, main_provider_id=main_provider,
            main_variant=ref.variant, first_request_time_ms=0, last_request_time_ms=ref.prompt_time_ms,
            terminal_time_ms=0 if unverified else abort_time or terminal_time or ref.prompt_time_ms, entries=(), root_entry_count=0,
            cost=0, main_cost=0, subagent_cost=0, breakdown_known=True, has_cost_breakdown=False,
            main_estimated=False, subagent_estimated=False, fallback_requests=0,
            estimated_fallback_requests=0, unresolved_fallback_requests=0, input_tokens=0,
            output_tokens=0, cache_read_tokens=0, cache_write_tokens=0, input_context_tokens=0,
            total_token_volume=0, model_costs={}, prompt_context_tokens_approx=prompt_context_approx,
            previous_entry=previous_before_prompt, pre_prompt_entry=previous_before_prompt,
            previous_entry_is_compaction=_is_completed_compaction_entry(timeline.messages, previous_before_prompt),
            last_root_entry=None, aborted=aborted, watch_error=watch_error, abort_time_ms=abort_time,
            in_progress=in_progress,
            completed_successfully=successful_final,
            duration_ms=max(0, terminal_time - ref.prompt_time_ms) if evidence else 0,
            execution_duration_ms=None if unverified else prompt_duration(ref, attempt_messages, latest, (), timeline.messages,
                                                  in_progress=in_progress, now_ms=now_ms, background=snapshot.background),
            linked_session_ids=tuple(sorted(child_ids)),
            **background_fields,
        )

    first, last = (root_entries or child_entries)[0], (root_entries or child_entries)[-1]
    previous = timeline.index.before_entry(first)

    prompt_start = ref.prompt_time_ms
    prompt_end = last.completed_at_ms
    if not in_progress and not unverified and terminal_time <= 0:
        terminal_time = abort_time or prompt_end
    causal_end = now_ms if in_progress else max(prompt_end, terminal_time)
    local_intervals = _local_intervals(attempt_messages, prompt_start, causal_end)
    entries = [*root_entries, *child_entries]
    for scope in scopes:
        local_intervals.extend(_local_intervals(timeline.children.messages((scope,)), scope.start_ms, scope.end_ms))

    billed = measure_prompt_billing(entries, len(root_entries), estimator)
    meaningful_first = first
    last_root_for_next: TraceEntry | None = root_entries[-1] if root_entries else None
    if ref.prompt_kind == "subtask":
        meaningful = sorted((entry for entry in entries if entry.request_input_approx > 0), key=lambda e: (e.completed_at_ms, e.sort_order))
        if meaningful:
            meaningful_first = meaningful[0]
        nonzero_root = [entry for entry in root_entries if entry.request_input_approx > 0]
        last_root_for_next = nonzero_root[-1] if nonzero_root else None

    main_binding = meaningful_first.model if root_entries else (latest.model if latest else None)
    main_model = ref.model_id or (main_binding.model if main_binding else "")
    main_provider = ref.provider_id or (main_binding.provider if main_binding else "")
    # Keep Watch's historical metadata-based metric separate from qualified
    # report execution_duration_ms and causal request/terminal boundaries.
    watch_end = causal_end if in_progress else max(
        (session.updated_at_ms for session in snapshot.sessions if session.session_id in child_ids),
        default=causal_end,
    )
    duration = max(0, max(causal_end, watch_end) - prompt_start)
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
        execution_duration_ms=None if unverified else prompt_duration(ref, attempt_messages, latest, entries, timeline.messages,
                                              in_progress=in_progress, now_ms=now_ms, background=snapshot.background),
        local_duration_ms=local_ms, model_wait_ms=max(0, duration - local_ms),
        prompt_context_tokens_approx=prompt_context_approx, previous_entry=previous,
        pre_prompt_entry=previous_before_prompt,
        previous_entry_is_compaction=_is_completed_compaction_entry(timeline.messages, previous),
        last_root_entry=last_root_for_next, aborted=aborted, watch_error=watch_error,
        abort_time_ms=abort_time, in_progress=in_progress,
        completed_successfully=successful_final,
        linked_session_ids=tuple(sorted(child_ids)),
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
    timeline = _root_timeline(snapshot, subscription_providers, tracked_provider)
    records = []
    for ref in prompt_references(snapshot, since_ms=since_ms, timeline=timeline):
        record = build_prompt_record(
            snapshot, ref, tracked_provider=tracked_provider, estimator=estimator, now_ms=now_ms,
            subscription_providers=subscription_providers, timeline=timeline,
        )
        if record is not None:
            records.append(record)
        observe_work('analyzing', 1)
    return tuple(sorted(records, key=lambda record: (record.prompt_time_ms, record.prompt_number)))
