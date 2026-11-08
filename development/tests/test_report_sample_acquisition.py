"""Speculative sample snapshots remain distinct from consumed report evidence."""
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from development.tests.fixtures.session_snapshots import make_snapshot
from src.analysis.cache import AnalysisDependencies, DerivedAnalysisCache
from src.analysis.models import RootAnalysisBundle
from src.domain.acquisition import AcquisitionMetrics
from src.cache import CacheDatabase, CacheRepository
from src.reports.acquisition import RootAcquisition
from src.sources import errors


class SampleSource:
    def __init__(self):
        self.revisions = {'first':'first-1', 'tail':'tail-1'}
        self.reads, self.batches = [], []
        base = make_snapshot()
        self.roots = tuple(replace(base.root, session_id=key) for key in self.revisions)
        self.base = replace(base, messages=(), parts=(), events=(), invocations=(), complete=True)
        self.batch_error = None
        self.after_batch = lambda: None

    def get_session_tree_revision(self, key):
        return self.revisions[key]

    def snapshot(self, key):
        root = next(root for root in self.roots if root.session_id == key)
        return replace(self.base, root=root, sessions=(root,), source_revision=self.revisions[key])

    def load_session_snapshot(self, key):
        self.reads.append(key)
        return self.snapshot(key)

    def load_session_snapshots_for_sampling(self, keys):
        self.batches.append(tuple(keys))
        if self.batch_error:
            raise self.batch_error
        result = {key:self.snapshot(key) for key in keys}
        self.after_batch()
        return result


class SampleCache:
    def __init__(self):
        self.bundles = {}
        self.reads = []

    def load(self, *, root_session_id, source_revision, **_kwargs):
        self.reads.append(root_session_id)
        bundle = self.bundles.get(root_session_id)
        return bundle if bundle and bundle.source_revision == source_revision else None


def acquisition(source, cache=None):
    return RootAcquisition(source, cache or SampleCache(),
        dependencies=lambda: AnalysisDependencies('config','prices'),
        analyzer=lambda snapshot: RootAnalysisBundle(snapshot.root.session_id, snapshot.source_revision, (), (), (), cacheable=False),
        progress=lambda _event: None, metrics=AcquisitionMetrics())


