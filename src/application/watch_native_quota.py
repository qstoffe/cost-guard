"""Allowlisted native quota facts for both cached Watch views."""
from decimal import Decimal
from itertools import islice

from src.cache.display_watch_quota import WATCH_ACCOUNT_LIMIT, WatchQuotaFact
from src.domain import AccountUsageStatus, QuotaComponent
from src.reports.accounts import account_display_labels
from src.watch.accounts import FRESH_MS, MAX_STALE_MS, durable_quota_failure

from .contracts import record
from .projection import identity
from .watch_accounts import primary_quota, watch_quota

QUOTA_COMPONENT_LIMIT = 64


def _amount(value):
    return str(value) if value is not None else None


def native_quotas(owner, *, bound_ms, now_ms):
    """Select only current-process provider observations, not the history projection."""
    if owner is None:
        return ()
    accounts = tuple(islice(owner.snapshots, WATCH_ACCOUNT_LIMIT + 1))
    if len(accounts) > WATCH_ACCOUNT_LIMIT:
        return ()
    results = []
    for native, label in account_display_labels(accounts):
        completed = owner.seen_ms.get(native.key, 0)
        observed = min(completed, native.fetched_at_ms)
        if (not 0 < bound_ms < observed <= completed <= now_ms or now_ms - observed > MAX_STALE_MS
                or native.availability not in {"available", "partial", "stale"} or durable_quota_failure(native)
                or len(native.quotas) > QUOTA_COMPONENT_LIMIT):
            continue
        primary = primary_quota(native)
        if primary.origin != "provider_native":
            continue
        # Reference capacity, computed CCost and account-history estimates are
        # not provider quota evidence. Do not admit them on this slice.
        results.append(WatchQuotaFact(identity(native.key), native.ref.provider_id[:128], label[:256], observed,
            native.availability == "stale", primary.label[:128], primary.period, _amount(primary.used),
            _amount(primary.limit), _amount(primary.remaining), _amount(primary.remaining_fraction),
            primary.unit[:64] if primary.unit else None, primary.reset_at_ms, primary.duration_seconds,
            primary.status.value, primary.unlimited, _amount(primary.remaining_money),
            _amount(primary.limit_money), primary.window_active))
    return tuple(results)


def present_native_quotas(batch, now_ms):
    if batch is None:
        return None
    return record(cached_native=True, now_ms=now_ms,
                  accounts=tuple(item for fact in batch.facts if (item := _present(fact, now_ms)) is not None))


def _present(fact, now_ms):
    discard_at = fact.observed_ms + MAX_STALE_MS + 1
    if not fact.observed_ms <= now_ms < discard_at:
        return None
    fresh_until = fact.observed_ms + FRESH_MS + 1
    if fact.reset_ms is not None:
        fresh_until = min(fresh_until, fact.reset_ms)
    stale = bool(fact.stale) or now_ms >= fresh_until

    def decimal(value):
        return Decimal(value) if value is not None else None

    primary = QuotaComponent(fact.quota_label, period=fact.period, used=decimal(fact.used),
        limit=decimal(fact.capacity), remaining=decimal(fact.remaining), remaining_fraction=decimal(fact.remaining_fraction),
        unit=fact.unit, reset_at_ms=fact.reset_ms, duration_seconds=fact.duration_seconds,
        status=AccountUsageStatus(fact.status), unlimited=bool(fact.unlimited),
        remaining_money=decimal(fact.remaining_money), limit_money=decimal(fact.limit_money),
        window_active=None if fact.window_active is None else bool(fact.window_active))
    return record(observation=record(id=fact.account_id, provider_id=fact.provider_id,
                  label=fact.label, observed_at_ms=fact.observed_ms),
                  primary=watch_quota(primary, provider_id=fact.provider_id,
                                      availability="stale" if stale else "available"),
                  fresh_until_ms=fresh_until, discard_at_ms=discard_at, stale=stale)
