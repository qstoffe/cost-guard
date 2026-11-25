"""Canonical synthetic historical mixes and finite jobs for browser refresh proof."""
from decimal import Decimal
import time
from uuid import uuid4

from src.analysis.token_mix import priced_token_mix
from src.analysis.timezones import calendar_periods
from src.application.projection import project
from src.domain import ModelRef, TokenUsage
from src.reports.models import ModelTokenMixProjection, PublisherTokenMixProjection, ReportKind, ReportProjection
from .web_help_reports import HelpAuditJobs


def token_mix_report(generation=1):
    def valuation(model, tokens):
        if model.model == 'unknown':
            return None
        return tuple(Decimal(value) / 1000000 for value in
            (tokens.input, tokens.cache_read * 2, tokens.cache_write * 3, (tokens.output + tokens.reasoning) * 4))

    models, publishers, requests = [], [], []
    observed_total = [0] * 4
    for index in range(65):
        model = ModelRef('synthetic', 'unknown' if index == 63 else f'model-{index}')
        usage = TokenUsage(input=100 + index * 3, cache_read=65 - index, cache_write=index,
            output=(index + 1 + (generation - 1) * 10000) * 7, reasoning=2)
        if index == 61:
            usage = TokenUsage(input=9007199254740993, output=3)
        elif index == 62:
            usage = TokenUsage(input=9007199254740992, output=3)
        elif index == 64:
            usage = TokenUsage(input=99, known_fields=('input',))
        items = [(model, usage)] * (index + 1)
        requests.extend(items)
        mix = priced_token_mix(items, valuation, sample_size=1)
        observed = tuple((getattr(usage, name) if name in usage.known_fields else 0) * len(items)
                         for name in ('input', 'cache_read', 'cache_write', 'output'))
        observed = (*observed[:3], observed[3] + usage.reasoning * len(items))
        observed_total = [a + b for a, b in zip(observed_total, observed)]
        models.append(ModelTokenMixProjection(f'Synthetic model {index:02d} — Full readable model name', 1, index + 1, mix,
            f'Publisher {index:02d}', f'model-{index}', observed))
        publishers.append(PublisherTokenMixProjection(f'Publisher {index:02d}', 1, index + 1, mix, observed))
    return ReportProjection(ReportKind.TOKEN_MIX, 'Token Mix', 'SYNTHETIC', (),
        token_mix=priced_token_mix(requests, valuation, sample_size=65),
        model_token_mix=tuple(models), publisher_token_mix=tuple(publishers),
        token_mix_observed_totals=tuple(observed_total))


class TokenMixJobs:
    def __init__(self):
        self.jobs = {}
        self.generation = 0
        self.other = HelpAuditJobs()

    def submit(self, request):
        if request.kind is not ReportKind.TOKEN_MIX:
            return self.other.submit(request)
        self.generation += 1
        key = uuid4().hex
        report = token_mix_report(self.generation)
        observed = int(time.time() * 1000)
        from dataclasses import replace
        start = dict(calendar_periods('UTC', observed))[request.token_mix_scope]
        report = replace(report, token_mix_period=dict(period=request.token_mix_scope,
            start_ms=start, end_ms=observed))
        result = dict(schema_version=1, instance_id='synthetic', sequence=self.generation,
            observed_at_ms=observed, source=dict(status='acquired', observed_at_ms=observed),
            view=project(report).to_json(), error=None)
        self.jobs[key] = dict(id=key, status='running', progress=dict(phase='history', completed=0), result=result,
            error=None, ready_at=time.monotonic() + (2 if self.generation > 1 else 0))
        return key

    def snapshot(self, key):
        job = self.jobs.get(key)
        if not job:
            return self.other.snapshot(key)
        if time.monotonic() >= job['ready_at']:
            job['status'] = 'complete'
        return {**job, 'result': job['result'] if job['status'] == 'complete' else None}

    def readiness(self):
        return dict(http='ready', analysis='reported', source='synthetic', accounts='not_requested')

    def updates(self):
        return dict(readiness=self.readiness(), jobs=[])

    def tick(self):
        pass

    def cancel(self, key):
        return key in self.jobs

    def close(self):
        self.jobs.clear()
        self.other.close()
