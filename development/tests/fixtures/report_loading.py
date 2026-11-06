"""Manually stepped canonical finite results, never private history/providers."""
from uuid import uuid4
import time

from src.application.projection import project
from src.reports import ReportKind
from .ai_stats_views import stats_result
from .matched_inputs import browser_result
from .model_views import model_report
from .token_mix_views import token_mix_report


class LoadingJobs:
    def __init__(self):
        self.jobs = {}
        self.mode = 'hold'
        self.step = 0
        self.busy = 0

    def submit(self, request):
        if self.busy:
            self.busy -= 1
            raise RuntimeError('busy')
        for key, job in self.jobs.items():
            if job['request'] == request and job['status'] == 'running':
                return key
        if request.kind is ReportKind.AI_STATS:
            result = stats_result(request)
        elif request.kind is ReportKind.COMPARISONS:
            result = browser_result(request)
        else:
            report = model_report(include_model_catalog=True) if request.kind is ReportKind.NORMAL else token_mix_report()
            result = dict(view=project(report).to_json(), source=dict(status='acquired'), error=None,
                observed_at_ms=int(time.time() * 1000))
        key = uuid4().hex
        self.jobs[key] = dict(request=request, status='running', result=result)
        return key

    def snapshot(self, key):
        job = self.jobs.get(key)
        if not job:
            return None
        if self.mode == 'complete' and job['status'] == 'running':
            job['status'] = 'complete'
        stages = ['sampling', 'account-analysis', 'finalizing'] if job['request'].kind is ReportKind.NORMAL else [
            'history-cache', 'history-load', 'finalizing']
        progress = dict(phase='history', stage=stages[min(2, self.step // 2)],
            completed=1 if self.step % 2 == 0 else 9, total=10, sequence=self.step + 1)
        return dict(id=key, status=job['status'], progress=progress,
            result=job['result'] if job['status'] == 'complete' else None, error=None)

    def cancel(self, key):
        if key in self.jobs:
            self.jobs[key]['status'] = 'cancelled'
            return True
        return False

    def readiness(self):
        return dict(http='ready', source='synthetic', analysis='ready', accounts='not_requested')

    def updates(self):
        return dict(readiness=self.readiness(), jobs=[])

    def tick(self):
        pass

    def close(self):
        pass
