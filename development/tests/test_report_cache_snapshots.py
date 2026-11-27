"""Committed report reads across process, page and owner boundaries."""
from dataclasses import replace
from decimal import Decimal
from multiprocessing import active_children
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from development.tests.fixtures.account_periods import request, subscription
from development.tests.fixtures.report_runtime import FakePricingProvider
from development.tests.test_account_timeline import NOV_1, NOV_5, projected
from development.tests.fixtures.session_snapshots import DAY as DAY_MS
from src.analysis.account_timeline import PERIODS
from src.analysis.cache import encode_trace_entry
from src.application.account_timeline import account_roster
from src.application.session_archive import SessionArchive
from src.application.session_epoch_page import sort_value
from src.cache.session_projection import SESSIONS_DOMAIN, SORT_COLUMNS
from src.cache.web_archive import ArchiveFact, WebArchive
from src.domain import QuotaComponent, TokenUsage
from src.reports.archived_usage import ArchivedUsage, DOMAIN
from src.reports.models import SessionUsageRow
from src.reports.session_summary import encode_summary
from src.watch.account_timeline_archive import ArchivedAccountTimeline
from src.watch.account_timeline_projection import ArchivedAccountProjection
from src.watch.account_timeline_snapshots import AccountTimelineSnapshots, DOMAIN as CHART_FRAMES
from src.web.session_cache_events import SessionCacheEvents


class ReportCacheSnapshotTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.archive = WebArchive(Path(directory.name))
        self.archive.initialize()

    def test_earliest_prompt_follows_committed_history_not_acquisition_order_or_activity(self):
        owner = SessionArchive(self.archive)

        def coverage(pending):
            self.assertTrue(owner.update_runtime(state='observed', terminal=False, reset_pending=True,
                                                 pending=pending, live={}))

        def detail(root, prompts):
            rows = [{'is_compaction': compact, 'at_ms': at} for compact, at in prompts]
            fact = ArchiveFact('rev', NOV_5, {'view': {'prompt_blocks': [{'rows': rows}]}})
            self.archive.publish('source', 'detail/1', {root: fact})

        def earliest():
            return self.archive.earliest_prompt(owner.run, NOV_5)

        self.assertEqual((None, False), earliest(), 'inventory not observed')
        coverage({})
        self.assertEqual((None, True), earliest(), 'observed empty store')
        coverage({'older': (NOV_1, False)})
        detail('future', [(False, NOV_5 + 1)])
        detail('recent', [(True, NOV_1), (False, NOV_5 - 1500)])
        self.assertEqual((NOV_5 - 1500, False), earliest())
        detail('older', [(False, NOV_1 + 3700)])
        coverage({})
        self.assertEqual((NOV_1 + 3700, True), earliest())
        reopened = WebArchive(self.archive.path.parent)
        self.assertEqual((NOV_1 + 3700, False), reopened.earliest_prompt(SessionArchive(reopened).run, NOV_5))

    def test_committed_future_activity_triggers_a_read_at_eligibility_without_a_new_write(self):
        later = NOV_5 + 1000
        row = SessionUsageRow('later', 'Later', 'Model', False, None, 1, last_activity_ms=later)
        self.archive.publish_session('source', {SESSIONS_DOMAIN: {'later': ArchiveFact(
            'rev', NOV_5, {'row': encode_summary(row)})}}, 'later',
            {name: sort_value(row, name) for name in SORT_COLUMNS}, later, later)
        hub = Mock()
        events = SessionCacheEvents(hub, 'UTC', self.archive.next_ready_activity)

        def read(at):
            _, _, rows = self.archive.ready_sessions_page(offset=0, size=25, sort='activity',
                direction=-1, start_ms=None, end_ms=at + 1)
            return [key for key, _ in rows]

        with patch('src.web.session_cache_events.time_ns') as clock:
            clock.return_value = NOV_5 * 1_000_000
            events.roll_calendar(storage_ready=True)
            hub.reset_mock()
            self.assertEqual([], read(NOV_5))
            clock.return_value = (later - 1) * 1_000_000
            events.roll_calendar(storage_ready=True)
            hub.publish.assert_not_called()
            clock.return_value = later * 1_000_000
            events.roll_calendar(storage_ready=True)
            channel, notice = hub.publish.call_args.args
            self.assertEqual('sessions_cache', channel)
            self.assertEqual({notice['revision']}, set(notice['periods'].values()))
            self.assertEqual(['later'], read(later))

    def test_only_eligible_live_rows_shadow_history_in_both_count_and_sorted_slice(self):
        def row(key, at):
            return SessionUsageRow(key, key, 'Model', False, None, 1, last_activity_ms=at)

        for key, at in [('alpha', 90), ('beta', 91), ('gamma', 92), ('old', 10)]:
            saved = row(key, at)
            fact = ArchiveFact('settled', 100, {'row': encode_summary(saved)})
            self.archive.publish_session('source', {SESSIONS_DOMAIN: {key: fact}}, key,
                {name: sort_value(saved, name) for name in SORT_COLUMNS}, at, at)
        owner = SessionArchive(self.archive)
        # The future overlay for beta must not hide its eligible *historical* value.
        owner.update_runtime(state='observed', terminal=False, reset_pending=True,
            pending={'outside': (10, False), 'unplaced': (None, True)},
            live={'alpha': (row('alpha', 50), 50, None), 'new': (row('new', 95), 95, None),
                  'beta': (row('beta', 110), 110, None)})

        def read(owner, offset, direction):
            total, offset, facts, live, cached, state, coverage = owner.storage.sessions_page(
                start_ms=80, end_ms=101, run=owner.run, finish_cutoff=99,
                offset=offset, size=3, sort='name', direction=direction)
            ids = [(key, bool(saved)) for key, _, _, _, saved in live] + [(key, True) for key, _ in facts]
            return total, offset, cached, state, coverage, ids

        self.assertEqual((4, 0, 3, ('observed', 0), (True, 1),
                          [('new', False), ('alpha', True), ('gamma', True)]), read(owner, 0, -1))
        self.assertEqual((4, 3, 3, ('observed', 0), (True, 1), [('gamma', True)]), read(owner, 60, 1))
        restarted = SessionArchive(WebArchive(self.archive.path.parent))
        self.assertEqual((3, 0, 3, None, (True, 0), [('alpha', True), ('beta', True), ('gamma', True)]),
                         read(restarted, 0, 1))

    def test_reopened_month_survives_a_partial_archive_slice_until_corrected_recent_usage_is_ready(self):
        account = subscription()
        roster = account_roster(projected(account))
        catalog = FakePricingProvider().catalog
        roots = [('early', NOV_1 + 1000), ('recent', NOV_5 - 1000)]
        observation = SimpleNamespace(root_by_session={key: key for key, _ in roots}, sessions=[
            SimpleNamespace(session_id=key, created_at_ms=at, updated_at_ms=at, archived_at_ms=None)
            for key, at in roots])

        def write(key, at, amount):
            call = request(key, at, amount=amount, ref=account.ref)
            self.archive.publish('source', DOMAIN, {key: ArchiveFact(str(amount), NOV_5 + amount,
                {'account_usage': [encode_trace_entry(call)]})})

        def project(owner, **kwargs):
            return owner.step('source', observation, {'today', 'month'}, roster, 'UTC', catalog, lambda: catalog,
                              None, NOV_5, source_available=True, **kwargs)[0]

        for key, at in roots:
            write(key, at, 1_000_000)
        saved = project(ArchivedAccountTimeline(ArchivedUsage(self.archive)))['month'].to_json()
        # The old compatible format persisted points but could misqualify the range total.
        saved['series'][0]['total'] = None
        day = NOV_1 + 4 * DAY_MS
        self.archive.publish_checkpoint(CHART_FRAMES, {'month': ArchiveFact('saved', NOV_5 - 1,
            dict(zone='UTC', day=day, scope='previous', view=saved, series=[], ready=True, active_until=1e12))})
        write('recent', roots[-1][1], 3_000_000)

        archive = WebArchive(self.archive.path.parent)
        frames = AccountTimelineSnapshots(archive, None)
        owner = ArchivedAccountTimeline(ArchivedUsage(archive))
        def lookup():
            return frames.lookup('month', None, zone='UTC', now=NOV_5)

        protected = frames.restored_periods({'today', 'month'}, 'UTC', day)
        changes = archive.history_changes
        with patch.object(archive, 'history_changes', side_effect=lambda d, cursor: changes(d, cursor, limit=1)), \
             patch('src.reports.archived_usage.monotonic', side_effect=[0, 5]):
            partial = project(owner, defer_while_loading=protected)
        self.assertEqual({'today'}, set(partial), 'a cold period may advance, but not at the expense of a saved one')
        restored = lookup()
        self.assertTrue(restored['restored'])
        self.assertFalse(restored['acquiring'], 'do not revive the prior process activity cue')
        row, = restored['view']['series']
        self.assertEqual([100, 0, 0, 0, 100], [Decimal(p['amount']) for p in row['points'][:5]])
        self.assertEqual('200', row['total']['display']['credits'])

        current = project(owner, defer_while_loading=protected)
        frames.publish(zone='UTC', day=day, marker='current', now=NOV_5, periods={'month'},
                       results={'month': current['month'].to_json()}, roster=(), ready=True, active=(), active_until=0)
        reply = lookup()
        self.assertFalse(reply.get('restored'))
        self.assertTrue(reply['view']['history_progress']['complete'])
        row, = reply['view']['series']
        self.assertEqual([100, 0, 0, 0, 300], [Decimal(p['amount']) for p in row['points'][:5]])
        self.assertEqual('400', row['total']['display']['credits'])

    def test_owned_accounts_process_prices_committed_facts_and_rejects_a_regressed_result(self):
        quota = QuotaComponent('Monthly', 'fixed', unlimited=True, unit='AI credits',
                               reset_at_ms=NOV_1 + 30 * DAY_MS)
        account = replace(subscription('github-copilot'), quotas=(quota,))
        roster = account_roster(projected(account), now_ms=NOV_5)
        call = request('priced', NOV_5 - 5000, provider='github-copilot', ref=account.ref)
        unpriced = replace(call, model=replace(call.model, model='missing'), invocation_id='observed',
            message_id='observed', completed_at_ms=NOV_5 - 1000, tokens=TokenUsage(),
            reported_cost=Decimal('3.25'), reported_cost_currency='USD')
        fact = ArchiveFact('rev', NOV_5, {'account_usage': [encode_trace_entry(e) for e in (call, unpriced)]})
        self.assertTrue(self.archive.publish('source', DOMAIN, {'root': fact}))
        revision = self.archive.generation(DOMAIN)
        observation = SimpleNamespace(root_by_session={'root': 'root'}, sessions=(
            SimpleNamespace(session_id='root', created_at_ms=NOV_1, updated_at_ms=NOV_5, archived_at_ms=None),))
        catalog = FakePricingProvider().catalog
        direct = ArchivedAccountTimeline(ArchivedUsage(self.archive))
        child = ArchivedAccountProjection(self.archive)
        self.addCleanup(child.close)
        args = ('source', observation, PERIODS, roster, 'UTC', None, lambda: catalog, None, NOV_5)

        values, more, removed = child.step(*args, source_available=True, archive_revision=revision)
        self.assertEqual(direct.step(*args, source_available=True), (values, more, removed))
        self.assertEqual(set(PERIODS), set(values))
        self.assertFalse(more or removed)
        today = values['today'].to_json()
        self.assertTrue(today['history_progress']['complete'])
        self.assertEqual('~425', today['series'][0]['total']['display']['credits'])
        # Monthly account valuation excludes the fallback observed dollars.
        self.assertEqual(Decimal(100), Decimal(values['month'].to_json()['series'][0]['total']['amount']))
        pid = child.process.pid

        catalog = replace(catalog, reference_stale=True, source_revision='stale-prices')
        pending = dict(pending_history={'root'}, source_available=False)
        values, more, removed = child.step(*args, **pending, archive_revision=revision)
        self.assertEqual(direct.step(*args, **pending), (values, more, removed))
        today = values['today'].to_json()
        self.assertTrue(more and today['history_progress']['recovering'])
        self.assertFalse(today['history_progress']['complete'])
        self.assertEqual(catalog.diagnostic_signature, today['price_revision'])
        self.assertEqual(set(PERIODS), child.pending_periods)
        self.assertEqual(pid, child.process.pid)

        with self.assertRaisesRegex(RuntimeError, 'result_not_qualified'):
            child.step(*args, **pending, archive_revision=revision - 1)
        self.assertEqual(revision, child.revision)
        self.assertNotIn(pid, [process.pid for process in active_children()])
