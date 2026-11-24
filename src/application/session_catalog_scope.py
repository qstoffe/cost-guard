"""Cheap catalog membership and immutable server-issued period windows."""
from bisect import bisect_left
from collections import OrderedDict
from dataclasses import dataclass, field

from src.analysis.timezones import calendar_periods

PERIODS = ("today", "7-days", "30-days", "month", "all")
PAGE_SIZE = 25


def retain_live_arrivals(live, roots, previous, added, since_ms, now_ms):
    # Unlike display grace, acquisition ownership lasts for the source epoch.
    # Roots first discovered late with old creation timestamps are history.
    retained = {key for key in live if key in roots and roots[key].provenance == previous[key].provenance}
    if since_ms is not None:
        retained.update(key for key in added if since_ms <= roots[key].created_at_ms <= now_ms)
    return retained


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
    browsable_candidates: bool = False
    arrivals: frozenset = frozenset()
    served: OrderedDict = field(default_factory=OrderedDict, compare=False, repr=False)

    def remember_page(self, offset):
        self.served[offset] = None
        self.served.move_to_end(offset)
        if len(self.served) > 32:
            self.served.popitem(last=False)


def catalog_window(period, timezone_id, now_ms):
    if period not in PERIODS:
        raise ValueError("invalid_request")
    return CatalogWindow(period, timezone_id, dict(calendar_periods(timezone_id, now_ms))[period], now_ms + 1)


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


def event_members(candidates, window, rows, activity_current, recent_finishes):
    """Partial/retained evidence cannot establish a current-revision exclusion."""
    return tuple(key for key in candidates if window.period == 'all'
                  or not activity_current(key) or row_in_window(rows[key], window, recent_finishes.get(key)))


def row_in_window(row, window, recently_finished=None):
    # A currently executing, source-qualified prompt spans midnight. Its fixed
    # display start need not be in today's window; ancient finished work does.
    return (in_window(row.activity_latest_ms, window) or in_window(row.last_activity_ms, window)
        or in_window(recently_finished, window) or bool(row.running
        and type(row.prompt_started_ms) is int and 0 < row.prompt_started_ms < window.end_ms))


def activity_time(row):
    return row.last_activity_ms if row.last_activity_ms is not None else row.prompt_started_ms


def provisional_order(rows, metadata):
    """Unknown clocks have discovery hints only, never displayed event times."""
    live = tuple(row for row in rows if row.running)
    unknown = sorted((row for row in rows if not row.running and activity_time(row) is None),
        key=lambda row: (-(metadata.get(row.session_id) or 0), row.session_id))
    return live + tuple(unknown) + tuple(row for row in rows if not row.running and activity_time(row) is not None)


def live_activity_order(rows, metadata, activity_current):
    """Merge current event clocks with explicitly preliminary catalog clocks."""
    running = tuple(row for row in rows if row.running)
    def rank(row):
        at = activity_time(row) if activity_current(row.session_id) else metadata.get(row.session_id)
        return -(at or 0), row.session_id
    return running + tuple(sorted((row for row in rows if not row.running), key=rank))


def retained_positions(rows, positions, display):
    """Old issued positions are display-only while their current keys are pending."""
    live = tuple(row for row in rows if row.running)
    ordinary = [row for row in rows if not row.running]
    for key, position in positions.items():
        ordinary.insert(min(position, len(ordinary)), display[key])
    return live + tuple(ordinary)
