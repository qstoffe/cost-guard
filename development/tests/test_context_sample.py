"""Compact guidance samples match the retained reference and release owned roots."""
from dataclasses import replace
import tempfile
import unittest
from unittest.mock import patch

from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from development.tests.fixtures.watch_runtime import make_service
from src.domain import ModelRef, TokenUsage
from src.pricing.catalog import normalized_average_token_mix
from src.reports.context_sample import collect_context_sample
from src.reports.sampling import latest_prompts, latest_token_prompts, recent_sample_roots


class ContextSampleTests(unittest.TestCase):
    def test_empty_short_and_large_sources_match_retained_reference_without_heavy_retention(self):
        for count in (0, 7, 240):
            with self.subTest(roots=count), tempfile.TemporaryDirectory() as tmp:
                source = SyntheticMonthSource(count, 2, month_start_ms=1000,
                    running_roots=min(count, 40))
                service = make_service(tmp, source, now_ms=100_000_000)[2]
                roots, activity = service._ordered_roots(service.session_catalog())
                # Force full exhaustion: no root metadata may exclude a competitor here.
                activity = {root.session_id: 100_000_000 for root in roots}
                reference = recent_sample_roots(roots, activity, service._analyze, service._priceable())
                expected_comparison = latest_prompts(reference, service._priceable())
                expected_token = latest_token_prompts(reference, service._priceable())
                expected_mix = normalized_average_token_mix(service._relative_usage(expected_comparison))
                service._analyzed.clear()
                service._analyzed_at_ms.clear()

                actual = collect_context_sample(service, roots, activity)

                self.assertEqual(expected_mix, actual.mix)
                self.assertEqual(tuple((row.prompt_time_ms, row.session_id, row.prompt_id)
                    for row in expected_comparison), tuple(row.order for row in actual.comparison))
                self.assertEqual(tuple((row.prompt_time_ms, row.session_id, row.prompt_id)
                    for row in expected_token), actual.token_order)
                self.assertEqual(count, actual.scanned_roots)
                self.assertLessEqual(len(actual.comparison), 100)
                self.assertLessEqual(len(actual.token_order), 100)
                self.assertFalse(service._analyzed)
                self.assertFalse(service._analyzed_at_ms)
                self.assertLessEqual(service.metrics.counts.get('context_sample_peak_analysis_roots', 0), 1)

    def test_ties_mixed_requests_reasoning_duplicates_and_missing_prices_match_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = SyntheticMonthSource(260, 1, month_start_ms=1000)
            service = make_service(tmp, source, now_ms=100_000_000)[2]
            roots, activity = service._ordered_roots(service.session_catalog())
            analyze = service._analyze
            def varied(root):
                item = analyze(root)
                number = int(root.session_id.removeprefix('root-'))
                prompt = item.bundle.prompts[0]
                entry = prompt.entries[0]
                priced = replace(entry, tokens=TokenUsage(input=100 + number, cache_read=number,
                    cache_write=1, output=10, reasoning=7))
                missing = replace(entry, model=ModelRef('synthetic', 'unpriced'))
                incomplete = replace(entry, tokens=TokenUsage(input=5, output=3,
                    known_fields=frozenset({'input', 'output'})))
                entries = (missing, incomplete) if number % 7 == 0 else (priced, priced, missing, incomplete)
                item.bundle = replace(item.bundle, prompts=(replace(prompt, entries=entries,
                    prompt_time_ms=1000, in_progress=number % 3 == 0, aborted=number % 5 == 0),))
                return item
            service._analyze = varied
            reference = recent_sample_roots(roots, activity, service._analyze, service._priceable())
            selected = latest_prompts(reference, service._priceable())
            expected = normalized_average_token_mix(service._relative_usage(selected))
            expected_ids = tuple((row.prompt_time_ms, row.session_id, row.prompt_id) for row in selected)
            service._analyzed.clear()
            service._analyzed_at_ms.clear()

            actual = collect_context_sample(service, roots, activity)

            self.assertEqual(expected, actual.mix)
            self.assertEqual(expected_ids, tuple(row.order for row in actual.comparison))
            self.assertEqual(100, len(actual.comparison))
            self.assertTrue(all(not hasattr(row, 'entries') for row in actual.comparison))
            self.assertTrue(all(not hasattr(row.usage, 'entries') for row in actual.comparison))
            self.assertFalse(service._analyzed)

    def test_independent_cutoffs_equal_activity_and_caller_owned_analysis_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = SyntheticMonthSource(240, 1, month_start_ms=1000, running_roots=50)
            service = make_service(tmp, source, now_ms=100_000_000)[2]
            roots, activity = service._ordered_roots(service.session_catalog())
            retained = service._analyze(roots[0])
            reference = recent_sample_roots(roots, activity, service._analyze, service._priceable())
            expected_count = len(reference)
            expected_mix = normalized_average_token_mix(service._relative_usage(
                latest_prompts(reference, service._priceable())))
            service._analyzed.clear()
            service._analyzed_at_ms.clear()
            service._analyzed[roots[0].session_id] = retained
            service._analyzed_at_ms[roots[0].session_id] = service.now_ms

            actual = collect_context_sample(service, roots, activity)

            self.assertEqual(expected_count, actual.scanned_roots)
            self.assertLess(actual.scanned_roots, len(roots))
            self.assertEqual(expected_mix, actual.mix)
            self.assertEqual({roots[0].session_id: retained}, service._analyzed)
            self.assertLessEqual(service.metrics.counts['context_sample_peak_analysis_roots'], 2)

    def test_reduction_failure_releases_sampler_owned_analysis_not_scalar_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = SyntheticMonthSource(2, 1, month_start_ms=1000)
            service = make_service(tmp, source)[2]
            roots, activity = service._ordered_roots(service.session_catalog())

            with patch.object(service, '_relative_usage', side_effect=ValueError('synthetic reduction defect')):
                with self.assertRaisesRegex(ValueError, 'synthetic reduction defect'):
                    collect_context_sample(service, roots, activity)

            self.assertFalse(service._analyzed)
            self.assertFalse(service._analyzed_at_ms)
            self.assertEqual({roots[0].session_id}, set(service._acquisition.revisions))

    def test_multiplier_reuses_compact_observation_until_its_original_fifteen_minute_expiry(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = SyntheticMonthSource(12, 1, month_start_ms=1000)
            service = make_service(tmp, source, now_ms=1_000_000)[2]

            service._threshold_multiplier('gpt-test', 100_000)
            original_mix = service._comparison_mix
            catalog_reads = source.catalog_count
            service.now_ms += 899_999
            service._threshold_multiplier('gpt-test', 100_000)

            self.assertEqual(original_mix, service._comparison_mix)
            self.assertEqual(catalog_reads, source.catalog_count)
            self.assertFalse(service._analyzed)
            service.now_ms += 1
            service._threshold_multiplier('gpt-test', 100_000)
            self.assertEqual(1_900_000, service._comparison_mix[1])
            self.assertEqual(catalog_reads + 1, source.catalog_count)

            service.now_ms = 900_000  # Earlier-as-of/clock rollback cannot borrow a future observation.
            service._threshold_multiplier('gpt-test', 100_000)
            self.assertEqual(900_000, service._comparison_mix[1])
            self.assertEqual(catalog_reads + 2, source.catalog_count)


if __name__ == '__main__':
    unittest.main()
