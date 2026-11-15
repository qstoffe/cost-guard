"""Cheap catalog membership and immutable server-issued period windows."""
from bisect import bisect_left
from dataclasses import dataclass

from src.analysis.ai_stats import windows

PERIODS = ("today", "7-days", "30-days", "month", "all")
PAGE_SIZE = 25


@dataclass(frozen=True, slots=True)
class CatalogWindow:
    period: str
    timezone_id: str
    start_ms: int | None
    end_ms: int

    @property
    def identity(self):
        # Calendar cutoffs stay stable within the same configured-local date.
        return self.period, self.timezone_id, self.start_ms


@dataclass(frozen=True, slots=True)
class CatalogEpoch:
    rows: tuple
    sort: str
    direction: int
    window: CatalogWindow
    provisional: bool = False
    facts: tuple = ()


def catalog_window(period, timezone_id, now_ms):
    if period not in PERIODS:
        raise ValueError("invalid_request")
    return CatalogWindow(period, timezone_id, dict(windows(timezone_id, now_ms))[period], now_ms + 1)


def population(roots, activity_index, window):
    """Metadata admits candidates, not final prompt-based day membership.

    Do not exclude a valid prompt because a source's modification clock is in
    the future. Actual event timestamps are checked against both window bounds.
    """
    if window.period == "all":
        return tuple(roots)
    left = bisect_left(activity_index, (max(1, window.start_ms),))
    return tuple(key for _, key in activity_index[left:])


def candidate_population(roots, metadata, metadata_index, rows, hints, window):
    candidates = population(roots, metadata_index, window)
    if window.period == 'all':
        return candidates
    extra = hints | {key for key, row in rows.items() if row.running
                     or in_window(row.activity_latest_ms or row.last_activity_ms, window)}
    extra.update(key for key in roots if not metadata.get(key))
    return tuple(dict.fromkeys((*candidates, *sorted(extra & roots.keys()))))


def in_window(at, window):
    return type(at) is int and max(1, window.start_ms or 1) <= at < window.end_ms


def event_members(candidates, window, rows, activity_current):
    """Partial/retained evidence cannot establish a current-revision exclusion."""
    return tuple(key for key in candidates if window.period == 'all'
                  or not activity_current(key) or row_in_window(rows[key], window))


def row_in_window(row, window):
    # A currently executing, source-qualified prompt spans midnight. Its fixed
    # display start need not be in today's window; ancient finished work does.
    return in_window(row.activity_latest_ms or row.last_activity_ms, window) or bool(row.running
        and type(row.prompt_started_ms) is int and 0 < row.prompt_started_ms < window.end_ms)


def provisional_order(rows, metadata):
    """Unknown clocks have discovery hints only, never displayed event times."""
    live = tuple(row for row in rows if row.running)
    unknown = sorted((row for row in rows if not row.running and row.last_activity_ms is None),
        key=lambda row: (-(metadata.get(row.session_id) or 0), row.session_id))
    return live + tuple(unknown) + tuple(row for row in rows if not row.running and row.last_activity_ms is not None)
