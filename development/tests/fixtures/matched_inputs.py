"""Deterministic repeated first inputs with later work, independent root identities."""
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

BROWSER_START = int(time.time() * 1000) - 86400000


def source(groups=11, repeats=3, *, start=1_790_000_000_000):
    result = SyntheticMonthSource(groups * repeats, 2, month_start_ms=start)
    for index, (sid, snapshot) in enumerate(tuple(result.snapshots.items())):
        first = snapshot.messages[0]
        part = replace(first.parts[0], data={'text': f'Exact first input {index // repeats}\n  preserve whitespace'})
        duration = (index % repeats + 1) * 100
        messages = (replace(first, parts=(part,)), replace(snapshot.messages[1], completed_at_ms=first.created_at_ms + duration),
                    *snapshot.messages[2:])
        root = replace(snapshot.root, title=f'Quest <img src=x onerror=alert(1)> {index}',
                       archived_at_ms=start if index % repeats == 0 else None)
        invocations = (replace(snapshot.invocations[0], completed_at_ms=first.created_at_ms + duration),
                       replace(snapshot.invocations[1], tokens=replace(snapshot.invocations[1].tokens, input=999999)))
        result.snapshots[sid] = replace(snapshot, root=root, sessions=(root,), messages=messages,
            parts=tuple(p for message in messages for p in message.parts), invocations=invocations, complete=True)
    return result


def browser_result(request, *, groups=11):
    with tempfile.TemporaryDirectory() as tmp:
        database = CacheDatabase(Path(tmp)); database.initialize()
        history = source(groups, start=BROWSER_START)

        def factory(now, progress):
            return ReportService(selection=SourceSelection(history, 'v2', (), history.probe()),
                pricing_provider=FakePricingProvider(), account_provider=None,
                cache_repository=CacheRepository(database), config={'timezone': 'UTC'}, now_ms=now, progress=progress)

        return ReportApplication(factory).execute(request).to_json()


def finite_comparisons(sender, request):
    sender.send(('result', json.dumps(browser_result(request)).encode('ascii')))
    sender.close()


class ComparisonsJobs(TokenMixJobs):
    """Actual canonical projections, immediate fixture transport with optional delay."""
    def __init__(self, *, groups=11):
        super().__init__()
        self.groups = groups

    def submit(self, request):
        if request.kind not in (ReportKind.COMPARISONS, ReportKind.AI_STATS):
            return super().submit(request)
        key = uuid4().hex
        self.jobs[key] = dict(id=key, status='running', error=None,
            progress=dict(phase='history', completed=1, total=self.groups * 3), result=browser_result(request, groups=self.groups),
            ready_at=time.monotonic() + .2)
        return key
