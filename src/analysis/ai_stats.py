"""AI Stats-only fun figures; canonical accounting and timing remain unchanged."""
from dataclasses import dataclass, replace
from bisect import bisect_right
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from .active_hour import HOUR_MS, USAGE_FIELDS, deduplicated_requests
from .ai_stats_rates import HourlyRates, hourly_rates
from .timezones import local_day_start_ms, local_month_start_ms, resolve_timezone

DAY_MS = 24 * HOUR_MS
FALLBACK_MS = 60_000
MAX_GUESSED_MS = 4 * HOUR_MS
GENERIC_TOKEN_COST = Decimal('.000003')
POLICY = 'fun-2-tokens'


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
    rates: HourlyRates | None = None


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
    days, night, boundaries = {}, 0, {}
    for left, right in intervals:
        day = datetime.fromtimestamp(left / 1000, timezone.utc).astimezone(tz).date()
        while True:
            next_day = day + timedelta(days=1)
            bounds = boundaries.get(day)
            if bounds is None:
                bounds = [int(datetime(day.year, day.month, day.day, hour, tzinfo=tz).timestamp() * 1000)
                          for hour in (0, 6, 22)]
                bounds.append(int(datetime(next_day.year, next_day.month, next_day.day, tzinfo=tz).timestamp() * 1000))
                boundaries[day] = bounds
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


def _root_intervals(root, now):
    """Keep measured work; fill broken boundaries using local activity, never age."""
    stamps = sorted({e.completed_at_ms for e in root.entries if 0 < e.completed_at_ms <= now})
    anchors = sorted({left for left, _duration, _running in root.intervals if 0 < left < now} | set(stamps))
    result = []
    for left, duration, running in root.intervals:
        if not 0 < left < now:
            if left > 0 or not stamps:
                continue
            right = stamps[-1]
            amount = duration if type(duration) is int and duration > 0 else FALLBACK_MS
            result.append((max(1, right - min(amount, MAX_GUESSED_MS)), right))
            continue
        if type(duration) is int and duration >= 0:
            right = min(now, left + duration)
        elif running:
            right = min(now, left + MAX_GUESSED_MS)
        else:
            index = bisect_right(anchors, left)
            following = anchors[index] if index < len(anchors) else left + FALLBACK_MS
            right = min(now, left + MAX_GUESSED_MS, following)
        result.append((left, right))
    # Request-only histories still get a timeline. Complete measured histories
    # never gain extra time merely because a completion timestamp is at an edge.
    if not root.intervals or any(left <= 0 or duration is None or duration < 0
                                 for left, duration, _ in root.intervals):
        measured = union(result)
        starts = [left for left, _ in measured]
        for stamp in stamps:
            index = bisect_right(starts, stamp) - 1
            if index < 0 or measured[index][1] < stamp:
                result.append((max(1, stamp - FALLBACK_MS), stamp))
    return union(result)


def _timing(roots, start, now, preparation):
    per_root, unknown, provisional = {}, False, False
    for root in roots:
        clipped = []
        intervals, root_unknown, root_provisional = preparation.timing(root)
        unknown |= root_unknown
        provisional |= root_provisional
        for left, right in intervals:
            left = max(start or 1, left)
            if right > left:
                clipped.append((left, right))
        per_root[root.session_id] = union(clipped)
    return per_root, unknown, provisional


def _time_metrics(roots, per_root, unknown, provisional, zone, source_complete):
    merged = union(pair for pairs in per_root.values() for pair in pairs)
    reasons = tuple(code for code, present in (
        ('source-incomplete', not source_complete), ('unknown-duration', unknown)) if present)
    unknown = bool(reasons)
    observed = sum(right - left for left, right in merged)
    duration = observed
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
    metrics = (Stat('working-time', duration, observed_status, reasons=reasons),
        Stat('longest-session', sum(b - a for a, b in per_root[record.session_id]) if record else 0,
             observed_status, record.session_id if record else None, record.title if record else '', reasons=reasons),
        Stat('busiest-day', days[busy] if busy else 0, observed_status, detail=str(busy or ''), reasons=reasons),
        Stat('night-owl', Decimal(night) * 100 / duration if duration else Decimal(0), observed_status, reasons=reasons),
        Stat('streak', longest, observed_status, reasons=reasons),
        Stat('parallel', peak, observed_status, reasons=reasons))
    return duration, status, reasons, metrics


