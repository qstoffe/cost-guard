"""Persistent incremental root-tree cost, authoritative reconciliation and isolation."""
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import json
import sqlite3
import subprocess
import sys
import tempfile
from threading import Event
import unittest
from unittest.mock import patch

from development.tests.fixtures.pricing_catalog import catalog, threshold_catalog
from development.tests.fixtures.session_snapshots import make_snapshot
from development.tests.fixtures.synthetic_month import make_root_snapshot, SyntheticMonthSource
from development.tests.fixtures.watch_runtime import make_service, MutableSource
from src.analysis.session_cost import reconcile_session_cost, NAMESPACE
from src.analysis.valuation import comparison_cost
from src.application.live_projection import project_live
from src.cache import CacheDatabase, CacheRepository
from src.domain import ModelRef, TokenUsage
from src.reports.watch_capture import capture_rows
from src.reports.sampling import AnalyzedRoot
from src.watch.card_workers import CardResult, CardWorkers
from src.watch.cards import CardSession, WatchCards
from src.watch.models import WatchProjection
from src.watch.session_costs import SessionCosts


class SessionCostCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.database = CacheDatabase(Path(self.tmp.name))
        self.database.initialize()
        self.repository = CacheRepository(self.database)

    def test_long_history_one_new_request_noop_reorder_and_restart_work_counts(self):
        first = replace(make_root_snapshot(0, 2000, month_start_ms=1000), complete=True)
        newer = replace(make_root_snapshot(0, 2001, month_start_ms=1000), complete=True)
        prices = catalog()

        with patch('src.analysis.session_cost.comparison_cost', wraps=comparison_cost) as valuations, \
                patch.object(self.repository, 'put', wraps=self.repository.put) as writes:
            initial = reconcile_session_cost(self.repository, first, prices)
            delta = reconcile_session_cost(self.repository, newer, prices)
            no_op = reconcile_session_cost(self.repository, newer, prices)
            reordered = reconcile_session_cost(self.repository,
                replace(newer, invocations=tuple(reversed(newer.invocations))), prices)
            restarted = reconcile_session_cost(CacheRepository(CacheDatabase(Path(self.tmp.name))), newer, catalog())

        # Independent fixture arithmetic: input 100+i, cached 20 at .1, output 10 at 4 per million.
        expected = sum((Decimal(142 + i) / 10000 for i in range(2001)), Decimal(0))
        self.assertEqual(expected, delta.total.known_ccost)
        self.assertEqual(2001, valuations.call_count)
        self.assertEqual(2, writes.call_count)
        self.assertEqual([2000, 1, 0, 0, 0],
            [value.valued_requests for value in (initial, delta, no_op, reordered, restarted)])
        self.assertEqual([True, True, False, False, False],
            [value.cache_written for value in (initial, delta, no_op, reordered, restarted)])
        self.assertTrue(all(value.total.complete for value in (initial, delta, no_op, reordered, restarted)))
        with self.database.connect() as connection:
            payload = connection.execute('SELECT payload_json FROM cache_entries WHERE namespace=?', (NAMESPACE,)).fetchone()[0]
        self.assertNotIn('prompt 0-', payload)
        self.assertNotIn('input', payload)

        restarted_process = subprocess.run([sys.executable, '-c', '''
import json, sys
from pathlib import Path
from dataclasses import replace
from development.tests.fixtures.pricing_catalog import catalog
from development.tests.fixtures.synthetic_month import make_root_snapshot
from src.cache import CacheRepository, CacheDatabase
from src.analysis.session_cost import reconcile_session_cost
snapshot = replace(make_root_snapshot(0, 2001, month_start_ms=1000), complete=True)
value = reconcile_session_cost(CacheRepository(CacheDatabase(Path(sys.argv[1]))), snapshot, catalog())
print(json.dumps(dict(valued=value.valued_requests, written=value.cache_written, total=str(value.total.known_ccost))))
''', self.tmp.name], cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=10)
        self.assertEqual(0, restarted_process.returncode, restarted_process.stderr)
        observed = json.loads(restarted_process.stdout)
        self.assertEqual((0, False, expected), (observed['valued'], observed['written'], Decimal(observed['total'])))

    def test_late_children_compaction_provisional_corrections_deletion_and_report_parity(self):
        source = MutableSource(replace(make_snapshot(running=True), complete=True))
        _, _, service, _ = make_service(self.tmp.name, source, now_ms=10000)
        prices = service._load_comparison_catalog()
        snapshot = source.snapshot
        missing_child = replace(snapshot, invocations=tuple(i for i in snapshot.invocations if i.session_id != 'child'))
        reconcile_session_cost(self.repository, missing_child, prices)

        late = reconcile_session_cost(self.repository, snapshot, prices)
        changed = replace(snapshot, source_revision='corrected', invocations=tuple(
            replace(i, tokens=TokenUsage(input=90, output=12), completed_at_ms=5000)
            if i.invocation_id == 'i_next' else i for i in snapshot.invocations))
        corrected = reconcile_session_cost(self.repository, changed, prices)
        repeated = reconcile_session_cost(self.repository, changed, prices)
        deleted = replace(changed, source_revision='deleted', invocations=changed.invocations[:-1])
        removed = reconcile_session_cost(self.repository, deleted, prices)
        expected = service._range_comparison((AnalyzedRoot(changed.root, service._analyze_snapshot(changed), False),), 0)

        self.assertEqual(1, late.valued_requests)
        self.assertEqual(1, corrected.valued_requests)
        self.assertEqual(0, repeated.valued_requests)
        self.assertEqual((expected.known_ccost, expected.observed_requests, expected.priced_requests),
            (corrected.total.known_ccost, corrected.total.observed_requests, corrected.total.priced_requests))
        self.assertLess(removed.total.known_ccost, corrected.total.known_ccost)
        self.assertEqual(len(deleted.invocations), removed.total.observed_requests)

    def test_partial_unknown_zero_source_failure_and_catalog_source_algorithm_invalidation(self):
        snapshot = replace(make_root_snapshot(0, 2, month_start_ms=1000), complete=True)
        prices = catalog()
        original = reconcile_session_cost(self.repository, snapshot, prices)
        unknown = replace(snapshot, invocations=(replace(snapshot.invocations[0], model=ModelRef('other', 'unknown')),
            snapshot.invocations[1]))

        partial = reconcile_session_cost(self.repository, unknown, prices)
        unavailable = reconcile_session_cost(self.repository, replace(unknown, complete=False), prices)
        empty = reconcile_session_cost(self.repository, replace(snapshot, invocations=()), prices)
        restored = reconcile_session_cost(self.repository, snapshot, prices)
        repriced = reconcile_session_cost(self.repository, snapshot, threshold_catalog())
        other_source = replace(snapshot, root=replace(snapshot.root,
            provenance=replace(snapshot.root.provenance, source_instance='different')))
        isolated = reconcile_session_cost(self.repository, other_source, prices)
        with patch('src.analysis.session_cost.ALGORITHM', 'next-algorithm'):
            algorithm = reconcile_session_cost(self.repository, snapshot, prices)

        self.assertFalse(partial.total.complete)
        self.assertEqual((2, 1), (partial.total.observed_requests, partial.total.priced_requests))
        self.assertFalse(unavailable.source_complete)
        self.assertFalse(unavailable.cache_written)
        self.assertTrue(empty.total.complete)
        self.assertEqual(0, empty.total.known_ccost)
        self.assertEqual(original.total.known_ccost, restored.total.known_ccost)
        self.assertEqual([2, 2, 2], [value.valued_requests for value in (repriced, isolated, algorithm)])

    def test_locked_or_corrupt_optional_cache_recomputes_honestly(self):
        snapshot = replace(make_snapshot(), complete=True)
        for error in (sqlite3.OperationalError('locked'), sqlite3.DatabaseError('corrupt'), OSError('unavailable')):
            with self.subTest(error=type(error).__name__), patch.object(self.repository, 'get', side_effect=error), \
                    patch.object(self.repository, 'put', side_effect=error):
                value = reconcile_session_cost(self.repository, snapshot, catalog())
                self.assertFalse(value.cache_available)
                self.assertFalse(value.cache_written)
                self.assertTrue(value.total.complete)
                self.assertGreater(value.total.known_ccost, 0)

    def test_concurrent_cards_share_summary_reentry_and_ticks_do_not_do_cost_work(self):
        source = SyntheticMonthSource(1, 8, month_start_ms=1000)
        snapshot = source.snapshots['root-0000']
        _, _, service, _ = make_service(self.tmp.name, source, now_ms=100000)
        capture, _ = capture_rows(service, snapshot.root)
        rows = tuple(replace(row, in_progress=True) for row in capture.rows[-2:])
        cost = reconcile_session_cost(self.repository, snapshot, catalog())
        entry = CardSession(snapshot.root, 'revision', 1, capture=replace(capture, rows=rows),
            session_cost=cost, cost_generation=1, cost_state='observed', state='observed')
        cards = WatchCards(None)
        cards.sessions[snapshot.root.session_id] = entry

        with patch('src.analysis.session_cost.reconcile_session_cost', side_effect=AssertionError('presentation work')):
            first = cards.project(100000)[0]
            second = cards.project(100001)[0]
            entry.capture = None
            entry.capture = replace(capture, rows=rows)
            reentry = cards.project(100002)[0]
        summaries = project_live(WatchProjection('Watch', 'fixture', (), active_cards=first)).to_json()['active_cards']

        self.assertEqual(2, len(first))
        self.assertTrue(all(card.session_cost is cost for card in (*first, *second, *reentry)))
        self.assertEqual(summaries[0]['session_summary'], summaries[1]['session_summary'])
        self.assertNotIn('context_cell', summaries[0]['rows'][0])
        self.assertIn('incoming_context_tokens', summaries[0]['rows'][0]['prompt'])

    def test_cost_lane_is_bounded_and_does_not_delay_row_publication(self):
        source = SyntheticMonthSource(1, 8, month_start_ms=1000)
        root = source.snapshots['root-0000'].root
        started, release = Event(), Event()
        factory = lambda now: make_service(self.tmp.name, source, now_ms=now)[2]
        costs = SessionCosts(factory)
        workers = CardWorkers(factory, workers=1)
        self.addCleanup(costs.close)
        self.addCleanup(workers.close)
        self.addCleanup(release.set)
        def blocked(*args):
            started.set()
            if not release.wait(5):
                raise AssertionError('test release missing')
            return reconcile_session_cost(*args)
        with patch('src.watch.session_costs.reconcile_session_cost', side_effect=blocked):
            self.assertTrue(costs.submit(root.session_id, 1, source.snapshots[root.session_id], 100000))
            self.assertTrue(started.wait(3))
            self.assertFalse(costs.submit(root.session_id, 2, source.snapshots[root.session_id], 100001))
            workers.submit(root, 1, 100000)
            workers.jobs[root.session_id].result(timeout=3)
            self.assertIn('rows', [value.phase for value in workers.drain()])
            release.set()
            costs.job.result(timeout=3)
            self.assertEqual((root.session_id, 1), costs.drain()[:2])

    def test_scheduler_rejects_superseded_total_and_reconciles_new_capture(self):
        source = MutableSource(replace(make_snapshot(), complete=True))
        factory = lambda now: make_service(self.tmp.name, source, now_ms=now)[2]
        capture, _ = capture_rows(factory(10000), source.snapshot.root)
        costs = SessionCosts(factory)
        self.addCleanup(costs.close)
        cards = WatchCards(None, costs=costs)
        entry = CardSession(source.snapshot.root, source.snapshot.source_revision, 1)
        cards.sessions['root'] = entry
        cards.accept(CardResult('root', 1, 'rows', (capture, (), None)), 10000)
        cards._tick_costs(10000)
        costs.job.result(timeout=3)
        changed = replace(source.snapshot, source_revision='changed', invocations=source.snapshot.invocations[:-1])
        source.snapshot = changed
        entry.revision, entry.generation = 'changed', 2
        newer, _ = capture_rows(factory(10001), changed.root)

        cards.accept(CardResult('root', 2, 'rows', (newer, (), None)), 10001)
        cards._tick_costs(10001)
        self.assertIsNone(entry.session_cost, 'old generation is not a current total')
        costs.job.result(timeout=3)
        cards._tick_costs(10002)

        self.assertEqual('observed', entry.cost_state)
        self.assertEqual('changed', entry.session_cost.source_revision)
        self.assertEqual(len(changed.invocations), entry.session_cost.total.observed_requests)
        self.assertIsNone(entry.cost_snapshot)

    def test_pricing_only_refresh_reuses_exact_evidence_without_source_hydration(self):
        source = MutableSource(replace(make_snapshot(), complete=True))
        prices = [catalog()]
        def factory(now):
            service = make_service(self.tmp.name, source, now_ms=now)[2]
            service.pricing_provider.catalog = prices[0]
            return service
        capture, _ = capture_rows(factory(10000), source.snapshot.root)
        costs = SessionCosts(factory)
        self.addCleanup(costs.close)
        cards = WatchCards(None, costs=costs)
        entry = CardSession(source.snapshot.root, source.snapshot.source_revision, 1)
        cards.sessions['root'] = entry
        cards.accept(CardResult('root', 1, 'rows', (capture, (), None)), 10000)
        cards._tick_costs(10000)
        costs.job.result(timeout=3)
        cards._tick_costs(10001)
        self.assertTrue(entry.session_cost.total.complete)
        loads = source.load_count
        prices[0] = replace(prices[0], models=())

        cards._tick_costs(70000)
        self.assertIsNotNone(costs.job)
        costs.job.result(timeout=3)
        cards._tick_costs(70001)

        self.assertFalse(entry.session_cost.total.complete)
        self.assertEqual(loads, source.load_count)
        self.assertEqual('observed', entry.cost_state, 'pricing coverage remains distinct from source coverage')

    def test_aggregate_resources_need_no_source_service_or_schema_writes(self):
        snapshot = replace(make_snapshot(), complete=True)
        reconcile_session_cost(self.repository, snapshot, catalog())
        def forbidden(now):
            self.fail('aggregate-only work must not create another source service')
        costs = SessionCosts(forbidden, lambda: (self.repository, catalog()))
        self.addCleanup(costs.close)
        with patch.object(self.database, 'initialize', side_effect=AssertionError('schema write')), \
                patch.object(self.repository, 'put', side_effect=AssertionError('no-op write')):
            costs.submit('root', 1, snapshot, 10000)
            costs.job.result(timeout=3)
            value = costs.drain()[2]
        self.assertEqual(0, value.valued_requests)
        self.assertFalse(value.cache_written)


if __name__ == '__main__':
    unittest.main()
