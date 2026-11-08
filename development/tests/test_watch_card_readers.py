"""Exclusive card-reader reuse preserves brackets, epochs and shutdown ownership."""
import json
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import tempfile
import time
import unittest
from unittest.mock import patch

from development.tests.fixtures.opencode_v2_service import source_with_current_service
from development.tests.fixtures.watch_runtime import make_service
from src.sources.errors import SourceConcurrentChangeError, SourceError
from src.sources.selection import SourceSelector
from src.watch.card_workers import CardRequest, CardWorkers


class CardReaderSourceTests(unittest.TestCase):
    def test_second_job_saves_only_before_catalog_and_keeps_probe_and_after_bracket(self):
        with source_with_current_service() as (origin, _server, _registration):
            reader = origin.new_card_reader()
            self.addCleanup(reader.close_reads)
            self.assertEqual(origin.registration_path, reader.registration_path)
            self.assertEqual(origin._timeout_seconds, reader._timeout_seconds)
            for expected_catalogs in (2, 1):
                reader.begin_card_read(origin)
                with patch.object(reader, 'probe', wraps=reader.probe) as probe:
                    selection = SourceSelector(v2_factory=lambda: reader, inspect_migration_gap=False).select('v2')
                probe.assert_called_once_with()
                snapshot = selection.source.load_session_snapshot('ses_current')
                self.assertTrue(snapshot.complete)
                self.assertEqual(expected_catalogs, reader.metrics.counts['full_catalog_fetches'])
                self.assertEqual(1 if expected_catalogs == 1 else 0,
                    reader._diagnostics['snapshot_catalog_reuses'])

    def test_expiry_actor_content_and_registration_change_each_invalidate_retained_catalog(self):
        with source_with_current_service() as (origin, _server, registration):
            reader = origin.new_card_reader()
            self.addCleanup(reader.close_reads)
            reader.begin_card_read(origin)
            reader.load_session_snapshot('ses_current')
            old_listed = reader._catalog_listed_at
            reader.begin_card_read(origin)
            self.assertEqual(old_listed, reader._catalog_listed_at, 'borrowing must not renew freshness')
            with patch('src.sources.opencode_v2.time.monotonic', return_value=old_listed + 3):
                reader.load_session_snapshot('ses_current')
            self.assertEqual(2, reader.metrics.counts['full_catalog_fetches'])
            for event_name in ('first', 'other'):
                # Same-size replacement must invalidate too, not just additions.
                origin._interruptions._observed.clear()
                origin._interruptions.observe(dict(id='evt_' + event_name,
                    type='session.execution.interrupted', created=5000,
                    data=dict(sessionID='ses_current', reason='user')))
                reader.begin_card_read(origin)
                self.assertIsNone(reader._catalog_cache)
                self.assertIsNone(reader._catalog_index)
                reader.load_session_snapshot('ses_current')
                self.assertEqual(2, reader.metrics.counts['full_catalog_fetches'])
            value = json.loads(registration.read_text(encoding='utf-8'))
            value['pid'] += 1
            registration.write_text(json.dumps(value), encoding='utf-8')
            reader.begin_card_read(origin)
            self.assertIsNone(reader._catalog_cache)
            self.assertEqual((), reader._interruptions.signature('ses_current'))

    def test_singleton_rejects_restart_even_when_tree_metadata_is_unchanged(self):
        with source_with_current_service() as (origin, server, registration):
            reader = origin.new_card_reader()
            self.addCleanup(reader.close_reads)
            reader.begin_card_read(origin)

            def restart(_key):
                value = json.loads(registration.read_text(encoding='utf-8'))
                value['pid'] += 1
                registration.write_text(json.dumps(value), encoding='utf-8')
                server.before_message = None

            server.before_message = restart
            with self.assertRaises(SourceConcurrentChangeError):
                reader.load_session_snapshot('ses_current')

    def test_job_metrics_diagnostics_and_skills_reset_without_retaining_prior_service_metrics(self):
        with source_with_current_service() as (origin, _server, _registration):
            reader = origin.new_card_reader()
            self.addCleanup(reader.close_reads)
            reader.begin_card_read(origin)
            reader.load_session_snapshot('ses_current')
            old_metrics = reader.metrics
            old_counts = old_metrics.snapshot()
            client = reader._http
            reader._skill_origin_cache['old-location'] = {'old-skill':'custom'}

            reader.begin_card_read(origin)
            self.assertIs(client, reader._http)
            self.assertEqual({}, reader._skill_origin_cache)
            self.assertEqual({}, reader._diagnostics['message_contracts'])
            self.assertEqual(0, sum(reader._diagnostics['transport'].values()))
            reader.load_session_snapshot('ses_current')

            self.assertIsNot(old_metrics, reader.metrics)
            self.assertEqual(old_counts, old_metrics.snapshot())
            self.assertEqual(1, reader.metrics.counts['full_catalog_fetches'])
            self.assertIs(client.stats, reader._diagnostics['transport'])
            self.assertGreater(client.stats['requests'], 0)


class OwnedReader:
    def __init__(self):
        self.cancelled = Event()
        self.closed = False

    def cancel_reads(self):
        self.cancelled.set()

    def close_reads(self):
        self.closed = True


