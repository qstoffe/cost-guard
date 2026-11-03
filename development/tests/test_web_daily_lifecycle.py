"""Real V2 bracket work charged against the unchanged Daily publication budget."""
from copy import deepcopy
from pathlib import Path
import tempfile
from threading import Event, Thread
import unittest
from unittest.mock import patch

from development.tests.fixtures.opencode_v2_service import source_with_current_service
from development.tests.fixtures.watch_runtime import make_service
from src.watch.web_coordinator import WebWatchCoordinator


class DailyCatalogBudgetTests(unittest.TestCase):
    def populate(self, remote, count):
        remote.session_page_size = 500
        template, messages = deepcopy(remote.sessions[0]), deepcopy(remote.messages['ses_current'])
        remote.sessions, remote.messages = [], {}
        for index in range(count):
            session = dict(template, id=f'session-{index}')
            remote.sessions.append(session)
            remote.messages[session['id']] = [dict(item, id=f'{item["id"]}-{index}',
                time={key: value + index * 10_000 for key, value in item['time'].items()})
                for item in deepcopy(messages)]

    def test_daily_batches_share_catalog_brackets_without_losing_requests(self):
        with source_with_current_service() as (source, remote, _):
            self.populate(remote, 64)
            sessions = source.list_sessions()
            # The measured baseline repeatedly spends ~1–2s on catalog brackets.
            # Charge two seconds per actual global fetch, not arbitrary sleeps or
            # fabricated output. All V2 pagination/revision proofs still execute.
            work_seconds = [0.0]
            catalogs = [0]
            original = source._list_native_sessions

            def catalog(*args, **kwargs):
                before = source.metrics.counts.get('full_catalog_fetches', 0)
                value = original(*args, **kwargs)
                fetched = source.metrics.counts.get('full_catalog_fetches', 0) - before
                catalogs[0] += fetched
                work_seconds[0] += fetched * 2
                return value

            with tempfile.TemporaryDirectory() as tmp:
                config, selection, service, _ = make_service(tmp, source, now_ms=80_000_000)
                owner = WebWatchCoordinator(selection=selection, report_service=service, config=config,
                    service_factory=lambda now: make_service(tmp, source, now_ms=now)[2])
                try:
                    with patch.object(source, '_list_native_sessions', side_effect=catalog):
                        result = owner._account_history(sessions, (), 80_000_000)
                    self.assertIsInstance(result, tuple)
                    self.assertEqual(64, result[1].mix.request_count)
                    self.assertEqual(64, result[1].prompt_count)
                    self.assertLessEqual(work_seconds[0], 120, f'{catalogs[0]} full catalog brackets')
                    self.assertLessEqual(catalogs[0], 34)
                finally:
                    owner.close()

    def test_redundant_catalog_request_cannot_block_daily_publication(self):
        release, finished = Event(), Event()
        results, errors, catalogs = [], [], []
        with source_with_current_service() as (source, remote, _), tempfile.TemporaryDirectory() as tmp:
            self.populate(remote, 4)
            sessions = source.list_sessions()
            config, selection, service, _ = make_service(tmp, source, now_ms=80_000_000)
            owner = WebWatchCoordinator(selection=selection, report_service=service, config=config,
                service_factory=lambda now: make_service(tmp, source, now_ms=now)[2])

            def contention(query):
                if 'cursor' not in query:
                    catalogs.append(1)
                    if len(catalogs) > 1:
                        # Hold the redundant full-catalog HTTP response at the
                        # same measured source boundary. No fabricated error or
                        # successful result: the actual V2 snapshot path runs.
                        release.wait(3)

            def acquire():
                try:
                    results.append(owner._account_history(sessions, (), 80_000_000))
                except BaseException as error:
                    errors.append(error)
                finally:
                    finished.set()

            remote.before_catalog = contention
            worker = Thread(target=acquire)
            try:
                worker.start()
                self.assertTrue(finished.wait(1), 'Daily blocked by a redundant catalog response')
                self.assertEqual([], errors)
                self.assertEqual(4, results[0][1].mix.request_count)
                self.assertEqual(4, results[0][1].prompt_count)
                self.assertEqual(1, len(catalogs))
            finally:
                release.set()
                worker.join(4)
                owner.close()
                self.assertFalse(worker.is_alive())


if __name__ == '__main__':
    unittest.main()
