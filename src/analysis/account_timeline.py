"""Absolute, half-open timeline buckets with local calendar boundaries."""
from calendar import monthrange
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone

from .timezones import local_day_start_ms, local_month_start_ms, resolve_timezone


PERIODS = ('today', '7-days', '30-days', 'month')
DAY_MS = 86_400_000


@dataclass(frozen=True, slots=True)
class TimelineWindow:
    start: int
    buckets: tuple[tuple[int, int], ...]
    partial: tuple[int, ...]
    dates: tuple[str, ...] = ()
    future: tuple[int, ...] = ()


def period_start(period, now_ms, zone):
    if period == 'today':
        return local_day_start_ms(zone, now_ms=now_ms)
    if period == 'month':
        return local_month_start_ms(zone, now_ms=now_ms)
    if period == '7-days':
        return now_ms - 7 * DAY_MS
    if period == '30-days':
        return local_day_start_ms(zone, now_ms=now_ms, days_ago=29)
    raise ValueError('invalid_timeline_period')


def _local(ms, zone):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).astimezone(zone)


def _stamp(value):
    return int(value.timestamp() * 1000)


def _midnight(day, zone):
    return _stamp(datetime.combine(day, time(), zone))


def _calendar_window(period, now_ms, zone):
    today = _local(now_ms, zone).date()
    if period == 'month':
        first, count = today.replace(day=1), monthrange(today.year, today.month)[1]
    else:
        first, count = today - timedelta(days=29), 30
    days = tuple(first + timedelta(days=i) for i in range(count + 1))
    edges = tuple(_midnight(day, zone) for day in days)
    current = (today - first).days
    # Even exactly at midnight, the current date owns a (then empty) slot.
    buckets = tuple((left, now_ms if i == current else right)
                    for i, (left, right) in enumerate(zip(edges, edges[1:])))
    return TimelineWindow(edges[0], buckets, (current,), tuple(day.isoformat() for day in days[:-1]),
                          tuple(range(current + 1, count)))


def _hours(day, zone):
    # Round-trip each fold: nonexistent local clocks are not bucket boundaries.
    # Also split at non-hour offset transitions (e.g. Lord Howe's 30 minutes).
    boundaries = set()
    for hour in range(25):
        wall = datetime.combine(day, time()) + timedelta(hours=hour)
        candidates = [_stamp(wall.replace(tzinfo=zone, fold=fold)) for fold in (0, 1)]
        boundaries.update(ms for ms in candidates if _local(ms, zone).replace(tzinfo=None) == wall)
    edges = sorted(boundaries)
    for start, end in zip(edges, edges[1:]):
        offset = _local(start, zone).utcoffset()
        if offset == _local(end, zone).utcoffset():
            continue
        lo, hi = start, end
        while hi - lo > 1:
            middle = (hi + lo) // 2
            if _local(middle, zone).utcoffset() == offset:
                lo = middle
            else:
                hi = middle
        boundaries.add(hi)
    return boundaries


def timeline_window(period, now_ms, timezone_id):
    zone = resolve_timezone(timezone_id)
    if period in ('month', '30-days'):
        return _calendar_window(period, now_ms, zone)
    start = period_start(period, now_ms, timezone_id)
    first_day = _local(start, zone).date()
    if period == 'today':
        boundaries = _hours(first_day, zone)
    else:
        last_day = _local(now_ms, zone).date()
        day = first_day
        boundaries = set()
        while day <= last_day:
            boundaries.add(_midnight(day, zone))
            day += timedelta(days=1)
    edges = [start, *sorted(ms for ms in boundaries if start < ms < now_ms), now_ms]
    buckets = tuple(zip(edges, edges[1:]))
    partial = tuple(sorted({index for index, edge in ((0, start), (len(buckets) - 1, now_ms))
                            if edge not in boundaries}))
    if period == 'today' and now_ms in boundaries:
        buckets = (*buckets[:-1], (now_ms, now_ms)) if start == now_ms else (*buckets, (now_ms, now_ms))
        partial = (*partial, len(buckets) - 1)
    return TimelineWindow(start, buckets, partial)
