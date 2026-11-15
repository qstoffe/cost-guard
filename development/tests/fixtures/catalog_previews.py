"""Offline shared-catalog / blocked-rich-history seam for real browser timing."""
from dataclasses import replace
from threading import Event
from types import SimpleNamespace

from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from development.tests.fixtures.watch_runtime import make_service
from src.application.session_catalog import SessionCatalog
from src.application.session_detail import SessionDetails
from src.watch.cards import WatchCards
from src.watch.observers import observe_catalog
from src.watch.web_coordinator import WebWatchCoordinator
from src.watch.card_workers import CardResult
from src.reports.watch_capture import capture_rows


class CatalogPreviewFixture:
    def __init__(self, root, now):
        self.now = now
        self.source = SyntheticMonthSource(3217, 1, month_start_ms=now - 365 * 86400000,
            today_roots=25, now_ms=now)
        self.source.snapshots = {key: replace(value, complete=True, root=replace(value.root, active=False))
            for key, value in self.source.snapshots.items()}
        self.observation = observe_catalog(self.source, include_archived_revisions=True)
        self.catalog = SessionCatalog(clock_ms=lambda: now)
        self.catalog.observe(self.observation)
        self.details = SessionDetails()
        self.service = make_service(str(root / "preview-source"), self.source, now_ms=now)[2]
        self.cards = WatchCards(SimpleNamespace(jobs={}, drain=lambda: (), limit=4))
        self.cards.catalog(self.observation)
        self.stopping, self.observed = Event(), Event()
        self.driver = self.source_failure = None

    def start(self):
        pass  # The test explicitly controls metadata/scalar publication, never rich capture.

    def close(self):
        self.service.close_accounts()

    def warm(self):
        page = self.catalog.page(period="today")
        for _ in range(7):
            self.catalog.tick(self.service)
        return self.catalog.page(token=page["token"], period="today")

    def frame(self, frame, running=0):
        active = tuple(replace(frame.active_cards[0], session_id=f"preview-running-{index}")
            for index in range(running))
        return WebWatchCoordinator.catalog_frame(self, self.catalog, replace(frame, active_cards=active,
            history_cards=(), recent_finished_cards=(), earlier_cards=(), now_ms=self.now,
            history_state="loading", history_epoch=0, history_checked=20, history_total=3217))

    def upgrade(self):
        key = self.catalog.previews()[0].session_id
        entry = self.cards.sessions[key]
        capture, item = capture_rows(self.service, entry.root)
        self.cards.accept(CardResult(key, entry.generation, "rows", (capture, (), item.snapshot)), self.now)

    def counts(self):
        return dict(reads=self.source.load_count, catalogs=self.source.catalog_count,
            revisions=self.source.batch_count, leases=len(self.catalog.leases))
