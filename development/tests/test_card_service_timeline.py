"""Numeric future timing is unique per group and observes, never releases, permits."""
from concurrent.futures import Future
from types import SimpleNamespace
import unittest

from development.tests.fixtures.card_service_timeline import CardServiceTimeline
from src.domain.acquisition import AcquisitionMetrics


class HeldPool:
    def __init__(self):
        self.calls = []

    def submit(self, function):
        future = Future()
        self.calls.append((function, future))
        return future

    def complete(self):
        function, future = self.calls[-1]
        future.set_result(function())


class CardServiceTimelineTests(unittest.TestCase):
    def test_factory_and_source_counters_are_observed_after_cleanup_without_retaining_services(self):
        clock = [0.0]
        pool = HeldPool()
        metrics = AcquisitionMetrics(generation='v2')
        transport = {'requests':1, 'connections_opened':1, 'private':'not evidence'}
        service = SimpleNamespace(metrics=metrics, source=SimpleNamespace(_diagnostics={'transport':transport}))

        def factory(_now):
            clock[0] += .5
            return service

        workers = SimpleNamespace(pool=pool, jobs={}, history_jobs=set(), factory=factory,
            _publish=lambda *_: None, drain=lambda: ())
        cards = SimpleNamespace(workers=workers, sessions={}, active_candidates=set(),
            _focals=lambda *_: (), tick=lambda _now: ())
        timeline = CardServiceTimeline(clock=lambda: clock[0])
        timeline.attach(cards)

        def _capture(_root):
            self.assertIs(service, workers.factory(1000))
            metrics.add('full_catalog_fetches', 2)
            transport['requests'] += 3
            clock[0] += 1

        pool.submit(_capture, object())
        pool.complete()
        observed = timeline.summary()['futures'][0]

        self.assertEqual(.5, observed['factory_seconds'])
        self.assertEqual(2, observed['acquisition']['counts']['full_catalog_fetches'])
        self.assertEqual({'requests':4, 'connections_opened':1}, observed['transport'])
        self.assertNotIn('not evidence', str(observed))
        self.assertIsNone(timeline.current.resources)

    def test_group_completion_wait_is_counted_once_with_logical_permits(self):
        clock = [0.0]
        pool = HeldPool()
        workers = SimpleNamespace(pool=pool, jobs={}, history_jobs=set())
        published = []
        workers._publish = lambda *values: published.append(values)

        def drain():
            for key, future in tuple(workers.jobs.items()):
                if future.done():
                    del workers.jobs[key]
            return ()

        workers.drain = drain
        entry = SimpleNamespace(refresh_requested=True, verified_generation=0, generation=1)
        cards = SimpleNamespace(workers=workers, sessions={'pending':entry}, active_candidates=set(),
            _focals=lambda *_: (), tick=lambda _now: workers.drain())
        timeline = CardServiceTimeline(clock=lambda: clock[0])
        timeline.attach(cards)

        def _capture_batch(_requests):
            clock[0] = 1.0
            workers._publish('private-root', 1, 'rows', object(), 1000)
            clock[0] = 2.0

        future = pool.submit(_capture_batch, (object(), object()))
        workers.jobs.update(first=future, second=future)
        workers.history_jobs.update(('first', 'second'))
        pool.complete()
        clock[0] = 2.25
        cards.tick(2250)
        observed = timeline.summary()

        self.assertEqual(1, observed['unique_futures'])
        self.assertEqual(.5, observed['completed_permit_wait_with_ready_history_seconds'])
        self.assertEqual({'rows':1}, observed['futures'][0]['outcomes'])
        self.assertEqual('history', observed['futures'][0]['role'])
        self.assertEqual(2.0, observed['futures'][0]['future_completed'])
        self.assertEqual(2.25, observed['futures'][0]['owner_reaped'])
        self.assertNotIn('private-root', str(observed))
        self.assertEqual(1, len(published))
        self.assertEqual({}, workers.jobs)

    def test_completed_future_is_not_reaped_or_counted_without_owner_drain(self):
        pool = HeldPool()
        workers = SimpleNamespace(pool=pool, jobs={}, history_jobs=set(), _publish=lambda *_: None,
            drain=lambda: ())
        cards = SimpleNamespace(workers=workers, sessions={}, active_candidates=set(),
            _focals=lambda *_: (), tick=lambda _now: workers.drain())
        timeline = CardServiceTimeline(clock=lambda: 0.0)
        timeline.attach(cards)

        future = pool.submit(lambda: None)
        workers.jobs['occupied'] = future
        pool.complete()
        observed = timeline.summary()

        self.assertEqual({'occupied':future}, workers.jobs)
        self.assertNotIn('owner_reaped', observed['futures'][0])
        self.assertEqual(0, observed['completed_permit_wait_with_ready_history_seconds'])


if __name__ == '__main__':
    unittest.main()
