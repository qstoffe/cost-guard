"""Run real Web/Live owners over the benchmark's owned, local source fixture."""
from collections import Counter
import json
from pathlib import Path
import shutil
import sys
from threading import Lock, current_thread

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.integration.serve_web_sessions import CaptureJobs
from development.tests.fixtures.report_runtime import FakePricingProvider
from development.tools.benchmark_session_period_change import NOW, fixture
from src.cache import CacheDatabase, CacheRepository
from src.reports import ReportService
from src.sources.selection import SourceSelection
from src.watch.acquisition import LiveAcquisition
from src.watch.web_coordinator import WebWatchCoordinator
from src.web.host import WebHost


def main():
    root = Path(sys.argv[1])
    (root / 'config').mkdir()
    shutil.copyfile(ROOT / 'config/default-config.jsonc', root / 'config/default-config.jsonc')
    source = fixture(302)
    source.source_instance = 'cold-period-fixture'
    database = CacheDatabase(root)
    database.initialize()
    cache, pricing = CacheRepository(database), FakePricingProvider()
    selection = SourceSelection(source, 'v1', (), source.probe())
    config = dict(timezone='UTC', watchStartupEarlierSessions=2)
    reads, lock = Counter(), Lock()
    original_load = source.load_session_snapshot

    def load(key):
        with lock:
            reads[current_thread().name.split('_')[0], key] += 1
        return original_load(key)

    source.load_session_snapshot = load

    def service(now):
        return ReportService(selection=selection, pricing_provider=pricing, account_provider=None,
            cache_repository=cache, config=config, now_ms=now)

    def driver():
        return LiveAcquisition(WebWatchCoordinator(selection=selection, report_service=service(NOW),
            config=config, service_factory=service, clock_ms=lambda: NOW, record_observations=False))

    host = WebHost(root, jobs=CaptureJobs(), live_factory=driver)
    host.live.catalog.clock_ms = lambda: NOW
    host.start()
    host.publish_ready()
    print(json.dumps(dict(url=host.browser_url())), flush=True)
    try:
        for line in sys.stdin:
            command = json.loads(line)['command']
            if command == 'stop':
                break
            if command != 'stats':
                raise ValueError('unsupported_fixture_command')
            with lock:
                catalog_reads = {key: value for (lane, key), value in reads.items()
                                 if lane == 'cost-guard-session-index'}
            with host.live.catalog.lock:
                counts = dict(host.live.catalog.metrics)
                released = any(lease.get('released') and not lease.get('navigation')
                               for lease in host.live.catalog.lease_pages.leases.values())
            print(json.dumps(dict(catalog_reads=catalog_reads, metrics=counts, acknowledged=released)), flush=True)
    finally:
        host.close()


if __name__ == '__main__':
    main()
