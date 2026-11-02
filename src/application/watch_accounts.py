"""Watch-only subscription comparison slots; ordinary Accounts export is unchanged."""
from decimal import Decimal

from src.display import quota_usage
from src.domain import QuotaComponent
from .contracts import record
from .projection import account, fields


def watch_quota(quota):
    fraction, _used, _money = quota_usage(**{key: getattr(quota, key) for key in
        ("used", "limit", "remaining", "remaining_fraction", "unlimited", "remaining_money", "limit_money")})
    percent = "—" if fraction is None else ("<100%" if fraction < 1 and fraction * 100 >= Decimal("99.95")
        else f"{fraction * 100:.1f}".removesuffix(".0") + "%")
    return record(quota=fields(quota, "label period duration_seconds reset_at_ms window_active unlimited"),
        used_fraction=fraction, used_percent=percent, exhausted=fraction == 1,
        restricted=quota.status == "blocked" and fraction != 1)


def primary_quota(native):
    if native.primary_quota_label:
        return next((item for item in native.quotas if item.label == native.primary_quota_label),
                    QuotaComponent(native.primary_quota_label))
    explicit = next((item for item in native.quotas if item.primary), None)
    if explicit is not None:
        return explicit
    if native.ref.provider_id in {"github-copilot", "github-copilot-enterprise"}:
        return next((item for item in native.quotas if item.label.casefold() in {"monthly", "month"}),
                    QuotaComponent("Monthly"))
    if native.ref.provider_id in {"anthropic", "claude-code", "openai"}:
        return next((item for item in native.quotas if item.duration_seconds == 18_000 and item.scope == "account"),
                    QuotaComponent("5-hour"))
    return next(iter(native.quotas), QuotaComponent("Primary quota"))


def watch_account(item):
    native = item.account
    primary = primary_quota(native)
    base = account(item)
    allowed = {"observation", "ccost_scopes", "ccost_account_unknown"}
    return record(**{name: value for name, value in base.fields if name in allowed},
        primary=watch_quota(primary), secondary=tuple(watch_quota(quota) for quota in native.quotas if quota is not primary),
        today_estimated="today" in item.ccost_estimated_scopes,
        today_note=next((note for note in item.ccost_notes if note.startswith("CCost today:")), ""))
