"""Wire-safe historical reference cost by the current account roster."""
from bisect import bisect_left
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from src.analysis.account_timeline import timeline_window
from src.analysis.period_ccost import account_usage_routes
from src.analysis.quota_pace import is_workday
from src.analysis.timezones import resolve_timezone
from src.numbers import ccost_amount

from .archive_exact_cost import ExactCost
from .contracts import record
from .projection import identity


@dataclass(frozen=True, slots=True)
class AccountSeries:
    key: str
    account_key: tuple
    label: str
    routes: tuple[str, ...]
    allocation: tuple[tuple[str, int], ...]


def account_roster(accounts):
    # Card projection supplies the safe heading and its stable account identity.
    distinct = {item.account.key: item for item in accounts}
    counts = Counter(route for item in distinct.values() for route in account_usage_routes(item.account))
    return tuple(AccountSeries(identity(key), key, item.label, account_usage_routes(item.account, proven=True),
        tuple((route, counts[route]) for route in account_usage_routes(item.account)))
        for key, item in distinct.items())


def _bucket_cost(index, series, start, end, *, partial=False):
    proven = [index.cost(route, series.account_key, start, end) for route in series.routes]
    amount = sum((value.known_ccost for value in proven), Decimal(0))
    uncertain = partial or any(not value.complete for value in proven)
    for route, candidates in series.allocation:
        unknown = index.cost(route, None, start, end)
        if unknown.observed_requests:
            amount += unknown.known_ccost / candidates
            uncertain = True
    # A missing provider has no legitimate candidate set. It can weaken the
    # confidence of a subtotal, but cannot be allocated across unrelated routes.
    uncertain = uncertain or bool(index.cost('', None, start, end).observed_requests)
    if uncertain and not amount and not any(value.priced_requests for value in proven):
        return None
    return amount, '~' if uncertain else ''


def _point(amount, mark=''):
    return record(amount=amount, display=record(credits=mark + ccost_amount(amount, unit='credits'),
                                                usd=mark + ccost_amount(amount, unit='usd')))


def _range_total(amounts):
    subtotal = sum((point[0] for point in amounts if point is not None), Decimal(0))
    uncertain = any(point is None or point[1] for point in amounts)
    if not amounts or (uncertain and not subtotal):
        return None
    return _point(subtotal, '~' if uncertain else '')


