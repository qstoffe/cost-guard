"""Watch-only origin lookup for skill calls in active, hydrated sessions."""
from __future__ import annotations

from collections.abc import Mapping

from src.domain import SessionSnapshot
from src.reports.models import SessionPromptBlock
from src.sources.base import SessionSource

from .tool_contracts import is_skill_tool, skill_tool_id


def active_skill_origins(
    source: SessionSource, snapshot: SessionSnapshot, block: SessionPromptBlock,
) -> dict[str, Mapping[str, str]]:
    """Resolve each skill-calling session once, and only while its prompt is live."""
    lookup = getattr(source, "skill_origins_for_session", None)
    if not callable(lookup) or not any(row.in_progress for row in block.rows):
        return {}
    origins: dict[str, Mapping[str, str]] = {}
    for part in snapshot.parts:
        if part.kind != "tool" or not is_skill_tool(part.data) or not skill_tool_id(part.data):
            continue
        if part.session_id not in origins:
            origins[part.session_id] = lookup(part.session_id)
    return origins
