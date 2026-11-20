"""Strict upstream provenance, coherent repricing and Web-only job isolation."""
from dataclasses import replace
from decimal import Decimal
import json
from multiprocessing.reduction import ForkingPickler
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from development.tests.fixtures.model_views import model_report
from development.tests.fixtures.report_runtime import FakeSource
from src.application.projection import project
from src.cache import CacheDatabase, CacheRepository
from src.pricing.base import PricingUnavailableError
from src.pricing.catalog import PricingCatalog
from src.pricing.github_copilot import (CACHE_KEY, CACHE_NAMESPACE, DOCS_API_BODY,
    PRICING_ARTICLE_PATH, GitHubCopilotPricingProvider)
from src.reports import ReportRequest, ReportService
from src.reports.model_comparison import web_model_catalog
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
                retained = self.provider.get_catalog(force=True)
                self.assertEqual(original, retained, 'legacy fail-soft behavior remains')
                self.assertTrue(retained.reference_stale, 'failed fetch qualifies explanatory evidence, not rates')
                self.assertEqual(original.analysis_signature, retained.analysis_signature)
                self.assertNotEqual(original.diagnostic_signature, retained.diagnostic_signature)

    def test_metadata_only_refresh_cannot_clear_failed_price_observation(self):
        original = self.provider.get_catalog()
        self.now += 1000
        self.fetch.side_effect = OSError('offline')
        retained = self.provider.get_catalog(force=True)

        with patch.object(self.provider, '_enrich', side_effect=lambda models, previous, **kwargs: models):
            metadata_only = self.provider.refresh_release_metadata()

        self.assertTrue(retained.reference_stale)
        self.assertTrue(metadata_only.reference_stale)
        self.assertEqual(original.analysis_signature, metadata_only.analysis_signature)
        self.assertEqual(original.retrieved_at_ms, metadata_only.retrieved_at_ms)
        self.fetch.side_effect = None

        verified = self.provider.refresh_catalog()

        self.assertFalse(verified.reference_stale)
        self.assertEqual(original.analysis_signature, verified.analysis_signature)

    def test_published_categories_stay_with_model_and_agree_across_tiers(self):
        document = """## OpenAI
| Model | Input | Cached input | Output | Cache write | Category | Threshold (input tokens) |
| --- | --- | --- | --- | --- | --- | --- |
| GPT-Test | $1 | $0.1 | $4 | $1.25 | Powerful | ≤ 200K |
| GPT-Test | $2 | $0.2 | $8 | $2.50 | Powerful | > 200K |
| GPT-Test Mini | $1 | $0.1 | $4 | $1.25 | Lightweight | |
| GPT-Test Plus | $1 | $0.1 | $4 | $1.25 | Versatile | |
| GPT-Conflict | $1 | $0.1 | $4 | $1.25 | Powerful | ≤ 200K |
| GPT-Conflict | $2 | $0.2 | $8 | $2.50 | Versatile | > 200K |
| GPT-Legacy | $1 | $0.1 | $4 | $1.25 | | |
| GPT-Future | $1 | $0.1 | $4 | $1.25 | Future Tier | |
| GPT-Long | $1 | $0.1 | $4 | $1.25 | CATEGORY_TOO_LONG | |
| GPT-Control | $1 | $0.1 | $4 | $1.25 | A\u202eB | |
"""
        self.fetch.return_value = document.replace("CATEGORY_TOO_LONG", "A" * 65)
        expected = {"GPT-Test": "Powerful", "GPT-Test Mini": "Lightweight", "GPT-Test Plus": "Versatile",
                    "GPT-Conflict": None, "GPT-Legacy": None, "GPT-Future": "Future Tier",
                    "GPT-Long": None, "GPT-Control": None}

        fetched = self.provider.refresh_catalog()

        self.fetch.assert_called_once_with(DOCS_API_BODY + PRICING_ARTICLE_PATH, 20)
        cached_categories = {**expected, "GPT-Long": "A" * 65, "GPT-Control": "A\u202eB"}
        self.assertEqual(cached_categories, {
            model.model.display_name: model.metadata.get("category") for model in fetched.models})
        cache = self.cache.get(CACHE_NAMESPACE, CACHE_KEY).payload
        self.assertEqual(cached_categories, {
            model["display"]: model["metadata"].get("category") for model in cache["models"]})

        def web_rows(catalog):
            selected = PricingCatalog((catalog.resolve_reference("GPT-Test"),))
            projection = web_model_catalog((), catalog, selected, now_ms=self.now, cache_repository=None)
            view = project(replace(model_report(), model_catalog=projection)).to_json()
            return {row["model"]: row for row in view["model_catalog"]["rows"]}

        offline = Mock(side_effect=OSError("offline"))
        reader = GitHubCopilotPricingProvider(cache=self.cache, fetch_text=offline, now_ms=lambda: self.now,
                                             defer_metadata_refresh=True)
        warm = reader.get_catalog()
        offline.assert_not_called()
        stale = reader.get_catalog(force=True)
        self.assertTrue(stale.reference_stale)
        for catalog in (fetched, warm, stale):
            with self.subTest(stale=catalog.reference_stale, from_cache=catalog is not fetched):
                rows = web_rows(catalog)
                self.assertEqual(expected, {name: row["category"] for name, row in rows.items()})
                self.assertEqual(["GPT-Test"], [name for name, row in rows.items() if row["selectable"]])
                self.assertEqual(2, len(rows["GPT-Test"]["relative_levels"]))
                self.assertEqual(2, len(rows["GPT-Conflict"]["relative_levels"]))
                self.assertIsNotNone(rows["GPT-Legacy"]["relative_cost"])

        self.fetch.reset_mock()
        self.fetch.return_value = self.fetch.return_value.replace("| Powerful |", "| Lightweight |", 2)
        refreshed = self.provider.refresh_catalog()
        self.fetch.assert_called_once_with(DOCS_API_BODY + PRICING_ARTICLE_PATH, 20)
        self.assertEqual(fetched.analysis_signature, refreshed.analysis_signature)
        self.assertEqual("Lightweight", web_rows(refreshed)["GPT-Test"]["category"])

    def test_isolated_refresh_rebuilds_fixed_prices_without_history_accounts_or_watch_repricing(self):
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
            with patch.object(ReportService, 'session_catalog', side_effect=AssertionError('no price-list history')):
                first = application(ModelsPriceRefresh()).execute(ModelsPriceRefresh()).to_json()
                self.now += 1000
                self.fetch.return_value = pricing_document(10)

                refreshed = application(ModelsPriceRefresh()).execute(ModelsPriceRefresh()).to_json()

        self.assertIsNone(first['error'])
        self.assertIsNone(refreshed['error'])
        accounts.assert_not_called()
        before, after = first['view'], refreshed['view']
        self.assertEqual(0, after['model_comparison_sample_size'])
        self.assertIsNone(after['model_comparison_mix'])
        old = next(row for row in before['model_catalog']['rows'] if row['model'] == 'GPT-Test')
        new = next(row for row in after['model_catalog']['rows'] if row['model'] == 'GPT-Test')
        self.assertGreater(Decimal(new['relative_cost']), Decimal(old['relative_cost']))
        self.assertEqual(before['token_mix'], after['token_mix'], 'no synthetic or revalued user telemetry')
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
