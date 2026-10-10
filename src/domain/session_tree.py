"""Canonical session catalog topology; metadata gates, never hydrated usage truth."""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from .models import NormalizedSession


def root_by_session(sessions: Sequence[NormalizedSession]) -> dict[str, str]:
    """Map known descendants to their highest known ancestor without recursion.

    Missing parents stop at the last known session; they never invent a root.
    Cycles terminate with the historical traversal/memoization behavior. Only
    parentless records qualify as report/Watch roots, regardless of this map.
    """
    by_id = {item.session_id: item for item in sessions}
    memo: dict[str, str] = {}
    for item in sessions:
        if item.session_id in memo:
            continue
        current = item
        trail: list[str] = []
        seen: set[str] = set()
        while current.parent_session_id and current.session_id not in seen:
            seen.add(current.session_id)
            trail.append(current.session_id)
            parent = by_id.get(current.parent_session_id)
            if parent is None:
                break
            current = parent
        resolved = current.session_id
        memo[resolved] = resolved
        for session_id in trail:
            memo[session_id] = resolved
    return memo


def root_activity(
    sessions: Sequence[NormalizedSession], mapping: Mapping[str, str] | None = None,
) -> dict[str, int]:
    """Newest creation/update/archive metadata across each known causal tree."""
    roots = root_by_session(sessions) if mapping is None else mapping
    activity: dict[str, int] = {}
    for item in sessions:
        resolved = roots.get(item.session_id, item.session_id)
        observed = max(item.created_at_ms, item.updated_at_ms, item.archived_at_ms or 0)
        activity[resolved] = max(activity.get(resolved, 0), observed)
    return activity


def root_for_session(sessions: Sequence[NormalizedSession], session_id: str) -> NormalizedSession | None:
    """Resolve a detail target; a missing requested ancestor stays unavailable.

    Unlike activity's best-effort mapping, an incomplete chain must not turn an
    orphan into a valid session-detail target. Cycles remain bounded as before.
    """
    by_id = {item.session_id: item for item in sessions}
    current = by_id.get(session_id)
    seen: set[str] = set()
    while current is not None and current.parent_session_id and current.session_id not in seen:
        seen.add(current.session_id)
        current = by_id.get(current.parent_session_id)
    return current
