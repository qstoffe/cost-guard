"""Scope relevance and wording for V1→V2 migration-gap report notes.

Session selection owns gap discovery and normalized activity windows; this
module decides whether that evidence intersects a report's actual data scope.
Watch never consumes it, and Diagnostics reads the full diagnostic directly.
"""
from __future__ import annotations

from src.sources.selection import MISSING_IN_V2, MigrationGapDiagnostic


def migration_gap_notes(
    gap: MigrationGapDiagnostic | None,
    *,
    start_ms: int | None = None,
    end_ms: int | None = None,
    root_id: str | None = None,
) -> tuple[str, ...]:
    """Return an informational note only when the gap can affect this scope.

    No bounds means an all-history scope. ``start_ms`` is a bounded sample's
    effective cutoff or a date range start; ``end_ms`` is an exclusive date end;
    ``root_id`` restricts relevance to one requested causal root.
    """
    if gap is None or not gap.has_gap:
        return ()
    if start_ms is None and end_ms is None and root_id is None:
        missing, newer = len(gap.missing_in_v2), len(gap.newer_in_v1)
    else:
        relevant = [
            item for item in gap.sessions
            if item.overlaps(start_ms or 0, end_ms)
            and (root_id is None or root_id in {item.root_session_id, item.session_id})
        ]
        missing = sum(item.kind == MISSING_IN_V2 for item in relevant)
        newer = len(relevant) - missing
    pieces: list[str] = []
    if missing:
        pieces.append(f"{missing} missing from V2")
    if newer:
        pieces.append(f"{newer} newer than their V2 copy")
    if not pieces:
        return ()
    return (
        "OpenCode V1 has session(s) relevant to this report that V2 may not contain ("
        + ", ".join(pieces)
        + "); sources are not merged. Set openCode.source to v1 to inspect legacy history.",
    )
