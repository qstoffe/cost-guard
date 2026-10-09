"""Wire-shape compatibility helpers for OpenCode V2 HTTP generations.

OpenCode 2 has exposed more than one read contract during its migration. Keep
those wire details out of the canonical source adapter so legacy array payloads
and current cursor-paginated payloads normalize through the same domain path.
"""
from __future__ import annotations

from bisect import bisect_left
from copy import deepcopy
from dataclasses import replace
import math
from typing import Any, Mapping, Sequence
from urllib.parse import quote

from src.domain import ContextBoundary, MessageRole, NormalizedMessage, TerminalEvidence, TerminalOutcome

from .errors import SourceDataError, SourceUnavailableError


# Some OpenCode 2 compatibility surfaces can expose session lifecycle/status
# rows where Cost Guard expects a message page. These are not billing/history
# messages. Qualified durable idle outcomes are normalized separately into
# attempt-bound terminal evidence; transient/unqualified statuses remain hints.
_LIFECYCLE_STATUS_TYPES = frozenset({
    "idle", "busy", "retry", "session.idle", "session.status",
})


def is_lifecycle_status_item(value: Mapping[str, Any]) -> bool:
    message_type = value.get("type")
    return isinstance(message_type, str) and message_type in _LIFECYCLE_STATUS_TYPES


def _is_message_wire_item(value: Mapping[str, Any]) -> bool:
    if is_lifecycle_status_item(value):
        return False
    return (
        is_legacy_message_bundle(value)
        or isinstance(value.get("type"), str)
        or (isinstance(value.get("role"), str) and isinstance(value.get("parts"), list))
    )


def parse_page(value: Any, *, label: str) -> tuple[list[Mapping[str, Any]], str | None, str]:
    """Return mapping items, an opaque next cursor, and a safe contract label."""
    if isinstance(value, list):
        items = value
        contract = "legacy-array"
        next_cursor = None
    elif isinstance(value, Mapping) and isinstance(value.get("data"), list):
        items = value["data"]
        cursor = value.get("cursor")
        cursor_map = cursor if isinstance(cursor, Mapping) else {}
        raw_next = cursor_map.get("next")
        next_cursor = str(raw_next) if raw_next not in (None, "") else None
        contract = "paged-data"
    else:
        raise SourceDataError(f"OpenCode V2 {label} returned an unsupported response shape")

    result: list[Mapping[str, Any]] = []
    for item in items:
        if not isinstance(item, Mapping):
            raise SourceDataError(f"OpenCode V2 {label} contains an invalid item")
        result.append(item)
    return result, next_cursor, contract


def session_directory(session: Mapping[str, Any], fallback: str = "") -> str:
    direct = session.get("directory")
    if isinstance(direct, str) and direct:
        return direct
    location = session.get("location")
    if isinstance(location, Mapping):
        value = location.get("directory")
        if isinstance(value, str) and value:
            return value
    project = session.get("project")
    if isinstance(project, Mapping):
        for key in ("directory", "worktree"):
            value = project.get(key)
            if isinstance(value, str) and value:
                return value
    return fallback


def project_directory(value: Mapping[str, Any]) -> str | None:
    for key in ("worktree", "directory"):
        result = value.get(key)
        if isinstance(result, str) and result.strip():
            return result
    return None


def fetch_global_sessions(client: Any) -> tuple[list[tuple[Mapping[str, Any], str]], str, int]:
    """Read every session from the current global cursor-paginated contract."""
    sessions: dict[str, tuple[Mapping[str, Any], str]] = {}
    cursor: str | None = None
    seen: set[str] = set()
    pages = 0
    contract = "unknown"
    while True:
        # OpenCode cursors are opaque and encode the original query. Current
        # servers reject combining a continuation cursor with order/options.
        query: dict[str, Any] = {"cursor": cursor} if cursor else {"limit": 500, "order": "desc"}
        raw = client.json("/api/session", query=query)
        items, next_cursor, page_contract = parse_page(raw, label="session list")
        contract = "global-" + page_contract
        pages += 1
        for item in items:
            session_id = item.get("id")
            if not isinstance(session_id, str):
                raise SourceDataError("OpenCode V2 session list contains an invalid identity")
            sessions[session_id] = (dict(item), session_directory(item))
        if not items or not next_cursor:
            break
        if next_cursor in seen:
            raise SourceDataError("OpenCode V2 session pagination repeated a cursor")
        seen.add(next_cursor)
        cursor = next_cursor
        if pages > 10000:
            raise SourceDataError("OpenCode V2 session pagination exceeded the safety limit")
    return list(sessions.values()), contract, pages


