"""Deterministic Watch sources, account scheduling and service composition."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from development.fixtures.session_snapshots import make_snapshot
from development.fixtures.report_runtime import FakeAccountProvider, FakePricingProvider
from src.accounts.acquisition import AccountUpdate
from src.cache import CacheDatabase, CacheRepository
from src.config import load_configuration
from src.domain import AccountRef, AccountSnapshot, QuotaComponent, IntegrationHealth, SessionCapabilities
from src.reports import ReportService
from src.reports.models import AccountProjection
from src.sources.errors import SourceResyncRequiredError
from src.sources.selection import SourceSelection

ROOT = Path(__file__).resolve().parents[2]


class MutableSource:
    source_id = "fake-v1"
    capabilities = SessionCapabilities(native_cost=True, child_sessions=True, compaction_events=True)

    def __init__(self, snapshot=None):
        self.snapshot = snapshot or make_snapshot(running=True)
        self.load_count = 0
        self.revision_calls = 0
        self.batch_calls = 0

    def probe(self):
        return IntegrationHealth(True, True, "ok")

    def list_sessions(self, since_ms=None):
        values = self.snapshot.sessions
        if since_ms is None:
            return values
        return tuple(item for item in values if item.updated_at_ms >= since_ms)

    def get_session_tree_revision(self, session_id):
        self.revision_calls += 1
        return self.snapshot.source_revision

    def get_session_tree_revisions(self, session_ids):
        self.batch_calls += 1
        return {session_id: self.snapshot.source_revision for session_id in session_ids}

    def load_session_snapshot(self, session_id):
        self.load_count += 1
        return self.snapshot


class FakeLiveSource(MutableSource):
    source_id = "fake-v2"
    capabilities = replace(MutableSource.capabilities, live_changes=True)

    def __init__(self, *results):
        super().__init__(make_snapshot(generation="v2", running=True))
        self.results = list(results)

    def iter_changes(self):
        for item in self.results:
            if isinstance(item, BaseException):
                raise item
            yield item
        raise SourceResyncRequiredError("stream ended")


class CountingAccountProvider(FakeAccountProvider):
    def __init__(self):
        self.calls = 0

    def get_quota_snapshot(self):
        self.calls += 1
        return super().get_quota_snapshot()


def openai_account():
    return AccountProjection(AccountSnapshot(
        AccountRef("fixture", "openai", "a"), 2200, "OpenAI", "Plus",
        quotas=(
            QuotaComponent("5-hour", "rolling", remaining_fraction=Decimal("0.75"), reset_at_ms=7_201_000, duration_seconds=18_000),
            QuotaComponent("weekly", "rolling", remaining_fraction=Decimal("0.60"), reset_at_ms=345_601_000, duration_seconds=604_800),
        ),
    ), "OpenAI Plus")


def inline_account_refresh(service):
    """Synchronous fixture scheduler; actual worker races have separate tests."""
    pending = [False]

    def begin():
        pending[0] = True

    def poll():
        if not pending[0]:
            return None
        pending[0] = False
        snapshots = service.account_quota_snapshots()
        return AccountUpdate(snapshots, tuple(item.key for item in snapshots))

    service.begin_account_refresh = begin
    service.poll_account_refresh = poll


def make_service(tmp: str, source, *, now_ms: int = 2200, account_provider=None, async_accounts=False):
    db = CacheDatabase(Path(tmp))
    db.initialize()
    config = dict(load_configuration(ROOT).values)
    config.update(timezone="UTC", monthlyAiCredits=100, sessionWatchIntervalSeconds=5, watchRecentEventSeconds=30)
    selection = SourceSelection(source, "v2" if source.capabilities.live_changes else "v1", (), source.probe())
    service = ReportService(
        selection=selection, pricing_provider=FakePricingProvider(),
        account_provider=account_provider or FakeAccountProvider(),
        cache_repository=CacheRepository(db), config=config, now_ms=now_ms,
    )
    if not async_accounts:
        inline_account_refresh(service)
    return config, selection, service, db
