"""Absolute, half-open timeline buckets with local calendar boundaries."""
from datetime import datetime, time, timedelta, timezone

from .timezones import local_day_start_ms, local_month_start_ms, resolve_timezone


PERIODS = ('today', '7-days', '30-days', 'month')
DAY_MS = 86_400_000


def period_start(period, now_ms, zone):
    if period == 'today':
        return local_day_start_ms(zone, now_ms=now_ms)
    if period == 'month':
        return local_month_start_ms(zone, now_ms=now_ms)
    if period in ('7-days', '30-days'):
        return now_ms - int(period.split('-')[0]) * DAY_MS
    raise ValueError('invalid_timeline_period')


def _local(ms, zone):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).astimezone(zone)


def _stamp(value):
    return int(value.timestamp() * 1000)


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
    start = period_start(period, now_ms, timezone_id)
    if start >= now_ms:
        return start, (), ()
    zone = resolve_timezone(timezone_id)
    first_day = _local(start, zone).date()
    if period == 'today':
        boundaries = _hours(first_day, zone)
    else:
        last_day = _local(now_ms, zone).date()
        day = first_day
        boundaries = set()
        while day <= last_day:
            boundaries.add(_stamp(datetime.combine(day, time(), zone)))
            day += timedelta(days=1)
    edges = [start, *sorted(ms for ms in boundaries if start < ms < now_ms), now_ms]
    buckets = tuple(zip(edges, edges[1:]))
    partial = tuple(sorted({index for index, edge in ((0, start), (len(buckets) - 1, now_ms))
                            if edge not in boundaries}))
    return start, buckets, partial