class ReportSampleAcquisitionTests(unittest.TestCase):
    def test_two_cold_roots_share_one_cache_lookup_and_do_not_reread_misses(self):
        source = SampleSource()
        with tempfile.TemporaryDirectory() as directory:
            database = CacheDatabase(Path(directory))
            database.initialize()
            repository = CacheRepository(database)
            cache = DerivedAnalysisCache(repository)
            owner = acquisition(source, cache)
            with patch.object(repository, 'get_many', wraps=repository.get_many) as bulk:
                owner.prepare_sample(source.roots)
            with patch.object(repository, 'get', side_effect=AssertionError('duplicate miss read')):
                results = [owner.analyze(root, now_ms=10000) for root in source.roots]

            bulk.assert_called_once()
            self.assertEqual(['first', 'tail'], [item.bundle.root_session_id for item in results])
            self.assertTrue(all(not item.cache_hit for item in results))
            self.assertEqual([], source.reads)
            self.assertEqual([('first', 'tail')], source.batches)
            self.assertEqual({'first':'first-1', 'tail':'tail-1'}, owner.revisions)

    def test_staged_cache_hit_is_revalidated_without_deserializing_it_twice(self):
        source, cache = SampleSource(), SampleCache()
        cached = RootAnalysisBundle('first', 'first-1', (), (), (), cacheable=False)
        cache.bundles['first'] = cached
        cache.bundles['tail'] = RootAnalysisBundle('tail', 'tail-1', (), (), (), cacheable=False)
        owner = acquisition(source, cache)

        owner.prepare_sample(source.roots)
        self.assertEqual({}, owner.revisions)
        self.assertEqual({}, owner.analyzed)
        first = owner.analyze(source.roots[0], now_ms=10000)
        owner.clear_sample()

        self.assertIs(cached, first.bundle)
        self.assertTrue(first.cache_hit)
        self.assertEqual(['first', 'tail'], cache.reads)
        self.assertEqual([], source.reads)
        self.assertEqual({'first':'first-1'}, owner.revisions)
        self.assertEqual(1, owner.metrics.counts['sample_prefetch_discarded_roots'])

    def test_staged_cache_hit_is_rejected_after_revision_changes_without_a_batch(self):
        source, cache = SampleSource(), SampleCache()
        cache.bundles['first'] = RootAnalysisBundle('first', 'first-1', (), (), (), cacheable=False)
        owner = acquisition(source, cache)
        owner.prepare_sample(source.roots)
        source.revisions['first'] = 'first-2'

        first = owner.analyze(source.roots[0], now_ms=10000)

        self.assertEqual('first-2', first.bundle.source_revision)
        self.assertFalse(first.cache_hit)
        self.assertEqual(['first'], source.reads)

    def test_staged_cache_hit_is_rejected_after_analysis_dependencies_change(self):
        source, cache = SampleSource(), SampleCache()
        stale = RootAnalysisBundle('first', 'first-1', (), (), (), cacheable=False)
        cache.bundles['first'] = stale
        owner = acquisition(source, cache)
        owner.prepare_sample(source.roots)
        owner.dependencies = lambda: AnalysisDependencies('changed-config', 'changed-prices')
        cache.bundles.clear()

        first = owner.analyze(source.roots[0], now_ms=10000)

        self.assertIsNot(stale, first.bundle)
        self.assertFalse(first.cache_hit)
        self.assertEqual(['first'], source.reads)

    def test_staged_cache_hit_cannot_cross_source_provenance(self):
        source, cache = SampleSource(), SampleCache()
        stale = RootAnalysisBundle('first', 'first-1', (), (), (), cacheable=False)
        cache.bundles['first'] = stale
        owner = acquisition(source, cache)
        owner.prepare_sample(source.roots)
        other_source = replace(source.roots[0], provenance=replace(source.roots[0].provenance,
            source_instance='different-source-instance'))
        cache.bundles.clear()

        first = owner.analyze(other_source, now_ms=10000)

        self.assertIsNot(stale, first.bundle)
        self.assertFalse(first.cache_hit)
        self.assertEqual(['first'], source.reads)

    def test_prefetch_has_no_analysis_or_provenance_until_consumed(self):
        source = SampleSource()
        owner = acquisition(source)

        owner.prepare_sample(source.roots)

        self.assertEqual({}, owner.analyzed)
        self.assertEqual({}, owner.revisions)
        first = owner.analyze(source.roots[0], now_ms=10000)
        self.assertEqual('first-1', first.bundle.source_revision)
        self.assertEqual({'first'}, set(owner.analyzed))
        self.assertEqual({'first':'first-1'}, owner.revisions)
        self.assertEqual([], source.reads)
        owner.clear_sample()
        self.assertEqual(1, owner.metrics.counts['sample_prefetch_discarded_roots'])

    def test_cached_hit_is_rechecked_after_other_miss_refreshes_catalog(self):
        source, cache = SampleSource(), SampleCache()
        source.roots += (replace(source.roots[1], session_id='other'),)
        source.revisions['other'] = 'other-1'
        cache.bundles['first'] = RootAnalysisBundle('first', 'first-1', (), (), (), cacheable=False)
        source.after_batch = lambda: source.revisions.update(first='first-2')
        owner = acquisition(source, cache)

        owner.prepare_sample(source.roots)
        first = owner.analyze(source.roots[0], now_ms=10000)

        self.assertEqual([('tail', 'other')], source.batches)
        self.assertEqual(['first'], source.reads)
        self.assertEqual('first-2', first.bundle.source_revision)

    def test_staged_snapshot_is_discarded_if_available_revision_changes(self):
        source = SampleSource()
        owner = acquisition(source)
        owner.prepare_sample(source.roots)
        source.revisions['first'] = 'first-2'

        first = owner.analyze(source.roots[0], now_ms=10000)

        self.assertEqual(['first'], source.reads)
        self.assertEqual('first-2', first.bundle.source_revision)

    def test_identified_tail_failure_returns_to_strict_single_consumption_once(self):
        source = SampleSource()
        failure = errors.SourceDataError('Synthetic tail cannot be read')
        source.batch_error = errors.SourceSnapshotMemberError('tail', failure)
        owner = acquisition(source)

        owner.prepare_sample(source.roots)
        first = owner.analyze(source.roots[0], now_ms=10000)

        self.assertEqual('first', first.session.session_id)
        self.assertEqual(['first'], source.reads)
        self.assertEqual(1, owner.metrics.counts['sample_prefetch_fallbacks'])

    def test_required_member_failure_and_source_wide_auth_are_not_suppressed(self):
        for member, failure in (('first', errors.SourceDataError('Synthetic required failure')),
                ('tail', errors.http_failure(401, phase='messages')),
                ('tail', errors.SourceSchemaError('Synthetic unsupported contract'))):
            with self.subTest(member=member, code=failure.code):
                source = SampleSource()
                source.batch_error = errors.SourceSnapshotMemberError(member, failure)
                owner = acquisition(source)

                with self.assertRaises(type(failure)) as raised:
                    owner.prepare_sample(source.roots)

                self.assertIs(failure, raised.exception)
                self.assertEqual([], source.reads)
                self.assertEqual({}, owner.revisions)

    def test_tail_failure_remains_real_if_sequential_consumption_needs_it(self):
        source = SampleSource()
        failure = errors.SourceDataError('Synthetic required tail')
        source.batch_error = errors.SourceSnapshotMemberError('tail', failure)
        owner = acquisition(source)
        owner.prepare_sample(source.roots)
        owner.analyze(source.roots[0], now_ms=10000)

        with patch.object(source, 'load_session_snapshot', side_effect=failure):
            with self.assertRaises(errors.SourceDataError) as raised:
                owner.analyze(source.roots[1], now_ms=10000)

        self.assertIs(failure, raised.exception)
        self.assertEqual({'first':'first-1'}, owner.revisions)

    def test_sources_without_sampling_batch_capability_stay_sequential(self):
        source = SampleSource()
        source.load_session_snapshots_for_sampling = None
        owner = acquisition(source)

        owner.prepare_sample(source.roots)
        owner.analyze(source.roots[0], now_ms=10000)

        self.assertEqual([], source.batches)
        self.assertEqual(['first'], source.reads)


if __name__ == '__main__':
    unittest.main()
