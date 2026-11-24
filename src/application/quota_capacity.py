"""Selection of qualified Web account capacity estimates, independent of storage."""
from dataclasses import dataclass
from decimal import Decimal

from src.analysis.period_ccost import empty_quota_window, quota_window
from .projection import identity, quota_record
from .quota_ccost import CapacityOffer, quota_ccost_values


REFRESH_FRACTION = Decimal("0.05")


@dataclass(frozen=True, slots=True)
class CapacitySample:
    capacity: Decimal
    compatibility: str
    reset_ms: int
    observed_ms: int
    pricing: str
    fraction_used: Decimal


def quota_capacity_key(account, quota):
    if not account.ref.account_id or account.capacity_kind == "credit":
        return None  # A reused login locator is not a verified account identity.
    primary = (quota.label == account.primary_quota_label if account.primary_quota_label else quota.primary)
    return identity((account.key, primary, quota.label, quota.scope, quota.model_id,
                     quota.period, quota.duration_seconds, quota.unit))


def compatibility(account, quota):
    return identity((account.plan, str(quota.limit.normalize()) if quota.limit is not None else None))


def capacity_candidate(account, quota, histories, match, now_ms):
    observed = account.fetched_at_ms
    if not histories or not 0 < observed <= now_ms:
        return None
    window = quota_window(quota, observed, include_monthly=True)
    if window is None or window[0] == window[1]:
        return None
    pricing = histories[0].catalog.analysis_signature
    for history in histories:
        if history.catalog.analysis_signature == pricing and history.covers(window[0]) and (
                history.observed_at_ms is not None and history.observed_at_ms >= observed):
            break
    else:
        return None
    cost = history.qualified_capacity_cost(account, quota, window)
    if cost is None:
        return None
    values = dict(quota_record(quota, cost, provider_id=account.ref.provider_id,
                               availability=account.availability).fields)
    reference = quota_ccost_values(values, observed)
    if reference["basis"] != "ratio":
        return None
    return CapacitySample(reference["capacity"], match, quota.reset_at_ms, observed, pricing,
                          reference["fraction_used"])


def capacity_selection(saved, candidate, match, quota, observed_ms, now_ms):
    """Choose one sample; never treat a different plan, limit or older window as current."""
    window = quota_window(quota, now_ms, include_monthly=True)
    if window is None:
        return None, None
    idle = empty_quota_window(quota)
    compatible = (saved is not None and saved.compatibility == match
                  and saved.observed_ms <= observed_ms
                  and (idle or saved.reset_ms <= quota.reset_at_ms))
    if (candidate is not None and (saved is None or candidate.observed_ms > saved.observed_ms)
            and (not compatible or candidate.fraction_used >= REFRESH_FRACTION)):
        return CapacityOffer(candidate.capacity, retained=False, idle=False), candidate
    if not compatible:
        return None, None
    retained = idle or saved.observed_ms != observed_ms or saved.reset_ms != quota.reset_at_ms
    return CapacityOffer(saved.capacity, retained=retained, idle=idle), None
