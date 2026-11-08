"""Cached Web historical Token Mix preserves CLI scope, deduplication and valuation."""
from dataclasses import replace
from decimal import Decimal
import time
import unittest
from unittest.mock import patch

from development.tests.fixtures.compact_reports import report_service, START
from development.tests.fixtures.synthetic_month import SyntheticMonthSource, make_root_snapshot
from src.application.projection import project
from src.domain import ModelRef, TokenUsage
from src.pricing.catalog import PricingCatalog
from src.reports import ReportKind, ReportRequest, ReportService
from src.reports.token_mix_cache import ALGORITHM, NAMESPACE, cache_key
from src.web.jobs import ReportJobs


class TokenMixCacheTests(unittest.TestCase):
    def fresh(self, original, *, cached=True):
        return ReportService(selection=original.selection, pricing_provider=original.pricing_provider,
            account_provider=None, cache_repository=original.cache_repository,
            config=original.config, now_ms=original.now_ms,
            model_availability_source=original.model_availability_source, cache_token_mix_history=cached)

    def test_cached_report_equals_cli_with_children_unknown_telemetry_and_prices(self):
        source = SyntheticMonthSource(8, 4, month_start_ms=START, children_per_root=1)
        for index, (sid, snapshot) in enumerate(list(source.snapshots.items())):
            source.snapshots[sid] = replace(snapshot, invocations=tuple(replace(item,
                model=ModelRef('route', 'unpriced') if index == 1 else item.model,
                tokens=TokenUsage(input=9007199254740993, output=2, reasoning=3,
                    known_fields=('input', 'output')) if index == 2 else item.tokens)
                for item in snapshot.invocations))
        original = report_service(self, source)
        original.model_availability_source.ids = None
        expected = original.build_token_mix_history()

        report = self.fresh(original).build_token_mix_history()

        self.assertEqual(expected, report)
        self.assertFalse(report.token_mix.cost_complete)
        self.assertIsNone(report.token_mix.total_tokens)
        self.assertGreater(report.token_mix.known_total_tokens, 9007199254740993)

    def test_warm_no_change_checks_revisions_without_hydration_analysis_or_repricing(self):
        source = SyntheticMonthSource(520, 4, month_start_ms=START)
        original = report_service(self, source)
        first = self.fresh(original).build_token_mix_history()
        loads = source.load_count

        with patch.object(source, 'load_session_snapshot', side_effect=AssertionError('unchanged history read')), \
                patch.object(PricingCatalog, 'reference_category_valuation', side_effect=AssertionError('repriced unchanged')):
            refreshed = self.fresh(original).build_token_mix_history()

        self.assertEqual(first, refreshed)
        self.assertEqual(520, loads)
        self.assertEqual(loads, source.load_count)
        self.assertEqual(1040, source.metrics.counts['token_mix_cache_hits'] + source.metrics.counts['token_mix_cache_misses'])

    def test_active_roots_remain_uncached_and_empty_history_stays_unknown_not_fabricated(self):
        source = SyntheticMonthSource(1, 2, month_start_ms=START, running_roots=1)
        original = report_service(self, source)
        self.fresh(original).build_token_mix_history()
        loads = source.load_count

        report = self.fresh(original).build_token_mix_history()

        self.assertEqual(loads + 1, source.load_count)
        self.assertEqual(self.fresh(original, cached=False).build_token_mix_history(), report)
        source.snapshots.clear()
        empty = self.fresh(original).build_token_mix_history()
        self.assertEqual(0, empty.token_mix.request_count)
        self.assertIsNone(empty.token_mix.known_total_tokens)
        self.assertEqual((), empty.model_token_mix)

    def test_only_changed_new_roots_load_and_removed_roots_do_not_survive(self):
        source = SyntheticMonthSource(6, 3, month_start_ms=START)
        original = report_service(self, source)
        self.fresh(original).build_token_mix_history()
        loads = source.load_count
        changed = source.snapshots['root-0001']
        source.snapshots['root-0001'] = replace(changed, source_revision='late-child-usage',
            invocations=tuple(replace(item, tokens=TokenUsage(output=1234)) for item in changed.invocations))
        del source.snapshots['root-0002']
        added = make_root_snapshot(7, 2, month_start_ms=START)
        source.snapshots[added.root.session_id] = added

        report = self.fresh(original).build_token_mix_history()

        self.assertEqual(loads + 2, source.load_count)
        self.assertEqual(self.fresh(original, cached=False).build_token_mix_history(), report)
        self.assertEqual(17, report.token_mix.request_count)

    def test_cached_clone_fingerprints_deduplicate_across_different_root_row_ids(self):
        source = SyntheticMonthSource(2, 3, month_start_ms=START)
        first, clone = source.snapshots.values()
        source.snapshots[clone.root.session_id] = replace(clone, invocations=tuple(
            replace(item, completed_at_ms=original.completed_at_ms)
            for item, original in zip(clone.invocations, first.invocations)))
        original = report_service(self, source)
        expected = original.build_token_mix_history()

        cold = self.fresh(original).build_token_mix_history()
        warm = self.fresh(original).build_token_mix_history()

        self.assertEqual(3, expected.token_mix.request_count)
        self.assertEqual(expected, cold)
        self.assertEqual(expected, warm)

    def test_zero_volume_and_optional_bulk_cache_errors_preserve_canonical_result(self):
        source = SyntheticMonthSource(1, 1, month_start_ms=START)
        snapshot = source.snapshots['root-0000']
        source.snapshots['root-0000'] = replace(snapshot, invocations=tuple(
            replace(item, tokens=TokenUsage()) for item in snapshot.invocations))
        original = report_service(self, source)
        expected = original.build_token_mix_history()

        with patch.object(original.cache_repository, 'get_many', side_effect=OSError('optional read')), \
                patch.object(original.cache_repository, 'put_many', side_effect=OSError('optional write')):
            report = self.fresh(original).build_token_mix_history()

        self.assertEqual(expected, report)
        self.assertEqual(0, report.token_mix.total_tokens)
        self.assertEqual((None,) * 4, report.token_mix.shares)
        self.assertEqual('0', project(report).to_json()['token_mix']['display']['mix_total_tokens'])

    def test_catalog_price_change_invalidates_valuation_but_availability_only_regroups(self):
        source = SyntheticMonthSource(3, 2, month_start_ms=START)
        original = report_service(self, source)
        first = self.fresh(original).build_token_mix_history()
        catalog = original.pricing_provider.catalog
        original.pricing_provider.catalog = PricingCatalog(tuple(replace(model,
            tiers=tuple(replace(tier, per_million_output=Decimal(999)) for tier in model.tiers))
            for model in catalog.models))

        repriced = self.fresh(original).build_token_mix_history()
        loads = source.load_count
        original.model_availability_source.ids = ()
        filtered = self.fresh(original).build_token_mix_history()

        self.assertNotEqual(first.token_mix.costs, repriced.token_mix.costs)
        self.assertEqual(loads, source.load_count)
        self.assertEqual((), filtered.model_token_mix)
        self.assertEqual((), filtered.publisher_token_mix)
        self.assertEqual(0, filtered.token_mix.request_count)

    def test_malformed_disposable_evidence_is_a_miss_not_a_successful_empty_report(self):
        source = SyntheticMonthSource(1, 2, month_start_ms=START)
        original = report_service(self, source)
        expected = self.fresh(original).build_token_mix_history()
        root = source.snapshots['root-0000'].root
        original.cache_repository.put(NAMESPACE, cache_key(original, root, original._load_comparison_catalog()),
            [{'tokens': [-1]}], source_revision=source.get_session_tree_revision(root.session_id), algorithm_version=ALGORITHM)

        report = self.fresh(original).build_token_mix_history()

        self.assertEqual(expected, report)
        self.assertEqual(2, report.token_mix.request_count)

    def test_managed_partial_chunk_observes_derived_cache_in_bounded_windows(self):
        source = SyntheticMonthSource(20, 2, month_start_ms=START)
        source.snapshots = {sid: replace(value, complete=True) for sid, value in source.snapshots.items()}
        original = report_service(self, source)
        self.fresh(original, cached=False).build_token_mix_history()
        for sid in ('root-0001', 'root-0002'):
            source.snapshots[sid] = replace(source.snapshots[sid], source_revision='late-usage')
        expected = report_service(self, source).build_token_mix_history()
        managed = self.fresh(original)
        managed.shared_web_evidence = managed.allow_partial_history = True
        available = lambda ids, _progress: {sid: source.load_session_snapshot(sid) for sid in ids}
        names = ('cache_bulk_reads', 'cache_repository_reads', 'cache_observation_hit_reuse',
                 'cache_observation_miss_reuse', 'cache_observation_invalidations')
        before = {name: source.metrics.counts.get(name, 0) for name in names}

        with patch.object(source, 'load_session_snapshots_available', side_effect=available, create=True):
            report = managed.build_token_mix_history()

        counted = {name: source.metrics.counts.get(name, 0) - before[name] for name in names}
        self.assertEqual(expected, report)
        self.assertEqual(dict(cache_bulk_reads=3, cache_repository_reads=3, cache_observation_hit_reuse=18,
            cache_observation_miss_reuse=2, cache_observation_invalidations=0), counted)

    def test_root_changed_after_chunk_observation_falls_back_to_its_current_revision(self):
        source = SyntheticMonthSource(3, 2, month_start_ms=START)
        source.snapshots = {sid: replace(value, complete=True) for sid, value in source.snapshots.items()}
        original = report_service(self, source)
        self.fresh(original, cached=False).build_token_mix_history()
        managed = self.fresh(original)
        managed.shared_web_evidence = managed.allow_partial_history = True
        observe = managed._acquisition.observe

        def observed_then_changed(roots, versions):
            observations = observe(roots, versions)
            source.snapshots['root-0001'] = replace(source.snapshots['root-0001'], source_revision='changed')
            return observations
        available = lambda ids, _progress: {sid: source.load_session_snapshot(sid) for sid in ids}
        before = source.metrics.counts.get('cache_observation_invalidations', 0)

        with patch.object(managed._acquisition, 'observe', side_effect=observed_then_changed), \
                patch.object(source, 'load_session_snapshots_available', side_effect=available, create=True):
            report = managed.build_token_mix_history()

        self.assertEqual(1, source.metrics.counts.get('cache_observation_invalidations', 0) - before)
        self.assertEqual(1, report.history_omitted_roots)
        self.assertEqual(4, report.token_mix.request_count)

    def test_exact_sort_fields_and_partial_display_do_not_change_legacy_tokens(self):
        source = SyntheticMonthSource(1, 1, month_start_ms=START)
        snapshot = source.snapshots['root-0000']
        source.snapshots['root-0000'] = replace(snapshot, invocations=tuple(replace(item,
            tokens=TokenUsage(input=9007199254740993, output=1)) for item in snapshot.invocations))
        report = self.fresh(report_service(self, source)).build_token_mix_history()
        partial = replace(report, token_mix=replace(report.token_mix, priced_requests=0))

        dto = project(partial).to_json()['token_mix']

        self.assertEqual('9007199254740994', dto['exact_total_tokens'])
        self.assertEqual('9007199254740993', dto['exact_totals'][0])
        self.assertEqual('N/A', dto['display']['mix_total_cost'])
        self.assertNotIn('%%', dto['display']['mix_input_share'])

    def test_host_coalesces_concurrent_and_recent_checks_without_relabeling_observation(self):
        jobs = ReportJobs()
        self.addCleanup(jobs.close)
        request = ReportRequest(ReportKind.TOKEN_MIX)
        first = jobs.submit(request)
        self.assertEqual(first, jobs.submit(request))
        jobs._jobs[first].update(status='complete', finished_at=time.monotonic(), result={'observed_at_ms': 123})

        reused = jobs.submit(request)

        self.assertEqual(first, reused)
        self.assertEqual(123, jobs.snapshot(reused)['result']['observed_at_ms'])
        jobs._jobs[first]['finished_at'] -= 61
        self.assertNotEqual(first, jobs.submit(request))


if __name__ == '__main__':
    unittest.main()
