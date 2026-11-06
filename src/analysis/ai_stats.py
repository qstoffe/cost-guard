"""Ten coherent historical statistics over canonical usage and execution evidence."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from .active_hour import HOUR_MS, USAGE_FIELDS, deduplicated_requests
from .timezones import local_day_start_ms, local_month_start_ms, resolve_timezone
from .valuation import comparison_cost

DAY_MS = 24 * HOUR_MS


@dataclass(frozen=True, slots=True)
class StatsRoot:
    session_id: str
    title: str
    entries: tuple
    # (start, duration, provisional); intervals already include attributable children.
    intervals: tuple
    cost_pending: bool = False


@dataclass(frozen=True, slots=True)
class Stat:
    metric: str
    value: Decimal | int | str | None
    status: str = 'complete'
    session_id: str | None = None
    session_title: str = ''
    detail: str = ''


@dataclass(frozen=True, slots=True)
class StatsPeriod:
    period: str
    start_ms: int | None
    end_ms: int
    metrics: tuple[Stat, ...]


def windows(zone, now):
    return (('today', local_day_start_ms(zone, now_ms=now)), ('7-days', now - 7 * DAY_MS),
            ('30-days', now - 30 * DAY_MS), ('month', local_month_start_ms(zone, now_ms=now)),
            ('all', None))


def union(intervals):
    """Half-open boundaries: touching sessions never inflate peak concurrency."""
    result = []
    for left, right in sorted(intervals):
        if result and left <= result[-1][1]:
            result[-1] = result[-1][0], max(right, result[-1][1])
        elif right > left:
            result.append((left, right))
    return result


def calendar_activity(intervals, zone):
    """Split unioned UTC intervals at local midnight, 06:00 and 22:00, including DST."""
    tz = resolve_timezone(zone)
    days, night = {}, 0
    for left, right in intervals:
        day = datetime.fromtimestamp(left / 1000, timezone.utc).astimezone(tz).date()
        while True:
            next_day = day + timedelta(days=1)
            bounds = [int(datetime(day.year, day.month, day.day, hour, tzinfo=tz).timestamp() * 1000)
                      for hour in (0, 6, 22)]
            bounds.append(int(datetime(next_day.year, next_day.month, next_day.day, tzinfo=tz).timestamp() * 1000))
            for index, (start, end) in enumerate(zip(bounds, bounds[1:])):
                amount = max(0, min(right, end) - max(left, start))
                if amount:
                    days[day] = days.get(day, 0) + amount
                    if index != 1:
                        night += amount
            if bounds[-1] >= right:
                break
            day = next_day
    return days, night


def _timing(roots, start, now):
    per_root, unknown, provisional = {}, False, False
    for root in roots:
        clipped = []
        for left, duration, running in root.intervals:
            if left >= now:
                continue
            if left <= 0 or duration is None or duration < 0:
                unknown = True  # An unknown end cannot prove non-overlap.
                continue
            right = min(now, left + duration)
            left = max(start or 1, left)
            if right > left:
                clipped.append((left, right))
                provisional |= running
        per_root[root.session_id] = union(clipped)
    return per_root, unknown, provisional


def _time_metrics(roots, per_root, unknown, provisional, zone):
    merged = union(pair for pairs in per_root.values() for pair in pairs)
    duration = None if unknown else sum(right - left for left, right in merged)
    status = 'unavailable' if unknown else 'provisional' if provisional else 'complete'
    days, night = calendar_activity(merged, zone)
    streak = longest = 0
    previous = None
    for day in sorted(days):
        streak = streak + 1 if previous is not None and (day - previous).days == 1 else 1
        longest = max(longest, streak)
        previous = day
    events = sorted((point, delta) for pairs in per_root.values() for left, right in pairs
                    for point, delta in ((left, 1), (right, -1)))
    active = peak = 0
    for _point, delta in events:
        active += delta
        peak = max(peak, active)
    ranked = sorted(roots, key=lambda root: (-sum(b - a for a, b in per_root[root.session_id]), root.session_id))
    record = ranked[0] if ranked and per_root[ranked[0].session_id] and not unknown else None
    busy = min(days, key=lambda day: (-days[day], day)) if days and not unknown else None
    metrics = (Stat('working-time', duration, status),
        Stat('longest-session', sum(b - a for a, b in per_root[record.session_id]) if record else None,
             status if record else 'unavailable', record.session_id if record else None, record.title if record else ''),
        Stat('busiest-day', days[busy] if busy else None, status if busy else 'unavailable', detail=str(busy or '')),
        Stat('night-owl', Decimal(night) * 100 / duration if duration else None, status if duration else 'unavailable'),
        Stat('streak', None if unknown else longest, status),
        Stat('parallel', None if unknown else peak, status))
    return duration, status, metrics


def period_stats(roots, valuation, *, period, start, now, zone, source_complete=True):
    """Cost uses event time, never proportional allocation or displayed amounts."""
    owner = {entry.session_id: root for root in roots for entry in root.entries}
    entries = tuple(entry for entry in deduplicated_requests(e for root in roots for e in root.entries)
                    if (start is None or entry.completed_at_ms >= start) and entry.completed_at_ms <= now)
    total = comparison_cost(entries, valuation)
    complete = source_complete and total.complete and all(USAGE_FIELDS <= set(e.tokens.known_fields) for e in entries)
    complete &= not any(root.cost_pending for root in roots)
    groups = {}
    for entry in entries:
        groups.setdefault(owner[entry.session_id].session_id, []).append(entry)
    costs = {sid: comparison_cost(group, valuation).known_ccost for sid, group in groups.items()}
    per_root, unknown, provisional = _timing(roots, start, now)
    duration, time_status, timed = _time_metrics(roots, per_root, unknown or not source_complete, provisional, zone)
    cost_status = 'complete' if complete else 'partial'
    rate = total.known_ccost * HOUR_MS / duration if complete and duration else None
    average = total.known_ccost / len(groups) if complete and groups else None
    expensive = min(costs, key=lambda sid: (-costs[sid], sid)) if costs and complete else None
    root = next((root for root in roots if root.session_id == expensive), None)
    values = (Stat('hourly-rate', rate, time_status if rate is not None else 'unavailable'),
        Stat('total-cost', total.known_ccost, cost_status), timed[0],
        Stat('average-cost', average, cost_status if average is not None else 'unavailable'),
        Stat('expensive-session', costs[expensive] if root else None, cost_status if root else 'unavailable',
             root.session_id if root else None, root.title if root else ''), *timed[1:])
    return StatsPeriod(period, start, now, values)
