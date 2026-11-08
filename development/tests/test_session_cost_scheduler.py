"""Evidence-gated scalar totals: idle work counts, fairness, failures and re-entry."""
from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from development.tests.fixtures.pricing_catalog import catalog
from development.tests.fixtures.synthetic_month import make_root_snapshot
from src.cache import CacheDatabase, CacheRepository
from src.reports.watch_capture import WatchCapture
from src.watch.card_workers import CardResult
from src.watch.cards import CardSession, WatchCards
from src.watch.session_costs import SessionCosts, SessionCostState


class SessionCostSchedulerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        database = CacheDatabase(Path(temporary.name))
        database.initialize()
        self.repository = CacheRepository(database)
        self.prices = catalog()
        self.snapshot = replace(make_root_snapshot(0, 2, month_start_ms=1000), complete=True)
        self.costs = SessionCosts(None, lambda: (self.repository, self.prices))
        self.addCleanup(self.costs.close)

    def complete_job(self, states, visible, now_ms):
        self.costs.job.result(timeout=3)
        self.costs.tick(states, visible, now_ms)

    def test_four_minutes_republications_other_roots_generation_and_reentry_do_no_root_work(self):
        snapshot = self.snapshot
        root = snapshot.root
        workers = Mock(jobs={}, limit=4, history_limit=3, history_jobs=set())
        workers.drain.return_value = ()
        cards = WatchCards(workers, costs=self.costs)
        entry = CardSession(root, snapshot.source_revision, 1, refresh_requested=False)
        cards.sessions[root.session_id] = entry
        capture = WatchCapture(root.session_id, "Old", (), 1000, 2000,
            authoritative=True, cost_snapshot=snapshot)
        cards.accept(CardResult(root.session_id, 1, "rows", (capture, (), None)), 2000)
        cards._tick_costs(2000)
        self.costs.job.result(timeout=3)
        cards._tick_costs(2001)
        baseline = entry.cost.value

        with patch('src.watch.session_costs.reconcile_session_cost', side_effect=AssertionError('idle root work')), \
                patch.object(self.repository, 'put', side_effect=AssertionError('idle write')), \
                patch.object(self.costs, 'submit', wraps=self.costs.submit) as submissions:
            for now in range(3000, 244001, 1000):
                observation = SimpleNamespace(roots=(root,), revisions={root.session_id: snapshot.source_revision},
                    active_candidates=frozenset(), live_candidates=frozenset())
                cards.catalog(observation)
                entry.generation += 1  # A recapture's lifecycle is not a cost revision.
                if now % 17000 == 0:
                    entry.capture = None
                    entry.cost.evidence = None
                cards.accept(CardResult(root.session_id, entry.generation, "rows",
                    (replace(capture, observed_at_ms=now), (), None)), now)
                cards.tick(now)
                if self.costs.job is not None:
                    self.costs.job.result(timeout=3)
                    cards.tick(now + 1)
                history = cards.project(now)[1]
                self.assertIs(baseline, history[0].session_cost)
                self.assertEqual('observed', history[0].session_cost_state)

        self.assertTrue(submissions.call_args_list, 'shared catalog identity is still checked')
        self.assertTrue(all(call.args[0] is None for call in submissions.call_args_list))
        workers.submit.assert_not_called()
        workers.submit_many.assert_not_called()

    def test_running_continuation_only_values_new_request_and_restart_reuses_persisted_baseline(self):
        state = SessionCostState()
        state.observe(self.snapshot)
        states = {self.snapshot.root.session_id: state}
        self.costs.tick(states, states, 10000)
        self.complete_job(states, states, 10001)
        newer = replace(make_root_snapshot(0, 3, month_start_ms=1000), complete=True, source_revision='continued')

        state.observe(newer)
        self.assertEqual('checking', state.status)
        self.assertEqual(D('.0285'), state.value.total.known_ccost)
        self.costs.tick(states, states, 11000)
        self.complete_job(states, states, 11001)

        self.assertEqual((1, D('.0429')), (state.value.valued_requests, state.value.total.known_ccost))
        self.assertEqual('observed', state.status)
        restarted = SessionCostState()
        restarted.observe(newer)
        states[newer.root.session_id] = restarted
        self.costs.tick(states, states, 12000)
        self.complete_job(states, states, 12001)
        self.assertEqual((0, False, D('.0429')), (restarted.value.valued_requests,
            restarted.value.cache_written, restarted.value.total.known_ccost))

    def test_busy_roots_cannot_discard_baselines_or_starve_static_history(self):
        snapshots = [replace(make_root_snapshot(index, 2, month_start_ms=1000), complete=True) for index in range(3)]
        states = {snapshot.root.session_id: SessionCostState() for snapshot in snapshots}
        for snapshot in snapshots:
            states[snapshot.root.session_id].observe(snapshot)
        self.costs.tick(states, states, 10000)
        first = self.costs.identity[0]
        # The first root advances before its result is drained, on every turn.
        states[first].observe(replace(snapshots[0], source_revision='newer'))
        self.complete_job(states, states, 10001)
        self.assertIsNotNone(states[first].value)
        self.assertEqual('checking', states[first].status)
        self.assertNotEqual(first, self.costs.identity[0])
        self.complete_job(states, states, 10002)
        self.complete_job(states, states, 10003)
        self.complete_job(states, states, 10004)

        self.assertTrue(all(state.status == 'observed' for state in states.values()))
        self.assertEqual('newer', states[first].value.source_revision)
        self.assertEqual(0, states[first].value.valued_requests)

    def test_real_failures_are_unavailable_until_validation_and_completeness_recovers(self):
        state = SessionCostState()
        state.observe(self.snapshot)
        states = {self.snapshot.root.session_id: state}
        self.costs.tick(states, states, 10000)
        self.complete_job(states, states, 10001)
        baseline = state.value

        with patch.object(self.costs, 'resources_factory', side_effect=OSError('pricing/source unavailable')):
            self.costs.tick(states, states, 70000)
            self.complete_job(states, states, 70001)
            self.assertEqual('unavailable', state.status)
            self.assertIs(baseline, state.value)
            self.costs.tick(states, states, 74000)
            self.assertIsNone(self.costs.job)
        self.costs.tick(states, states, 75000)
        self.complete_job(states, states, 75001)
        self.assertEqual('observed', state.status)

        state.observe(replace(self.snapshot, complete=False))
        self.costs.tick(states, states, 76000)
        self.complete_job(states, states, 76001)
        self.assertEqual('partial', state.status)
        state.observe(self.snapshot)
        self.costs.tick(states, states, 77000)
        self.complete_job(states, states, 77001)
        self.assertEqual('observed', state.status)

    def test_changed_source_identity_rejects_old_result_and_permanent_failure_is_not_loading(self):
        state = SessionCostState()
        state.observe(self.snapshot)
        states = {self.snapshot.root.session_id: state}
        self.costs.tick(states, states, 10000)
        self.costs.job.result(timeout=3)
        changed = replace(self.snapshot, root=replace(self.snapshot.root,
            provenance=replace(self.snapshot.root.provenance, source_instance='replacement')))
        state.observe(changed)
        with patch.object(self.costs, 'resources_factory', side_effect=OSError('source failed')):
            self.complete_job(states, states, 10001)
            self.assertIsNone(state.value, 'never borrow a baseline from another source')
            self.complete_job(states, states, 10002)
            self.assertEqual('unavailable', state.status)
            self.costs.tick(states, states, 15002)
            self.complete_job(states, states, 15003)
        self.assertIsNone(state.value)
        self.assertEqual('unavailable', state.status)


if __name__ == '__main__':
    unittest.main()
