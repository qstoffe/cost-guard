"""AI Stats-only fun figures; canonical accounting and timing remain unchanged."""
from dataclasses import dataclass, replace
from bisect import bisect_right
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from .active_hour import HOUR_MS, USAGE_FIELDS, deduplicated_requests
from .ai_stats_rates import HourlyRates, hourly_rates, model_hourly_rates
from .ai_stats_responses import response_rows
from .ai_stats_buckets import model_key
from .ai_stats_models import activity_groups, model_costs, model_time, observed_tokens, standings
from .ai_stats_subagents import child_requests
from .timezones import local_month_start_ms, resolve_timezone

DAY_MS = 24 * HOUR_MS
ROLLING_DAYS = {'today': 1, '7-days': 7, '30-days': 30}
FALLBACK_MS = 60_000
MAX_GUESSED_MS = 4 * HOUR_MS
GENERIC_TOKEN_COST = Decimal('.000003')
# AI Stats = BEST EFFORT / NEVER Unavailable. Sparse, partial and estimated
# observations show fun values; Loading and genuine operational errors differ.
# Standing contract: see development/README.md for the Reports module contract.
POLICY = 'fun-5-buckets'


@dataclass(frozen=True, slots=True)
class StatsRoot:
    session_id: str
    title: str
    entries: tuple
    # (start, duration, provisional); intervals already include attributable children.
    intervals: tuple
    cost_pending: bool = False
    source_complete: bool = True
    responses: tuple = ()
    activity: tuple = ()
    session_parents: tuple = ()
    source_instance: str = ''


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
    podium: tuple = ()


@dataclass(frozen=True, slots=True)
class StatsPeriod:
    period: str
    start_ms: int | None
    end_ms: int
    metrics: tuple[Stat, ...]
    matched: Stat | None = None


