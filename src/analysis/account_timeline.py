"""Absolute, half-open timeline buckets with local calendar boundaries."""
from datetime import datetime, time, timedelta, timezone

from .timezones import local_day_start_ms, local_month_start_ms, resolve_timezone


PERIODS = ('today', '7-days', '30-days', 'month', 'all')
DAY_MS = 86_400_000


def period_start(period, now_ms, zone, earliest_ms=None):
    if period == 'today':
        return local_day_start_ms(zone, now_ms=now_ms)
    if period == 'month':
        return local_month_start_ms(zone, now_ms=now_ms)
    if period in ('7-days', '30-days'):
        return now_ms - int(period.split('-')[0]) * DAY_MS
    if period == 'all':
        return earliest_ms
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


def timeline_buckets(period, now_ms, timezone_id, *, earliest_ms=None):
    start = period_start(period, now_ms, timezone_id, earliest_ms)
    if start is None or start >= now_ms:
        return start, ()
    zone = resolve_timezone(timezone_id)
    first_day = _local(start, zone).date()
    if period == 'today':
        boundaries = _hours(first_day, zone)
    else:
        last_day = _local(now_ms, zone).date()
        days = (last_day - first_day).days
        monthly = period == 'all' and days > 182
        weekly = period == 'all' and days > 62 and not monthly
        day = (first_day.replace(day=1) if monthly else
               first_day - timedelta(days=first_day.weekday()) if weekly else first_day)
        boundaries = set()
        while day <= last_day:
            boundaries.add(_stamp(datetime.combine(day, time(), zone)))
            if monthly:
                day = day.replace(year=day.year + 1, month=1) if day.month == 12 else day.replace(month=day.month + 1)
            else:
                day += timedelta(days=7 if weekly else 1)
    edges = [start, *sorted(ms for ms in boundaries if start < ms < now_ms), now_ms]
    return start, tuple(zip(edges, edges[1:]))
