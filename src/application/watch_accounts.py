"""Watch-only subscription comparison slots; ordinary Accounts export is unchanged."""
from decimal import Decimal

from src.display import quota_usage
from src.domain import QuotaComponent
from .contracts import record
from .projection import account, comparison, fields, quota_record


def watch_quota(quota, period=None, *, estimated=False, note="", provider_id="", availability="available"):
    period = period if period is not None and period.quota is quota else None
    fraction, _used, _money = quota_usage(**{key: getattr(quota, key) for key in
        ("used", "limit", "remaining", "remaining_fraction", "unlimited", "remaining_money", "limit_money")})
    percent = "—" if fraction is None else ("<100%" if fraction < 1 and fraction * 100 >= Decimal("99.95")
        else f"{fraction * 100:.1f}".removesuffix(".0") + "%")
    return record(quota=quota_record(quota, period.cost if period is not None else None,
            provider_id=provider_id, availability=availability, estimated=estimated, note=note),
        used_fraction=fraction, used_percent=percent, exhausted=fraction == 1,
        restricted=quota.status == "blocked" and fraction != 1,
        cost=comparison(period.cost) if period is not None else None,
        estimated=estimated, note=note,
        pace=fields(period.pace, "unit per_day days workdays per_workday")
            if period is not None and period.pace is not None else None)


def primary_quota(native):
    account_quotas = tuple(item for item in native.quotas if item.scope == "account" and item.model_id is None)
    if native.primary_quota_label:
        return next((item for item in account_quotas if item.label == native.primary_quota_label),
                    QuotaComponent(native.primary_quota_label))
    explicit = next((item for item in account_quotas if item.primary), None)
    if explicit is not None:
        return explicit
    return next(iter(account_quotas), QuotaComponent("Primary quota"))


def watch_account(item):
    native = item.account
    primary = primary_quota(native)
    base = account(item)
    def projected(quota):
        period = next((period for period in item.quota_periods if period.quota is quota), None)
        note = next((note for note in item.ccost_notes if note.startswith(f"CCost {quota.label}:")), "")
        return watch_quota(quota, period, estimated=quota.label in item.ccost_estimated_scopes, note=note,
                           provider_id=native.ref.provider_id, availability=native.availability)
    allowed = {"observation", "ccost_scopes", "ccost_account_unknown"}
    return record(**{name: value for name, value in base.fields if name in allowed},
        primary=projected(primary), secondary=tuple(projected(quota) for quota in native.quotas if quota is not primary),
        today_estimated="today" in item.ccost_estimated_scopes,
        today_note=next((note for note in item.ccost_notes if note.startswith("CCost today:")), ""))
