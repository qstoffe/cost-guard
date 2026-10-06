"""Request-attributable effort semantics, independent of model families/UI."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.domain import MessageRole, SessionSnapshot

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


def prompt_effort(record: PromptRecord, snapshot: SessionSnapshot) -> EffortSelection:
    """Use only the same root prompt/model, never child/previous/summary work."""
    levels = tuple(
        message.variant for message in snapshot.messages
        if message.session_id == record.session_id
        and message.parent_message_id == record.prompt_id
        and message.role is MessageRole.ASSISTANT and not message.summary
        and message.model is not None
        and message.model.model == record.main_model_id
        and message.model.provider == record.main_provider_id
    )
    return interpret_effort(
        record.main_variant, request_levels=levels,
        attributable=bool(record.main_model_id),
    )