def fetch_project_sessions(
    client: Any, since_ms: int | None
) -> tuple[list[tuple[Mapping[str, Any], str]], str, int]:
    """Read sessions from the transitional project-scoped V2 contract."""
    projects = client.json("/api/project")
    if not isinstance(projects, list):
        raise SourceDataError("OpenCode V2 project list is not an array")
    sessions: dict[str, tuple[Mapping[str, Any], str]] = {}
    last_contract = "legacy-array"
    for project in projects:
        if not isinstance(project, Mapping):
            raise SourceDataError("OpenCode V2 project list contains an invalid item")
        directory = project_directory(project)
        if not directory:
            continue
        query: dict[str, Any] = {"scope": "project", "directory": directory, "limit": 100000}
        if since_ms is not None:
            query["start"] = int(since_ms)
        raw = client.json("/api/session", query=query)
        items, _next, last_contract = parse_page(raw, label="legacy project session list")
        for item in items:
            session_id = item.get("id")
            if not isinstance(session_id, str):
                raise SourceDataError("OpenCode V2 session list contains an invalid identity")
            sessions[session_id] = (dict(item), session_directory(item, directory))
    return list(sessions.values()), "project-" + last_contract, len(projects)


def _fetch_message_pages(
    client: Any,
    *,
    path: str,
    initial_query: Mapping[str, Any],
    cursor_query: Mapping[str, Any] | None = None,
    label: str,
) -> tuple[list[Mapping[str, Any]], str, int]:
    items: list[Mapping[str, Any]] = []
    cursor: str | None = None
    seen: set[str] = set()
    pages = 0
    contract = "unknown"
    while True:
        if cursor:
            query = dict(cursor_query or {})
            query["cursor"] = cursor
        else:
            query = dict(initial_query)
        raw = client.json(path, query=query)
        page, next_cursor, page_contract = parse_page(raw, label=label)
        contract = page_contract
        pages += 1
        items.extend(page)
        if not page or not next_cursor:
            break
        if next_cursor in seen:
            raise SourceDataError(f"OpenCode V2 {label} pagination repeated a cursor")
        seen.add(next_cursor)
        cursor = next_cursor
        if pages > 10000:
            raise SourceDataError(f"OpenCode V2 {label} pagination exceeded the safety limit")
    return items, contract, pages


def fetch_messages(
    client: Any, *, session_id: str, directory: str
) -> tuple[list[Mapping[str, Any]], str, int, tuple[str, ...]]:
    """Read all messages across current and transitional V2 route shapes.

    The current public V2 contract is session-pinned
    ``/api/session/:id/message`` with no directory routing requirement. Older
    experimental services also exposed ``/api/message`` or required a legacy
    directory query. Try the current contract first, then the compatibility
    surfaces without letting one generation leak into canonical analysis.
    The directory is the session's current one, so moved sessions are followed.
    """
    path = f"/api/session/{quote(session_id, safe='')}/message"
    attempts = (
        (
            path,
            {"limit": 200, "order": "asc"},
            {},
            "session-message",
        ),
        (
            "/api/message",
            {"sessionID": session_id, "limit": 200, "order": "asc"},
            {},
            "message",
        ),
        (
            path,
            {"directory": directory or None, "limit": 200, "order": "asc"},
            {"directory": directory or None},
            "legacy-session-message",
        ),
    )
    last_error: Exception | None = None
    rejected_routes: list[str] = []
    for route, initial_query, cursor_query, label in attempts:
        try:
            items, contract, pages = _fetch_message_pages(
                client,
                path=route,
                initial_query=initial_query,
                cursor_query=cursor_query,
                label=label + " list",
            )
            # A non-empty lifecycle/status-only page is semantically not a
            # message result even if its outer pagination shape is valid. Keep
            # probing compatibility routes instead of accepting it and later
            # failing message normalization. Empty pages remain valid because a
            # session can genuinely contain no messages.
            if items and not any(_is_message_wire_item(item) for item in items):
                if all(is_lifecycle_status_item(item) for item in items):
                    rejected_routes.append(label + "-" + contract + ":lifecycle-only")
                    continue
            return items, label + "-" + contract, pages, tuple(rejected_routes)
        except (SourceUnavailableError, SourceDataError) as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise SourceDataError("OpenCode V2 message routes returned lifecycle/status data only")

def is_legacy_message_bundle(value: Mapping[str, Any]) -> bool:
    return isinstance(value.get("info"), Mapping) and isinstance(value.get("parts"), list)


