"""Host-owned AI Stats slices and bounded requested-scope priority; no analysis."""
from dataclasses import dataclass
import time

from src.reports import ReportKind, ReportRequest
from src.reports.ai_stats import BATCH_SIZE, SLICE_ROOTS
from .report_control import ManagedReport

@dataclass(frozen=True, slots=True)
class StatsSlice(ReportRequest):
    observation_ms: int = 0
    scan: str = ''
    slice_roots: int = SLICE_ROOTS
    batch_size: int = BATCH_SIZE


@dataclass(frozen=True, slots=True)
class ManagedStatsSlice(ManagedReport):
    """A resumable stats slice also participates in host quantum arbitration."""
    observation_ms: int = 0
    scan: str = ''
    slice_roots: int = SLICE_ROOTS
    batch_size: int = BATCH_SIZE


def is_stats(job):
    return job['request'].kind is ReportKind.AI_STATS


def ready(job, scope):
    view = (job.get('result') or {}).get('view', {})
    coverage = view.get('ai_stats_work', {}).get('scopes') if view.get('ai_stats_work') else None
    return (coverage.get(scope, {}).get('ready', False) if coverage is not None else
            any(row['period'] == scope for row in view.get('ai_stats', ())))


def request(job, key):
    original = job['request']
    if not is_stats(job):
        return original
    job.setdefault('observation_ms', int(time.time() * 1000))
    scope = next((scope for scope in (original.stats_scope, *job.get('goals', ()))
                  if not ready(job, scope)), original.stats_scope)
    cls = ManagedStatsSlice if isinstance(original, ManagedReport) else StatsSlice
    options = dict(source_identity=original.source_identity) if isinstance(original, ManagedReport) else {}
    return cls(ReportKind.AI_STATS, stats_scope=scope,
        observation_ms=job['observation_ms'], scan='ai-stats-scan-' + key,
        batch_size=job.get('batch_size', BATCH_SIZE), **options)


def accept(job, result):
    """Each slice replaces coverage atomically; old milestones cannot survive churn."""
    job['result'] = result
    work = (result.get('view') or {}).get('ai_stats_work')
    if result['error'] or not work:
        job['status'] = 'failed' if result['error'] else 'complete'
        return
    if all(ready(job, scope) for scope in job.get('goals', (job['request'].stats_scope,))):
        job['status'] = 'complete'
        return
    completed = work['completed']
    previous = job.get('covered', -1)
    job['stalls'] = 0 if completed > previous else min(6, job.get('stalls', 0) + 1)
    job['covered'] = completed
    # Settling a fun snapshot is not a claim that every root was scanned. Leave
    # remaining/ready truthful; a later scheduled refresh can improve the figures.
    if work.get('checkpoint_error') == 'ai_stats_checkpoint_unavailable' or job['stalls'] >= 6:
        job['status'] = 'complete'
        return
    now = time.monotonic()
    delay = min(60, 2 ** min(6, job['stalls'])) if job['stalls'] else 0
    if work.get('checkpoint_error') == 'ai_stats_checkpoint_busy':
        delay = max(2, delay)
    job.update(status='queued', queued_at=now, not_before=now + delay)
