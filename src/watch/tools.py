"""Watch-only tool/todo observations derived from already-hydrated canonical snapshots."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from src.analysis.causal import prompt_parent_ids
from src.analysis.child_links import ChildLinkIndex
from src.domain import EventKind, MessageRole, NormalizedMessage, NormalizedPart, SessionSnapshot

from .models import SkillObservation, ToolObservation, ToolOutcome
from .invocation import (
    MAX_INPUT_TEXT, MAX_INVOCATIONS, MAX_FAILED_INVOCATIONS,
    background_invocations, failed_invocations, invocation,
)
from .tool_contracts import (
    executed_skill_script, failure_skill, is_skill_tool, loaded_skill, skill_tool_id,
    structured_outcome, verified_skill_origin,
)


def without_live_activity(tool: ToolObservation) -> ToolObservation:
    """Keep final counts, removing every indicator of ongoing execution."""
    return replace(tool, running_tool="", running_ms=0, todo_completed=0, todo_total=0,
        active_todo="", background_kinds=(), background_ms=0,
        running_invocation=None, background_invocation=None, running_invocations=(),
        background_invocations=(), running_invocation_count=0, background_invocation_count=0)


def _parent_ids(snapshot: SessionSnapshot, event_id: str, *, is_compaction: bool) -> set[str]:
    if is_compaction:
        return {event_id}
    event = next((item for item in snapshot.events if item.event_id == event_id), None)
    if event is None:
        return {event_id}
    return prompt_parent_ids(snapshot, event_id, event.created_at_ms, subtask=event.kind is EventKind.SUBTASK)


def _part_start(part) -> int:
    if part.created_at_ms > 0:
        return int(part.created_at_ms)
    state = part.data.get("state")
    if not isinstance(state, Mapping):
        return 0
    time_value = state.get("time")
    if not isinstance(time_value, Mapping):
        return 0
    try:
        return int(time_value.get("start") or 0)
    except (TypeError, ValueError):
        return 0


RUNNING_VISIBLE_AFTER_MS = 10_000
# Current V2 uses `todo`; older data uses `todowrite`. Separator variants are tolerated.
_TODO_TOOL_NAMES = frozenset({"todo", "todowrite", "todos"})
_CANCELLATION_MARKERS = ("abort", "cancel", "interrupt")


def _is_todo_tool(part) -> bool:
    return _tool_name(part).replace("_", "").replace("-", "") in _TODO_TOOL_NAMES


def _tool_state(part) -> Mapping:
    state = part.data.get("state")
    return state if isinstance(state, Mapping) else {}


def _is_cancellation(state: Mapping) -> bool:
    """Identify user/session cancellation from structured error fields only (never tool output)."""
    metadata = state.get("metadata")
    if isinstance(metadata, Mapping) and metadata.get("interrupted") is True:
        return True
    error = state.get("error")
    values = [error] if isinstance(error, str) else (
        [error.get(key) for key in ("name", "type", "code", "message")] if isinstance(error, Mapping) else []
    )
    return any(
        isinstance(value, str) and any(marker in value.lower() for marker in _CANCELLATION_MARKERS)
        for value in values
    )


def _todo_state(part) -> tuple[tuple[str, str], ...] | None:
    if part.kind != "tool" or not _is_todo_tool(part):
        return None
    state = part.data.get("state")
    if not isinstance(state, Mapping):
        return None
    candidate = None
    input_value = state.get("input")
    metadata = state.get("metadata")
    if isinstance(input_value, Mapping) and "todos" in input_value:
        candidate = input_value.get("todos")
    elif isinstance(metadata, Mapping) and "todos" in metadata:
        candidate = metadata.get("todos")
    if not isinstance(candidate, list):
        return None
    values: list[tuple[str, str]] = []
    for item in candidate:
        if not isinstance(item, Mapping) or "status" not in item or "content" not in item:
            return None
        status = str(item.get("status") or "").strip()
        if not status:
            return None
        values.append((status, str(item.get("content") or "")))
    return tuple(values)


def _tool_name(part) -> str:
    return str(part.data.get("tool") or part.data.get("name") or "").lower()


def _physical_order(part):
    call = part.data.get("callID")
    return (_part_start(part), part.session_id,
            ("call", call) if isinstance(call, str) and call else ("part", part.part_id))


def _prompt_messages(snapshot: SessionSnapshot, parents: set[str], is_compaction: bool) -> list[NormalizedMessage]:
    """Use the same proven task/subagent windows as canonical prompt accounting."""
    messages = [
        message for message in snapshot.messages
        if message.role is MessageRole.ASSISTANT
        and message.session_id == snapshot.root.session_id
        and message.parent_message_id in parents
        and (not is_compaction or message.summary)
    ]
    children = ChildLinkIndex(snapshot)
    return [*messages, *children.messages(children.scopes(messages))]


def _physical_tools(messages: list[NormalizedMessage]) -> tuple[NormalizedPart, ...]:
    """Call IDs coalesce native copies; otherwise canonical part identity is authoritative."""
    calls: dict[tuple[str, str, str], NormalizedPart] = {}
    for message in messages:
        for part in message.parts:
            if part.kind != "tool":
                continue
            call_id = part.data.get("callID")
            key = (part.session_id, "call" if isinstance(call_id, str) and call_id else "part",
                   call_id if isinstance(call_id, str) and call_id else part.part_id)
            previous = calls.get(key)
            rank = (part.updated_at_ms, str(_tool_state(part).get("status") or "").lower() in {"completed", "error"})
            if previous is None or rank >= (
                previous.updated_at_ms, str(_tool_state(previous).get("status") or "").lower() in {"completed", "error"}
            ):
                calls[key] = part
    return tuple(calls.values())


def observe_tools(
    snapshot: SessionSnapshot, event_id: str, *, is_compaction: bool = False, now_ms: int = 0,
    skill_origins_by_session: Mapping[str, Mapping[str, str]] | None = None,
    include_invocations: bool = False,
) -> ToolObservation:
    """Count physical calls and evidenced outcomes within the canonical prompt scope."""
    parents = _parent_ids(snapshot, event_id, is_compaction=is_compaction)
    candidates = []
    tool_count = 0
    counts: dict[str, int] = {}
    outcomes: dict[tuple[str, str], int] = {}
    running_tool, running_ms = "", 0
    running_parts = []
    failed_parts = []
    order = 0
    messages = _prompt_messages(snapshot, parents, is_compaction)
    skills: dict[str, tuple[int, int]] = {}
    skill_failures: dict[str, int] = {}
    origins_by_session = skill_origins_by_session or {}
    physical = _physical_tools(messages)
    for part in physical:
        start = _part_start(part)
        if start <= 0:
            continue
        tool_count += 1
        name = _tool_name(part).strip() or "unknown"
        skill_call = is_skill_tool(part.data)
        skill_id = skill_tool_id(part.data) if skill_call else ""
        origin = verified_skill_origin(
            origins_by_session.get(part.session_id, {}).get(skill_id)
        ) if skill_id else ""
        if skill_call:
            name = f"{origin} skill" if origin else "skill"
        counts[name] = counts.get(name, 0) + 1
        state = _tool_state(part)
        status = str(state.get("status") or "").lower()
        skill = loaded_skill(part.data)
        if skill and origin == "custom":
            skills[skill] = max(skills.get(skill, (0, 0)), (start, tool_count))
        script = executed_skill_script(part.data)
        outcome = structured_outcome(part.data, script) if not _is_cancellation(state) else "cancelled"
        if outcome != "cancelled" and status == "error":
            outcome = "error"
        if outcome in {"error", "cancelled"}:
            key = (name, "failed" if outcome == "error" else "cancelled")
            outcomes[key] = outcomes.get(key, 0) + 1
        if outcome == "error":
            if include_invocations:
                failed_parts.append((name, part))
            owner = failure_skill(part.data, script)
            if owner:
                skill_failures[owner] = skill_failures.get(owner, 0) + 1
        elif not outcome and status == "running" and now_ms - start >= RUNNING_VISIBLE_AFTER_MS:
            running_parts.append(part)
            if now_ms - start > running_ms:
                running_tool, running_ms = name, now_ms - start
        if _is_todo_tool(part):
            order += 1
            candidates.append((start, order, _todo_state(part)))
    todos = None
    if candidates:
        _, _, todos = max(candidates, key=lambda item: (item[0], item[1]))
    running_parts.sort(key=_physical_order)
    failed_parts.sort(key=lambda item: _physical_order(item[1]))
    foreground_count = min(len(running_parts), MAX_INVOCATIONS)
    failure_count = min(len(failed_parts), MAX_FAILED_INVOCATIONS)
    background_details, background_count = background_invocations(
        snapshot, messages, physical, other_count=foreground_count + failure_count) if include_invocations else ((), 0)
    # One card-wide input budget keeps the existing 100-card SSE/replay bound
    # even when every card has maximum foreground, background and failed lists.
    budget = MAX_INPUT_TEXT // max(1, foreground_count + min(background_count, MAX_INVOCATIONS) + failure_count)
    running_details = tuple(replace(invocation(part, budget=budget), started_at_ms=_part_start(part))
                            for part in running_parts[:MAX_INVOCATIONS]) if include_invocations else ()
    summary = dict(
        tool_counts=tuple(sorted(counts.items(), key=lambda item: (-item[1], item[0]))),
        tool_outcomes=tuple(ToolOutcome(name, outcome, count) for (name, outcome), count in sorted(
            outcomes.items(), key=lambda item: (item[0][1] != "failed", -item[1], item[0][0]))),
        failed_count=sum(count for (_, outcome), count in outcomes.items() if outcome == "failed"),
        running_tool=running_tool, running_ms=running_ms,
        running_invocation=running_details[0] if running_details else None,
        background_invocation=background_details[0] if background_count == 1 and background_details[0].text else None,
        running_invocations=running_details, background_invocations=background_details,
        running_invocation_count=len(running_parts) if include_invocations else 0,
        background_invocation_count=background_count,
        failed_invocations=failed_invocations(failed_parts, snapshot.root.provenance, budget=budget),
        skills=tuple(SkillObservation(skill, skill_failures.get(skill, 0))
                     for skill in sorted(skills, key=lambda item: skills[item], reverse=True)),
    )
    if todos is None:
        return ToolObservation(tool_count=tool_count, **summary)
    completed = sum(1 for status, _ in todos if status == "completed")
    active = next((content for status, content in todos if status in {"in_progress", "in-progress"}), "")
    active = " ".join(active.replace("\t", " ").replace("\r", " ").replace("\n", " ").split())
    return ToolObservation(tool_count, completed, len(todos), active, **summary)
