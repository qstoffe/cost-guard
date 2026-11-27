"""Wire-safe historical reference cost by the current account roster."""
from __future__ import annotations

from bisect import bisect_left
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from src.analysis.account_timeline import timeline_window
from src.analysis.period_ccost import account_usage_routes, monthly_quota_window
from src.analysis.quota_pace import is_workday
from src.analysis.timezones import resolve_timezone
from src.numbers import ccost_amount

from .contracts import record
from .projection import identity, quota_record
from .quota_ccost import capacity_period, direct_native_ccost, quota_ccost_values
from .watch_accounts import primary_quota


@dataclass(frozen=True, slots=True)
class AccountSeries:
    key: str
    account_key: tuple
    label: str
    routes: tuple[str, ...]
    allocation: tuple[tuple[str, int], ...]
    month: AccountMonth | None = None


@dataclass(frozen=True, slots=True)
class AccountMonth:
    start: int | None
    reset: int | None
    provider_total: bool
    used: Decimal | None


def account_roster(accounts, *, now_ms=None):
    # Card projection supplies the safe heading and its stable account identity.
    distinct = {item.account.key: item for item in accounts}
    counts = Counter(route for item in distinct.values() for route in account_usage_routes(item.account))
    return tuple(AccountSeries(identity(key), key, item.label, account_usage_routes(item.account, proven=True),
        tuple((route, counts[route]) for route in account_usage_routes(item.account)),
        _account_month(item, now_ms) if now_ms is not None else None)
        for key, item in distinct.items())


def _account_month(item, now_ms):
    account = item.account
    primary = primary_quota(account)
    for quota in (primary, *(quota for quota in account.quotas if quota is not primary)):
        period = next((value for value in item.quota_periods if value.quota is quota), None)
        values = dict(quota_record(quota, period.cost if period else None,
                                   provider_id=account.ref.provider_id, availability=account.availability).fields)
        if not capacity_period(values)[0]:
            continue
        window = monthly_quota_window(quota, now_ms)
        reference = quota_ccost_values(values, now_ms)
        native = not quota.unlimited and (direct_native_ccost(values, account.ref.provider_id)
                                           or quota.reference_ccost_capacity is not None)
        return AccountMonth(window[0] if window else None, quota.reset_at_ms if window else None, native,
                            reference['used'] if window else None)
    return None


def _bucket_cost(index, series, start, end, *, partial=False, strict_attribution=False):
    proven = [index.cost(route, series.account_key, start, end) for route in series.routes]
    amount = sum((value.known_ccost for value in proven), Decimal(0))
    uncertain = partial or any(not value.complete for value in proven)
    for route, candidates in series.allocation:
        unknown = index.cost(route, None, start, end)
        if unknown.observed_requests:
            if strict_attribution and candidates != 1:
                return None
            amount += unknown.known_ccost / candidates
            uncertain |= not strict_attribution or not unknown.complete
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
    known = tuple(point[0] for point in amounts if point is not None)
    if not known:
        return None
    uncertain = any(point is None or point[1] for point in amounts)
    return sum(known, Decimal(0)), '~' if uncertain else ''


def restore_range_totals(view):
    """Older compatible checkpoints have the points but may misqualify their total."""
    future = set(view['future_buckets'])
    series = []
    for item in view['series']:
        amounts = []
        for i, ((left, right), point) in enumerate(zip(view['buckets'], item['points'])):
            if i in future:
                continue
            amount = Decimal(point['amount']) if point is not None else None
            if left < right or amount:
                amounts.append((amount, point['display']['credits'].startswith('~')) if point is not None else None)
        total = _range_total(amounts)
        series.append(dict(item, total=_point(*total).to_json() if total is not None else None))
    return dict(view, series=series)


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
        seeded = dict(item, points=points, total=total, peak=str(peak),
                      ticks=[tick.to_json() for tick in _ticks(peak)])
        if item.get('discrepancy_comparable'):
            seeded['discrepancy_comparable'] = False
        series.append(seeded)
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
                  price_revision=None, month_index=None):
    months = {item.key: item.month for item in roster if period == 'month' and item.month is not None}
    window = timeline_window(period, now_ms, zone)
    elapsed = window.buckets[:len(window.buckets) - len(window.future)]
    # Chart labels end at Now; the index consumes half-open millisecond ranges.
    clips = (*elapsed[:-1], (elapsed[-1][0], now_ms + 1))
    acquiring = _overlap(pending, clips)
    initial = acquiring if initial_pending is None else _overlap(initial_pending, elapsed)
    non_working, end_occurrence = _calendar_details(period, window, now_ms, zone)
    series = []
    for item in roster:
        month = months.get(item.key)
        native = bool(month and month.provider_total)
        comparable = bool(month and month.start == window.start)
        missing = _overlap(gaps, clips)
        partial = tuple(gap or queued or first_covered_ms is None or left < first_covered_ms
                        for (left, _), gap, queued in zip(clips, missing, acquiring))
        valuation = month_index if month and month.start is not None and not native and month_index is not None else index
        amounts = tuple(_bucket_cost(valuation, item, left, right, partial=uncertain,
                                     strict_attribution=valuation is not None and valuation is month_index)
                        if valuation is not None and left < right else None
                        for (left, right), uncertain in zip(clips, partial))
        peak = max((point[0] for point in amounts if point is not None), default=Decimal(0))
        points = tuple(_point(*point) if point is not None else None for point in amounts) + (None,) * len(window.future)
        # An empty boundary slot has no elapsed time, but may contain an event exactly at Now.
        elapsed_amounts = tuple(point for (left, right), point in zip(elapsed, amounts)
                                if left < right or point is not None and point[0])
        subtotal = _range_total(elapsed_amounts)
        exact_total = subtotal is not None and not subtotal[1]
        total = _point(*subtotal) if subtotal is not None else None
        # The browser chooses the largest visible series' scale, without
        # reimplementing the product's Decimal/unit formatting.
        discrepancy_comparable = (native and comparable and month.used is not None and exact_total
                                  and not any(partial) and not any(initial))
        authority = dict(provider_monthly_total=True, provider_window_matches=comparable, observed_total=total,
                          discrepancy_comparable=discrepancy_comparable,
                          month_total=_point(month.used) if month.used is not None else None) if native else {}
        series.append(record(id=item.key, account=item.label, peak=peak, ticks=_ticks(peak), points=points,
                             total=total, **authority))
    return record(period=period, timezone_id=zone, start_ms=window.start, end_ms=now_ms, buckets=window.buckets,
                  slot_dates=window.dates, future_buckets=window.future, partial_buckets=window.partial,
                  non_working_buckets=non_working, end_occurrence=end_occurrence,
                  pending_buckets=tuple(i for i, waiting in enumerate(acquiring) if waiting),
                  initial_pending_buckets=tuple(i for i, waiting in enumerate(initial) if waiting),
                  price_revision=price_revision, series=tuple(series))
