"""Last-good catalog fields never qualify pending values as fresh sort evidence."""
from dataclasses import replace
from decimal import Decimal
import unittest
from unittest.mock import patch

from development.tests.fixtures.compact_reports import report_service
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from development.tests.fixtures.watch_runtime import Recorder, watch_for
from src.application.session_catalog import SessionCatalog
from src.reports.models import SessionUsageRow
from src.watch.observers import observe_catalog


class StableRefreshTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.source = SyntheticMonthSource(1, 1, month_start_ms=1000)
        self.service = report_service(self, self.source, now_ms=100_000)
        self.catalog = SessionCatalog(clock=lambda: self.now, clock_ms=lambda: 100_000)
        self.catalog.observe(observe_catalog(self.source, include_archived_revisions=True))
        self.key = 'root-0000'
        self.page = self.catalog.page(period='all')

    def publish(self, row):
        self.now += 31
        self.source.snapshots[self.key] = replace(self.source.snapshots[self.key],
            source_revision=f'observation-{self.now}')
        self.catalog.observe(observe_catalog(self.source, include_archived_revisions=True))
        with patch('src.application.session_catalog.session_summary',
                side_effect=lambda service, root, revision, **kwargs: (row, revision)):
            self.catalog.tick(self.service)
        return self.catalog.page(token=self.page['token'], period='all')['view']['session_usage'][0]

    def test_cold_known_revision_churn_partial_zero_replacement_and_invalidation(self):
        cold = self.page['view']['session_usage'][0]
        self.assertEqual(cold['metric_states']['ctx'], 'pending')
        known = SessionUsageRow(self.key, 'Synthetic', 'Model', False, Decimal(0), 0,
            context_tokens=42_000)
        self.assertEqual(self.publish(known)['context_tokens'], 42_000)
        for sequence in range(4):
            snapshot = self.source.snapshots[self.key]
            self.source.snapshots[self.key] = replace(snapshot, source_revision=f'partial-{sequence}')
            self.catalog.observe(observe_catalog(self.source, include_archived_revisions=True))
            retained = self.catalog.page(token=self.page['token'], period='all')['view']['session_usage'][0]
            self.assertEqual(retained['context_tokens'], 42_000)
            self.assertEqual(retained['metric_states']['ctx'], 'retained')
            partial = self.publish(replace(known, context_tokens=None, context_qualified=False))
            self.assertEqual(partial['context_tokens'], 42_000)
            self.assertEqual(partial['metric_states']['ctx'], 'retained')
            self.assertTrue(self.catalog.page(period='all', sort='ctx')['pending_sort'])
        for tokens in (47_000, 0, None):
            observed = self.publish(replace(known, context_tokens=tokens))
            self.assertEqual(observed['context_tokens'], tokens)
            self.assertEqual(observed['metric_states']['ctx'], 'ready')
            self.assertFalse(self.catalog.page(period='all', sort='ctx')['pending_sort'])

    def test_independent_pending_model_and_effort_retain_help_not_new_sort_keys(self):
        known = SessionUsageRow(self.key, 'Synthetic', 'Model', False, Decimal(0), 0,
            context_tokens=0, effort='High', effort_key='high')
        self.publish(known)
        row = self.publish(replace(known, model='N/A', model_pending=True,
            effort='N/A', effort_key=None, effort_pending=True, effort_qualified=False))
        self.assertEqual((row['model'], row['effort'], row['context_tokens']), ('Model', 'High', 0))
        for sort in ('model', 'effort'):
            self.assertTrue(self.catalog.page(period='all', sort=sort)['pending_sort'])
        self.assertEqual(self.publish(replace(known, model='New model', effort='Low',
            effort_key='low'))['model'], 'New model')

    def test_failed_refresh_retains_but_new_source_and_removed_root_do_not(self):
        known = SessionUsageRow(self.key, 'Synthetic', 'Model', False, Decimal(0), 0,
            context_tokens=42_000)
        self.publish(known)
        self.catalog.observe(None, unavailable=True)
        retained = self.catalog.page(token=self.page['token'], period='all')['view']['session_usage'][0]
        self.assertEqual(retained['context_tokens'], 42_000)
        snapshot = self.source.snapshots[self.key]
        root = replace(snapshot.root, provenance=replace(snapshot.root.provenance, source_instance='other'))
        self.source.snapshots[self.key] = replace(snapshot, root=root)
        self.catalog.observe(observe_catalog(self.source, include_archived_revisions=True))
        cold = self.catalog.page(period='all')['view']['session_usage'][0]
        self.assertIsNone(cold['context_tokens'])
        self.assertFalse(cold['has_summary'])
        self.source.snapshots.clear()
        self.catalog.observe(observe_catalog(self.source, include_archived_revisions=True))
        self.assertEqual(self.catalog.page(period='all')['view']['session_usage'], [])

    def test_late_result_cannot_overwrite_new_source_revision(self):
        known = SessionUsageRow(self.key, 'Synthetic', 'Model', False, Decimal(0), 0,
            context_tokens=47_000)
        self.publish(known)
        def stale(service, root, revision, **kwargs):
            self.source.snapshots[self.key] = replace(self.source.snapshots[self.key], source_revision='newer')
            self.catalog.observe(observe_catalog(self.source, include_archived_revisions=True))
            return replace(known, context_tokens=1), revision
        self.now += 31
        self.catalog.valid.clear()
        with patch('src.application.session_catalog.session_summary', side_effect=stale):
            self.catalog.tick(self.service)
        row = self.catalog.page(period='all')['view']['session_usage'][0]
        self.assertEqual(row['context_tokens'], 47_000)
        self.assertEqual(row['metric_states']['ctx'], 'retained')


class QuietTerminalRefreshTests(unittest.TestCase):
    def test_automatic_cycles_never_publish_transient_acquisition_status(self):
        with watch_for() as (watch, source):
            try:
                cycle = watch.initialize()
                renderer = Recorder()
                with patch.object(watch, '_v1_wait'):
                    for sequence in range(3):
                        source.snapshot = replace(source.snapshot, source_revision=f'updated-{sequence}')
                        cycle = watch._advance(renderer, cycle)
                self.assertTrue(renderer.renders or renderer.statuses)
                self.assertFalse(any('Refreshing' in value.status for value in renderer.statuses))
                self.assertEqual(watch.activity_projection().status, 'Watching')
            finally:
                watch.close()


if __name__ == '__main__':
    unittest.main()
