"""Real Normal workflow over bounded synthetic history, optionally slowed at work units."""
from pathlib import Path
import json
import tempfile
import time

from src.application import ReportApplication
from src.cache import CacheDatabase, CacheRepository
from src.config import load_configuration
from src.reports import ReportService
from src.sources.selection import SourceSelection
from src.web.jobs import ProgressRelay

from .report_runtime import FakeAccountProvider, FakePricingProvider
from .synthetic_month import SyntheticMonthSource

NOW = 10_000_000


class BatchSource(SyntheticMonthSource):
    def load_session_snapshots(self, ids):
        return {key: self.load_session_snapshot(key) for key in ids}


class AvailableModels:
    def available_model_ids(self):
        return ("gpt-test", "claude-test")


class ModelsWorkload:
    def __init__(self, root, *, delay=0, batched=True, roots=28):
        database = CacheDatabase(Path(root))
        database.initialize()
        self.cache = CacheRepository(database)
        self.config = dict(load_configuration(Path(__file__).resolve().parents[3]).values, timezone="UTC")
        source_type = BatchSource if batched else SyntheticMonthSource
        self.source = source_type(roots, 10, month_start_ms=1000)
        self.delay = delay
        self.analyzed = 0

    def factory(self, now, progress):
        workload = self

        class Service(ReportService):
            def _analyze_snapshot(self, snapshot):
                bundle = super()._analyze_snapshot(snapshot)
                if workload.delay:
                    time.sleep(workload.delay)
                workload.analyzed += 1
                return bundle

        return Service(selection=SourceSelection(self.source, "v1", (), self.source.probe()),
            pricing_provider=FakePricingProvider(), account_provider=FakeAccountProvider(),
            model_availability_source=AvailableModels(), cache_repository=self.cache,
            config=self.config, now_ms=now, progress=progress)

    def application(self):
        return ReportApplication(self.factory, clock=lambda: NOW)


def models_progress_report(sender, request):
    """Spawn-safe production job boundary; no provider/network/personal history."""
    try:
        with tempfile.TemporaryDirectory() as root:
            relay = ProgressRelay(sender)
            result = ModelsWorkload(root, delay=0.22).application().execute(request, progress=relay.observe)
            relay.flush()
            sender.send(("result", json.dumps(result.to_json()).encode()))
    finally:
        sender.close()
