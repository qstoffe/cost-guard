"""Frozen cohorts, honest revision facts, bounded churn and release admission."""
from dataclasses import replace
from decimal import Decimal
import unittest
from unittest.mock import patch

from development.tests.fixtures.compact_reports import report_service
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from src.application.session_catalog import SessionCatalog
from src.reports.models import SessionUsageRow
from src.reports.session_summary import session_summary
from src.sources.errors import SourceUnavailableError
from src.watch.observers import observe_catalog
from src.web.session_catalog import catalog_page


class SessionNavigationTests(unittest.TestCase):
    def setUp(self):
        self.clock = 0
        self.now = 1_000_000_000

    def setup_catalog(self, count):
        self.source = SyntheticMonthSource(count, 1, month_start_ms=self.now - 4_000_000)
        self.catalog = SessionCatalog(clock=lambda: self.clock, clock_ms=lambda: self.now)
        self.observe()
        self.service = report_service(self, self.source, now_ms=self.now)
        self.acquired = []

    def observe(self):
        self.catalog.observe(observe_catalog(self.source, include_archived_revisions=True))

    def summary(self, service, root, revision, *, on_activity, **kwargs):
        self.acquired.append(root.session_id)
        number = int(root.session_id.split('-')[1])
        on_activity((self.now - 1000,), True)
        return SessionUsageRow(root.session_id, root.title, f"Model {number:04}", False,
            Decimal(number), number, duration_ms=number, context_tokens=number,
            last_activity_ms=self.now - 1000), revision

    def request(self, first=None, **kwargs):
        return self.catalog.page(token=first['token'] if first else None, period='all',
                                 sort='ccost', direction=1, **kwargs)

    def test_twenty_of_324_then_arrivals_hot_root_and_application_acknowledgement(self):
        self.setup_catalog(324)
        first = self.request(navigation=1)
        with patch('src.application.session_catalog.session_summary', side_effect=self.summary):
            for _ in range(5):
                self.catalog.tick(self.service)
            progress = self.request(first, navigation=1)
            self.assertEqual((progress['progress']['completed'], progress['progress']['total']), (20, 324))
            newer = SyntheticMonthSource(326, 1, month_start_ms=self.now - 4_000_000)
            self.source.snapshots.update({key: value for key, value in newer.snapshots.items()
                                          if key not in self.source.snapshots})
            frozen = self.catalog.leases[first['token']]['navigation']
            hot = next(iter(frozen.facts))
            accepted = frozen.facts[hot]
            for sequence in range(76):
                self.clock += 6
                self.source.snapshots[hot] = replace(self.source.snapshots[hot], source_revision=f'hot-{sequence}')
                self.observe()
                self.catalog.tick(self.service)
                progress = self.request(first, navigation=1)
                self.assertEqual(progress['progress']['total'], 324)
                self.assertGreaterEqual(progress['progress']['completed'], 20)
            self.assertFalse(progress['pending_sort'])
            self.assertEqual(len(self.acquired), 324)
            self.assertEqual(len(set(self.acquired)), 324)
            self.assertNotIn('root-0324', self.acquired)
            self.assertEqual(frozen.facts[hot], accepted)
            displayed = next(row for row in progress['view']['session_usage'] if row['session_id'] == hot)
            self.assertEqual(displayed['snapshot_revision'], accepted[1])
            self.assertEqual(displayed['metric_states']['ccost'], 'snapshot')
            self.assertEqual([row['session_id'] for row in progress['view']['session_usage']],
                             [f'root-{index:04d}' for index in range(25)])
            # A ready HTTP response is NOT acknowledgement that the UI applied it.
            for _ in range(3):
                self.catalog.tick(self.service)
            self.assertEqual(len(self.acquired), 324)
            self.request(first, applied=1)
            for _ in range(2):
                self.clock += 6
                self.catalog.tick(self.service)
            latest = self.request(first)
            self.assertEqual(latest['total'], 326)
            self.assertFalse(latest['pending_sort'])
            self.assertTrue({'root-0324', 'root-0325'} <= set(self.acquired))

    def test_period_membership_uses_earlier_real_event_when_latest_crosses_frozen_end(self):
        self.setup_catalog(1)
        first = self.catalog.page(sort='ccost', navigation=1)
        admitted_end = first['window']['end_ms']
        self.now += 5000
        def crossing(service, root, revision, *, on_activity, **kwargs):
            on_activity((admitted_end - 1000, self.now), True)
            row, actual = self.summary(service, root, revision, on_activity=lambda *_: None)
            return replace(row, last_activity_ms=self.now), actual
        with patch('src.application.session_catalog.session_summary', side_effect=crossing):
            self.catalog.tick(self.service)
        ready = self.catalog.page(token=first['token'], sort='ccost', navigation=1)
        self.assertFalse(ready['pending_sort'])
        self.assertEqual(ready['total'], 1)
        self.assertEqual(ready['view']['session_usage'][0]['last_activity_ms'], self.now)
        self.assertEqual(ready['window']['end_ms'], admitted_end)

    def test_two_tabs_reuse_acquisition_and_superseded_actions_cannot_return(self):
        self.setup_catalog(26)
        first = self.request(navigation=1)
        second = self.request(navigation=1)
        with patch('src.application.session_catalog.session_summary', side_effect=self.summary):
            for _ in range(7):
                self.catalog.tick(self.service)
            ready = self.request(first, navigation=1)
            other = self.request(second, navigation=1)
            self.assertFalse(ready['pending_sort'])
            self.assertFalse(other['pending_sort'])
            self.assertEqual(len(self.acquired), 26)
            self.request(first, navigation=2)
            with self.assertRaises(ValueError):
                self.request(first, navigation=1)
            self.request(first, navigation=2, applied=1)
            self.assertEqual(self.catalog.leases[first['token']]['navigation'].sequence, 2)

    def test_deleted_identity_dependency_and_calendar_changes_do_not_reuse_facts(self):
        for change in ('delete', 'provenance', 'source', 'dependencies', 'calendar'):
            with self.subTest(change=change):
                self.setup_catalog(26)
                first = self.catalog.page(sort='ccost', navigation=1)
                with patch('src.application.session_catalog.session_summary', side_effect=self.summary):
                    self.catalog.tick(self.service)
                    key = self.acquired[0]
                    snapshot = self.source.snapshots[key]
                    if change == 'delete':
                        self.source.snapshots.pop(key)
                    elif change == 'provenance':
                        root = replace(snapshot.root, provenance=replace(snapshot.root.provenance, source_instance='other'))
                        self.source.snapshots[key] = replace(snapshot, root=root, sessions=(root,))
                    elif change == 'source':
                        self.catalog._invalidate_navigation()
                    elif change == 'dependencies':
                        with patch.object(self.service, '_dependencies', return_value=('changed-authority',)):
                            self.catalog.tick(self.service)
                    else:
                        self.now += 86_400_000
                    self.observe()
                    with self.assertRaisesRegex(KeyError, 'catalog_expired'):
                        self.catalog.page(token=first['token'], sort='ccost', navigation=1)

    def test_frozen_older_epoch_values_do_not_mutate_and_new_evidence_creates_epoch(self):
        self.setup_catalog(26)
        first = self.request(navigation=1)
        with patch('src.application.session_catalog.session_summary', side_effect=self.summary):
            for _ in range(7):
                self.catalog.tick(self.service)
        ready = self.request(first, navigation=1)
        old = self.request(first, offset=25, epoch=ready['epoch'], navigation=2, applied=1)
        self.catalog.rows['root-0025'] = replace(self.catalog.rows['root-0025'], ccost=Decimal(1000))
        pinned = self.request(first, offset=25, epoch=ready['epoch'], navigation=2)
        self.assertEqual(pinned['view']['session_usage'][0]['ccost'], old['view']['session_usage'][0]['ccost'])
        latest = self.request(first, applied=2)
        self.assertNotEqual(latest['epoch'], ready['epoch'], 'same ID order with changed values is new evidence')

    def test_authority_failures_stay_terminal_and_validation_is_bounded(self):
        self.setup_catalog(26)
        first = self.request(navigation=1)
        with patch('src.application.session_catalog.session_summary',
                   side_effect=SourceUnavailableError('private', code='http_auth_failure')):
            self.catalog.tick(self.service)
        failed = self.request(first, navigation=1)
        self.assertEqual(failed['progress']['status'], 'failed')
        self.assertFalse(failed['progress']['retryable'])
        self.assertNotIn('private', str(failed['progress']))
        for value in (0, -1, True, '1', 10**30):
            with self.assertRaises(ValueError):
                catalog_page(self.catalog, {'navigation': value})

    def test_all_sort_keys_unknowns_ties_boundary_sizes_and_five_thousand_cached_roots(self):
        for count in (0, 1, 25, 26, 324, 5000):
            self.setup_catalog(count)
            for key, root in self.catalog.roots.items():
                row, revision = self.summary(self.service, root, self.catalog.revisions[key],
                                             on_activity=lambda *_: None)
                self.catalog.rows[key] = replace(row, last_activity_ms=self.now - count + row.prompt_count)
                self.catalog.valid[key] = revision, self.clock
                self.catalog.activity_valid[key] = revision
            for sort in ('activity', 'ccost', 'prompts', 'duration', 'ctx', 'model', 'name'):
                with self.subTest(count=count, sort=sort):
                    page = self.catalog.page(period='all', sort=sort, direction=1, navigation=1)
                    self.assertFalse(page['pending_sort'])
                    self.assertEqual(page['total'], count)
                    ids = [row['session_id'] for row in page['view']['session_usage']]
                    for offset in range(25, count, 25):
                        older = self.catalog.page(token=page['token'], offset=offset, epoch=page['epoch'],
                            period='all', sort=sort, direction=1)
                        ids.extend(row['session_id'] for row in older['view']['session_usage'])
                    self.assertEqual(ids, [f'root-{index:04d}' for index in range(count)])
                    self.catalog.leases.pop(page['token'])
            if count:
                key = f'root-{count - 1:04d}'
                row = self.catalog.rows[key]
                self.catalog.rows[key] = replace(row, complete=False, context_tokens=None,
                    model='N/A', duration_ms=None, last_activity_ms=None)
                for sort in ('ccost', 'ctx', 'duration', 'model', 'activity'):
                    for direction in (1, -1):
                        page = self.catalog.page(period='all', sort=sort, direction=direction, navigation=1)
                        epoch = self.catalog.leases[page['token']]['epochs'][page['epoch']]
                        self.assertEqual(epoch.rows[-1].session_id, key)
                        self.catalog.leases.pop(page['token'])

    def test_running_first_all_sorts_both_directions_and_overflow_boundaries(self):
        for running_count in (0, 1, 10, 24, 25, 26, 50, 51):
            self.setup_catalog(100 + running_count)
            for index, (key, root) in enumerate(self.catalog.roots.items()):
                row, revision = self.summary(self.service, root, self.catalog.revisions[key],
                                             on_activity=lambda *_: None)
                # Two running starts tie, including sub-minute precision.
                start = self.now - 10_000 + index // 2
                self.catalog.rows[key] = replace(row, running=index < running_count,
                    prompt_started_ms=start, activity_prompt_id=f"prompt-{index}",
                    last_activity_ms=start if index < running_count else self.now - 1000 + index)
                self.catalog.valid[key] = revision, self.clock
                self.catalog.activity_valid[key] = revision
            running_ids = [f"root-{index:04d}" for index in
                           sorted(range(running_count), key=lambda index: (-(index // 2), index))]
            for sort in ('activity', 'name', 'model', 'ccost', 'prompts', 'duration', 'ctx'):
                for direction in (1, -1):
                    with self.subTest(running=running_count, sort=sort, direction=direction):
                        page = self.catalog.page(period='all', sort=sort, direction=direction, navigation=1)
                        self.assertFalse(page['pending_sort'])
                        ids, running_flags = [], []
                        for offset in range(0, 100 + running_count, 25):
                            current = page if offset == 0 else self.catalog.page(token=page['token'],
                                offset=offset, epoch=page['epoch'], period='all', sort=sort, direction=direction)
                            ids.extend(row['session_id'] for row in current['view']['session_usage'])
                            running_flags.extend(row['running'] for row in current['view']['session_usage'])
                        finished = list(range(running_count, 100 + running_count))
                        if direction == -1:
                            finished.reverse()
                        self.assertEqual(ids, running_ids + [f"root-{index:04d}" for index in finished])
                        self.assertEqual(running_flags, [True] * running_count + [False] * 100)
                        self.assertEqual(len(set(ids)), 100 + running_count)
                        self.catalog.leases.pop(page['token'])
            # Mutable metrics never participate in running-group order.
            for key, row in tuple(self.catalog.rows.items())[:running_count]:
                self.catalog.rows[key] = replace(row, ccost=Decimal(99999), model="Changed",
                    context_tokens=None, context_qualified=False, model_pending=True, prompt_count=0)
            changed = self.catalog.page(period='all', sort='ccost', direction=1)
            epoch = self.catalog.leases[changed['token']]['epochs'][changed['epoch']]
            self.assertEqual([row.session_id for row in epoch.rows[:running_count]], running_ids)
            for sort in ('ctx', 'model'):
                missing = self.catalog.page(period='all', sort=sort, direction=1, navigation=1)
                self.assertFalse(missing['pending_sort'], "running sort never requires changing metric keys")
                self.catalog.leases.pop(missing['token'])

    def test_running_terminal_reinsertion_and_new_arrival_do_not_shift_pinned_pages(self):
        self.setup_catalog(151)
        for index, (key, root) in enumerate(self.catalog.roots.items()):
            row, revision = self.summary(self.service, root, self.catalog.revisions[key],
                                         on_activity=lambda *_: None)
            self.catalog.rows[key] = replace(row, running=index < 51,
                prompt_started_ms=self.now - 1000 + index, activity_prompt_id=f"prompt-{index}")
            self.catalog.valid[key] = revision, self.clock
            self.catalog.activity_valid[key] = revision
        first = self.request(navigation=1)
        old_pages = [self.request(first, offset=offset, epoch=first['epoch'])
                     for offset in (25, 50, 75)]
        old_ids = [[row['session_id'] for row in page['view']['session_usage']] for page in old_pages]
        self.catalog.rows['root-0050'] = replace(self.catalog.rows['root-0050'], running=False,
                                               last_activity_ms=self.now, ccost=Decimal(1000))
        self.catalog.rows['root-0150'] = replace(self.catalog.rows['root-0150'], running=True,
            activity_prompt_id='new', prompt_started_ms=self.now, last_activity_ms=self.now)
        latest = self.request(first, applied=1)
        self.assertNotEqual(latest['epoch'], first['epoch'])
        self.assertEqual(latest['view']['session_usage'][0]['session_id'], 'root-0150')
        newest = self.catalog.leases[first['token']]['epochs'][latest['epoch']]
        self.assertEqual(newest.rows[-1].session_id, 'root-0050')
        for offset, expected in zip((25, 50, 75), old_ids):
            pinned = self.request(first, offset=offset, epoch=first['epoch'])
            self.assertEqual([row['session_id'] for row in pinned['view']['session_usage']], expected)

    def test_repeated_supersession_preserves_released_background_fairness(self):
        self.setup_catalog(26)
        first = self.request(navigation=1)
        with patch('src.application.session_catalog.session_summary', side_effect=self.summary):
            for _ in range(7):
                self.catalog.tick(self.service)
            ready = self.request(first, navigation=1)
            self.request(first, applied=1)
            newcomer = replace(next(iter(self.source.snapshots.values())),
                root=replace(next(iter(self.source.snapshots.values())).root, session_id='root-9999'))
            self.source.snapshots['root-9999'] = newcomer
            self.observe()
            for sequence in range(2, 18):
                # New requests repeatedly supersede an expensive independent tab.
                self.request(first, navigation=sequence)
                self.clock += 6
                self.catalog.tick(self.service)
            self.assertIn('root-9999', self.acquired)
            self.assertEqual(self.acquired.count('root-9999'), 1)
            # A cancelled action must never be restored by a late request.
            self.request(first, cancelled=17)
            with self.assertRaises(ValueError):
                self.request(first, navigation=17)
            self.assertIn(ready['epoch'], self.catalog.leases[first['token']]['epochs'])

    def test_real_summary_supplies_source_event_membership_on_cache_hit_and_miss(self):
        self.setup_catalog(1)
        self.source.snapshots = {key: replace(snapshot, complete=True)
                                 for key, snapshot in self.source.snapshots.items()}
        self.observe()
        root = self.catalog.roots['root-0000']
        revision = self.catalog.revisions[root.session_id]
        observations = []
        row, _ = session_summary(self.service, root, revision,
            on_activity=lambda values, complete: observations.append((tuple(values), complete)))
        self.assertTrue(observations[0][1])
        self.assertIn(row.last_activity_ms, observations[0][0])
        with patch.object(self.service, '_analyze', wraps=self.service._analyze) as acquire:
            session_summary(self.service, root, revision, activity_end_ms=row.last_activity_ms,
                on_activity=lambda values, complete: observations.append((tuple(values), complete)))
            self.assertEqual(acquire.call_count, 1, 'latest scalar at/after admission cannot prove earlier absence')
        self.assertTrue(observations[-1][1])

    def test_unqualified_concurrent_read_never_becomes_a_snapshot_fact(self):
        self.setup_catalog(1)
        first = self.request(navigation=1)
        def concurrent(service, root, revision, **kwargs):
            row, _ = self.summary(service, root, revision, **kwargs)
            return row, 'not-the-requested-revision'
        with patch('src.application.session_catalog.session_summary', side_effect=concurrent):
            self.catalog.tick(self.service)
        pending = self.request(first, navigation=1)
        self.assertTrue(pending['pending_sort'])
        self.assertEqual(pending['progress']['completed'], 0)


if __name__ == '__main__':
    unittest.main()