def _request_costs(entries, valuation):
    """Known valuation first; bounded same-model token rate or generic fun cost."""
    values, missing_fields = [], []
    for entry in entries:
        try:
            value = valuation(entry.model, entry.tokens) if entry.tokens.total else Decimal(0)
            value = Decimal(value) if value is not None else None
            if value is not None and (not value.is_finite() or not 0 <= value <= Decimal('1e9')):
                value = None
        except (InvalidOperation, TypeError, ValueError, OverflowError):
            value = None
        values.append(value)
        missing_fields.append(USAGE_FIELDS - set(entry.tokens.known_fields))
    guessed = any(value is None or missing for value, missing in zip(values, missing_fields))
    if not guessed:
        return values, False
    rates = {}
    for entry, value, missing in zip(entries, values, missing_fields):
        if value is not None and entry.tokens.total and not missing:
            cost, tokens = rates.get(entry.model, (Decimal(0), 0))
            rates[entry.model] = cost + value, tokens + entry.tokens.total
    for index, (entry, value, missing) in enumerate(zip(entries, values, missing_fields)):
        if value is None or missing:
            cost, tokens = rates.get(entry.model, (Decimal(0), 0))
            rate = min(Decimal('.001'), cost / tokens) if tokens and cost else GENERIC_TOKEN_COST
            extra = sum({'input': 250, 'output': 1000, 'cache_read': 0, 'cache_write': 0}[field] for field in missing)
            amount = min(10_000_000, max(0, entry.tokens.total) + extra)
            supplement = min(Decimal(10), rate * (amount if value is None else extra))
            values[index] = (value or Decimal(0)) + supplement
    return values, guessed


def _cost_metrics(roots, entries, valuation, source_complete, duration, time_reasons, per_root):
    owner = {entry.session_id: root for root in roots for entry in root.entries}
    values, guessed = _request_costs(entries, valuation)
    reasons = tuple(code for code, present in (
        ('source-incomplete', not source_complete), ('unpriced-requests', guessed),
        ('missing-token-usage', any(not USAGE_FIELDS <= set(e.tokens.known_fields) for e in entries)),
        ('pending-usage', any(root.cost_pending for root in roots))) if present)
    costs = {}
    for entry, value in zip(entries, values):
        sid = owner[entry.session_id].session_id
        costs[sid] = costs.get(sid, Decimal(0)) + value
    for root in roots:
        if root.cost_pending and root.session_id not in costs and per_root[root.session_id]:
            costs[root.session_id] = Decimal('.003')
    total = sum(costs.values(), Decimal(0))
    cost_status = 'partial' if reasons else 'complete'
    rate = total * HOUR_MS / duration if duration else Decimal(0)
    average = total / len(costs) if costs else Decimal(0)
    expensive = min(costs, key=lambda sid: (-costs[sid], sid)) if costs else None
    root = next((root for root in roots if root.session_id == expensive), None)
    rate_reasons = tuple(dict.fromkeys((*reasons, *time_reasons)))
    return (Stat('hourly-rate', min(Decimal('1e9'), rate), cost_status, reasons=rate_reasons),
         Stat('total-cost', total, cost_status, reasons=reasons),
         Stat('average-cost', average, cost_status, reasons=reasons),
         Stat('expensive-session', costs[expensive] if root else Decimal(0), cost_status,
              root.session_id if root else None, root.title if root else '',
              reasons=reasons))


