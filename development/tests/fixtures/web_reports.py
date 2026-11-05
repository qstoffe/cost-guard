"""Spawn-safe synthetic report owner for HTTP and cancellation tests."""
import json
from dataclasses import replace
from pathlib import Path
import tempfile
from threading import Event, Thread
import time

from src.application import ReportApplication
from src.application.session_catalog import SessionCatalog
from src.application.session_detail import SessionDetails
from src.cache import CacheDatabase, CacheRepository
from src.config import load_configuration
from src.reports import ReportKind, ReportService
from src.sources.selection import SourceSelection
from src.sources.errors import FailureCode, SourceUnavailableError
from src.watch.observers import observe_catalog

from .report_runtime import FakeSource, FakePricingProvider
from .session_snapshots import make_snapshot


class SyntheticSessionsRuntime:
    """Session acquisition only; deliberately no Watch/SSE source observation."""

    def __init__(self, root):
        database = CacheDatabase(root / "session-cache")
        database.initialize()
        snapshot = make_snapshot()
        root_session = replace(snapshot.root, title='<script>PRIVATE_TEXT</script>')
        source = FakeSource(replace(snapshot, root=root_session,
            sessions=tuple(root_session if s.session_id == root_session.session_id else s for s in snapshot.sessions)))
        self.service = ReportService(selection=SourceSelection(source, "v1", (), source.probe()),
            pricing_provider=FakePricingProvider(), account_provider=None,
            cache_repository=CacheRepository(database), config=dict(load_configuration(root).values, timezone="UTC"),
            now_ms=4000, progress=lambda _: None)
        self.catalog = SessionCatalog()
        self.details = SessionDetails()
        self.stopping = Event()
        self.failure = None
        self.thread = Thread(target=self.run, name="synthetic-session-acquisition")

    def start(self):
        self.thread.start()

    def run(self):
        try:
            while not self.stopping.is_set():
                self.catalog.observe(observe_catalog(self.service.source, include_archived_revisions=True))
                self.details.tick(self.service)
                if self.catalog.needed():
                    self.catalog.tick(self.service)
                self.stopping.wait(.05)
        except BaseException as error:
            self.failure = error

    def close(self):
        self.stopping.set()
        self.thread.join(5)
        if self.thread.is_alive():
            raise RuntimeError("synthetic_session_shutdown_timeout")
        if self.failure:
            raise self.failure


def finite_report(sender, request):
    try:
        if request.kind is ReportKind.TOKEN_MIX:
            sender.send(("progress", {"phase": "history", "completed": 1, "total": 100}))
            time.sleep(60)
        with tempfile.TemporaryDirectory() as tmp:
            database = CacheDatabase(Path(tmp))
            database.initialize()
            cache = CacheRepository(database)
            config = dict(load_configuration(Path(__file__).resolve().parents[3]).values, timezone="UTC")

            def factory(now, progress):
                if request.kind is ReportKind.DATE:
                    raise SourceUnavailableError("PRIVATE path/token must not escape", code=FailureCode.ENDPOINT_UNRESPONSIVE)
                source = FakeSource(make_snapshot())
                if request.kind is ReportKind.SESSIONS:
                    source.snapshot = replace(source.snapshot, sessions=())
                else:
                    root = replace(source.snapshot.root, title='<script>PRIVATE_TEXT</script>')
                    source.snapshot = replace(source.snapshot, root=root,
                        sessions=tuple(root if s.session_id == root.session_id else s for s in source.snapshot.sessions))
                return ReportService(selection=SourceSelection(source, "v1", (), source.probe()),
                    pricing_provider=FakePricingProvider(), account_provider=None, cache_repository=cache, config=config,
                    now_ms=now, progress=progress)

            result = ReportApplication(factory, clock=lambda: 4000).execute(request)
            sender.send(("result", json.dumps(result.to_json()).encode()))
    finally:
        sender.close()
