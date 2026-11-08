"""Watch-only shared brackets preserve individual proof, failure and admission."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from threading import Event, Lock
import tempfile
import unittest
from unittest.mock import patch

from development.tests.fixtures.opencode_v2_service import source_with_current_service
from development.tests.fixtures.watch_runtime import make_service
from src.reports.watch_capture import capture_rows
from src.sources.errors import SourceError, SourceConcurrentChangeError, http_failure, transport_failure
from src.watch.card_workers import CardRequest, CardWorkers
from src.watch.cards import WatchCards
from src.watch.observers import observe_catalog


def add_roots(server, count=6):
    template = deepcopy(server.sessions[0])
    messages = deepcopy(server.messages['ses_current'])
    server.sessions = []
    server.messages = {}
    for index in range(count):
        key = f'ses_batch_{index}'
        root = deepcopy(template)
        root.update(id=key, title='Synthetic')
        server.sessions.append(root)
        values = deepcopy(messages)
        for message in values:
            message['id'] += f'_{index}'
        values[-1]['time']['completed'] = 4000 + index
        server.messages[key] = values


class WatchCardBatchTests(unittest.TestCase):
    def test_root_read_failure_preserves_certified_siblings_without_changing_strict_api(self):
        with source_with_current_service() as (source, server, _registration):
            add_roots(server)
            original = source._load_messages
            def read(native):
                if native.data['id'] == 'ses_batch_1':
                    raise transport_failure(TimeoutError(), phase='messages')
                return original(native)
            with patch.object(source, '_load_messages', side_effect=read):
                snapshots, failures = source.load_card_snapshots(('ses_batch_0', 'ses_batch_1', 'ses_batch_2'))
                with self.assertRaises(SourceError):
                    source.load_session_snapshots_available(('ses_batch_0', 'ses_batch_1'), lambda *_: None)

            self.assertEqual({'ses_batch_0', 'ses_batch_2'}, set(snapshots))
            self.assertTrue(all(value.complete for value in snapshots.values()))
            self.assertEqual({'ses_batch_1'}, set(failures))
            self.assertEqual('connection_timeout', failures['ses_batch_1'].code)

    def test_authentication_failure_is_not_a_member_failure(self):
        with source_with_current_service() as (source, server, _registration):
            add_roots(server)
            with patch.object(source, '_load_messages', side_effect=http_failure(401, phase='messages')):
                with self.assertRaises(SourceError) as raised:
                    source.load_card_snapshots(('ses_batch_0', 'ses_batch_1'))
            self.assertEqual('http_auth_failure', raised.exception.code)

    def test_membership_loss_leaves_only_that_root_unverified(self):
        with source_with_current_service() as (source, server, _registration):
            add_roots(server)
            listings = [0]
            def catalog(query):
                if 'cursor' not in query:
                    listings[0] += 1
                    if listings[0] == 2:
                        server.sessions = [root for root in server.sessions if root['id'] != 'ses_batch_1']
            server.before_catalog = catalog

            snapshots, failures = source.load_card_snapshots(('ses_batch_0', 'ses_batch_1'))

            self.assertEqual({'ses_batch_0'}, set(snapshots))
            self.assertEqual({'ses_batch_1'}, set(failures))
            self.assertEqual('concurrent_source_change', failures['ses_batch_1'].code)

    def test_missing_after_catalog_and_software_fault_never_publish_siblings(self):
        with source_with_current_service() as (source, server, _registration):
            add_roots(server)
            original = source._list_native_sessions
            listings = [0]
            def catalog(*args, **kwargs):
                listings[0] += 1
                if listings[0] == 2:
                    raise transport_failure(TimeoutError(), phase='sessions')
                return original(*args, **kwargs)
            with patch.object(source, '_list_native_sessions', side_effect=catalog):
                with self.assertRaises(SourceError):
                    source.load_card_snapshots(('ses_batch_0', 'ses_batch_1'))
            with patch.object(source, '_load_messages', side_effect=ValueError('synthetic defect')):
                with self.assertRaisesRegex(ValueError, 'synthetic defect'):
                    source.load_card_snapshots(('ses_batch_0', 'ses_batch_1'))

    def test_restart_during_hydration_rejects_entire_batch_even_with_identical_metadata(self):
        with source_with_current_service() as (source, server, registration):
            import json
            add_roots(server)
            before = registration.read_text(encoding='utf-8')
            restart_lock = Lock()
            def restart(_session_id):
                with restart_lock:
                    if server.before_message is None:
                        return
                    value = json.loads(before)
                    value['pid'] += 1
                    replacement = registration.with_suffix('.replacement')
                    replacement.write_text(json.dumps(value), encoding='utf-8')
                    replacement.replace(registration)
                    server.before_message = None
            server.before_message = restart

            with self.assertRaises(SourceConcurrentChangeError):
                source.load_card_snapshots(('ses_batch_0', 'ses_batch_1'))

    def test_preacquired_capture_is_identical_and_does_not_read_again(self):
        with source_with_current_service() as (source, server, _registration), tempfile.TemporaryDirectory() as tmp:
            add_roots(server)
            root = observe_catalog(source).roots[0]
            service = make_service(tmp, source, now_ms=90000)[2]
            snapshot = source.load_session_snapshot(root.session_id)
            expected, _ = capture_rows(service, root)

            with patch.object(source, 'load_session_snapshot', side_effect=AssertionError('duplicate acquisition')):
                actual, item = capture_rows(service, root, fresh=snapshot)

            self.assertEqual(expected, actual)
            self.assertEqual(snapshot, item.snapshot)

    def test_history_reserves_active_capacity_and_total_occupancy_is_per_root(self):
        with source_with_current_service() as (source, server, registration), tempfile.TemporaryDirectory() as tmp:
            from src.sources.opencode_v2 import OpenCodeV2Source
            add_roots(server)
            started, release = Event(), Event()
            original = OpenCodeV2Source.load_card_snapshots
            def blocked(reader, ids, **options):
                started.set()
                if not release.wait(5):
                    raise RuntimeError('fixture release missing')
                return original(reader, ids, **options)
            def factory(now):
                reader = OpenCodeV2Source(registration, timeout_seconds=2)
                return make_service(tmp, reader, now_ms=now)[2]
            workers = CardWorkers(factory, batch_size=3)
            cards = WatchCards(workers)
            observation = observe_catalog(source)
            cards.catalog(observation)
            try:
                with patch.object(OpenCodeV2Source, 'load_card_snapshots', blocked):
                    cards.tick(90000)
                    self.assertTrue(started.wait(3))
                    self.assertEqual(3, len(workers.jobs))
                    self.assertEqual(1, len(set(workers.jobs.values())))
                    active = next(root.session_id for root in observation.roots if root.session_id not in workers.jobs)
                    cards.catalog(replace(observation, active_candidates=frozenset({active})))

                    cards.tick(90001)

                    self.assertIn(active, workers.jobs)
                    self.assertEqual(4, len(workers.jobs))
                    self.assertEqual(2, len(set(workers.jobs.values())))
            finally:
                release.set()
                workers.close()

    def test_slow_member_transport_is_joined_then_replayed_fairly_without_false_outage(self):
        with source_with_current_service() as (source, server, registration), tempfile.TemporaryDirectory() as tmp:
            from src.sources.opencode_v2 import OpenCodeV2Source
            add_roots(server)
            blocked, release = Event(), Event()
            def delay(key):
                if key == 'ses_batch_1':
                    blocked.set()
                    release.wait(5)
            server.before_message = delay
            def factory(now):
                reader = OpenCodeV2Source(registration, timeout_seconds=2)
                return make_service(tmp, reader, now_ms=now)[2]
            workers = CardWorkers(factory, batch_size=3, batch_hydration_seconds=.15)
            cards = WatchCards(workers)
            cards.catalog(observe_catalog(source))
            try:
                cards.tick(90000)
                self.assertTrue(blocked.wait(3))
                for future in set(workers.jobs.values()):
                    future.result(timeout=3)
                results = workers.drain()
                self.assertEqual(3, sum(result.phase == 'replay' for result in results))
                self.assertFalse(any(result.phase in ('rows', 'unavailable') for result in results))
                self.assertFalse(workers.jobs, 'occupied readers must be joined before retry admission')
                for result in results:
                    if result.phase != 'timing':
                        cards.accept(result, 90000)
                self.assertFalse(cards.sessions['ses_batch_1'].batchable)
                self.assertTrue(all(entry.source_status.failed_at is None for entry in cards.sessions.values()))
                # The next untouched batch finishes while the slow source is still gated.
                cards.tick(90000)
                for future in set(workers.jobs.values()):
                    future.result(timeout=3)
                cards.tick(90000)
                for key, future in tuple(workers.jobs.items()):
                    if key != 'ses_batch_1':
                        future.result(timeout=3)
                cards.tick(90000)
                cards.project(90000)
                self.assertEqual(5, cards.history.checked)
                self.assertEqual('loading', cards.history.state)
                release.set()
                for _ in range(12):
                    cards.tick(90000)
                    for future in set(workers.jobs.values()):
                        future.result(timeout=5)
                    if cards.history.checked == 6:
                        break
                    cards.project(90000)
                history = cards.project(90000)[1]
                self.assertEqual((6, 6, 'observed'),
                    (cards.history.checked, cards.history.total, cards.history.state))
                # The newest five are presented chronologically, as in Full Watch.
                self.assertEqual(tuple(f'ses_batch_{index}' for index in range(1, 6)),
                    tuple(card.session_id for card in history))
            finally:
                release.set()
                workers.close()

    def test_watchdog_also_observes_a_single_member_revision_retry(self):
        with source_with_current_service() as (source, server, registration), tempfile.TemporaryDirectory() as tmp:
            from src.sources.opencode_v2 import OpenCodeV2Source
            add_roots(server)
            retry_started, cancelled = Event(), Event()
            def factory(now):
                reader = OpenCodeV2Source(registration, timeout_seconds=2)
                original_list, original_read, original_cancel = (
                    reader._list_native_sessions, reader._load_messages, reader.cancel_reads)
                listings, reads = [0], [0]
                def catalog(*args, **options):
                    listings[0] += 1
                    if listings[0] == 2:
                        server.sessions[1]['time']['updated'] += 1
                    return original_list(*args, **options)
                def read(native):
                    if native.data['id'] == 'ses_batch_1':
                        reads[0] += 1
                        if reads[0] == 2:
                            retry_started.set()
                            cancelled.wait(2)
                            raise transport_failure(ConnectionAbortedError(), phase='messages')
                    return original_read(native)
                def cancel():
                    cancelled.set()
                    original_cancel()
                reader._list_native_sessions, reader._load_messages, reader.cancel_reads = catalog, read, cancel
                return make_service(tmp, reader, now_ms=now)[2]
            workers = CardWorkers(factory, batch_size=2, batch_hydration_seconds=.15)
            roots = tuple(root for root in observe_catalog(source).roots
                if root.session_id in ('ses_batch_0', 'ses_batch_1'))
            try:
                workers.submit_many(tuple(CardRequest(root, index + 1, historical=True)
                    for index, root in enumerate(roots)), 90000)
                self.assertTrue(retry_started.wait(3))
                self.assertTrue(cancelled.wait(1), 'the watchdog must cancel while retry hydration is blocked')
                for future in set(workers.jobs.values()):
                    future.result(timeout=3)
                results = workers.drain()

                self.assertTrue(cancelled.is_set(), 'a one-member retry must still observe the batch watchdog')
                self.assertEqual(2, sum(result.phase == 'replay' for result in results))
                self.assertFalse(any(result.phase in ('rows', 'unavailable') for result in results))
            finally:
                cancelled.set()
                workers.close()


if __name__ == '__main__':
    unittest.main()
