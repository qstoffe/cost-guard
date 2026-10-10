"""Account/quota provider protocol."""
from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from src.domain import (
    AccountRef, AccountSnapshot, BillingComponent, IntegrationHealth,
    ProviderCapabilities, QuotaComponent, QuotaSnapshot,
)


class AccountProvider(Protocol):
    @property
    def provider_id(self) -> str: ...

    @property
    def capabilities(self) -> ProviderCapabilities: ...

    def probe(self) -> IntegrationHealth: ...

    def get_account_snapshots(self) -> tuple[AccountSnapshot, ...]: ...


def normalize_quota(snapshot: QuotaSnapshot, ref: AccountRef, label: str, *, capacity_kind: str = "usage_limit") -> AccountSnapshot:
    """Compatibility boundary for existing window-based provider integrations."""
    components = tuple(QuotaComponent(
        label="Monthly" if window.name == "monthly_ai_credits" else window.name,
        period=window.kind.value,
        used=window.native_used, limit=window.native_limit,
        remaining=(max(Decimal(0), window.native_limit - window.native_used)
                   if window.native_limit is not None and window.native_used is not None else None),
        remaining_fraction=window.remaining_fraction, unit=window.native_unit,
        reset_at_ms=window.reset_at_ms, duration_seconds=window.duration_seconds,
        unlimited=window.unlimited, status=window.status,
        model_id=window.model_id,
        scope=window.scope,
    ) for window in snapshot.windows)
    billing = snapshot.billing_components
    if snapshot.credit_balance is not None and not billing:
        billing = (BillingComponent("Credits", snapshot.credit_balance, snapshot.credit_unit or "credits", kind="balance"),)
    return AccountSnapshot(
        ref=snapshot.account_ref or ref, fetched_at_ms=snapshot.fetched_at_ms,
        provider_label=label, plan=snapshot.plan, quotas=components, billing=billing,
        status=snapshot.usage_status,
        availability=snapshot.availability if snapshot.available else (
            snapshot.availability if snapshot.availability != "available" else "unavailable"
        ),
        reason=snapshot.reason, observations=snapshot.observations, warnings=snapshot.warnings,
        capacity_kind=capacity_kind,
    )
