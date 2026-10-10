"""In-memory source/pricing/quota boundaries shared by report and Watch tests."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from development.fixtures.session_snapshots import make_snapshot
from development.fixtures.pricing_catalog import catalog as sample_catalog
from src.domain import (
    AccountUsageStatus, IntegrationHealth, ProviderCapabilities, QuotaSnapshot, QuotaWindow,
    QuotaWindowKind, SessionCapabilities,
)


def shifted_snapshot_with_stale_root():
    """Put causal work on 1970-01-02 while root metadata remains on day one."""
    base = make_snapshot()
    shift = 86_400_000

    def shift_part(item):
        return replace(item, created_at_ms=item.created_at_ms + shift, updated_at_ms=item.updated_at_ms + shift)

    messages = tuple(
        replace(item, created_at_ms=item.created_at_ms + shift,
                completed_at_ms=(item.completed_at_ms + shift if item.completed_at_ms is not None else None),
                parts=tuple(shift_part(part) for part in item.parts))
        for item in base.messages
    )
    parts = tuple(part for message in messages for part in message.parts)
    events = tuple(replace(item, created_at_ms=item.created_at_ms + shift) for item in base.events)
    invocations = tuple(
        replace(item, created_at_ms=item.created_at_ms + shift,
                completed_at_ms=(item.completed_at_ms + shift if item.completed_at_ms is not None else None))
        for item in base.invocations
    )
    root, child = base.sessions
    root = replace(root, updated_at_ms=5_000)
    child = replace(child, created_at_ms=child.created_at_ms + shift, updated_at_ms=child.updated_at_ms + shift)
    return replace(base, root=root, sessions=(root, child), messages=messages, parts=parts,
                   events=events, invocations=invocations, source_revision="stale-root-child-active")


class FakeSource:
    source_id = "fake-v1"
    capabilities = SessionCapabilities(native_cost=True, child_sessions=True, compaction_events=True)

    def __init__(self, snapshot=None):
        self.snapshot = snapshot or make_snapshot()

    def probe(self):
        return IntegrationHealth(True, True, "ok")

    def list_sessions(self, since_ms=None):
        values = self.snapshot.sessions
        if since_ms is None:
            return values
        return tuple(item for item in values if item.updated_at_ms >= since_ms)

    def get_session_tree_revision(self, session_id):
        if session_id != self.snapshot.root.session_id:
            raise ValueError("missing")
        return self.snapshot.source_revision

    def load_session_snapshot(self, session_id):
        if session_id != self.snapshot.root.session_id:
            raise ValueError("missing")
        return self.snapshot


class FakePricingProvider:
    provider_id = "github-copilot"
    capabilities = ProviderCapabilities(model_pricing=True, long_context_pricing=True)

    def __init__(self):
        self.catalog = replace(sample_catalog(), retrieved_at_ms=1, source_revision="prices-1")

    def probe(self):
        return IntegrationHealth(True, True, "ok")

    def get_model_pricing(self):
        return self.catalog.models

    def get_catalog(self, force=False):
        return self.catalog


class FakeAccountProvider:
    provider_id = "github-copilot"
    display_name = "GitHub Copilot"
    capabilities = ProviderCapabilities(account_quota=True)

    def probe(self):
        return IntegrationHealth(True, True, "ok")

    def get_quota_snapshot(self):
        return QuotaSnapshot(
            provider="github-copilot", fetched_at_ms=4_000, capabilities=self.capabilities,
            windows=(QuotaWindow("monthly_ai_credits", QuotaWindowKind.FIXED,
                                 used_fraction=Decimal("0.30"), remaining_fraction=Decimal("0.70"),
                                 native_used=Decimal("30"), native_limit=Decimal("100"), native_unit="AI credits"),),
            available=True, usage_status=AccountUsageStatus.AVAILABLE,
        )
