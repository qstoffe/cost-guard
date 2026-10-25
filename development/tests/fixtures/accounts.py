"""Normalized account snapshots and a fixed-snapshot account provider for account/quota tests."""
from __future__ import annotations

from decimal import Decimal

from src.domain import AccountRef, AccountSnapshot, IntegrationHealth, QuotaComponent

_PROVIDER_NAMES = {"openai": "OpenAI", "github-copilot": "GitHub Copilot", "anthropic": "Anthropic"}


def account(provider="openai", identity="a", *, label=None, plan="Plus", source="source"):
    return AccountSnapshot(AccountRef(source, provider, identity, account_label=label), 100_000,
                           _PROVIDER_NAMES[provider],
                           plan, quotas=(QuotaComponent("5-hour", "rolling", remaining_fraction=Decimal("0.75"),
                                                          duration_seconds=18_000, reset_at_ms=7_201_000),))


class NormalizedProvider:
    included_usage = False

    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.provider_id = snapshot.ref.provider_id

    def probe(self):
        return IntegrationHealth(True, True)

    def get_account_snapshots(self):
        return (self.snapshot,)
