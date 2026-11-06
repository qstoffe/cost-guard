"""Spawn-safe canonical AI Stats/Token Mix data for authenticated browser probes."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import time
from uuid import uuid4

from src.application import ReportApplication
from src.cache import CacheDatabase, CacheRepository
from src.reports import ReportKind, ReportService
from src.sources.selection import SourceSelection
from .report_runtime import FakePricingProvider
from .synthetic_month import SyntheticMonthSource
from .token_mix_views import TokenMixJobs


def stats_result(request):
    with tempfile.TemporaryDirectory() as tmp:
        database = CacheDatabase(Path(tmp))
        database.initialize()
        source = SyntheticMonthSource(3, 5, month_start_ms=int(time.time() * 1000) - 86400000)
        # A literal hostile title must remain text in the two record links.
        for sid, snapshot in tuple(source.snapshots.items()):
            root = replace(snapshot.root, title='Quest <img src=x onerror=alert(1)> — ' + sid)
            source.snapshots[sid] = replace(snapshot, root=root, sessions=(root,))

        def factory(now, progress):
            return ReportService(selection=SourceSelection(source, 'v2', (), source.probe()),
                pricing_provider=FakePricingProvider(), account_provider=None,
                cache_repository=CacheRepository(database), config={'timezone': 'UTC'}, now_ms=now, progress=progress)

        return ReportApplication(factory).execute(request).to_json()


def stats_report(sender, request):
    sender.send(('result', json.dumps(stats_result(request)).encode('ascii')))
    sender.close()


class AIStatsJobs(TokenMixJobs):
    """Browser UI fixture only; actual process admission has independent tests."""

    hold_all = False

    def submit(self, request):
        if request.kind is not ReportKind.AI_STATS:
            return super().submit(request)
        for key, job in self.jobs.items():
            if job.get('request') == request and job['status'] in ('running', 'complete'):
                return key
        key = uuid4().hex
        self.jobs[key] = dict(id=key, request=request, status='running', error=None,
            progress=dict(phase='history', completed=0), result=stats_result(request),
            ready_at=time.monotonic() + (60 if self.hold_all and request.stats_scope == 'all' else .2))
        return key

    def updates(self):
        return dict(readiness=self.readiness(), jobs=[])

    def snapshot(self, key):
        job = self.jobs.get(key)
        value = job if job and job['status'] == 'cancelled' else super().snapshot(key)
        return {name: item for name, item in value.items() if name != 'request'} if value else None

    def cancel(self, key):
        if key in self.jobs:
            self.jobs[key].update(status='cancelled', result=None)
            return True
        return self.other.cancel(key)
