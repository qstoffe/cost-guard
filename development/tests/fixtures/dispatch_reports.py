"""Spawn-safe bounded quantum workload; no workstation source or provider access."""
import json
import time
from dataclasses import dataclass, replace
from pathlib import Path

from src.reports import ReportKind
from src.web.report_control import Quantum
from src.web.report_control import ManagedReport


def quantum_report(sender, request):
    quantum = Quantum(sender, .03)
    total = 50 if request.kind is ReportKind.COMPARISONS else 3
    try:
        for completed in range(total):
            quantum.checkpoint()
            time.sleep(.01)
            sender.send(('progress', dict(phase='history', completed=completed + 1, total=total)))
        sender.send(('result', json.dumps(dict(error=None, view=dict(kind=request.kind.value),
            source=dict(status='acquired', observed_at_ms=int(time.time() * 1000)))).encode()))
    finally:
        sender.close()


@dataclass(frozen=True, slots=True)
class HistoryFixture(ManagedReport):
    directory: str = ''
    stall_once: bool = False


def durable_history_report(sender, request):
    """Real compact SQLite checkpoints across fresh finite processes."""
    from development.tests.fixtures.compact_reports import NOW
    from development.tests.fixtures.report_runtime import FakePricingProvider
    from development.tests.fixtures.synthetic_month import SyntheticMonthSource
    from src.cache import CacheDatabase, CacheRepository
    from src.config import load_configuration
    from src.reports import ReportService
    from src.reports.history_work import HistoryContinuation
    from src.sources.selection import SourceSelection

    source = SyntheticMonthSource(10, 1, month_start_ms=NOW - 86400000)
    source.snapshots = {key: replace(value, complete=True) for key, value in source.snapshots.items()}
    database = CacheDatabase(Path(request.directory))
    database.initialize()
    service = ReportService(selection=SourceSelection(source, 'v1', (), source.probe()),
        pricing_provider=FakePricingProvider(), account_provider=None, cache_repository=CacheRepository(database),
        config=dict(load_configuration(Path(__file__).resolve().parents[3]).values, timezone='UTC'),
        now_ms=NOW, cache_token_mix_history=True)
    service.shared_web_evidence = True
    service.history_slice_roots = 4
    service.history_batch_size = 2

    def checkpoint(value):
        sender.send(('checkpoint', value))
        marker = Path(request.directory) / 'stalled-once'
        if request.stall_once and not marker.exists():
            marker.touch()
            time.sleep(30)  # Parent must terminate this child, not extend its watchdog.

    service.history_checkpoint = checkpoint
    try:
        try:
            service.build_token_mix_history()
            result = dict(error=None, view=dict(kind=request.kind.value, roots_read=source.load_count),
                source=dict(status='acquired', identity=request.source_identity))
        except HistoryContinuation:
            result = dict(error=dict(code='history_continue'))
        sender.send(('result', json.dumps(result).encode()))
    finally:
        sender.close()