def _calendar_details(period, window, end_ms, zone):
    zone = resolve_timezone(zone)
    if period == 'today':
        end = datetime.fromtimestamp(end_ms // 1000, zone)
        # A published endpoint in the repeated wall-clock interval needs a fold
        # hint even if the other occurrence isn't plotted yet.
        repeated = end.replace(fold=0).utcoffset() != end.replace(fold=1).utcoffset()
        return (), end.fold + 1 if repeated else None
    days = (map(date.fromisoformat, window.dates) if window.dates else
            (datetime.fromtimestamp(start // 1000, zone).date() for start, _ in window.buckets))
    return tuple(i for i, day in enumerate(days) if not is_workday(day, 'SE')), None


def _ticks(peak):
    step = _nice_scale(peak)
    return tuple(_point(step * i) for i in range(5))


def seed_today(view, day, amounts):
    """Use the larger compatible daily subtotal, never add overlapping facts."""
    index = next((i for i, (left, _) in enumerate(view['buckets']) if left == day), None)
    if view['period'] == 'today' or index is None or day >= view['end_ms']:
        return view
    series = []
    for item in view['series']:
        amount = amounts.get(item['id'])
        point = item['points'][index]
        if (amount is None or point is not None and
                (not point['display']['credits'].startswith('~') or Decimal(point['amount']) >= amount)):
            series.append(item)
            continue
        points = item['points'].copy()
        points[index] = _point(amount, '~').to_json()
        peak = max(Decimal(point['amount']) for point in points if point is not None)
        # The compatible card seed replaces a bucket, not the whole summary or
        # an additional day's usage. Only the replacement delta is new.
        subtotal = Decimal(item['total']['amount']) if item['total'] else Decimal(0)
        subtotal += amount - (Decimal(point['amount']) if point else Decimal(0))
        total = _point(subtotal, '~').to_json() if subtotal else None
        series.append(dict(item, points=points, total=total, peak=str(peak),
                           ticks=[tick.to_json() for tick in _ticks(peak)]))
    return dict(view, series=series)


def _nice_scale(peak):
    # Choose four equally spaced, readable steps with modest headroom. Keep zero
    # legitimate and the scale nondegenerate even for an entirely zero series.
    if not peak:
        return Decimal(1)
    target = peak * Decimal('0.28')
    unit = Decimal(1).scaleb(target.adjusted())
    factor = min((Decimal('1'), Decimal('1.25'), Decimal('1.5'), Decimal('2'), Decimal('2.5'),
                  Decimal('3'), Decimal('4'), Decimal('5'), Decimal('6'), Decimal('8'), Decimal('10')),
                 key=lambda value: (value * unit < target, value))
    return factor * unit


def _overlap(intervals, buckets):
    starts, ends = [], []
    for left, right in sorted(intervals):
        if left >= right:
            continue
        if not ends or ends[-1] < left:
            starts.append(left)
            ends.append(right)
        else:
            ends[-1] = max(ends[-1], right)
    slots = (bisect_left(starts, right) - 1 for _, right in buckets)
    return tuple(left < right and slot >= 0 and ends[slot] > left for (left, right), slot in zip(buckets, slots))


def archived_timeline_view(period, as_of, now_ms, zone, roster, rows):
    """Project observed reference subtotals, never claim zero for unseen work."""
    current = timeline_window(period, now_ms, zone)
    observed = timeline_window(period, as_of, zone)
    if period != "7-days" and observed.start != current.start:
        return None
    # A former first bucket can overlap the new rolling start without being
    # wholly selected. Omit it, instead of prorating or using its old total.
    qualified = {(row.account, row.start, row.end): row for row in rows if row.start >= current.start}
    buckets = tuple((max(left, current.start), right) for left, right in observed.buckets
                    if right > current.start or left == right == current.start and period != "7-days")
    if not buckets:
        return None
    skipped = len(observed.buckets) - len(buckets)
    series = []
    for key, label in roster:
        saved = tuple(qualified.get((key, left, right)) if left < right else None for left, right in buckets)
        known = tuple(row for row in saved if row is not None and row.subtotal is not None)
        peak = max((row.subtotal for row in known), default=Decimal(0))
        total = ExactCost()
        for row in known:
            total.add(row.subtotal)
        compatible = len({row.pricing for row in known}) == 1
        series.append(record(id=key.hex(), account=label, peak=peak, ticks=_ticks(peak),
            points=tuple(_point(row.subtotal, "~") if row is not None and row.subtotal is not None else None
                         for row in saved),
            total=_point(total.amount(), "~") if compatible else None))
    non_working, occurrence = _calendar_details(period, observed, as_of, zone)
    partial = {index - skipped for index in observed.partial if index >= skipped}
    if buckets[0][0] != observed.buckets[skipped][0]:
        partial.add(0)
    return record(period=period, timezone_id=zone, start_ms=buckets[0][0], end_ms=as_of, buckets=buckets,
        slot_dates=observed.dates[skipped:], future_buckets=tuple(index - skipped for index in observed.future),
        partial_buckets=tuple(sorted(partial)),
        non_working_buckets=tuple(index - skipped for index in non_working if index >= skipped),
        end_occurrence=occurrence, pending_buckets=(), initial_pending_buckets=(),
        price_revision="archived-reference-only", series=tuple(series), coverage="unknown")


def timeline_view(period, now_ms, zone, roster, index, *, first_covered_ms, gaps, pending=(), initial_pending=None,
                  price_revision=None):
    window = timeline_window(period, now_ms, zone)
    elapsed = window.buckets[:len(window.buckets) - len(window.future)]
    acquiring = _overlap(pending, elapsed)
    missing = _overlap(gaps, elapsed)
    initial = acquiring if initial_pending is None else _overlap(initial_pending, elapsed)
    partial = tuple(gap or waiting or first_covered_ms is None or left < first_covered_ms
                    for (left, _), gap, waiting in zip(elapsed, missing, acquiring))
    non_working, end_occurrence = _calendar_details(period, window, now_ms, zone)
    series = []
    for item in roster:
        amounts = tuple(_bucket_cost(index, item, left, right, partial=uncertain)
                        if index is not None and left < right else None
                        for (left, right), uncertain in zip(elapsed, partial))
        peak = max((point[0] for point in amounts if point is not None), default=Decimal(0))
        points = tuple(_point(*point) if point is not None else None for point in amounts) + (None,) * len(window.future)
        # Ignore reserved dates and zero-duration boundary slots; neither adds
        # time in the published window nor makes it incomplete.
        total = _range_total(tuple(point for (left, right), point in zip(elapsed, amounts) if left < right))
        # The browser chooses the largest visible series' scale, without
        # reimplementing the product's Decimal/unit formatting.
        series.append(record(id=item.key, account=item.label, peak=peak, ticks=_ticks(peak), points=points, total=total))
    return record(period=period, timezone_id=zone, start_ms=window.start, end_ms=now_ms, buckets=window.buckets,
                  slot_dates=window.dates, future_buckets=window.future, partial_buckets=window.partial,
                  non_working_buckets=non_working, end_occurrence=end_occurrence,
                  pending_buckets=tuple(i for i, waiting in enumerate(acquiring) if waiting),
                  initial_pending_buckets=tuple(i for i, waiting in enumerate(initial) if waiting),
                  price_revision=price_revision, series=tuple(series))