def windows(zone, now):
    return (*((period, now - days * DAY_MS) for period, days in ROLLING_DAYS.items()),
            ('month', local_month_start_ms(zone, now_ms=now)),
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
    observed = tuple(value if not missing else None for value, missing in zip(values, missing_fields))
    guessed = any(value is None for value in observed)
    if not guessed:
        return values, observed, False
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
    return values, observed, guessed


def _cost_metrics(roots, entries, valuation, source_complete, time_reasons, per_root, key, activity):
    owner = {entry.session_id: root for root in roots for entry in root.entries}
    values, observed, guessed = _request_costs(entries, valuation)
    cost_podium, average_podium = model_costs(roots, entries, values, key)
    children, child_values, ancestry_unknown = child_requests(roots, entries, values)
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
    child_reasons = reasons + (('unknown-subagent-ancestry',) if ancestry_unknown else ())
    average = total / len(costs) if costs else Decimal(0)
    expensive = min(costs, key=lambda sid: (-costs[sid], sid)) if costs else None
    root = next((root for root in roots if root.session_id == expensive), None)
    earned = model_hourly_rates(activity, entries, observed, union)
    timing_reasons = ('unpaired-request-timing',) if earned.partial else ()
    rate_reasons = tuple(dict.fromkeys((*reasons, *time_reasons, *timing_reasons)))
    rate = earned.cost * HOUR_MS / earned.duration_ms if earned.duration_ms else (None if earned.partial else Decimal(0))
    metrics = (Stat('hourly-rate', rate, 'partial' if rate_reasons else 'complete', reasons=rate_reasons,
                    podium=earned.podium),
         Stat('total-cost', total, cost_status, reasons=reasons, podium=cost_podium),
         Stat('average-cost', average, cost_status, reasons=reasons, podium=average_podium),
         Stat('expensive-session', costs[expensive] if root else Decimal(0), cost_status,
              root.session_id if root else None, root.title if root else '',
              reasons=reasons),
         Stat('subagent-cost', sum(child_values, Decimal(0)), 'partial' if child_reasons else 'complete',
               reasons=child_reasons, podium=standings(children, child_values, key)))
    return metrics, earned


def _token_metrics(roots, entries, complete, start, now, key):
    """Observed physical traffic only: never borrow fun-page cost/time fillers."""
    reasons = tuple(code for code, present in (
        ('source-incomplete', not complete),
        ('missing-token-usage', any(not USAGE_FIELDS <= set(e.tokens.known_fields) for e in entries)),
        ('unknown-request-time', any(e.completed_at_ms <= 0 for root in roots for e in root.entries)),
        ('pending-usage', any(root.cost_pending for root in roots))) if present)
    volumes = [observed_tokens(e) for e in entries]
    total = sum(volumes)
    responses = response_rows(roots, entries, start, now, key)
    output = sum(row.output_tokens for row in responses)
    elapsed = sum(row.duration_ms for row in responses)
    return (Stat('total-tokens', total, 'partial' if reasons else 'complete', reasons=reasons,
                 podium=standings(entries, volumes, key)),
            Stat('token-rate', Decimal(output) * 1000 / elapsed if elapsed else 0, podium=responses[:3],
                 detail='activity' if entries or any(root.intervals for root in roots) else ''))


class StatsObservation:
    """Share only immutable preparation within one pinned multi-period calculation."""
    def __init__(self, roots, valuation, *, now, zone, workday_calendar='SE', model_name=None, model_bucket=None,
                 shared_history=False):
        self.roots, self.valuation = tuple(roots), valuation
        self.now, self.zone = now, zone
        self.workday_calendar = workday_calendar
        self._timelines, self._requests = {}, None
        self._model_names = {}
        self.model_bucket, self.model_name = model_bucket, model_name
        self.shared_history = shared_history

    def model_key(self, entry):
        model = entry.model
        if model not in self._model_names:
            self._model_names[model] = (self.model_bucket(model) if self.model_bucket else
                self.model_name(model_key(entry), model.provider) if self.model_name else model_key(entry))
        return self._model_names[model]

    def timing(self, root):
        key = id(root)
        if key not in self._timelines:
            self._timelines[key] = (_root_intervals(root, self.now),
                any(left <= 0 or duration is None or duration < 0 for left, duration, _ in root.intervals),
                any(running for _left, _duration, running in root.intervals))
        return self._timelines[key]

    def period(self, *, period, start, source_complete=True):
        if self._requests is None:
            self._requests = deduplicated_requests(
                (entry for root in self.roots for entry in root.entries), shared_history=self.shared_history)
        roots = tuple(root for root in self.roots if not outside_period(root, start))
        entries = tuple(entry for entry in self._requests
                        if (start is None or entry.completed_at_ms >= start) and entry.completed_at_ms <= self.now)
        complete = source_complete and all(root.source_complete for root in roots)
        per_root, unknown, provisional = _timing(roots, start, self.now, self)
        _duration, _status, reasons, timed = _time_metrics(roots, per_root, unknown, provisional, self.zone, complete)
        activity = activity_groups(roots, entries, start, self.now, self.model_key)
        cost, earned = _cost_metrics(roots, entries, self.valuation, complete, reasons, per_root, self.model_key, activity)
        # Original positive evidence only: no session metadata, epoch or guessed age.
        stamps = [entry.completed_at_ms for entry in entries if 0 < entry.completed_at_ms <= self.now]
        stamps.extend(left for root in roots for left, _duration, _running in root.intervals
                      if 0 < left <= self.now)
        rates = hourly_rates(earned.cost, earned.duration_ms, period=period, now=self.now, zone=self.zone,
            calendar=self.workday_calendar, evidence_start=min(stamps, default=None))
        metrics = (replace(cost[0], rates=rates), cost[1],
            replace(timed[0], podium=model_time(activity, union)),
            *cost[2:], *timed[1:], *_token_metrics(roots, entries, complete, start, self.now, self.model_key))
        return StatsPeriod(period, start, self.now, metrics)


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
