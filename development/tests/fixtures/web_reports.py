"""Spawn-safe synthetic report owner for HTTP and cancellation tests."""
import json
from dataclasses import replace
from pathlib import Path
import tempfile
import time

from src.application import ReportApplication
from src.cache import CacheDatabase, CacheRepository
from src.config import load_configuration
from src.reports import ReportKind, ReportService
from src.sources.selection import SourceSelection
from src.sources.errors import FailureCode, SourceUnavailableError

from .report_runtime import FakeSource, FakePricingProvider
from .session_snapshots import make_snapshot


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
