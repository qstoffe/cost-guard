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
        # Calendar windows can reuse an unchanged membership/order within the
        # same day/month. Rolling windows issue a new, exact cutoff snapshot.
        return self.period, self.timezone_id, self.start_ms


@dataclass(frozen=True, slots=True)
class CatalogEpoch:
    rows: tuple
    sort: str
    direction: int
    window: CatalogWindow


def catalog_window(period, timezone_id, now_ms):
    if period not in PERIODS:
        raise ValueError("invalid_request")
    return CatalogWindow(period, timezone_id, dict(windows(timezone_id, now_ms))[period], now_ms + 1)


def population(roots, activity_index, window):
    if window.period == "all":
        return tuple(roots)
    left = bisect_left(activity_index, (max(1, window.start_ms),))
    right = bisect_left(activity_index, (window.end_ms,))
    return tuple(key for _, key in activity_index[left:right])
