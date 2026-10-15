"""Presentation-only Watch retention: global prompt selection and startup Earlier sessions.

Sessions have no independent lifetime. A session block is visible exactly while
one of its prompt rows is selected; protected (running or still-highlighted)
rows always survive and the newest unprotected rows fill the remaining global
capacity. Startup Earlier sessions are a one-time baseline chosen from actual
prompt start times, never from catalog metadata, polling or quota refreshes.
"""
from __future__ import annotations

from typing import Callable, Hashable, Iterable, Mapping, Sequence, TypeVar

Row = TypeVar("Row")


def select_rows(
    rows: Sequence[Row], *, max_rows: int, is_protected: Callable[[Row], bool], sort_key: Callable[[Row], Hashable],
) -> list[Row]:
    """Keep every protected row, then the newest unprotected rows up to the soft cap."""
    ordered = sorted(rows, key=sort_key)
    protected = [row for row in ordered if is_protected(row)]
    ordinary = [row for row in ordered if not is_protected(row)]
    room = max(0, max_rows - len(protected))
    return sorted(protected + (ordinary[-room:] if room else []), key=sort_key)


def select_earlier_sessions(latest_prompt_ms: Mapping[str, int], count: int) -> tuple[str, ...]:
    """The ``count`` sessions with the newest completed pre-Watch prompt start.

    Ties use the stable session ID; sessions without any prompt never qualify.
    """
    ranked = sorted(((at_ms, session_id) for session_id, at_ms in latest_prompt_ms.items() if at_ms > 0), reverse=True)
    return tuple(session_id for _at_ms, session_id in ranked[:max(0, int(count))])


def session_order(session_times: Iterable[tuple[str, int]], *, active_sessions: set[str]) -> list[str]:
    """History first, active/recent last; chronological within each, with ID ties."""
    return [session_id for session_id, _at_ms in sorted(
        session_times, key=lambda item: (item[0] in active_sessions, item[1], item[0]))]
