"""Offline shared-catalog / blocked-rich-history seam for real browser timing."""
from dataclasses import replace
from threading import Event
from types import SimpleNamespace

from development.tests.fixtures.synthetic_month import SyntheticMonthSource, make_root_snapshot
from development.tests.fixtures.watch_runtime import make_service
from src.application.session_catalog import SessionCatalog
from src.application.session_detail import SessionDetails
from src.watch.cards import WatchCards
from src.watch.observers import observe_catalog
from src.watch.web_coordinator import WebWatchCoordinator
from src.watch.card_workers import CardResult
from src.reports.watch_capture import capture_rows


def _today_snapshot(snapshot, rank, now):
    # Keep this one-prompt browser seam in today's UTC window, even at midnight.
    # Integer slots keep metadata and qualified activity ordering identical.
    budget = min(3_600_000, now % 86_400_000)
    unit = min(1000, budget // 26)
    base = now - budget + rank * unit
    if unit < 10:
        # A zero-slot user/assistant tie changes causal attempt selection. At the
        # boundary, let the prompt start just before today and finish exactly now.
        unit, base = 10, now - 3
    original = snapshot.root.created_at_ms

    def retime(at):
        return None if at is None else base + (at - original) * unit // 1000

    def part(value):
        return replace(value, created_at_ms=retime(value.created_at_ms),
                       updated_at_ms=retime(value.updated_at_ms))

    root = replace(snapshot.root, created_at_ms=base,
                   updated_at_ms=min(now, retime(snapshot.root.updated_at_ms)))
    return replace(snapshot, root=root, sessions=(root,),
        messages=tuple(replace(value, created_at_ms=retime(value.created_at_ms),
            completed_at_ms=retime(value.completed_at_ms),
            parts=tuple(part(item) for item in value.parts)) for value in snapshot.messages),
        parts=tuple(part(value) for value in snapshot.parts),
        events=tuple(replace(value, created_at_ms=retime(value.created_at_ms))
                     for value in snapshot.events),
        invocations=tuple(replace(value, created_at_ms=retime(value.created_at_ms),
            completed_at_ms=retime(value.completed_at_ms)) for value in snapshot.invocations))


class CatalogPreviewFixture:
    def __init__(self, root, now):
        self.now = now
        self.source = SyntheticMonthSource(3217, 1, month_start_ms=now - 365 * 86400000,
            today_roots=25, now_ms=now)
        for index, (key, value) in enumerate(self.source.snapshots.items()):
            if index >= 3192:
                value = _today_snapshot(value, index - 3192, now)
            root_session = replace(value.root, active=False)
            self.source.snapshots[key] = replace(value, complete=True,
                root=root_session, sessions=(root_session,))
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

    def upgrade(self, key=None):
        key = key or self.catalog.previews()[0].session_id
        entry = self.cards.sessions[key]
        capture, item = capture_rows(self.service, entry.root)
        self.cards.accept(CardResult(key, entry.generation, "rows", (capture, (), item.snapshot)), self.now)

    def empty(self):
        snapshot = _today_snapshot(make_root_snapshot(3217, 1, month_start_ms=self.now), 25, self.now)
        root = replace(snapshot.root, active=False)
        self.original = snapshot = replace(snapshot, complete=True, root=root, sessions=(root,))
        self._observe_revision(replace(snapshot, messages=(), parts=(), events=(),
            invocations=(), source_revision="empty-history"))
        self.upgrade(root.session_id)

    def revise(self):
        self._observe_revision(replace(self.original, source_revision="history-returned"))

    def _observe_revision(self, snapshot):
        self.source.snapshots[snapshot.root.session_id] = snapshot
        self.observation = observe_catalog(self.source, include_archived_revisions=True)
        self.catalog.observe(self.observation)
        self.cards.catalog(self.observation)

    def counts(self):
        return dict(reads=self.source.load_count, catalogs=self.source.catalog_count,
            revisions=self.source.batch_count, leases=len(self.catalog.lease_pages.leases))