class CardReaderOwnershipTests(unittest.TestCase):
    def test_real_worker_jobs_keep_one_reader_but_fresh_analysis_and_per_job_counters(self):
        from src.watch.card_readers import CardReaders
        with source_with_current_service() as (origin, _server, _registration), tempfile.TemporaryDirectory() as tmp:
            services = []
            readers = CardReaders(origin.new_card_reader, limit=1)

            def factory(now, *, reader):
                reader.begin_card_read(origin)
                SourceSelector(v2_factory=lambda: reader, inspect_migration_gap=False).select('v2')
                service = make_service(tmp, reader, now_ms=now)[2]
                services.append(service)
                return service

            workers = CardWorkers(factory, workers=1, readers=readers)
            workers.defer_guidance = True
            root = origin.list_sessions()[0]
            try:
                for generation in (1, 2):
                    self.assertTrue(workers.submit(root, generation, 90000))
                    for future in set(workers.jobs.values()):
                        future.result(timeout=3)
                    results = workers.drain()
                    self.assertEqual(1, sum(value.phase == 'rows' for value in results))
                    self.assertFalse(any(value.phase == 'unavailable' for value in results))
                self.assertIsNot(services[0], services[1])
                self.assertIs(services[0].source, services[1].source)
                self.assertIsNot(services[0].metrics, services[1].metrics)
                self.assertEqual([2, 1], [service.metrics.counts['full_catalog_fetches'] for service in services])
            finally:
                workers.close()

    def test_batch_replay_retires_cancelled_reader_before_next_single_capture(self):
        from src.watch.card_readers import CardReaders
        from src.sources.opencode_v2 import OpenCodeV2Source
        with source_with_current_service() as (origin, server, _registration), tempfile.TemporaryDirectory() as tmp:
            other = deepcopy(server.sessions[0])
            other['id'] = 'ses_other'
            server.sessions.append(other)
            server.messages['ses_other'] = deepcopy(server.messages['ses_current'])
            services = []
            readers = CardReaders(origin.new_card_reader)

            def factory(now, *, reader):
                reader.begin_card_read(origin)
                service = make_service(tmp, reader, now_ms=now)[2]
                services.append(service)
                return service

            def overrun(reader, _ids, *, progress, on_root):
                reader._client()
                progress('messages', 0, 2)
                time.sleep(.01)
                progress('messages', 0, 2)
                self.fail('hydration overrun must replay')

            workers = CardWorkers(factory, readers=readers, batch_size=2, batch_hydration_seconds=.001)
            workers.defer_guidance = True
            roots = tuple(root for root in origin.list_sessions() if root.parent_session_id is None)
            try:
                with patch.object(OpenCodeV2Source, 'load_card_snapshots', overrun):
                    workers.submit_many(tuple(CardRequest(root, 1, historical=True) for root in roots), 90000)
                    for future in set(workers.jobs.values()):
                        future.result(timeout=3)
                    results = workers.drain()
                self.assertEqual(2, sum(value.phase == 'replay' for value in results))
                self.assertFalse(any(value.phase in ('rows', 'unavailable') for value in results))
                self.assertTrue(services[0].source._reads_cancelled.is_set())
                self.assertTrue(workers.submit(roots[0], 2, 90000))
                for future in set(workers.jobs.values()):
                    future.result(timeout=3)
                self.assertTrue(any(value.phase == 'rows' for value in workers.drain()))
                self.assertIsNot(services[0].source, services[1].source)
            finally:
                workers.close()

    def test_sequential_borrows_reuse_but_failure_retires_and_close_cancels_idle_reader(self):
        from src.watch.card_readers import CardReaders
        created = []

        def factory():
            reader = OwnedReader()
            created.append(reader)
            return reader

        readers = CardReaders(factory, limit=1)
        with readers.borrow() as first:
            pass
        with readers.borrow() as again:
            self.assertIs(first, again)
        with self.assertRaisesRegex(ValueError, 'defect'):
            with readers.borrow():
                raise ValueError('defect')
        self.assertTrue(first.closed)
        self.assertTrue(first.cancelled.is_set())
        with readers.borrow() as replacement:
            self.assertIsNot(first, replacement)
        readers.cancel()
        self.assertTrue(replacement.cancelled.is_set())
        readers.close()
        self.assertTrue(replacement.closed)
        self.assertEqual(2, len(created))
        with self.assertRaises(SourceError):
            with readers.borrow():
                self.fail('stopped owner must not revive a reader')

    def test_cancel_tracks_reader_before_first_blocking_validation(self):
        from src.watch.card_readers import CardReaders
        reader = OwnedReader()
        readers = CardReaders(lambda: reader, limit=1)
        started = Event()

        def validate():
            with readers.borrow() as selected:
                started.set()
                if not selected.cancelled.wait(3):
                    raise AssertionError('validation escaped cancellation')

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(validate)
            self.assertTrue(started.wait(2))
            readers.cancel()
            future.result(timeout=2)
        readers.close()
        self.assertTrue(reader.closed)

    def test_member_failure_discards_reader_only_after_certified_siblings_finish(self):
        from src.watch.card_readers import CardReaders
        reader = OwnedReader()
        readers = CardReaders(lambda: reader, limit=1)
        with readers.borrow() as selected:
            readers.discard(selected)
            self.assertFalse(reader.cancelled.is_set())
            self.assertFalse(reader.closed)
        self.assertTrue(reader.closed)
        self.assertTrue(reader.cancelled.is_set())
        readers.close()

    def test_worker_close_releases_idle_readers_even_when_completed_future_is_fatal(self):
        from src.watch.card_readers import CardReaders
        reader = OwnedReader()
        readers = CardReaders(lambda: reader, limit=1)
        workers = CardWorkers(lambda _now: None, workers=1, readers=readers)
        started = Event()

        def fail():
            with readers.borrow():
                pass
            started.set()
            raise ValueError('software defect')

        future = workers.pool.submit(fail)
        workers.jobs['synthetic'] = future
        self.assertTrue(started.wait(2))
        with self.assertRaisesRegex(ValueError, 'software defect'):
            workers.close()
        self.assertTrue(reader.closed)
        self.assertTrue(reader.cancelled.is_set())


if __name__ == '__main__':
    unittest.main()
