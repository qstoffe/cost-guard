"""Immediate synthetic reports for UI-help auditing, not report-process proof."""
from pathlib import Path
import tempfile
from uuid import uuid4

from src.application import ReportApplication
from src.cache import CacheDatabase, CacheRepository
from src.config import load_configuration
from src.reports import ReportService
from src.sources.selection import SourceSelection

from .report_runtime import FakeSource, FakePricingProvider, FakeAccountProvider


class HelpAuditJobs:
    """Keep UI inspection independent of cancellation-fixture delays and faults."""

    def __init__(self):
        self.jobs = {}

    def submit(self, request):
        with tempfile.TemporaryDirectory() as directory:
            database = CacheDatabase(Path(directory))
            database.initialize()
            config = dict(load_configuration(Path(__file__).resolve().parents[3]).values, timezone="UTC")

            def factory(now, progress):
                source = FakeSource()
                return ReportService(selection=SourceSelection(source, "v1", (), source.probe()),
                    pricing_provider=FakePricingProvider(), account_provider=FakeAccountProvider(),
                    cache_repository=CacheRepository(database), config=config, now_ms=now, progress=progress)

            result = ReportApplication(factory, clock=lambda: 4000).execute(request).to_json()
        key = uuid4().hex
        self.jobs[key] = dict(id=key, status="failed" if result["error"] else "complete",
                              progress=None, result=result, error=None)
        return key

    def snapshot(self, key):
        return self.jobs.get(key)

    def readiness(self):
        return dict(http="ready", analysis="reported", source="synthetic", accounts="reported")

    def updates(self):
        return dict(readiness=self.readiness(), jobs=[])

    def tick(self):
        pass

    def cancel(self, key):
        return key in self.jobs

    def close(self):
        self.jobs.clear()
