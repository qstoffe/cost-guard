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


def evidence_views():
    """Canonical, explicitly synthetic period states, with no browser-invented causes."""
    from decimal import Decimal
    from src.analysis.ai_stats import StatsRoot, period_stats
    from src.analysis.models import TraceEntry
    from src.application.projection import project
    from src.domain import ModelRef, TokenUsage
    from src.reports import ReportRequest
    from src.reports.models import ReportProjection

    now = int(time.time() * 1000)
    at = now - 3_600_000
    entry = TraceEntry('root', 'prompt', 'message', None, at, 0,
                       ModelRef('synthetic', 'model'), None, TokenUsage(input=4))
    root = StatsRoot('root', 'Synthetic record', (entry,), ((at, 3_600_000, False),))
    missing = replace(root, entries=(replace(entry, tokens=TokenUsage(input=4, known_fields=())),))
    base = stats_result(ReportRequest(ReportKind.AI_STATS, stats_scope='all'))
    cases = (
        ('complete', (root,), True, Decimal(4)), ('empty', (), True, Decimal(4)),
        ('source-gap', (root,), False, Decimal(4)),
        ('unknown-duration', (replace(root, intervals=((at, None, False),)),), True, Decimal(4)),
        ('missing-price', (root,), True, None), ('missing-telemetry', (missing,), True, Decimal(4)),
        ('pending-usage', (replace(root, cost_pending=True),), True, Decimal(4)),
        ('provisional', (replace(root, intervals=((at, 3_600_000, True),)),), True, Decimal(4)),
        ('observed-time', (replace(root, intervals=((at, 1_800_000, False), (at - 86_400_000, None, False))),), True, Decimal(4)),
    )
    result = []
    for name, roots, complete, price in cases:
        period = period_stats(roots, lambda *_: price, period='all', start=None, now=now,
                              zone='UTC', source_complete=complete)
        view = project(ReportProjection(ReportKind.AI_STATS, 'AI Stats', 'SYNTHETIC', ai_stats=(period,),
            ai_stats_work=dict(scopes={period.period: dict(ready=True)}))).to_json()
        result.append(dict(name=name, result={**base, 'view': view}))
    # Fixed seven local date slots; these are calculated in Python, never in JS.
    from .active_hour import epoch
    fixed_now, start = epoch('2026-11-08T20:00:00+00:00'), epoch('2026-11-02T06:00:00+00:00')
    for name, hours, period_name, clock, stamp in (
        ('three-rates', 28, '7-days', fixed_now, start),
        ('faster-robot', 7, '7-days', fixed_now, start),
        ('no-workdays', 4, 'today', epoch('2026-11-07T12:00:00+00:00'), epoch('2026-11-07T06:00:00+00:00'))):
        synthetic = replace(root, entries=(replace(entry, completed_at_ms=stamp),),
                            intervals=((stamp, hours * 3_600_000, False),))
        period = period_stats((synthetic,), lambda *_: Decimal(840), period=period_name,
            start=clock - 7 * 86_400_000 if period_name == '7-days' else epoch('2026-11-06T23:00:00+00:00'),
            now=clock, zone='Europe/Stockholm')
        view = project(ReportProjection(ReportKind.AI_STATS, 'AI Stats', 'SYNTHETIC', ai_stats=(period,),
            ai_stats_work=dict(scopes={period.period: dict(ready=True)}))).to_json()
        result.append(dict(name=name, result={**base, 'view': view}))
    return result


def stats_result(request):
    with tempfile.TemporaryDirectory() as tmp:
        database = CacheDatabase(Path(tmp))
        database.initialize()
        source = SyntheticMonthSource(3, 5, month_start_ms=int(time.time() * 1000) - 86400000)
        # A literal hostile title must remain text in the two record links.
        for sid, snapshot in tuple(source.snapshots.items()):
            root = replace(snapshot.root, title='Quest <img src=x onerror=alert(1)> — ' + sid)
            source.snapshots[sid] = replace(snapshot, root=root, sessions=(root,), complete=True)

        def factory(now, progress):
            return ReportService(selection=SourceSelection(source, 'v2', (), source.probe()),
                pricing_provider=FakePricingProvider(), account_provider=None,
                cache_repository=CacheRepository(database), config={'timezone': 'UTC'}, now_ms=now, progress=progress)

        result = ReportApplication(factory).execute(request).to_json()
        # Keep the baseline at twelve cards; optional matched facts have separate probes.
        for period in result['view']['ai_stats']:
            period['matched'] = None
        return result


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
