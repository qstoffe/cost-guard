"""Wire-safe historical reference cost by the current Accounts quota roster."""
from bisect import bisect_left
from collections import Counter
from dataclasses import dataclass, replace
from decimal import Decimal

from src.analysis.account_timeline import timeline_buckets
from src.analysis.period_ccost import account_usage_routes, combined_cost
from src.numbers import ccost_amount
from src.pricing.identities import reference_identity, unverified_alias

from .contracts import record
from .projection import identity
from .watch_accounts import primary_quota


@dataclass(frozen=True, slots=True)
class QuotaSeries:
    key: str
    account_key: tuple
    label: str
    quota: str
    model: str | None
    eligible: bool
    primary: bool
    routes: tuple[str, ...]
    estimates: tuple[str, ...]


def quota_roster(accounts):
    candidates = Counter(route for item in accounts for route in account_usage_routes(item.account))
    result = []
    for item in accounts:
        account = item.account
        primary = primary_quota(account)
        routes = account_usage_routes(account, proven=True)
        estimates = tuple(route for route in account_usage_routes(account) if candidates[route] == 1)
        ordinals = Counter()
        for quota in sorted(account.quotas, key=lambda quota: quota is not primary):
            model = quota.model_id if quota.scope == 'model' and quota.model_id else None
            eligible = (quota.scope == 'account' or bool(model)
                        and bool(reference_identity(model)) and not unverified_alias(model, account.ref.provider_id))
            shape = (quota.label, quota.scope, quota.model_id, quota.period, quota.duration_seconds, quota.origin)
            ordinals[shape] += 1
            result.append(QuotaSeries(identity((*account.key, *shape, ordinals[shape])), account.key,
                item.label, quota.label, model, eligible, quota is primary, routes, estimates))
    return tuple(result)


def retain_compatible_quotas(accounts, previous):
    """Temporary partial observations don't delete otherwise compatible quota slots."""
    result = []
    for item in accounts:
        account = item.account
        prior = previous.get(account.key)
        if (account.availability in {'partial', 'stale'} and prior and
                account.plan == prior.plan and account.primary_quota_label == prior.primary_quota_label and
                account_usage_routes(account) == account_usage_routes(prior)):
            labels = {quota.label for quota in account.quotas}
            account = replace(account, quotas=account.quotas + tuple(
                quota for quota in prior.quotas if quota.label not in labels))
            item = replace(item, account=account)
        result.append(item)
    return tuple(result)


def _bucket_cost(index, series, start, end, *, partial=False):
    if index.cost('', 'provider', start, end).observed_requests:
        return None  # Unknown route could belong to any current account.
    proven, estimated = [], []
    for route in series.routes:
        proven.append(index.cost(route, series.account_key, start, end, series.model))
        unknown = index.cost(route, None, start, end, series.model)
        if route in series.estimates:
            estimated.append(unknown)
        elif unknown.observed_requests:
            return None
        if series.model and any(index.unknown_model_cost(route, owner, start, end).observed_requests
                                for owner in (None, series.account_key)):
            return None
    total = combined_cost((*proven, *estimated))
    if not total.complete:
        return None
    amount = total.known_ccost
    if partial and not amount:
        return None
    mark = '~' if partial or any(value.known_ccost > 0 for value in estimated) else ''
    return amount, mark


def _point(amount, mark=''):
    return record(amount=amount, display=record(credits=mark + ccost_amount(amount, unit='credits'),
                                               usd=mark + ccost_amount(amount, unit='usd')))


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


def timeline_view(period, now_ms, zone, roster, index, *, first_covered_ms, gaps):
    start, buckets = timeline_buckets(period, now_ms, zone, earliest_ms=index.earliest_ms)
    # Gaps can overlap (parent and child) and must not create false zeroes.
    gap_starts, gap_ends = [], []
    for left, right in sorted(gaps):
        if left >= right:
            continue
        if not gap_ends or gap_ends[-1] < left:
            gap_starts.append(left)
            gap_ends.append(right)
        else:
            gap_ends[-1] = max(gap_ends[-1], right)

    def covered(left, right):
        if first_covered_ms is None or right <= first_covered_ms:
            return False
        slot = bisect_left(gap_starts, right) - 1
        return slot < 0 or gap_ends[slot] <= left

    qualified = tuple((left, right, covered(left, right)) for left, right in buckets)
    series = []
    for item in roster:
        amounts = tuple(_bucket_cost(index, item, max(left, first_covered_ms), right,
                                     partial=left < first_covered_ms) if complete and item.eligible else None
                       for left, right, complete in qualified)
        peak = max((point[0] for point in amounts if point is not None), default=Decimal(0))
        points = tuple(_point(*point) if point is not None else None for point in amounts)
        # The browser chooses the largest visible series' scale, without
        # reimplementing the product's Decimal/unit formatting.
        step = _nice_scale(peak)
        ticks = tuple(_point(step * i) for i in range(5))
        series.append(record(id=item.key, account=item.label, quota=item.quota, primary=item.primary,
                             peak=peak, ticks=ticks, points=points))
    return record(period=period, timezone_id=zone, start_ms=start, end_ms=now_ms, buckets=buckets, series=tuple(series))
