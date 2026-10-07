"""Allowlisted account/parser evidence without credentials or account labels."""
from __future__ import annotations

import hashlib

from src.domain import AccountSnapshot

_OBSERVATION_FIELDS = frozenset({
    "provider", "plan", "has_quota", "unlimited", "credits_used", "entitlement",
    "remaining", "remaining_fraction", "numeric_quota_usable", "parser_reason",
    "parser_status", "http_status", "entitlement_http_status", "limit_reached",
    "internal_http_status", "primary_has_quota", "fallback_has_quota",
    "auth_status", "backend_status", "account_kind",
    "credential_discovered", "credential_category", "credential_active", "credential_qualifying",
    "request_attempted", "mapping_matched", "malformed_fields", "ignored_rows",
    "quota_components", "billing_components", "response_form", "quota_windows", "provider_status",
})


def sanitized_account_observation(account: AccountSnapshot) -> dict[str, object]:
    return {
        "provider": account.ref.provider_id,
        "account_source_hash": hashlib.sha256("\0".join(account.key).encode()).hexdigest()[:16],
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
        "billing_categories": sorted({component.kind for component in account.billing}),
        "billing_currencies": sorted({component.currency for component in account.billing}),
    }
