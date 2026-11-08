"""Completion wakes refill existing permits without accelerating Live/source cadence."""
from concurrent.futures import Future
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from development.tests.fixtures.session_snapshots import make_snapshot
from src.application.live import LiveRuntime
from src.reports.watch_capture import WatchCapture
from src.sources.errors import SourceConcurrentChangeError
from src.watch.card_workers import CardRequest, CardResult, CardWorkers
from src.watch.cards import CardSession, WatchCards


class ControlledWorkers:
    limit = 4
    history_limit = 3

    def __init__(self):
        self.jobs, self.history_jobs, self.results = {}, set(), []
        self.admissions = []

    def drain(self):
        results, self.results = self.results, []
        for result in results:
            self.jobs.pop(result.session_id, None)
            self.history_jobs.discard(result.session_id)
        return results

    def submit_many(self, requests, _now):
        for request in requests:
            key = request.root.session_id
            self.jobs[key] = object()
            if request.historical:
                self.history_jobs.add(key)
            self.admissions.append(key)
        return tuple(request.root.session_id for request in requests)


class WatchCompletionServiceTests(unittest.TestCase):
    def owner(self):
        from dataclasses import replace
        workers = ControlledWorkers()
        cards = WatchCards(workers)
        root = make_snapshot().root
        for index in range(8):
            key = f'root-{index}'
            cards.sessions[key] = CardSession(replace(root, session_id=key), 'revision', index + 1)
        return cards, workers

    def test_success_refills_existing_slots_without_cost_guidance_or_proof_publication(self):
        cards, workers = self.owner()
        cards.tick(10000)
        finished = workers.admissions[0]
        entry = cards.sessions[finished]
        capture = WatchCapture(finished, 'Synthetic', (), 1, 10000, authoritative=True)
        workers.results.append(CardResult(finished, entry.generation, 'rows', (capture, (), None), 10000))
        cards.guidance = SimpleNamespace(tick=Mock(), pending=False)
        with patch.object(cards, '_tick_costs') as costs, patch.object(cards.history, 'project') as publication:
            cards.tick(10001, completed_only=True)

        self.assertEqual(4, len(workers.admissions))
        self.assertEqual(3, len(workers.jobs))
        self.assertEqual(entry.generation, entry.verified_generation)
        costs.assert_not_called()
        cards.guidance.tick.assert_not_called()
        publication.assert_not_called()

    def test_existing_three_history_permits_complete_independent_winners_in_three_rounds(self):
        from dataclasses import replace
        import tempfile
        from development.tests.fixtures.synthetic_month import SyntheticMonthSource
        from development.tests.fixtures.watch_runtime import make_service
        from src.reports.watch_capture import capture_rows
        from src.watch.observers import CatalogObservation

        with tempfile.TemporaryDirectory() as tmp:
            source = SyntheticMonthSource(8, 1, month_start_ms=1000)
            source.snapshots = {key: replace(value, complete=True) for key, value in source.snapshots.items()}
            _, _, service, _ = make_service(tmp, source, now_ms=1_000_000)
            self.addCleanup(service.close_accounts)
            roots = source.list_sessions()
            captures = {root.session_id: capture_rows(service, root)[0] for root in roots}
            workers = ControlledWorkers()
            cards = WatchCards(workers)
            cards.catalog(CatalogObservation(roots, roots, {root.session_id:root.session_id for root in roots},
                {root.session_id:'revision' for root in roots}, frozenset()))
            cards.tick(1_000_000)
            for turn in range(1, 4):
                for key in tuple(workers.jobs):
                    workers.results.append(CardResult(key, cards.sessions[key].generation, 'rows', (captures[key], (), None)))
                cards.tick(1_000_000 + turn, completed_only=True)
                _, history, state = cards.project(1_000_000 + turn)
                self.assertEqual('observed' if turn == 3 else 'loading', cards.history.state)
            self.assertEqual([f'root-{index:04d}' for index in range(3, 8)], [card.session_id for card in history])

    def test_three_history_permits_include_guidance_and_still_admit_live_and_real_history(self):
        cards, workers = self.owner()
        workers.jobs['guidance'] = object()
        workers.history_jobs.add('guidance')
        cards.active_candidates = frozenset({'root-0'})

        cards.tick(10000)

        self.assertIn('root-0', workers.jobs)
        self.assertNotIn('root-0', workers.history_jobs)
        self.assertEqual(3, len(workers.history_jobs))
        self.assertEqual(4, len(workers.jobs))
        self.assertEqual(2, len(workers.history_jobs - {'guidance'}))

    def test_churn_completion_cannot_start_a_fault_only_fast_retry_loop(self):
        cards, workers = self.owner()
        cards.tick(10000)
        original = list(workers.admissions)
        for key in original:
            workers.results.append(CardResult(key, cards.sessions[key].generation, 'unavailable',
                SourceConcurrentChangeError('Synthetic changing revision'), 10000))

        cards.tick(10001, completed_only=True)

        self.assertEqual(original, workers.admissions)
        self.assertEqual({}, workers.jobs)
        cards.tick(10002, completed_only=True)
        self.assertEqual(original, workers.admissions, 'a redundant late notification cannot restart a failed burst')
        cards.tick(10250)
        self.assertEqual(6, len(workers.admissions), 'normal cadence may admit the next fair bounded round')
        self.assertTrue(all(cards.sessions[key].refresh_requested for key in original))

    def test_done_future_cannot_be_reclaimed_ahead_of_its_queued_result(self):
        workers = CardWorkers(lambda _now: None)
        future = Future()
        result = CardResult('root', 1, 'rows', object())
        class RacingQueue:
            def __init__(self):
                self.raced, self.values = False, []

            def empty(self):
                if not self.raced:
                    self.raced = True
                    self.values.append(result)
                    future.set_result(None)
                    return True
                return not self.values

            def get(self):
                return self.values.pop(0)

        workers.jobs['root'] = future
        workers.results = RacingQueue()
        try:
            first = workers.drain()
            self.assertTrue(result in first or 'root' in workers.jobs,
                'a reclaimed future must have its queued result delivered before replacement planning')
            second = workers.drain()
            self.assertEqual([result], first + second)
            self.assertEqual({}, workers.jobs)
        finally:
            workers.close()

    def test_runtime_services_completion_without_an_extra_full_publication(self):
        class Coordinator:
            today_ccost = SimpleNamespace(history_pending=True)
            work_ready = Event()

            def tick_catalog(self, *_args, **_kwargs):
                pass

            def tick_details(self, *_args, **_kwargs):
                pass

        owner = Coordinator()
        driver = SimpleNamespace(coordinator=owner, tick=Mock(return_value=None), terminal=False,
            error=None, close=Mock())
        runtime = LiveRuntime(lambda: driver, Mock())
        owner.service_completed = Mock(side_effect=runtime.stopping.set)
        owner.work_ready.set()
        runtime._publish_frame = Mock()

        with patch('src.application.live.time.monotonic', return_value=100):
            runtime._run()

        self.assertEqual(1, driver.tick.call_count)
        self.assertEqual(1, runtime._publish_frame.call_count)
        owner.service_completed.assert_called_once_with()
        driver.close.assert_called_once_with()

    def test_cancel_interrupts_completion_wait(self):
        workers = CardWorkers(lambda _now: None)
        try:
            workers.cancel()
            self.assertTrue(workers.completed.is_set())
        finally:
            workers.close()

    def test_due_publication_wins_over_a_completion_arriving_during_service(self):
        class Coordinator:
            today_ccost = SimpleNamespace(history_pending=True)
            work_ready = Event()

            def tick_catalog(self, *_args, **_kwargs):
                pass

            def tick_details(self, *_args, **_kwargs):
                pass

        owner, clock = Coordinator(), [100.0]
        driver = SimpleNamespace(coordinator=owner, terminal=False, error=None, close=Mock())
        runtime = LiveRuntime(lambda: driver, Mock())
        def tick():
            if driver.tick.call_count == 2:
                runtime.stopping.set()
        driver.tick = Mock(side_effect=tick)
        def service():
            clock[0] += .3
            owner.work_ready.set()
        owner.service_completed = Mock(side_effect=service)
        owner.work_ready.set()
        runtime._publish_frame = Mock()

        with patch('src.application.live.time.monotonic', side_effect=lambda: clock[0]):
            runtime._run()

        self.assertEqual(2, driver.tick.call_count)
        self.assertEqual(2, runtime._publish_frame.call_count)
        owner.service_completed.assert_called_once_with()
        self.assertTrue(owner.work_ready.is_set(), 'a wake arriving during servicing must remain signalled')

    def test_group_rows_do_not_notify_or_release_permits_before_cleanup_finishes(self):
        from dataclasses import replace
        workers = CardWorkers(lambda _now: None, batch_size=2)
        queued, release = Event(), Event()
        root = make_snapshot().root
        roots = (replace(root, session_id='first'), replace(root, session_id='second'))
        def capture(requests, now_ms):
            for request in requests:
                workers._publish(request.root, request.generation, 'rows', object(), now_ms)
            queued.set()
            if not release.wait(3):
                raise RuntimeError('fixture_cleanup_release_missing')
        workers._capture_batch = capture
        original_completed = workers.completed
        workers.completed = Mock(wraps=original_completed)
        try:
            workers.submit_many(tuple(CardRequest(root, 1, historical=True) for root in roots), 10000)
            self.assertTrue(queued.wait(2))
            self.assertEqual(2, len(workers.jobs))
            self.assertFalse(original_completed.is_set())
            self.assertEqual(2, len(workers.drain()))
            self.assertEqual(2, len(workers.jobs))

            release.set()
            for future in set(workers.jobs.values()):
                future.result(timeout=2)
            self.assertTrue(original_completed.wait(2))
            workers.drain()

            self.assertEqual({}, workers.jobs)
            workers.completed.set.assert_called_once_with()
        finally:
            release.set()
            workers.close()


if __name__ == '__main__':
    unittest.main()
