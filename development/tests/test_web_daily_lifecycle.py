"""Real V2 bracket work charged against the unchanged Daily publication budget."""
from copy import deepcopy
from pathlib import Path
import tempfile
import time
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

    def test_four_root_daily_slice_shares_one_fresh_catalog_bracket(self):
        catalogs = []
        with source_with_current_service() as (source, remote, _), tempfile.TemporaryDirectory() as tmp:
            self.populate(remote, 4)
            # This check isolates batch sharing with a fresh before-catalog.
            # Real HTTP scheduling must not expire it or become a publication SLA;
            # source-history tests separately cover freshness and changed-tree retries.
            with patch('src.sources.opencode_v2.time', wraps=time) as source_clock:
                source_clock.monotonic.return_value = 100.0
                sessions = source.list_sessions()
                config, selection, service, _ = make_service(tmp, source, now_ms=80_000_000)
                owner = WebWatchCoordinator(selection=selection, report_service=service, config=config,
                    service_factory=lambda now: make_service(tmp, source, now_ms=now)[2])

                def count_catalog(query):
                    if 'cursor' not in query:
                        catalogs.append(1)

                remote.before_catalog = count_catalog
                try:
                    result = owner._account_history(sessions, (), 80_000_000)
                    self.assertIsInstance(result, tuple)
                    self.assertEqual(4, result[1].mix.request_count)
                    self.assertEqual(4, result[1].prompt_count)
                    self.assertEqual(1, len(catalogs))
                finally:
                    owner.close()


if __name__ == '__main__':
    unittest.main()