def _synthetic_part_id(message_id: str, index: int) -> str:
    return f"{message_id}:part:{index:04d}"


def _part_time(value: Mapping[str, Any], fallback: Mapping[str, Any]) -> dict[str, Any]:
    raw = value.get("time")
    source = raw if isinstance(raw, Mapping) else fallback
    created = source.get("created", source.get("start"))
    completed = source.get("completed", source.get("end"))
    result: dict[str, Any] = {}
    if created is not None:
        result["start"] = created
    if completed is not None:
        result["end"] = completed
    return result


def _model_fields(model: Any) -> tuple[str | None, str | None, str | None]:
    if not isinstance(model, Mapping):
        return None, None, None
    provider = model.get("providerID")
    model_id = model.get("id", model.get("modelID"))
    variant = model.get("variant")
    return (
        str(provider) if provider not in (None, "") else None,
        str(model_id) if model_id not in (None, "") else None,
        str(variant) if variant not in (None, "") else None,
    )


def current_union_message_to_legacy_bundle(
    value: Mapping[str, Any], *, session: Mapping[str, Any], ordinal: int
) -> dict[str, Any]:
    """Project the current SessionMessage union into the legacy bundle shape.

    Current OpenCode V2 messages are discriminated by ``type``. Assistant
    usage/model/cost live directly on the assistant message and assistant
    content is an embedded array rather than V1 ``part`` rows. Converting only
    at this wire boundary lets the established canonical normalizer remain the
    single source of causal/billing semantics.
    """
    message_id = value.get("id")
    message_type = value.get("type")
    if not isinstance(message_id, str) or not isinstance(message_type, str):
        raise SourceDataError("OpenCode V2 current message identity is invalid")
    session_id = session.get("id")
    if not isinstance(session_id, str):
        raise SourceDataError("OpenCode V2 current message has no session identity")
    raw_time = value.get("time")
    time_map = dict(raw_time) if isinstance(raw_time, Mapping) else {}

    role = "other"
    if message_type in {"user", "synthetic", "compaction"}:
        role = "user"
    elif message_type == "assistant":
        role = "assistant"

    info: dict[str, Any] = {
        "id": message_id,
        "sessionID": session_id,
        "role": role,
        "time": time_map,
    }
    for key in ("error", "finish", "cost", "tokens"):
        if key in value:
            info[key] = deepcopy(value[key])
    if value.get("agent") not in (None, ""):
        info["agent"] = str(value["agent"])

    provider, model_id, variant = _model_fields(value.get("model"))
    if message_type == "assistant":
        if provider:
            info["providerID"] = provider
        if model_id:
            info["modelID"] = model_id
        if variant:
            info["variant"] = variant
    # Current V2 user messages do not own a request-bound model.
    # Never borrow the mutable session selection for historical prompt events.
    # Actual assistant requests retain their own model and effort above.

    parts: list[dict[str, Any]] = []

    def append_part(raw: Mapping[str, Any], *, fallback_type: str | None = None) -> None:
        index = len(parts)
        part = deepcopy(dict(raw))
        part.setdefault("id", _synthetic_part_id(message_id, index))
        part.setdefault("messageID", message_id)
        part.setdefault("sessionID", session_id)
        if fallback_type and not part.get("type"):
            part["type"] = fallback_type
        native_time = part.get("time") if isinstance(part.get("time"), Mapping) else {}
        part["time"] = _part_time(part, time_map)
        if part.get("type") == "tool":
            if native_time.get("ran") is not None:
                part["time"]["start"] = native_time["ran"]
            if part.get("tool") in (None, "") and part.get("name") not in (None, ""):
                part["tool"] = str(part["name"])
            state = dict(part.get("state")) if isinstance(part.get("state"), Mapping) else {}
            state_time = dict(state.get("time")) if isinstance(state.get("time"), Mapping) else {}
            created = native_time.get("ran", native_time.get("created", part["time"].get("start")))
            completed = native_time.get("completed", part["time"].get("end"))
            if created is not None:
                state_time.setdefault("start", created)
            if completed is not None:
                state_time.setdefault("end", completed)
            if state_time:
                state["time"] = state_time
            part["state"] = state
        parts.append(part)

    if message_type == "user":
        text = value.get("text")
        if isinstance(text, str) and text:
            append_part({"type": "text", "text": text})
        files = value.get("files")
        if isinstance(files, list):
            for raw_file in files:
                if not isinstance(raw_file, Mapping):
                    continue
                file_part = dict(raw_file)
                file_part["type"] = "file"
                if file_part.get("filename") in (None, ""):
                    filename = file_part.get("name") or file_part.get("uri")
                    if filename not in (None, ""):
                        file_part["filename"] = str(filename)
                append_part(file_part)
    elif message_type == "synthetic":
        append_part({"type": "text", "text": str(value.get("text", "")), "synthetic": True})
    elif message_type == "compaction":
        compact_part = {
            "type": "compaction",
            "auto": str(value.get("reason", "")).lower() == "auto",
            "reason": value.get("reason"),
            "status": value.get("status"),
            "summary": value.get("summary"),
            "recent": value.get("recent"),
            "model": deepcopy(value.get("model")),
            "providerContext": deepcopy(value.get("providerContext")),
        }
        for key in ("tokens", "cost", "error"):
            if key in value:
                compact_part[key] = deepcopy(value[key])
        append_part(compact_part)
    elif message_type == "assistant":
        content = value.get("content")
        if not isinstance(content, list):
            raise SourceDataError("OpenCode V2 assistant message content is not an array")
        for item in content:
            if not isinstance(item, Mapping):
                raise SourceDataError("OpenCode V2 assistant content contains an invalid item")
            append_part(item)
    elif message_type == "system":
        append_part({"type": "text", "text": str(value.get("text", "")), "system": True})
    elif message_type == "shell":
        append_part({
            "type": "tool",
            "name": "shell",
            "callID": value.get("callID"),
            "command": value.get("command"),
            "output": value.get("output"),
        })
    elif message_type in {"agent-switched", "model-switched"}:
        append_part({"type": message_type, **{k: deepcopy(v) for k, v in value.items() if k not in {"id", "time", "metadata", "type"}}})
    else:
        raise SourceDataError(f"OpenCode V2 current message type is unsupported: {message_type}")

    return {
        "info": info,
        "parts": parts,
        "_cost_guard_wire": {"shape": "current-v2-union", "ordinal": ordinal, "type": message_type},
    }


