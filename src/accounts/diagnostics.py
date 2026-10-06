"""Allowlisted account/parser evidence without credentials or account labels."""
from __future__ import annotations

from src.domain import AccountSnapshot

_OBSERVATION_FIELDS = frozenset({
    "provider", "plan", "has_quota", "unlimited", "credits_used", "entitlement",
    "remaining", "remaining_fraction", "numeric_quota_usable", "parser_reason",
    "parser_status", "http_status", "entitlement_http_status", "limit_reached",
    "internal_http_status", "primary_has_quota", "fallback_has_quota",
    "auth_status", "backend_status", "account_kind",
})


def sanitized_account_observation(account: AccountSnapshot) -> dict[str, object]:
    return {
        "provider": account.ref.provider_id,
        "plan": account.plan,
        "status": account.status.value,
        "availability": account.availability,
        "quota_shape": {name: value for name, value in account.observations.items() if name in _OBSERVATION_FIELDS},
        "components": [{
            "label": component.label, "period": component.period,
            "used": str(component.used) if component.used is not None else None,
            "limit": str(component.limit) if component.limit is not None else None,
            "remaining": str(component.remaining) if component.remaining is not None else None,
            "remaining_fraction": str(component.remaining_fraction) if component.remaining_fraction is not None else None,
            "reset_at_ms": component.reset_at_ms, "scope": component.scope,
            "unlimited": component.unlimited, "status": component.status.value,
        } for component in account.quotas],
    }
