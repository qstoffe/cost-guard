"""Wire-safe historical reference cost by the current account roster."""
from bisect import bisect_left
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal

from src.analysis.account_timeline import timeline_window
from src.analysis.period_ccost import account_usage_routes, combined_cost
from src.numbers import ccost_amount

from .contracts import record
from .projection import identity


@dataclass(frozen=True, slots=True)
class AccountSeries:
    key: str
    account_key: tuple
    label: str
    routes: tuple[str, ...]
    candidates: tuple[str, ...]
    estimates: tuple[str, ...]


def account_roster(accounts):
    # Card projection supplies the safe heading and its stable account identity.
    distinct = {item.account.key: item for item in accounts}
    candidates = Counter(route for item in distinct.values() for route in account_usage_routes(item.account))
    return tuple(AccountSeries(identity(key), key, item.label, account_usage_routes(item.account, proven=True),
        account_usage_routes(item.account),
        tuple(route for route in account_usage_routes(item.account) if candidates[route] == 1))
        for key, item in distinct.items())


def _bucket_cost(index, series, start, end, *, partial=False):
    if index.cost('', 'provider', start, end).observed_requests:
        return None  # Unknown route could belong to any current account.
    proven = [index.cost(route, series.account_key, start, end) for route in series.routes]
    estimated = []
    for route in series.candidates:
        unknown = index.cost(route, None, start, end)
        if route in series.estimates:
            estimated.append(unknown)
        elif unknown.observed_requests:
            return None
    total = combined_cost((*proven, *estimated))
    if not total.complete:
        return None
    amount = total.known_ccost
    if partial and not amount:
        return None
    mark = '~' if partial or any(value.observed_requests for value in estimated) else ''
    return amount, mark


def _point(amount, mark=''):
    return record(amount=amount, display=record(credits=mark + ccost_amount(amount, unit='credits'),
                                                usd=mark + ccost_amount(amount, unit='usd')))


def _ticks(peak):
    step = _nice_scale(peak)
    return tuple(_point(step * i) for i in range(5))


def seed_today(view, day, amounts):
    """Supplement only an acquiring daily bucket with a separate observed subtotal."""
    index = next((i for i, (left, _) in enumerate(view['buckets']) if left == day), None)
    if view['period'] == 'today' or index not in view['pending_buckets']:
        return view
    series = []
    for item in view['series']:
        amount = amounts.get(item['id'])
        if amount is None:
            series.append(item)
            continue
        points = item['points'].copy()
        points[index] = _point(amount, '~').to_json()
        peak = max(Decimal(point['amount']) for point in points if point is not None)
        series.append(dict(item, points=points, peak=str(peak), ticks=[tick.to_json() for tick in _ticks(peak)]))
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


def timeline_view(period, now_ms, zone, roster, index, *, first_covered_ms, gaps, pending=(), initial_pending=None,
                  price_revision=None):
    window = timeline_window(period, now_ms, zone)
    elapsed = window.buckets[:len(window.buckets) - len(window.future)]
    # Unread scheduled roots allow provisional positive costs from acquired facts.
    # Unavailable facts (failed/incomplete reads, migration gaps) still block
    # qualification. Neither can manufacture a zero.
    acquiring = _overlap(pending, elapsed)
    unavailable = _overlap(gaps, elapsed)
    initial = acquiring if initial_pending is None else _overlap(initial_pending, elapsed)
    qualified = tuple((max(left, first_covered_ms), right, waiting or left < first_covered_ms)
                      if first_covered_ms is not None and right > max(left, first_covered_ms) and not gap else None
                      for (left, right), gap, waiting in zip(elapsed, unavailable, acquiring))
    series = []
    for item in roster:
        amounts = tuple(_bucket_cost(index, item, bucket[0], bucket[1], partial=bucket[2])
                        if index is not None and bucket is not None else None for bucket in qualified)
        peak = max((point[0] for point in amounts if point is not None), default=Decimal(0))
        points = tuple(_point(*point) if point is not None else None for point in amounts) + (None,) * len(window.future)
        # The browser chooses the largest visible series' scale, without
        # reimplementing the product's Decimal/unit formatting.
        series.append(record(id=item.key, account=item.label, peak=peak, ticks=_ticks(peak), points=points))
    return record(period=period, timezone_id=zone, start_ms=window.start, end_ms=now_ms, buckets=window.buckets,
                  slot_dates=window.dates, future_buckets=window.future, partial_buckets=window.partial,
                  pending_buckets=tuple(i for i, waiting in enumerate(acquiring) if waiting and not unavailable[i]),
                  initial_pending_buckets=tuple(i for i, waiting in enumerate(initial) if waiting and not unavailable[i]),
                  price_revision=price_revision, series=tuple(series))


def retain_refresh(prior, view):
    """Within one scoped publication, hold usable values only for passive revisions."""
    if prior is None or prior['price_revision'] != view['price_revision']:
        return view
    refreshing = set(view['pending_buckets']) - set(view['initial_pending_buckets'])
    if not refreshing:
        return view
    old_slots = {start: i for i, (start, _) in enumerate(prior['buckets'])}
    old_series = {item['id']: item for item in prior['series']}
    series = []
    for item in view['series']:
        old = old_series.get(item['id'])
        if old is None:
            series.append(item)
            continue
        points = item['points'].copy()
        retained_peak = Decimal(0)
        for index in refreshing:
            previous = old_slots.get(view['buckets'][index][0])
            if previous is not None and (point := old['points'][previous]) is not None:
                points[index] = point
                retained_peak = max(retained_peak, Decimal(point['amount']))
        replacement = dict(item, points=points)
        if retained_peak > Decimal(item['peak']):
            replacement.update(peak=old['peak'], ticks=old['ticks'])
        series.append(replacement)
    return dict(view, series=series)
