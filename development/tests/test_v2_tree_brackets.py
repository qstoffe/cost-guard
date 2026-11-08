"""Web-card tree brackets retain complete topology and canonical revision proof."""
from copy import deepcopy
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from urllib.parse import parse_qs, urlsplit
import unittest
from unittest.mock import patch

from development.tests.fixtures.opencode_v2_service import source_with_current_service
from src.sources.errors import (FailureCode, SourceConcurrentChangeError, SourceDataError,
    SourceError, SourceSchemaError, SourceUnavailableError, http_failure, transport_failure)


class V2TreeBracketTests(unittest.TestCase):
    def reader(self, origin, server):
        server.scoped_snapshots = True
        reader = origin.new_card_reader()
        self.addCleanup(reader.close_reads)
        reader.begin_card_read(origin)
        return reader

    def test_scoped_multilevel_child_heavy_tree_matches_global_without_global_scans(self):
        with source_with_current_service() as (origin, server, _registration):
            for index in range(65):
                child = deepcopy(server.sessions[1])
                child.update(id=f'ses_extra_{index}', parentID='ses_current_child' if index % 2 else 'ses_current')
                server.sessions.append(child)
                server.messages[child['id']] = []
            server.session_page_size = 25
            expected = origin.load_session_snapshot('ses_current')
            reader = self.reader(origin, server)

            actual = reader.load_session_snapshot('ses_current')

            self.assertEqual(expected, actual)
            self.assertEqual(67, len(actual.sessions))
            self.assertTrue(actual.complete)
            self.assertEqual(0, reader.metrics.counts.get('full_catalog_fetches', 0))
            self.assertEqual(2, reader.metrics.counts['scoped_catalog_brackets'])
            self.assertGreater(reader.metrics.counts['scoped_child_pages'], 134)
            self.assertIsNone(reader._catalog_cache, 'partial topology must never become complete-global metadata')

    def test_capability_once_per_epoch_never_becomes_an_auth_or_transport_fallback(self):
        with source_with_current_service() as (origin, server, registration):
            reader = self.reader(origin, server)
            reader.load_session_snapshot('ses_current')
            reader.begin_card_read(origin)
            reader.load_session_snapshot('ses_current')
            self.assertEqual(1, sum(path == '/openapi.json' for path, _auth in server.requests))
            value = json.loads(registration.read_text(encoding='utf-8'))
            value['pid'] += 1
            registration.write_text(json.dumps(value), encoding='utf-8')
            reader.begin_card_read(origin)
            reader.load_session_snapshot('ses_current')
            self.assertEqual(2, sum(path == '/openapi.json' for path, _auth in server.requests))

        for error in (http_failure(401, phase='capability'), transport_failure(TimeoutError(), phase='capability')):
            with self.subTest(code=error.code), source_with_current_service() as (origin, server, _registration):
                reader = self.reader(origin, server)
                client = reader._client()
                original = client.json

                def fail(path, **options):
                    if path == '/openapi.json':
                        raise error
                    return original(path, **options)

                with patch.object(client, 'json', side_effect=fail), self.assertRaises(type(error)):
                    reader.load_session_snapshot('ses_current')
                self.assertEqual(0, reader.metrics.counts.get('full_catalog_fetches', 0))

    def test_valid_unsupported_spec_uses_global_but_malformed_spec_is_typed_failure(self):
        for specification, expected_global in (({'openapi':'3.1.0', 'paths':{}}, True), ([], False)):
            with self.subTest(specification=specification), source_with_current_service() as (origin, server, _registration):
                reader = self.reader(origin, server)
                client, original = reader._client(), reader._client().json
                with patch.object(client, 'json', side_effect=lambda path, **options:
                        specification if path == '/openapi.json' else original(path, **options)):
                    if expected_global:
                        self.assertTrue(reader.load_session_snapshot('ses_current').complete)
                        self.assertEqual(2, reader.metrics.counts['full_catalog_fetches'])
                    else:
                        with self.assertRaises(SourceSchemaError):
                            reader.load_session_snapshot('ses_current')

    def test_insert_remove_and_reparent_during_messages_force_fresh_revision_retry(self):
        for mutation in ('insert', 'remove', 'reparent'):
            with self.subTest(mutation=mutation), source_with_current_service() as (origin, server, _registration):
                reader = self.reader(origin, server)

                def change(_key):
                    if mutation == 'insert':
                        child = deepcopy(server.sessions[1])
                        child.update(id='ses_new', parentID='ses_current_child')
                        server.sessions.append(child)
                        server.messages['ses_new'] = []
                    elif mutation == 'remove':
                        server.sessions = server.sessions[:1]
                    else:
                        server.sessions[1]['parentID'] = 'ses_elsewhere'
                    server.before_message = None

                server.before_message = change
                actual = reader.load_session_snapshot('ses_current')
                expected = origin.load_session_snapshot('ses_current')

                self.assertEqual(expected, actual)
                self.assertEqual(1, reader._diagnostics['snapshot_revision_rechecks'])
                self.assertEqual(4, reader.metrics.counts['scoped_catalog_brackets'])

    def test_active_parity_and_moved_skill_lookup_use_scoped_metadata_not_stale_global(self):
        with source_with_current_service() as (origin, server, _registration):
            reader = self.reader(origin, server)
            reader.list_sessions()
            global_cache, global_index, global_at = reader._catalog_cache, reader._catalog_index, reader._catalog_listed_at
            global_memo = dict(global_index.revisions)
            server.active = {'ses_current': {'type':'running'}}  # inactive drains are absent
            server.sessions[0]['location'] = {'directory':'/synthetic/moved'}

            actual = reader.load_session_snapshot('ses_current')
            reader.skill_origins_for_session('ses_current')

            self.assertTrue(actual.root.active)
            self.assertFalse(next(value for value in actual.sessions if value.parent_session_id).active)
            self.assertIs(global_cache, reader._catalog_cache)
            self.assertIs(global_index, reader._catalog_index)
            self.assertEqual(global_at, reader._catalog_listed_at)
            self.assertEqual(global_memo, global_index.revisions)
            skill_queries = [parse_qs(urlsplit(path).query) for path, _auth in server.requests
                if urlsplit(path).path == '/api/skill']
            self.assertEqual(['/synthetic/moved'], skill_queries[-1]['location[directory]'])

    def test_missing_member_is_not_unsupported_capability_and_restart_rejects_batch(self):
        with source_with_current_service() as (origin, server, registration):
            reader = self.reader(origin, server)
            snapshots, failures = reader.load_card_snapshots(('ses_current', 'ses_missing'))
            self.assertEqual({'ses_current'}, set(snapshots))
            self.assertEqual({'ses_missing'}, set(failures))
            self.assertEqual(0, reader.metrics.counts.get('full_catalog_fetches', 0))

            def restart(_key):
                value = json.loads(registration.read_text(encoding='utf-8'))
                value['pid'] += 1
                registration.write_text(json.dumps(value), encoding='utf-8')
                server.before_message = None

            server.before_message = restart
            with self.assertRaises(SourceConcurrentChangeError):
                reader.load_card_snapshots(('ses_current',))

    def test_only_complete_qualified_global_before_is_reused_and_every_after_is_fresh_scoped(self):
        with source_with_current_service() as (origin, server, _registration):
            reader = self.reader(origin, server)
            reader.list_sessions()
            listed = reader._catalog_listed_at
            reader.load_session_snapshot('ses_current')
            self.assertEqual(1, reader.metrics.counts['scoped_catalog_brackets'])
            self.assertEqual(1, reader.metrics.counts['snapshot_catalog_reuses'])
            self.assertEqual({}, reader._catalog_index.revisions)

            reader.begin_card_read(origin)
            self.assertEqual({}, reader._card_trees.trees, 'no scoped proof survives a borrow')
            with patch('src.sources.opencode_v2_tree.time.monotonic', return_value=listed + 3):
                reader.load_session_snapshot('ses_current')
            self.assertEqual(2, reader.metrics.counts['scoped_catalog_brackets'])
            self.assertEqual(0, reader.metrics.counts.get('full_catalog_fetches', 0))
            self.assertEqual(listed, reader._catalog_listed_at)

            other = deepcopy(server.sessions[0])
            other['id'] = 'ses_new_root'
            server.sessions.append(other)
            server.messages[other['id']] = []
            reader.begin_card_read(origin)
            snapshots, failures = reader.load_card_snapshots(('ses_current', 'ses_new_root'))
            self.assertFalse(failures)
            self.assertEqual(2, len(snapshots))
            self.assertEqual(2, reader.metrics.counts['scoped_catalog_brackets'], 'ALL requested roots must be present for reuse')

    def test_spec_endpoint_only_explicit_unsupported_statuses_fallback_and_detection_rejects_restart(self):
        for status in (404, 405, 501, 400, 422, 500):
            with self.subTest(status=status), source_with_current_service() as (origin, server, _registration):
                reader = self.reader(origin, server)
                client, original = reader._client(), reader._client().json

                def reply(path, **options):
                    if path == '/openapi.json':
                        raise http_failure(status, phase='capability')
                    return original(path, **options)

                with patch.object(client, 'json', side_effect=reply):
                    if status in (404, 405, 501):
                        self.assertTrue(reader.load_session_snapshot('ses_current').complete)
                        self.assertEqual(2, reader.metrics.counts['full_catalog_fetches'])
                    else:
                        with self.assertRaisesRegex(SourceUnavailableError, f'HTTP {status}'):
                            reader.load_session_snapshot('ses_current')
                        self.assertEqual(0, reader.metrics.counts.get('full_catalog_fetches', 0))

        with source_with_current_service() as (origin, server, registration):
            reader = self.reader(origin, server)
            client, original = reader._client(), reader._client().json

            def restart(path, **options):
                response = original(path, **options)
                if path == '/openapi.json':
                    value = json.loads(registration.read_text())
                    value['pid'] += 1
                    registration.write_text(json.dumps(value))
                return response

            with patch.object(client, 'json', side_effect=restart), self.assertRaises(SourceConcurrentChangeError):
                reader.load_session_snapshot('ses_current')
            self.assertIsNone(reader._card_trees.supported)

    def test_invalid_identity_cycle_parent_and_repeated_cursor_are_typed_not_global_fallbacks(self):
        with source_with_current_service() as (origin, server, _registration):
            reader = self.reader(origin, server)
            client, original = reader._client(), reader._client().json

            def wrong_parent(path, **options):
                if path == '/api/session':
                    return {'data': [dict(id='ses_wrong', parentID='ses_other')], 'cursor': {}}
                return original(path, **options)

            with patch.object(client, 'json', side_effect=wrong_parent), self.assertRaises(SourceConcurrentChangeError):
                reader.load_session_snapshot('ses_current')
            self.assertEqual(0, reader.metrics.counts.get('full_catalog_fetches', 0))

            def cycle(path, **options):
                if path == '/api/session':
                    return {'data': [dict(id='ses_current', parentID='ses_current')], 'cursor': {}}
                return original(path, **options)

            with patch.object(client, 'json', side_effect=cycle), self.assertRaises(SourceDataError) as caught:
                reader.load_session_snapshot('ses_current')
            self.assertEqual(FailureCode.DATA, caught.exception.code)

            def invalid_root(path, **options):
                if path == '/api/session/ses_current':
                    return {'data': dict(id=42)}
                return original(path, **options)

            with patch.object(client, 'json', side_effect=invalid_root), self.assertRaises(SourceDataError):
                reader.load_session_snapshot('ses_current')

            page_number = 0

            def repeat_cursor(path, **options):
                nonlocal page_number
                if path == '/api/session':
                    page_number += 1
                    return {'data': [dict(id=f'ses_page_{page_number}', parentID='ses_current')], 'cursor': {'next': 'same'}}
                return original(path, **options)

            with patch.object(client, 'json', side_effect=repeat_cursor), self.assertRaises(SourceDataError):
                reader.load_session_snapshot('ses_current')
            self.assertIsNone(reader._catalog_cache)

    def test_scoped_member_io_failure_preserves_sibling_and_code_but_shared_auth_rejects(self):
        for status in (503, 403):
            with self.subTest(status=status), source_with_current_service() as (origin, server, _registration):
                reader = self.reader(origin, server)
                client, original = reader._client(), reader._client().json

                def fail(path, **options):
                    if path == '/api/session/ses_failed':
                        raise http_failure(status, phase='snapshot')
                    return original(path, **options)

                with patch.object(client, 'json', side_effect=fail):
                    if status == 403:
                        with self.assertRaisesRegex(SourceUnavailableError, 'HTTP 403'):
                            reader.load_card_snapshots(('ses_current', 'ses_failed'))
                    else:
                        snapshots, failures = reader.load_card_snapshots(('ses_current', 'ses_failed'))
                        self.assertEqual({'ses_current'}, set(snapshots))
                        self.assertEqual(FailureCode.HTTP, failures['ses_failed'].code)
                        self.assertEqual(503, failures['ses_failed'].http_status)
                self.assertEqual(0, reader.metrics.counts.get('full_catalog_fetches', 0))

    def test_active_unknown_running_and_absence_use_exact_global_interpretation(self):
        for active in ({}, {'ses_current': {'type': 'idle'}}, {'ses_current': {'type': 'running'}}, None):
            with self.subTest(active=active), source_with_current_service() as (origin, server, _registration):
                server.active = active
                expected = origin.load_session_snapshot('ses_current')
                reader = self.reader(origin, server)
                actual = reader.load_session_snapshot('ses_current')
                self.assertEqual(expected, actual)
                self.assertIs(actual.root.active, None if active is None or active == {'ses_current': {'type': 'idle'}} else bool(active))

    def test_group_after_begins_after_all_hydration_and_cancel_never_publishes_partial(self):
        with source_with_current_service() as (origin, server, _registration):
            other = deepcopy(server.sessions[0])
            other['id'] = 'ses_slow'
            server.sessions.append(other)
            server.messages[other['id']] = []
            reader = self.reader(origin, server)
            started, release = Event(), Event()

            def pause(key):
                if key == 'ses_slow':
                    started.set()
                    if not release.wait(3):
                        raise AssertionError('test hydration did not release')

            server.before_message = pause
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(reader.load_card_snapshots, ('ses_current', 'ses_slow'))
                try:
                    self.assertTrue(started.wait(2))
                    self.assertEqual(1, reader.metrics.counts['scoped_catalog_brackets'])
                    self.assertFalse(future.done())
                finally:
                    release.set()
                snapshots, failures = future.result(timeout=3)
            self.assertFalse(failures)
            self.assertEqual(2, len(snapshots))
            self.assertEqual(2, reader.metrics.counts['scoped_catalog_brackets'])
            reader.begin_card_read(origin)
            reader.cancel_reads()
            with self.assertRaises(SourceError):
                reader.load_card_snapshots(('ses_current',))


if __name__ == '__main__':
    unittest.main()