def interim_flat_message_to_legacy_bundle(
    value: Mapping[str, Any], *, session: Mapping[str, Any], ordinal: int
) -> dict[str, Any]:
    """Compatibility for an earlier experimental role/parts V2 wire shape."""
    message_id = value.get("id")
    role = value.get("role")
    raw_parts = value.get("parts")
    metadata = value.get("metadata")
    if not isinstance(message_id, str) or not isinstance(role, str) or not isinstance(raw_parts, list):
        raise SourceDataError("OpenCode V2 experimental flat message payload is invalid")
    meta = metadata if isinstance(metadata, Mapping) else {}
    session_id = meta.get("sessionID") or session.get("id")
    if not isinstance(session_id, str):
        raise SourceDataError("OpenCode V2 experimental message has no session identity")
    time_value = meta.get("time")
    time_map = dict(time_value) if isinstance(time_value, Mapping) else {}

    info: dict[str, Any] = {"id": message_id, "sessionID": session_id, "role": role, "time": time_map}
    error = meta.get("error")
    if error is not None:
        info["error"] = deepcopy(error)
    assistant = meta.get("assistant")
    if isinstance(assistant, Mapping):
        for source, target in (("providerID", "providerID"), ("modelID", "modelID"), ("cost", "cost"), ("tokens", "tokens"), ("summary", "summary")):
            if source in assistant:
                info[target] = deepcopy(assistant[source])
        if isinstance(assistant.get("variant"), str) and assistant["variant"].strip():
            info["variant"] = assistant["variant"]
    agent = session.get("agent")
    if agent not in (None, ""):
        info["agent"] = str(agent)

    parts: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_parts):
        if not isinstance(raw, Mapping):
            raise SourceDataError("OpenCode V2 experimental message contains an invalid part")
        part = deepcopy(dict(raw))
        part.setdefault("id", _synthetic_part_id(message_id, index))
        part.setdefault("messageID", message_id)
        part.setdefault("sessionID", session_id)
        part["time"] = _part_time(part, time_map)
        parts.append(part)

    return {
        "info": info,
        "parts": parts,
        "_cost_guard_wire": {"shape": "experimental-role-parts", "ordinal": ordinal},
    }

