"""Finite history continuation: durable coverage, bounded attempts, no watchdog waiver."""
import re
import time

from src.reports import ReportKind
from .report_control import ManagedReport

KINDS = {ReportKind.TOKEN_MIX, ReportKind.COMPARISONS}
MAX_STEPS = 32


def managed(job):
    return isinstance(job['request'], ManagedReport) and job['request'].kind in KINDS


def checkpoint(job, value):
    if (not managed(job) or not isinstance(value, dict) or set(value) != {'signature', 'completed', 'total'}
            or not isinstance(value['signature'], str) or not re.fullmatch('[0-9a-f]{64}', value['signature'])
            or type(value['completed']) is not int or type(value['total']) is not int
            or not 0 < value['completed'] <= value['total'] <= 100_000):
        raise ValueError('invalid_history_checkpoint')
    previous = job.get('checkpoint')
    if previous and (previous['signature'] != value['signature'] or previous['completed'] >= value['completed']):
        raise ValueError('invalid_history_progress')
    job['checkpoint'] = value


def resume(job, *, timeout=False):
    proof = job.pop('checkpoint', None)
    previous = job.get('continued')
    steps = job.get('history_steps', 0)
    changed = previous and proof and previous['signature'] != proof['signature']
    advancing = proof and (previous is None or proof['completed'] > previous['completed'])
    churn = 0 if advancing else job.get('history_churn', 0) + bool(changed)
    increased = proof and (previous is None or changed or proof['completed'] > previous['completed'])
    if steps >= MAX_STEPS or churn >= 3 or not increased:
        code = ('history_resource_limit' if steps >= MAX_STEPS else 'history_revision_churn' if churn >= 3 else
                'history_slice_timeout' if timeout else 'history_no_progress')
        job.update(status='failed', error=code)
        return
    job.update(status='queued', result=None, continued=proof, history_steps=steps + 1,
               history_churn=churn, queued_at=time.monotonic())
    if timeout:
        job['history_batch_size'] = 16 if job.get('history_batch_size', 64) > 16 else 1
