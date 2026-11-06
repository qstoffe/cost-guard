"""Spawn-safe finite slices over one fixed synthetic history and disposable cache."""
from dataclasses import replace
from decimal import Decimal
import json
import os
from pathlib import Path
import time

from src.application import ReportApplication
from src.cache import CacheDatabase, CacheRepository
from src.pricing.catalog import PricingCatalog
from src.reports import ReportKind, ReportRequest, ReportService
from src.sources.selection import SourceSelection
from src.web.jobs import ProgressRelay
from .report_runtime import FakePricingProvider
from .synthetic_month import SyntheticMonthSource


def slice_report(sender, request):
    if request.kind is not ReportKind.AI_STATS:
        # This fixture owns only Stats. Do not let an unrelated default Models
        # acquisition occupy the one real finite lane before the tested route.
        sender.send(('error', 'synthetic_unrequested_report'))
        sender.close()
        return
    now = request.observation_ms
    root = Path(os.environ['COST_GUARD_STATS_FIXTURE'])
    browser = os.environ.get('COST_GUARD_STATS_BROWSER') == '1'
    pinned = root / 'observation.txt'
    if browser and not pinned.exists():
        pinned.write_text(str(now))
    source_now = int(pinned.read_text()) if browser else now
    database = CacheDatabase(root)
    database.initialize()
    source = SyntheticMonthSource(24 if browser else 9, 3,
        month_start_ms=source_now - (20 if browser else 1) * 86400000,
        today_roots=2 if browser else 0, now_ms=source_now)
    source.snapshots = {sid: replace(snapshot, complete=True) for sid, snapshot in source.snapshots.items()}
    pricing = FakePricingProvider()

    def factory(at, progress):
        service = ReportService(selection=SourceSelection(source, 'v2', (), source.probe()),
            pricing_provider=pricing, account_provider=None,
            cache_repository=CacheRepository(database), config={'timezone': 'UTC'}, now_ms=at, progress=progress)
        service.stats_slice_roots = 2
        service.stats_scan = request.scan
        return service

    if browser:
        seeded = root / 'seeded.txt'
        if not seeded.exists():
            baseline = factory(now, lambda *_: None)
            baseline.stats_slice_roots = None
            baseline.build(ReportRequest(ReportKind.AI_STATS, stats_scope='all'))
            seeded.write_text('Canonical stable coverage before a pricing change')
        pricing.catalog = PricingCatalog(tuple(replace(model,
            tiers=tuple(replace(tier, per_million_output=Decimal(999)) for tier in model.tiers))
            for model in pricing.catalog.models))
        original = source.load_session_snapshot

        def slowed(sid):
            time.sleep(.2)
            return original(sid)

        source.load_session_snapshot = slowed
        source.load_count = 0

    relay = ProgressRelay(sender)
    result = ReportApplication(factory, clock=lambda: now).execute(request, progress=relay.observe).to_json()
    if browser:
        with (root / 'loads.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(dict(scope=request.stats_scope, hydrated=source.load_count,
                completed=(result.get('view') or {}).get('ai_stats_work', {}).get('completed'))) + '\n')
    relay.flush()
    sender.send(('result', json.dumps(result).encode('ascii')))
    sender.close()
