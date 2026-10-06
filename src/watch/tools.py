"""Watch-only tool/todo observations derived from already-hydrated canonical snapshots."""
from __future__ import annotations

from collections.abc import Mapping

from src.domain import EventKind, MessageRole, SessionSnapshot

from .models import ToolObservation


def _parent_ids(snapshot: SessionSnapshot, event_id: str, *, is_compaction: bool) -> set[str]:
    ids = {event_id}
    if is_compaction:
        return ids
    event = next((item for item in snapshot.events if item.event_id == event_id), None)
    if event is None or event.kind is not EventKind.SUBTASK:
        return ids
    visible = sorted(
        (
            item for item in snapshot.events
            if item.session_id == snapshot.root.session_id
            and item.kind in {EventKind.USER_PROMPT, EventKind.SUBTASK}
        ),
        key=lambda item: (item.created_at_ms, item.event_id),
    )
    next_time = min(
        (item.created_at_ms for item in visible if item.created_at_ms > event.created_at_ms),
        default=2**63 - 1,
    )
    for item in snapshot.events:
        if (
            item.session_id == snapshot.root.session_id
            and item.kind is EventKind.SYNTHETIC_CONTINUATION
            and event.created_at_ms < item.created_at_ms < next_time
        ):
            ids.add(item.event_id)
    return ids


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


def _child_session_id(part) -> str:
    if _tool_name(part) != "task":
        return ""
    state = part.data.get("state")
    metadata = state.get("metadata") if isinstance(state, Mapping) else None
    if isinstance(metadata, Mapping):
        value = metadata.get("sessionId", metadata.get("sessionID"))
        if value:
            return str(value)
    metadata = part.data.get("metadata")
    if isinstance(metadata, Mapping):
        value = metadata.get("sessionId", metadata.get("sessionID"))
        if value:
            return str(value)
    return ""


def observe_tools(
    snapshot: SessionSnapshot, event_id: str, *, is_compaction: bool = False, now_ms: int = 0,
) -> ToolObservation:
    """Count tool calls by name, structured failures, the longest long-running tool and the newest reliable todo state."""
    parents = _parent_ids(snapshot, event_id, is_compaction=is_compaction)
    candidates = []
    tool_count = 0
    counts: dict[str, int] = {}
    failed = 0
    running_tool, running_ms = "", 0
    order = 0
    messages = [
        message for message in snapshot.messages
        if message.role is MessageRole.ASSISTANT
        and message.parent_message_id in parents
        and (not is_compaction or message.summary)
    ]
    child_ids: set[str] = set()
    pending = list(messages)
    while pending:
        message = pending.pop()
        for part in message.parts:
            child_id = _child_session_id(part)
            if not child_id or child_id in child_ids:
                continue
            child_ids.add(child_id)
            child_messages = [
                item for item in snapshot.messages
                if item.role is MessageRole.ASSISTANT and item.session_id == child_id
            ]
            messages.extend(child_messages)
            pending.extend(child_messages)
    seen_parts: set[str] = set()
    for message in messages:
        for part in message.parts:
            if part.kind != "tool" or part.part_id in seen_parts:
                continue
            seen_parts.add(part.part_id)
            start = _part_start(part)
            if start <= 0:
                continue
            tool_count += 1
            name = _tool_name(part).strip() or "unknown"
            counts[name] = counts.get(name, 0) + 1
            state = _tool_state(part)
            status = str(state.get("status") or "").lower()
            if status == "error" and not _is_cancellation(state):
                failed += 1
            elif status == "running" and now_ms - start >= RUNNING_VISIBLE_AFTER_MS and now_ms - start > running_ms:
                running_tool, running_ms = name, now_ms - start
            if _is_todo_tool(part):
                order += 1
                candidates.append((start, order, _todo_state(part)))
    todos = None
    if candidates:
        _, _, todos = max(candidates, key=lambda item: (item[0], item[1]))
    summary = dict(
        tool_counts=tuple(sorted(counts.items(), key=lambda item: (-item[1], item[0]))),
        failed_count=failed, running_tool=running_tool, running_ms=running_ms,
    )
    if todos is None:
        return ToolObservation(tool_count=tool_count, **summary)
    completed = sum(1 for status, _ in todos if status == "completed")
    active = next((content for status, content in todos if status in {"in_progress", "in-progress"}), "")
    active = " ".join(active.replace("\t", " ").replace("\r", " ").replace("\n", " ").split())
    return ToolObservation(tool_count, completed, len(todos), active, **summary)
