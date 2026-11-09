"""Canonical in-memory report composition for pricing browser interaction proof.

This fixture deliberately does not establish process-startup/lifecycle evidence.
"""
import json
from threading import RLock
from unittest.mock import patch
from uuid import uuid4

from src.application import ReportApplication
from src.cache import CacheDatabase, CacheRepository
from src.config import load_configuration
from src.pricing.github_copilot import GitHubCopilotPricingProvider
from src.reports import ReportService
from src.sources.selection import SourceSelection
from src.web.jobs import ModelsPriceRefresh, run_report

from .report_runtime import FakeSource


def models_refresh_report(root, sender, request):
    config = load_configuration(root).values

    def fetch(url, timeout):
        with (root / 'fetches.txt').open('a') as stream:
            stream.write('fetch\n')
        mode = (root / 'pricing-mode.txt').read_text()
        if mode == 'offline':
            raise OSError('synthetic offline')
        if mode == 'invalid':
            return 'invalid upstream document'
        rate = 10 if mode == 'changed' else 1
        rows = [f'GPT-Test | ${rate} | $0.1 | ${rate * 4}']
        rows += [f'GPT-Other-{i} | $1 | $0.1 | $4' for i in range(4)]
        return ('## OpenAI\nModel | Input | Cached input | Output\n'
                '--- | --- | --- | ---\n' + '\n'.join(rows))

    def factory(now, progress):
        source = FakeSource()
        database = CacheDatabase(root)
        database.initialize()
        provider = GitHubCopilotPricingProvider(cache=CacheRepository(database), fetch_text=fetch,
            defer_metadata_refresh=True)
        catalog = provider.refresh_catalog() if isinstance(request, ModelsPriceRefresh) else None
        service = ReportService(selection=SourceSelection(source, 'v1', (), source.probe()),
            pricing_provider=provider, account_provider=None, cache_repository=CacheRepository(database),
            config=config, now_ms=now, progress=progress)
        service.catalog = catalog
        return service

    with patch('src.web.composition.application', return_value=ReportApplication(factory)):
        run_report(sender, request)


class ModelsRefreshJobs:
    """Controlled pending/result states; not production coalescing/bounds proof."""

    def __init__(self, root):
        self.root = root
        self.jobs = {}
        self.lock = RLock()
        self.hold = False

    def submit(self, request):
        with self.lock:
            for key, job in self.jobs.items():
                if job['request'] == request and job['status'] == 'running':
                    return key
            key = uuid4().hex
            self.jobs[key] = dict(id=key, request=request, status='running', progress={'phase':'running'},
                                  polls=0, result=None, error=None)
            return key

    def snapshot(self, key):
        with self.lock:
            job = self.jobs.get(key)
            if job is None:
                return None
            job['polls'] += 1
            if job['status'] == 'running' and job['polls'] > 1 and not self.hold:
                class Sender:
                    def send(self, value):
                        kind, payload = value
                        if kind == 'result':
                            job['result'] = json.loads(payload)
                            job['status'] = 'failed' if job['result']['error'] else 'complete'
                        elif kind == 'error':
                            job.update(status='failed', error=payload)

                    def close(self):
                        pass

                models_refresh_report(self.root, Sender(), job['request'])
            return {name: job[name] for name in ('id', 'status', 'progress', 'result', 'error')}

    def readiness(self):
        return dict(http='ready', analysis='synthetic', source='synthetic', accounts='not_acquired')

    def updates(self):
        return dict(readiness=self.readiness(), jobs=[])

    def tick(self):
        pass

    def cancel(self, key):
        return key in self.jobs

    def close(self):
        self.jobs.clear()
