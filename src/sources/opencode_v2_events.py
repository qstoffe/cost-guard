"""Prompt/event normalization for canonical OpenCode V2 user-role messages.

Visible user parts become prompts or subtasks; synthetic task summaries become
continuations and background-job completion notices resume the current prompt.
"""
from __future__ import annotations

import re
from typing import Mapping, Sequence

from src.domain import EventKind, MessageRole, NormalizedEvent, NormalizedMessage, NormalizedPart

_SYNTHETIC_CONTINUATION = re.compile(
    r"^\s*Summarize the task tool output above and continue with your task\.?\s*$",
    flags=re.IGNORECASE,
)
_VISIBLE_USER_PARTS = frozenset({"text", "file", "subtask"})


def _event_text(parts: Sequence[NormalizedPart]) -> str:
    values: list[str] = []
    for part in parts:
        data = part.data
        if part.kind not in _VISIBLE_USER_PARTS or bool(data.get("synthetic", False)):
            continue
        if part.kind == "text":
            text = str(data.get("text", "")).strip()
            if text:
                values.append(text)
        elif part.kind == "file":
            filename = str(data.get("filename", "")).strip()
            if filename:
                values.append(f"[file: {filename}]")
        elif part.kind == "subtask":
            command = str(data.get("command", "")).strip()
            description = str(data.get("description", "")).strip()
            prompt = str(data.get("prompt", "")).strip()
            prefix = f"/{command}" if command else "[subtask]"
            if description:
                values.append(f"{prefix} - {description}")
            elif prompt:
                preview = " ".join(prompt.split())[:240]
                values.append(f"{prefix} - {preview}")
            else:
                values.append(prefix)
    return " ".join(" ".join(values).replace("\t", " ").split())


def _event_kind(parts: Sequence[NormalizedPart]) -> EventKind:
    if any(part.kind == "compaction" for part in parts):
        return EventKind.COMPACTION
    visible = [
        part for part in parts
        if part.kind in _VISIBLE_USER_PARTS and not bool(part.data.get("synthetic", False))
    ]
    if any(part.kind == "subtask" for part in visible):
        return EventKind.SUBTASK
    if visible:
        return EventKind.USER_PROMPT
    for part in parts:
        if part.kind == "text" and bool(part.data.get("synthetic", False)):
            if _SYNTHETIC_CONTINUATION.match(str(part.data.get("text", ""))):
                return EventKind.SYNTHETIC_CONTINUATION
    return EventKind.OTHER


def _event_metadata(message: NormalizedMessage) -> dict[str, str]:
    metadata: dict[str, str] = {}
    if message.model:
        metadata["provider_id"] = message.model.provider
        metadata["model_id"] = message.model.model
    if message.variant:
        metadata["variant"] = message.variant
    if message.agent:
        metadata["agent"] = message.agent
    for part in message.parts:
        if part.kind == "subtask":
            model = part.data.get("model")
            if isinstance(model, Mapping):
                for source_key, target_key in (("providerID", "provider_id"), ("modelID", "model_id"), ("variant", "variant")):
                    value = str(model.get(source_key, "")).strip()
                    if value:
                        metadata[target_key] = value
        elif part.kind == "compaction":
            metadata["auto"] = "true" if bool(part.data.get("auto", False)) else "false"
            model = part.data.get("model")
            if isinstance(model, Mapping):
                provider = model.get("providerID")
                model_id = model.get("id", model.get("modelID"))
                if provider not in (None, ""):
                    metadata["provider_id"] = str(provider)
                if model_id not in (None, ""):
                    metadata["model_id"] = str(model_id)
                variant = model.get("variant")
                if isinstance(variant, str) and variant.strip():
                    metadata["variant"] = variant
            tail = part.data.get("tail_start_id", part.data.get("tailStartId"))
            if tail:
                metadata["tail_start_id"] = str(tail)
    return metadata


def normalize_event(message: NormalizedMessage, background_notices: frozenset[str] = frozenset()) -> NormalizedEvent | None:
    if message.role is not MessageRole.USER:
        return None
    return NormalizedEvent(
        event_id=message.message_id,
        session_id=message.session_id,
        kind=(EventKind.BACKGROUND_COMPLETION if message.message_id in background_notices
              else _event_kind(message.parts)),
        created_at_ms=message.created_at_ms,
        provenance=message.provenance,
        text=_event_text(message.parts) or None,
        metadata=_event_metadata(message),
    )
