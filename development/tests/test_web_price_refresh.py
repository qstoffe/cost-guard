"""Strict upstream provenance, coherent repricing and Web-only job isolation."""
from decimal import Decimal
import json
from multiprocessing.reduction import ForkingPickler
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from development.tests.fixtures.report_runtime import FakeSource
from src.cache import CacheDatabase, CacheRepository
from src.pricing.base import PricingUnavailableError
from src.pricing.github_copilot import (CACHE_KEY, CACHE_NAMESPACE, DOCS_API_BODY,
    PRICING_ARTICLE_PATH, GitHubCopilotPricingProvider)
from src.reports import ReportRequest
from src.sources.selection import SourceSelection
from src.web.composition import application
from src.web.jobs import ModelsPriceRefresh, ReportJobs


def pricing_document(rate=1):
    rows = [f'GPT-Test | ${rate} | $0.1 | ${rate * 4}']
    rows += [f'GPT-Other-{i} | $1 | $0.1 | $4' for i in range(4)]
    return ('## OpenAI\nModel | Input | Cached input | Output\n'
            '--- | --- | --- | ---\n' + '\n'.join(rows))


class PriceRefreshTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = CacheDatabase(Path(self.directory.name))
        self.database.initialize()
        self.cache = CacheRepository(self.database)
        self.now = 1793952000000
        self.fetch = Mock(return_value=pricing_document())
        self.provider = GitHubCopilotPricingProvider(cache=self.cache, fetch_text=self.fetch,
            now_ms=lambda: self.now, defer_metadata_refresh=True)

    def test_explicit_refresh_bypasses_warm_cache_and_unchanged_fetch_advances_only_observation(self):
        first = self.provider.get_catalog()
        self.now += 1000
        self.assertIs(first, self.provider.get_catalog())
        self.fetch.reset_mock()

        refreshed = self.provider.refresh_catalog()

        self.fetch.assert_called_once_with(DOCS_API_BODY + PRICING_ARTICLE_PATH, 20)
        self.assertEqual(first.source_revision, refreshed.source_revision)
        self.assertEqual(first.models, refreshed.models)
        self.assertEqual(self.now, refreshed.retrieved_at_ms)
        self.assertEqual(first.retrieved_at_ms + 1000, refreshed.retrieved_at_ms)

    def test_failed_or_invalid_forced_fetch_never_claims_cached_catalog_as_fresh(self):
        original = self.provider.get_catalog()
        payload = self.cache.get(CACHE_NAMESPACE, CACHE_KEY).payload
        self.now += 1000
        for failure in (OSError('offline'), 'not a price list'):
            with self.subTest(failure=type(failure).__name__):
                self.fetch.side_effect = failure if isinstance(failure, Exception) else None
                self.fetch.return_value = failure

                with self.assertRaises(PricingUnavailableError):
                    self.provider.refresh_catalog()

                self.assertEqual(payload, self.cache.get(CACHE_NAMESPACE, CACHE_KEY).payload)
                self.assertEqual(original, self.provider.get_catalog(force=True), 'legacy fail-soft behavior remains')

    def test_isolated_refresh_rebuilds_prices_ratios_and_sample_valuation_without_accounts_or_watch_repricing(self):
        pinned_watch = self.provider.get_catalog()
        source = FakeSource()
        selection = SourceSelection(source, 'v1', (), source.probe())

        def provider(**kwargs):
            return GitHubCopilotPricingProvider(**kwargs, fetch_text=self.fetch,
                now_ms=lambda: self.now, defer_metadata_refresh=True)

        with patch('src.web.composition.CacheDatabase', return_value=self.database), \
                patch('src.web.composition.SourceSelector') as selector, \
                patch('src.web.composition.GitHubCopilotPricingProvider', side_effect=provider), \
                patch('src.bootstrap._account_providers') as accounts, \
                patch('src.bootstrap._model_availability_source', return_value=None):
            selector.return_value.select.return_value = selection
            first = application(ModelsPriceRefresh()).execute(ModelsPriceRefresh()).to_json()
            self.now += 1000
            self.fetch.return_value = pricing_document(10)

            refreshed = application(ModelsPriceRefresh()).execute(ModelsPriceRefresh()).to_json()

        self.assertIsNone(first['error'])
        self.assertIsNone(refreshed['error'])
        accounts.assert_not_called()
        before, after = first['view'], refreshed['view']
        self.assertGreater(after['model_comparison_sample_size'], 0)
        old = next(row for row in before['model_catalog']['rows'] if row['model'] == 'GPT-Test')
        new = next(row for row in after['model_catalog']['rows'] if row['model'] == 'GPT-Test')
        self.assertGreater(Decimal(new['relative_cost']), Decimal(old['relative_cost']))
        self.assertNotEqual(before['token_mix']['costs'], after['token_mix']['costs'])
        self.assertEqual(self.now, after['pricing_retrieved_at_ms'])
        self.assertEqual(Decimal(1), pinned_watch.resolve('gpt-test').per_million_input)
        self.assertEqual(pinned_watch.retrieved_at_ms, self.provider.get_catalog().retrieved_at_ms)

    def test_concurrent_tabs_coalesce_one_refresh_but_not_an_ordinary_cached_report(self):
        jobs = ReportJobs()
        self.addCleanup(jobs.close)

        refresh = jobs.submit(ModelsPriceRefresh())
        duplicate = jobs.submit(ModelsPriceRefresh())
        normal = jobs.submit(ReportRequest())

        self.assertEqual(refresh, duplicate)
        self.assertNotEqual(refresh, normal)
        jobs._jobs[refresh].update(status='failed')
        self.assertNotEqual(refresh, jobs.submit(ModelsPriceRefresh()), 'failure permits explicit retry')

    def test_refresh_marker_survives_multiprocessing_serialization(self):
        restored = ForkingPickler.loads(ForkingPickler.dumps(ModelsPriceRefresh()))

        self.assertIs(type(restored), ModelsPriceRefresh)
        self.assertEqual(ModelsPriceRefresh(), restored)
        self.assertNotEqual(ReportRequest(), restored)

    def test_completed_price_job_does_not_claim_account_acquisition(self):
        jobs = ReportJobs()
        self.addCleanup(jobs.close)
        key = jobs.submit(ModelsPriceRefresh())
        receiver, process = Mock(), Mock()
        receiver.poll.return_value = True
        receiver.recv.return_value = ('result', json.dumps({'error':None, 'source':{'status':'acquired'}}).encode())
        process.is_alive.return_value = False
        jobs._active = key, process, receiver, time.monotonic()

        jobs.tick()

        self.assertEqual('complete', jobs.snapshot(key)['status'])
        self.assertEqual('not_requested', jobs.readiness()['accounts'])


if __name__ == '__main__':
    unittest.main()
