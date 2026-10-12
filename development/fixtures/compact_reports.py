"""Cache-backed report service factory, fixed model availability and plain report rendering."""
from __future__ import annotations

from datetime import datetime, timezone
import io
from pathlib import Path
import tempfile

from development.fixtures.report_runtime import FakePricingProvider, FakeSource
from src.cache import CacheDatabase, CacheRepository
from src.config import load_configuration
from src.presentation import ReportRenderer
from src.reports import ReportService
from src.sources.selection import SourceSelection

ROOT = Path(__file__).resolve().parents[2]
START = int(datetime(2026, 9, 30, 23, 50, tzinfo=timezone.utc).timestamp() * 1000)
NOW = START + 2 * 86_400_000


class Availability:
    def __init__(self, ids=("openai/gpt-test",)):
        self.ids = ids
        self.calls = 0

    def available_model_ids(self):
        self.calls += 1
        return self.ids


def rendered(report, config=None, *, width=180, color=False):
    stream = io.StringIO()
    ReportRenderer(config or {"timezone": "UTC"}, stream=stream,
                   terminal_width=width, color_enabled=color).render(report)
    return stream.getvalue()


def report_service(test, source=None, *, availability=None, accounts=(), now_ms=NOW):
    """Fresh V2-labelled service over a disposable cache that ``test`` cleans up."""
    tmp = tempfile.TemporaryDirectory()
    test.addCleanup(tmp.cleanup)
    db = CacheDatabase(Path(tmp.name)); db.initialize()
    source = source or FakeSource()
    config = dict(load_configuration(ROOT).values)
    config["timezone"] = "UTC"
    return ReportService(
        selection=SourceSelection(source, "v2", ("Source-wide warning",), source.probe()),
        pricing_provider=FakePricingProvider(), account_provider=None,
        account_providers=accounts, cache_repository=CacheRepository(db),
        config=config, now_ms=now_ms,
        model_availability_source=availability or Availability(),
    )
