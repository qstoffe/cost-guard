"""Host-owned AI Stats slices and bounded requested-scope priority; no analysis."""
from dataclasses import dataclass
import time

from src.reports import ReportKind, ReportRequest
from src.reports.ai_stats import BATCH_SIZE, SLICE_ROOTS

@dataclass(frozen=True, slots=True)
class StatsSlice(ReportRequest):
    observation_ms: int = 0
    scan: str = ''
    slice_roots: int = SLICE_ROOTS
    batch_size: int = BATCH_SIZE


def is_stats(job):
    return job['request'].kind is ReportKind.AI_STATS


def ready(job, scope):
    return any(row['period'] == scope for row in (job.get('result') or {}).get('view', {}).get('ai_stats', ()))


def request(job, key):
    original = job['request']
    if not is_stats(job):
        return original
    job.setdefault('observation_ms', int(time.time() * 1000))
    scope = next((scope for scope in (original.stats_scope, *job.get('goals', ()))
                  if not ready(job, scope)), original.stats_scope)
    return StatsSlice(ReportKind.AI_STATS, stats_scope=scope,
        observation_ms=job['observation_ms'], scan='ai-stats-scan-' + key,
        batch_size=job.get('batch_size', BATCH_SIZE))


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
    job['stalls'] = 0 if completed > previous else job.get('stalls', 0) + 1
    job['covered'] = completed
    if job['stalls'] >= 8:
        job.update(status='failed', error='ai_stats_revision_churn')
    else:
        job.update(status='queued', queued_at=time.monotonic())


def timed_out(job):
    """Only Stats may resume a watchdog failure, with a strictly smaller chunk."""
    size = job.get('batch_size', BATCH_SIZE)
    if is_stats(job) and size > 1:
        job.update(status='queued', batch_size=16 if size > 16 else 1,
                   queued_at=time.monotonic())
    else:
        job.update(status='failed', error='ai_stats_slice_timeout' if is_stats(job) else 'report_timeout')
