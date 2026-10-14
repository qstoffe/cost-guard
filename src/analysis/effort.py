"""Request-attributable effort semantics, independent of model families/UI."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from src.domain import MessageRole, NormalizedMessage, SessionSnapshot

from .models import PromptRecord


class EffortKind(str, Enum):
    EXPLICIT = "explicit"
    RESOLVED_DEFAULT = "resolved_default"
    DEFAULT = "unresolved_default"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class EffortSelection:
    kind: EffortKind
    level: str | None = None


def interpret_effort(
    selected: str | None, *, request_levels: tuple[str | None, ...] = (),
    attributable: bool = True, compaction: bool = False,
) -> EffortSelection:
    """Only request-bound concrete variants may resolve a normal Default.

    Absent variants on a known normal model request mean OpenCode Default.
    Missing/conflicting request evidence stays unresolved. Compaction never
    consumes surrounding selection or a resolved normal default.
    """
    value = (selected or "").strip()
    if not attributable:
        return EffortSelection(EffortKind.NONE)
    if value and value.lower() != "default":
        return EffortSelection(EffortKind.EXPLICIT, value)
    if compaction:
        return EffortSelection(EffortKind.NONE)
    levels = {(level or "").strip().lower() for level in request_levels}
    if len(levels) == 1 and not levels.intersection({"", "default"}):
        return EffortSelection(EffortKind.RESOLVED_DEFAULT, next(iter(levels)))
    return EffortSelection(EffortKind.DEFAULT, "Default")


PromptReplies = Mapping[tuple[str, str | None], tuple[NormalizedMessage, ...]]


def prompt_replies(snapshot: SessionSnapshot) -> PromptReplies:
    """Index non-summary model replies by (session, parent prompt) once per snapshot."""
    replies: dict[tuple[str, str | None], list[NormalizedMessage]] = {}
    for message in snapshot.messages:
        if message.role is MessageRole.ASSISTANT and not message.summary and message.model is not None:
            replies.setdefault((message.session_id, message.parent_message_id), []).append(message)
    return {key: tuple(values) for key, values in replies.items()}


def prompt_effort(record: PromptRecord, snapshot: SessionSnapshot, *,
                  replies: PromptReplies | None = None) -> EffortSelection:
    """Use only the same root prompt/model, never child/previous/summary work.

    Pass one shared ``prompt_replies`` index when projecting many prompts.
    """
    replies = prompt_replies(snapshot) if replies is None else replies
    levels = tuple(
        message.variant for message in replies.get((record.session_id, record.prompt_id), ())
        if message.model.model == record.main_model_id
        and message.model.provider == record.main_provider_id
    )
    return interpret_effort(
        record.main_variant, request_levels=levels,
        attributable=bool(record.main_model_id),
    )
