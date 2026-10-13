"""Presentation-only Watch session visibility: idle expiry and recent-session protection.

Visibility is derived on every projection from prompt lifecycle evidence alone,
so it needs no per-session timer state, survives Watch restarts/reconnections
and never treats polling, quota refreshes or title changes as activity.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from src.domain import NormalizedSession

SESSION_IDLE_EXPIRY_MS = 10 * 60 * 1000
PROTECTED_RECENT_SESSIONS = 2


@dataclass(frozen=True, slots=True)
class SessionActivity:
    """Prompt lifecycle evidence of one Watch session."""
    session_id: str
    running: bool
    last_prompt_activity_ms: int


@dataclass(frozen=True, slots=True)
class SessionVisibility:
    visible: frozenset[str]
    # Running or most recently prompt-active: the row cap keeps at least one row.
    represented: frozenset[str]


def startup_visible_roots(
    roots: Sequence[NormalizedSession], activity: Mapping[str, int], now_ms: int,
) -> set[str]:
    """Roots that may still be visible at Watch startup, from catalog metadata only.

    ``roots`` is ordered most recently active first. The leading roots are
    protected; others qualify only inside the idle expiry. Hydrated prompt
    timestamps then decide visibility, so a restart grants no fresh period.
    """
    keep = {root.session_id for root in roots[:PROTECTED_RECENT_SESSIONS]}
    keep.update(root.session_id for root in roots
                if now_ms - activity.get(root.session_id, root.updated_at_ms) < SESSION_IDLE_EXPIRY_MS)
    return keep


def _recency(activity: SessionActivity, now_ms: int) -> tuple[int, str]:
    return (now_ms if activity.running else activity.last_prompt_activity_ms, activity.session_id)


def session_visibility(activities: Iterable[SessionActivity], now_ms: int) -> SessionVisibility:
    """Hide idle sessions after the expiry unless running or among the most recent.

    Expiry applies exactly at the boundary. A session displaced from the most
    recent set immediately uses its existing idle age; no new grace period starts.
    """
    items = tuple(activities)
    ranked = sorted(items, key=lambda item: _recency(item, now_ms), reverse=True)
    represented = {item.session_id for item in ranked[:PROTECTED_RECENT_SESSIONS]}
    represented.update(item.session_id for item in items if item.running)
    idle_visible = {
        item.session_id for item in items
        if now_ms - item.last_prompt_activity_ms < SESSION_IDLE_EXPIRY_MS
    }
    return SessionVisibility(frozenset(represented | idle_visible), frozenset(represented))