def normalize_message_items(
    items: Sequence[Mapping[str, Any]], *, session: Mapping[str, Any]
) -> tuple[list[Mapping[str, Any]], str]:
    if not items:
        return [], "empty"
    shapes: set[str] = set()
    bundles: list[Mapping[str, Any]] = []
    for ordinal, item in enumerate(items):
        if is_lifecycle_status_item(item):
            shapes.add("lifecycle-ignored")
            continue
        if item.get("type") == "location-switched":
            # Current V2 emits worktree/location bookkeeping among messages.
            # It has no prompt, invocation or context content; do not ingest
            # its filesystem paths into the canonical history (its context-epoch
            # boundary is extracted separately by location_boundaries). Fail closed if
            # a later wire generation gives this type billable content.
            if any(key in item for key in ("cost", "tokens", "content")):
                raise SourceDataError("OpenCode V2 location switch contains unsupported usage")
            shapes.add("location-ignored")
            continue
        if is_legacy_message_bundle(item):
            shapes.add("legacy-with-parts")
            bundles.append(item)
        elif isinstance(item.get("type"), str):
            shapes.add("current-v2-union")
            bundles.append(current_union_message_to_legacy_bundle(item, session=session, ordinal=ordinal))
        elif isinstance(item.get("role"), str) and isinstance(item.get("parts"), list):
            shapes.add("experimental-role-parts")
            bundles.append(interim_flat_message_to_legacy_bundle(item, session=session, ordinal=ordinal))
        else:
            raise SourceDataError("OpenCode V2 message item has an unsupported wire shape")
    return bundles, "+".join(sorted(shapes))


def location_boundaries(items: Sequence[Mapping[str, Any]], *, session_id: str) -> tuple[ContextBoundary, ...]:
    """Location switches start a new context epoch for the same session.

    Only identity and time are kept; paths never enter canonical data. A switch
    without a usable timestamp cannot be ordered and is ignored.
    """
    result: list[ContextBoundary] = []
    for item in items:
        if item.get("type") != "location-switched" or not isinstance(item.get("id"), str) or not item["id"]:
            continue
        raw_time = item.get("time")
        at = raw_time.get("created") if isinstance(raw_time, Mapping) else None
        if isinstance(at, bool) or not isinstance(at, (int, float)) or not math.isfinite(at) or at <= 0:
            continue
        result.append(ContextBoundary(session_id, item["id"], int(at)))
    return tuple(sorted(result, key=lambda value: (value.at_ms, value.boundary_id)))


def normalize_terminal_lifecycle(
    items: Sequence[Mapping[str, Any]], messages: Sequence[NormalizedMessage], *, session_id: str
) -> tuple[NormalizedMessage, ...]:
    """Bind persisted idle outcomes to the preceding assistant attempt only.

    User/synthetic/compaction boundaries prevent cross-run attribution. Later
    assistant or tool work wins over old terminal evidence. Never manufacture
    inference completion, errors or usage from session inactivity/status hints.
    """
    outcomes = {"succeeded": TerminalOutcome.SUCCESS, "failed": TerminalOutcome.FAILURE,
                "interrupted": TerminalOutcome.CANCELLATION}
    result = list(messages)
    ordered = sorted((message.created_at_ms, index) for index, message in enumerate(messages)
                     if message.session_id == session_id)
    times = [at for at, _index in ordered]
    for item in items:
        outcome = item.get("outcome")
        if item.get("type") != "idle" or not isinstance(outcome, str) or outcome not in outcomes:
            continue
        if not isinstance(item.get("id"), str) or not item["id"]:
            continue
        if item.get("sessionID", session_id) != session_id:
            continue
        raw_time = item.get("time")
        at = raw_time.get("created") if isinstance(raw_time, Mapping) else None
        if isinstance(at, bool) or not isinstance(at, (int, float)) or not math.isfinite(at) or at <= 0:
            continue
        # An equal/coarsened timestamp is ambiguous, not proof of ordering.
        position = bisect_left(times, at)
        if not position or (position < len(times) and times[position] == at):
            continue
        if position > 1 and times[position - 1] == times[position - 2]:
            continue
        index = ordered[position - 1][1]
        message = result[index]
        if message.role is not MessageRole.ASSISTANT:
            continue
        activity = [message.completed_at_ms or message.created_at_ms]
        for part in message.parts:
            activity.extend((part.created_at_ms, part.updated_at_ms))
            state = part.data.get("state")
            part_times = state.get("time") if isinstance(state, Mapping) else None
            if isinstance(part_times, Mapping):
                activity.extend(value for key in ("start", "end")
                                if isinstance(value := part_times.get(key), (int, float)))
        if max(activity) > at or (message.termination and message.termination.completed_at_ms >= at):
            continue
        result[index] = replace(message, termination=TerminalEvidence(int(at), outcomes[outcome]))
    return tuple(result)
