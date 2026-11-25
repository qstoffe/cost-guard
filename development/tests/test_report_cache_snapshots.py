"""Committed report reads across process, page and owner boundaries."""
from dataclasses import replace
from decimal import Decimal
from multiprocessing import active_children
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from development.tests.fixtures.account_periods import request, subscription
from development.tests.fixtures.report_runtime import FakePricingProvider
from development.tests.test_account_timeline import NOV_1, NOV_5, projected
from src.analysis.account_timeline import DAY_MS, PERIODS
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


class ReportCacheSnapshotTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.archive = WebArchive(Path(directory.name))
        self.archive.initialize()

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