def _token_metrics(roots, entries, complete, duration, time_reasons, rates):
    """Observed physical traffic only: never borrow fun-page cost/time fillers."""
    reasons = tuple(code for code, present in (
        ('source-incomplete', not complete),
        ('missing-token-usage', any(not USAGE_FIELDS <= set(e.tokens.known_fields) for e in entries)),
        ('unknown-request-time', any(e.completed_at_ms <= 0 for root in roots for e in root.entries)),
        ('pending-usage', any(root.cost_pending for root in roots))) if present)
    total = sum(sum(getattr(e.tokens, field) for field in USAGE_FIELDS if field in e.tokens.known_fields)
                + (e.tokens.reasoning if 'output' in e.tokens.known_fields else 0)
                for e in entries if e.completed_at_ms > 0)
    # Reuse the cost card's exact denominators, including its all-time evidence start.
    numerator = Decimal(total)
    active = numerator * HOUR_MS / duration if duration else Decimal(0) if not total else None
    active_reasons = tuple(dict.fromkeys((*reasons, *time_reasons,
        *(('unknown-duration',) if any(root.entries and not root.intervals for root in roots) else ()),
        *(('zero-active-time',) if total and not duration else ()))))
    token_rates = replace(rates, total=numerator,
        calendar_rate=numerator / rates.calendar_hours if rates.calendar_hours else Decimal(0),
        workday_rate=numerator / rates.workday_hours if rates.workday_hours else None,
        active_rate=None if active_reasons else active, robot_day=Decimal(0), robot_period=Decimal(0))
    if reasons:
        token_rates = replace(token_rates, calendar_rate=None, workday_rate=None)
    return (Stat('total-tokens', total, 'partial' if reasons else 'complete', reasons=reasons),
            Stat('token-rate', token_rates.active_rate, 'partial' if active_reasons else 'complete',
                 reasons=active_reasons, rates=token_rates))


class StatsObservation:
    """Share only immutable preparation within one pinned multi-period calculation."""
    def __init__(self, roots, valuation, *, now, zone, workday_calendar='SE'):
        self.roots, self.valuation = tuple(roots), valuation
        self.now, self.zone = now, zone
        self.workday_calendar = workday_calendar
        self._timelines, self._requests = {}, {}

    def timing(self, root):
        key = id(root)
        if key not in self._timelines:
            self._timelines[key] = (_root_intervals(root, self.now),
                any(left <= 0 or duration is None or duration < 0 for left, duration, _ in root.intervals),
                any(running for _left, _duration, running in root.intervals))
        return self._timelines[key]

    def period(self, *, period, start, source_complete=True):
        roots = tuple(root for root in self.roots if not outside_period(root, start))
        population = tuple(id(root) for root in roots)
        if population not in self._requests:
            self._requests[population] = tuple(deduplicated_requests(e for root in roots for e in root.entries))
        entries = tuple(entry for entry in self._requests[population]
                        if (start is None or entry.completed_at_ms >= start) and entry.completed_at_ms <= self.now)
        complete = source_complete and all(root.source_complete for root in roots)
        per_root, unknown, provisional = _timing(roots, start, self.now, self)
        duration, _status, reasons, timed = _time_metrics(roots, per_root, unknown, provisional, self.zone, complete)
        cost = _cost_metrics(roots, entries, self.valuation, complete, duration, reasons, per_root)
        # Original positive evidence only: no session metadata, epoch or guessed age.
        stamps = [entry.completed_at_ms for entry in entries if 0 < entry.completed_at_ms <= self.now]
        stamps.extend(left for root in roots for left, _duration, _running in root.intervals
                      if 0 < left <= self.now)
        rates = hourly_rates(cost[1].value, duration, period=period, now=self.now, zone=self.zone,
            calendar=self.workday_calendar, evidence_start=min(stamps, default=None))
        return StatsPeriod(period, start, self.now,
            (replace(cost[0], rates=rates), cost[1], timed[0], *cost[2:], *timed[1:],
             *_token_metrics(roots, entries, complete, duration, reasons, rates)))


def period_stats(roots, valuation, *, period, start, now, zone, source_complete=True, workday_calendar='SE'):
    """Cost uses request event time; guesses never escape this fun-page owner."""
    return StatsObservation(roots, valuation, now=now, zone=zone, workday_calendar=workday_calendar).period(
        period=period, start=start, source_complete=source_complete)


def outside_period(root, start):
    """Complete execution AND request evidence only; never use session metadata.

    A missing end, pending usage or incomplete snapshot cannot prove irrelevance.
    Global membership/migration warnings are intentionally not discharged here.
    """
    if start is None or not root.source_complete or root.cost_pending or any(e.completed_at_ms <= 0 for e in root.entries):
        return False
    if any(left <= 0 or duration is None or duration < 0 or running
           for left, duration, running in root.intervals):
        return False
    return (all(left + duration < start for left, duration, _running in root.intervals)
            and all(entry.completed_at_ms < start for entry in root.entries))
