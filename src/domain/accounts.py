"""Account identity and independent native capacity/billing contracts.

An account is never identified by provider alone. Unknown IDs use an adapter's
stable source locator; labels are display metadata, never attribution evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Mapping

from .models import AccountUsageStatus


@dataclass(frozen=True, slots=True)
class AccountRef:
    source_instance: str
    provider_id: str
    account_id: str | None = None
    source_account: str = ""
    account_label: str | None = None

    @property
    def key(self) -> tuple[str, str, str]:
        if not self.account_id and not self.source_account:
            raise ValueError("Account identity requires an ID or source account locator")
        identity = "id:" + self.account_id if self.account_id else "source:" + self.source_account
        return self.source_instance, self.provider_id, identity


@dataclass(frozen=True, slots=True)
class QuotaComponent:
    label: str
    period: str = "unknown"
    used: Decimal | None = None
    limit: Decimal | None = None
    remaining: Decimal | None = None
    remaining_fraction: Decimal | None = None
    unit: str | None = None
    reset_at_ms: int | None = None
    duration_seconds: int | None = None
    status: AccountUsageStatus = AccountUsageStatus.UNKNOWN
    unlimited: bool = False
    # Only an adapter with an explicit native conversion may populate money.
    remaining_money: Decimal | None = None
    limit_money: Decimal | None = None
    origin: str = "provider_native"
    model_id: str | None = None
    scope: str = "account"
    # False only when the provider proves a rolling window has not started yet
    # (no usage, hence no reset time); None means unknown.
    window_active: bool | None = None

    def __post_init__(self) -> None:
        if self.remaining_fraction is not None and not (0 <= self.remaining_fraction <= 1):
            raise ValueError("Remaining fraction must be between 0 and 1")
        for value in (self.used, self.limit, self.remaining, self.remaining_money, self.limit_money):
            if value is not None and (not value.is_finite() or value < 0):
                raise ValueError("Native quota amounts must be finite and nonnegative")


@dataclass(frozen=True, slots=True)
class BillingComponent:
    label: str
    amount: Decimal | None = None
    currency: str = "USD"
    period: str = ""
    kind: str = "spend"  # spend, balance, budget
    status: str = "unknown"

    def __post_init__(self) -> None:
        if self.amount is not None and (not self.amount.is_finite() or self.amount < 0):
            raise ValueError("Billing amounts must be finite and nonnegative")


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    ref: AccountRef
    fetched_at_ms: int
    provider_label: str
    plan: str | None = None
    quotas: tuple[QuotaComponent, ...] = ()
    billing: tuple[BillingComponent, ...] = ()
    status: AccountUsageStatus = AccountUsageStatus.UNKNOWN
    availability: str = "available"  # available, partial, unavailable, error, stale
    reason: str = ""
    warnings: tuple[str, ...] = ()
    observations: Mapping[str, object] = field(default_factory=dict)
    # True only when a source can prove the complete usage scope for this account.
    usage_attribution_complete: bool = False
    # Adapter-owned capacity class, independent of remaining/availability.
    capacity_kind: str = "usage_limit"  # credit, usage_limit

    @property
    def key(self) -> tuple[str, str, str]:
        return self.ref.key
