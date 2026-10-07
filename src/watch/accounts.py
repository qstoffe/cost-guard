"""Per-account transient quota reconciliation, independent of source changes."""
from __future__ import annotations

from dataclasses import replace
from typing import Mapping, Sequence

from src.domain import AccountSnapshot, AccountUsageStatus

AccountKey = tuple[str, str, str]
MAX_STALE_MS = 300_000


def durable_quota_failure(snapshot: AccountSnapshot | None) -> bool:
    """Provider-normalized rejection/unavailability must not be masked by Watch."""
    return snapshot is not None and (
        snapshot.availability == "unavailable"
        or snapshot.observations.get("parser_reason") == "auth_failure"
        or snapshot.observations.get("parser_reason") == "software_failure"
        or snapshot.observations.get("http_status") in (401, 403)
    )


def recovery_account_keys(
    previous: Sequence[AccountSnapshot], fresh: Sequence[AccountSnapshot],
    reconciled: Sequence[AccountSnapshot],
) -> tuple[AccountKey, ...]:
    """Accounts still needing a retry, without scheduling or provider wire fields."""
    old, incoming = {s.key: s for s in previous}, {s.key: s for s in fresh}
    pending = []
    for item in reconciled:
        current = incoming.get(item.key)
        if durable_quota_failure(current) or (current is None and durable_quota_failure(old.get(item.key))):
            continue
        if current is None or current.availability == "error" or item.availability == "stale":
            pending.append(item.key)
    return tuple(pending)


def reconcile_accounts(
    previous: Sequence[AccountSnapshot], fresh: Sequence[AccountSnapshot],
    seen: Mapping[AccountKey, int], *, now_ms: int, recovering: bool = False, update_seen: bool = True,
) -> tuple[tuple[AccountSnapshot, ...], dict[AccountKey, int], bool]:
    old = {item.key: item for item in previous}
    incoming = {item.key: item for item in fresh}
    timestamps = dict(seen)
    result = []
    for key in dict.fromkeys((*old, *incoming)):
        prior = old.get(key)
        current = incoming.get(key)
        recent = prior is not None and 0 <= now_ms - timestamps.get(key, 0) <= MAX_STALE_MS
        retain = prior is not None and not durable_quota_failure(prior) and (recent or recovering)
        if durable_quota_failure(current):
            result.append(current)
            continue
        if current is None or current.availability == "error":
            if retain and prior and (prior.quotas or prior.billing):
                result.append(replace(prior, availability="stale", reason="Transient quota refresh failed; last known capacity",
                                      observations={**prior.observations, "parser_status": "stale"}))
            elif current:
                result.append(current)
            elif prior:
                result.append(replace(prior, quotas=(), billing=(), availability="unavailable",
                                      reason="Last known capacity expired; refresh unavailable"))
            continue
        if current.availability == "partial" and retain and prior:
            older = {component.label: component for component in prior.quotas}
            components = []
            retained = False
            for component in current.quotas:
                before = older.pop(component.label, None)
                fields = {}
                if before and component.limit == before.limit and component.used == before.used:
                    # Missing percentages/reset fields can be transient; changed
                    # native counters/limits must not inherit an unrelated share.
                    for name in ("remaining_fraction", "remaining", "reset_at_ms", "remaining_money", "limit_money"):
                        if getattr(component, name) is None and getattr(before, name) is not None:
                            fields[name] = getattr(before, name)
                retained |= bool(fields)
                components.append(replace(component, **fields))
            if older:
                components.extend(older.values())
                retained = True
            if not current.billing and prior.billing:
                current = replace(current, billing=prior.billing)
                retained = True
            if retained:
                status = current.status if current.status is not AccountUsageStatus.UNKNOWN else prior.status
                current = replace(current, quotas=tuple(components), availability="stale",
                                  plan=current.plan or prior.plan, status=status,
                                  warnings=current.warnings or (prior.warnings if current.status is AccountUsageStatus.UNKNOWN else ()))
        if prior and current.plan is None:
            current = replace(current, plan=prior.plan)
        if update_seen and current.availability in {"available", "partial"}:
            timestamps[key] = now_ms
        result.append(current)
    return tuple(result), timestamps, any(item.availability == "stale" for item in result)
