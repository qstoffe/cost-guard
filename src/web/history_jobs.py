"""Finite history slices: durable coverage and quiet retries, no lifetime deadline."""
import re
import time

from src.reports import ReportKind
from .report_control import ManagedReport

KINDS = {ReportKind.TOKEN_MIX, ReportKind.COMPARISONS}


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


def resume(job):
    proof = job.pop('checkpoint', None)
    previous = job.get('continued')
    steps = job.get('history_steps', 0)
    advancing = proof and (previous is None or proof['completed'] > previous['completed'])
    stalls = 0 if advancing else min(6, job.get('history_stalls', 0) + 1)
    if proof is None:
        # A continuation without its promised durable receipt is a protocol
        # defect, not a slow calculation. Never pretend evidence was saved.
        job.update(status='failed', error='history_no_progress')
        return
    delay = 0 if advancing else min(60, 2 ** stalls)
    now = time.monotonic()
    job.update(status='queued', result=None, continued=proof, history_steps=steps + 1,
               history_stalls=stalls, queued_at=now, not_before=now + delay)
