"""Anthropic account adapter; no undocumented subscription HTTP/auth probing.

Configured API accounts are visible even when native spend/quota is unavailable.
A supported source can inject quota observations through the same normalization
boundary; Pro/Max/Team/Enterprise are not excluded by the account model.
"""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal, InvalidOperation
from pathlib import Path
import time
from typing import Callable, Mapping

from src.domain import AccountSnapshot, AccountUsageStatus, BillingComponent, IntegrationHealth, ProviderCapabilities, QuotaComponent
from .credentials import provider_credentials, resolve_auth_path


def _number(value: object) -> Decimal | None:
    try:
        result = Decimal(str(value))
    except (ValueError, InvalidOperation):
        return None
    return result if result.is_finite() and result >= 0 else None


def normalize_anthropic_usage(account: AccountSnapshot, payload: Mapping[str, object]) -> AccountSnapshot:
    components = []
    for key, label, seconds in (("five_hour", "5-hour", 18_000), ("seven_day", "weekly", 604_800),
                                ("seven_day_sonnet", "Sonnet weekly", 604_800),
                                ("seven_day_opus", "Opus weekly", 604_800)):
        value = payload.get(key)
        if not isinstance(value, Mapping):
            continue
        used = _number(value.get("utilization"))
        fraction = 1 - used / 100 if used is not None and used <= 100 else None
        reset = value.get("reset_at_ms")
        components.append(QuotaComponent(
            label, "rolling", remaining_fraction=fraction, duration_seconds=seconds,
            reset_at_ms=int(reset) if isinstance(reset, int) and not isinstance(reset, bool) else None,
            status=AccountUsageStatus.BLOCKED if value.get("blocked") is True else AccountUsageStatus.UNKNOWN,
            model_id=str(value["model_id"]) if isinstance(value.get("model_id"), str) else None,
            scope="model" if key not in {"five_hour", "seven_day"} else "account",
        ))
    billing = []
    extra = payload.get("extra_usage")
    if isinstance(extra, Mapping):
        balance = _number(extra.get("remaining"))
        billing.append(BillingComponent("Usage credits", balance,
                       "USD" if extra.get("currency") == "USD" else "credits", kind="balance",
                       status="ACTIVE" if extra.get("enabled") is True else "unknown"))
    plan = payload.get("plan")
    recognized = {"pro": "Pro", "max": "Max", "team": "Team", "enterprise": "Enterprise"}
    status = AccountUsageStatus.BLOCKED if payload.get("blocked") is True else account.status
    partial = not components or any(component.remaining_fraction is None for component in components)
    return replace(account, plan=recognized.get(str(plan).lower(), account.plan), quotas=tuple(components),
                   billing=tuple(billing), status=status, availability="partial" if partial else "available",
                   reason="" if not partial else "Partial quota observations")


class AnthropicAccountProvider:
    provider_id = "anthropic"
    integration_ids = ("anthropic",)
    included_usage = False
    capabilities = ProviderCapabilities(account_quota=True, reset_windows=True)

    def __init__(self, *, enabled: bool = True, auth_json_path: str | None = None, credential_db_path: Path | None = None,
                 home: Path | None = None, quota_reader: Callable | None = None):
        self.enabled = enabled
        self.auth_json_path = resolve_auth_path(auth_json_path, home=home)
        self.credential_db_path = credential_db_path if not auth_json_path else None
        self.quota_reader = quota_reader

    def probe(self):
        if not self.enabled:
            return IntegrationHealth(True, False, "disabled in config")
        detected = bool(provider_credentials(self, self.integration_ids))
        return IntegrationHealth(detected, detected, "configured Anthropic account" if detected else "Anthropic account not configured")

    def get_account_snapshots(self):
        if not self.enabled:
            return ()
        accounts = []
        for record in provider_credentials(self, self.integration_ids):
            account = AccountSnapshot(record.ref, int(time.time() * 1000), "Anthropic",
                                      plan="API pay as you go" if record.value.get("type") == "api" else None,
                                      availability="unavailable", reason="Supported quota/billing source unavailable")
            if self.quota_reader is not None:
                try:
                    payload = self.quota_reader(record.ref)
                except (OSError, ValueError):
                    account = replace(account, availability="error", reason="Quota source failed")
                else:
                    if isinstance(payload, Mapping):
                        account = normalize_anthropic_usage(account, payload)
            accounts.append(account)
        return tuple(accounts)
