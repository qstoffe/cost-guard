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
    source_complete: bool = True


@dataclass(frozen=True, slots=True)
class Stat:
    metric: str
    value: Decimal | int | str | None
    status: str = 'complete'
    session_id: str | None = None
    session_title: str = ''
    detail: str = ''
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StatsPeriod:
    period: str
    start_ms: int | None
    end_ms: int
    metrics: tuple[Stat, ...]
    matched: Stat | None = None


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


def _time_metrics(roots, per_root, unknown, provisional, zone, source_complete):
    merged = union(pair for pairs in per_root.values() for pair in pairs)
    reasons = tuple(code for code, present in (
        ('source-incomplete', not source_complete), ('unknown-duration', unknown)) if present)
    unknown = bool(reasons)
    observed = sum(right - left for left, right in merged)
    duration = None if unknown else observed
    status = 'unavailable' if unknown else 'provisional' if provisional else 'complete'
    if provisional:
        reasons += ('running-executions',)
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
    record = ranked[0] if ranked and per_root[ranked[0].session_id] else None
    busy = min(days, key=lambda day: (-days[day], day)) if days else None
    observed_status = 'partial' if unknown else status
    record_status = observed_status if record else status if unknown else 'no-data'
    ratio_status = status if merged or unknown else 'no-data'
    activity_reasons = reasons if merged or unknown else ('no-execution-time',)
    metrics = (Stat('working-time', observed if observed else duration,
                   observed_status if observed else status, reasons=reasons),
        Stat('longest-session', sum(b - a for a, b in per_root[record.session_id]) if record else None,
             record_status, record.session_id if record else None, record.title if record else '', reasons=activity_reasons),
         Stat('busiest-day', days[busy] if busy else None, record_status, detail=str(busy or ''), reasons=activity_reasons),
          Stat('night-owl', Decimal(night) * 100 / duration if duration else None, ratio_status, reasons=activity_reasons),
         Stat('streak', None if unknown else longest, status, reasons=reasons),
         Stat('parallel', None if unknown else peak, status, reasons=reasons))
    return duration, status, reasons, metrics


def _cost_metrics(roots, entries, valuation, source_complete, duration, time_status, time_reasons):
    owner = {entry.session_id: root for root in roots for entry in root.entries}
    total = comparison_cost(entries, valuation)
    reasons = tuple(code for code, present in (
        ('source-incomplete', not source_complete), ('unpriced-requests', not total.complete),
        ('missing-token-usage', any(not USAGE_FIELDS <= set(e.tokens.known_fields) for e in entries)),
        ('pending-usage', any(root.cost_pending for root in roots))) if present)
    complete = not reasons
    groups = {}
    for entry in entries:
        groups.setdefault(owner[entry.session_id].session_id, []).append(entry)
    costs = {sid: comparison_cost(group, valuation).known_ccost for sid, group in groups.items()}
    cost_status = 'complete' if complete else 'partial'
    rate = total.known_ccost * HOUR_MS / duration if complete and duration else None
    average = total.known_ccost / len(groups) if complete and groups else None
    expensive = min(costs, key=lambda sid: (-costs[sid], sid)) if costs and (complete or total.known_ccost > 0) else None
    root = next((root for root in roots if root.session_id == expensive), None)
    rate_reasons = tuple(dict.fromkeys((*reasons, *time_reasons)))
    missing_cost_status = 'unavailable' if reasons else 'no-data'
    return (Stat('hourly-rate', rate, time_status if rate is not None else
             'unavailable' if reasons or duration is None else 'no-data',
             reasons=rate_reasons if rate_reasons or duration else ('no-execution-time',)),
         Stat('total-cost', total.known_ccost, cost_status, reasons=reasons),
         Stat('average-cost', average, cost_status if average is not None else missing_cost_status,
              reasons=reasons or (() if groups else ('no-requests',))),
         Stat('expensive-session', costs[expensive] if root else None, cost_status if root else missing_cost_status,
              root.session_id if root else None, root.title if root else '',
              reasons=reasons or (() if groups else ('no-requests',))))


def period_stats(roots, valuation, *, period, start, now, zone, source_complete=True):
    """Cost uses event time, never proportional allocation or displayed amounts."""
    roots = tuple(root for root in roots if not outside_period(root, start))
    source_complete = source_complete and all(root.source_complete for root in roots)
    entries = tuple(entry for entry in deduplicated_requests(e for root in roots for e in root.entries)
                     if (start is None or entry.completed_at_ms >= start) and entry.completed_at_ms <= now)
    per_root, unknown, provisional = _timing(roots, start, now)
    duration, status, reasons, timed = _time_metrics(roots, per_root, unknown, provisional, zone, source_complete)
    cost = _cost_metrics(roots, entries, valuation, source_complete, duration, status, reasons)
    values = (cost[0], cost[1], timed[0], *cost[2:], *timed[1:])
    return StatsPeriod(period, start, now, values)


def outside_period(root, start):
    """Complete execution AND request evidence only; never use session metadata.

    A missing end, pending usage or incomplete snapshot cannot prove irrelevance.
    Global membership/migration warnings are intentionally not discharged here.
    """
    if start is None or not root.source_complete or root.cost_pending:
        return False
    if any(left <= 0 or duration is None or duration < 0 or running
           for left, duration, running in root.intervals):
        return False
    return (all(left + duration < start for left, duration, _running in root.intervals)
            and all(entry.completed_at_ms < start for entry in root.entries))
