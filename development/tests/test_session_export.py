"""One authorized selection -> all and only its native family, masked inside a complete ZIP."""
from copy import deepcopy
import http.client
from io import BytesIO
import json
from pathlib import Path
import shutil
import subprocess
from threading import Event, Thread
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile

from development.tests.fixtures.session_export import CHILD, GRANDCHILD, LEAF, SESSION, SIBLING, TRANSFER, export_source
from src.application.session_detail import SessionDetails
from src.application.session_export_archive import analysis_filename
from src.sources.errors import SessionExportError
from src.web.http import LoopbackServer
from src.web.observations import WebObservations

ROOT = Path(__file__).resolve().parents[2]


def selected_details(source, member=SESSION):
    details = SessionDetails()
    token = details.open(member, 'live')
    details.histories[member].update(validated=details.clock(), source_unavailable=False, export_identity=(
        source.source_id, source.source_instance, source.observation_epoch, member))
    return details, token


def export(source, member=SESSION):
    details, token = selected_details(source, member)
    return details.export(token, source, lambda: False)[0]


class SessionArchiveTests(unittest.TestCase):
    def test_paged_tree_preserves_full_native_documents_in_unique_pretty_compressed_entries(self):
        names = {SESSION: 'Unicode å 日本語.json', CHILD: 'Unicode å 日本語 (1).json',
            SIBLING: 'unicode å 日本語 (2).json', GRANDCHILD: 'session-ses_c.json', LEAF: 'Deep 🚀.json'}
        with export_source() as (source, state, _):
            state.tree[LEAF]['messages'] = [{'id': f'msg_{i}', 'type': 'assistant', 'sessionID': LEAF,
                'text': 'cache hit 🇸🇪\n  ' * 160, 'cost': 0.125, 'tokens': {'input': 671, 'cached': 520},
                'providerID': 'sample', 'modelID': 'test-large', 'effort': 'high',
                'time': {'created': 1500 + i}, 'nativeExtension': [None, False, True]} for i in range(500)]

            payload = export(source)

            # Comparing the full decoded UTF-8 text checks Unicode, whitespace, key order and final newline too.
            with ZipFile(BytesIO(payload)) as archive:
                self.assertCountEqual(names.values(), archive.namelist())
                for member, name in names.items():
                    self.assertEqual(ZIP_DEFLATED, archive.getinfo(name).compress_type)
                    expected = json.dumps(state.tree[member], indent=2, ensure_ascii=False) + '\n'
                    self.assertEqual(expected, archive.read(name).decode('utf-8'))
                self.assertLess(len(payload), archive.getinfo(names[LEAF]).file_size // 4)
            self.assertCountEqual([f'/api/experimental/session/{member}/export?sanitize=false' for member in names],
                [url for url in state.requests if '/experimental/' in url])
            with ZipFile(BytesIO(export(source, LEAF))) as one:
                self.assertEqual([names[LEAF]], one.namelist(), 'selecting the leaf excludes even its own ancestors')

    def test_only_credential_values_change_in_native_logs_inputs_errors_and_structured_metadata(self):
        with export_source() as (source, state, _):
            native = state.tree[LEAF]
            native['messages'] = [{'id': 'msg_detail', 'type': 'assistant', 'sessionID': LEAF, 'content': [
                {'type': 'tool', 'callID': 'call_a83f', 'name': 'read', 'args': {'apiKey': 'fixture-key-42',
                    'authorization': 'Basic Zml4dHVyZQ==', 'pin': 109, 'password': 91826},
                 'output': 'retry Authorization: Bearer fixture.t0ken; git=6fba937dd84146cabcec00010203040506070809',
                 'error': 'E012: postgres://user:fixture-pass@localhost/db => denied',
                 'code': ('if (token === expected) return true;\n'
                          'tokens.filter(token => token == expected);\n'
                          'check(password=os.getenv("DB_PASS"))\n'
                          'connect(password=process.env.DB_PASS)\n'),
                 'log': 'stage 1\nPASSWORD="fixture pass"; next\n' + 'ghp_' + 'A' * 36,
                 'pem': 'start\n-----BEGIN PRIVATE KEY-----\nZml4dHVyZQ==\n-----END PRIVATE KEY-----\nend'}]}]
            expected = deepcopy(native)
            tool = expected['messages'][0]['content'][0]
            tool['args'].update(apiKey='[REDACTED]', authorization='Basic [REDACTED]', password=0)
            tool['output'] = 'retry Authorization: Bearer [REDACTED]; git=6fba937dd84146cabcec00010203040506070809'
            tool['error'] = 'E012: postgres://user:[REDACTED]@localhost/db => denied'
            tool['log'] = 'stage 1\nPASSWORD="[REDACTED]"; next\n[REDACTED]'
            tool['pem'] = 'start\n-----BEGIN PRIVATE KEY-----\n[REDACTED]\n-----END PRIVATE KEY-----\nend'

            for _ in range(2):
                with ZipFile(BytesIO(export(source, LEAF))) as archive:
                    self.assertEqual(expected, json.loads(archive.read('Deep 🚀.json')))

    def test_suggested_names_stay_flat_portable_and_do_not_disclose_credentials(self):
        for title, stem in [('Refactor: <auth>/fix?', 'Refactor authfix'), ('Översyn 👩‍💻', 'Översyn 👩‍💻'),
                ('a\x00b\u202ec. . ', 'abc'), ('password=fixture-only', 'password=[REDACTED]'),
                ('🚀' * 100, '🚀' * 50), ('  internal spaces', '  internal spaces'),
                *[(value, 'session-' + SESSION) for value in (None, '.. ', 'COM1 .txt', 'lpt9', '<>:|?*')]]:
            with self.subTest(title=title):
                self.assertEqual(stem + '.zip', analysis_filename(title, SESSION))

    def test_bad_member_identity_and_incomplete_catalog_cannot_produce_a_partial_zip(self):
        for error in ('foreign parent', 'foreign session', 'foreign message', 'duplicate message', 'cycle cursor',
                'empty continuation', 'invalid transfer', 'unsupported', 'missing descendant'):
            with self.subTest(error=error), export_source() as (source, state, _):
                expected = 'export_invalid_response'
                if error == 'foreign parent':
                    state.tree[LEAF]['info'] = {**state.tree[LEAF]['info'], 'parentID': SESSION}
                elif error == 'foreign session':
                    state.tree[LEAF]['info'] = {**state.tree[LEAF]['info'], 'id': CHILD}
                elif error == 'foreign message':
                    state.tree[LEAF]['messages'] = [{'id': 'm', 'type': 'user', 'sessionID': SESSION}]
                elif error == 'duplicate message':
                    state.tree[LEAF]['messages'] = [TRANSFER['messages'][0]] * 2
                elif error == 'cycle cursor':
                    state.pages['page 2']['cursor']['next'] = 'page 2'
                elif error == 'empty continuation':
                    state.pages['page 2'] = {'data': [], 'cursor': {'next': 'omitted'}}
                elif error == 'invalid transfer':
                    state.body = b'{"data":null}'
                elif error == 'unsupported':
                    state.specification['paths'].clear()
                    expected = 'export_unavailable'
                elif error == 'missing descendant':
                    del state.tree[LEAF]
                    expected = 'export_descendant_unavailable'
                with self.assertRaisesRegex(SessionExportError, '^' + expected + '$'):
                    export(source)

    def test_response_bounds_status_and_malformed_wire_fail_closed(self):
        for field, value, expected in [
                ('length', '33554433', 'export_too_large'), ('length', '99999', 'export_invalid_response'),
                ('content_type', 'text/html', 'export_invalid_response'), ('status', 403, 'export_source_denied'),
                ('status', 302, 'export_source_unavailable'), ('status', 500, 'export_source_unavailable'),
                ('body', b'{"data":{}, "data":{}}', 'export_invalid_response')]:
            with self.subTest(field=field, value=value), export_source() as (source, state, _):
                setattr(state, field, value)
                with self.assertRaisesRegex(SessionExportError, '^' + expected + '$'):
                    export(source)
        for limit in ('MAX_ARCHIVE_BYTES', 'MAX_JSON_BYTES'):
            with self.subTest(limit=limit), export_source() as (source, _, _):
                with patch('src.application.session_export_archive.' + limit, 128):
                    with self.assertRaisesRegex(SessionExportError, '^export_too_large$'):
                        export(source)

    def test_source_restart_explicit_cancellation_and_idle_reader_discard_work(self):
        with export_source() as (source, state, registration):
            def restart(member):
                if member == LEAF:
                    record = json.loads(registration.read_text())
                    record['pid'] += 1
                    registration.write_text(json.dumps(record))
            state.before_export = restart
            with self.assertRaisesRegex(SessionExportError, '^export_source_changed$'):
                export(source)
        with export_source() as (source, state, _):
            details, token = selected_details(source)
            cancelled = Event()
            state.before_export = lambda member: cancelled.set() if member == CHILD else None
            with self.assertRaisesRegex(SessionExportError, '^export_cancelled$'):
                details.export(token, source, cancelled.is_set)
            self.assertFalse(any(f'/{LEAF}/export' in url for url in state.requests))
        with export_source() as (source, state, _):
            state.hold = True
            started = time.monotonic()
            with patch('src.sources.opencode_v2_export.REQUEST_SECONDS', .25):
                with self.assertRaisesRegex(SessionExportError, '^export_timed_out$'):
                    export(source)
            self.assertLess(time.monotonic() - started, 2)

    def test_unobserved_selection_stale_epoch_and_invalid_id_never_contact_source(self):
        with export_source() as (source, state, _):
            details, token = selected_details(source)
            details.histories[SESSION]['export_identity'] = None
            with self.assertRaisesRegex(SessionExportError, '^export_unavailable$'):
                details.export(token, source, lambda: False)
            for member, epoch, code in [(SESSION, 'retired', 'export_source_changed'),
                    ('ses_bad?sanitize=false', source.observation_epoch, 'export_unavailable')]:
                with self.assertRaisesRegex(SessionExportError, '^' + code + '$'):
                    list(source.export_session_tree(member, epoch, lambda: False))
            self.assertEqual([], state.requests)


class ExportHttpTests(unittest.TestCase):
    def test_authenticated_complete_attachment_or_bounded_error_only(self):
        with export_source() as (source, state, _):
            clock = 1000
            details = SessionDetails(clock=lambda: clock)
            owner = SimpleNamespace(root=ROOT, nonce='export-host', observations=WebObservations(), stopping=Event(),
                live=SimpleNamespace(details=details, driver=SimpleNamespace(coordinator=SimpleNamespace(
                    report_service=SimpleNamespace(source=source)))))
            server = LoopbackServer(SimpleNamespace(), owner)
            thread = Thread(target=server.serve_forever, args=(.02,)); thread.start()
            cookie, csrf = server.session.exchange(server.session.bootstrap())

            def request(body=None, *, path='/api/detail/export', method='POST', extra=None, authenticated=True):
                connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=15)
                try:
                    headers = {'Origin': server.origin, 'Content-Type': 'application/json', 'X-CG-CSRF': csrf,
                        'X-CG-Instance': owner.nonce}
                    if authenticated:
                        headers['Cookie'] = server.session.cookie_name + '=' + cookie
                    headers.update(extra or {})
                    connection.request(method, path, json.dumps(body) if body is not None else None, headers)
                    response = connection.getresponse()
                    return response.status, dict(response.getheaders()), response.read()
                finally:
                    connection.close()

            def open_selection():
                status, _, data = request({'action': 'open', 'session_id': SESSION, 'mode': 'live'}, path='/api/detail')
                self.assertEqual(200, status)
                selected = json.loads(data)
                self.assertEqual('ready', selected['export_state'], 'cold selection, before any analysis')
                return {'action': 'start', 'id': 'c' * 32, 'token': selected['token'], 'scope': selected['export_scope']}

            def poll(job):
                end = time.monotonic() + 15
                while time.monotonic() < end:
                    status, headers, data = request({**job, 'action': 'status'})
                    value = json.loads(data)
                    if value != {'state': 'preparing'}:
                        return status, headers, value
                    time.sleep(.05)
                self.fail('Export did not settle')

            release = Event()
            try:
                start = open_selection()
                token = start['token']
                job = {'id': start['id']}
                for extra, status in (({'Origin': 'https://foreign.invalid'}, 403), ({'Sec-Fetch-Site': 'cross-site'}, 403),
                        ({'X-CG-CSRF': 'wrong'}, 403), ({'Host': 'foreign.invalid'}, 403), ({'X-CG-Instance': 'retired'}, 409)):
                    self.assertEqual(status, request(start, extra=extra)[0])
                self.assertEqual(401, request(start, authenticated=False)[0])
                self.assertEqual(404, request(method='GET')[0])
                for body in ({'token': token, 'path': '../out'}, {'session_id': SESSION}, {'token': ['bad']}):
                    self.assertEqual(400, request(body)[0])
                self.assertEqual(410, request({**start, 'token': 'a' * 32})[0])
                self.assertEqual({'error': 'export_source_changed'}, json.loads(request({**start, 'scope': 'b'*64})[2]))
                self.assertEqual([], state.requests)
                entered = Event()
                def hold(member):
                    entered.set()
                    release.wait(10)

                state.before_export = hold
                self.assertEqual(202, request(start)[0])
                self.assertTrue(entered.wait(3))
                self.assertEqual({'error': 'export_busy'}, json.loads(request(start)[2]))
                self.assertEqual(200, request({**job, 'action': 'cancel'})[0])
                self.assertEqual({'error': 'export_retiring'}, json.loads(request(start)[2]))
                release.set()
                # The slot becomes reusable only after the cancelled producer exits.
                state.before_export = lambda member: time.sleep(1.1)
                end = time.monotonic() + 5
                while True:
                    status, _, data = request(start)
                    if status == 202:
                        break
                    self.assertEqual({'error': 'export_retiring'}, json.loads(data))
                    self.assertLess(time.monotonic(), end)
                    time.sleep(.05)
                clock += 301
                self.assertEqual(410, request(start)[0], 'expired view cannot admit a new export')
                self.assertEqual('ready', poll(job)[2]['state'])
                status, headers, body = request({**job, 'action': 'chunk', 'offset': 0})
                state.before_export = None
                self.assertEqual(200, status)
                self.assertEqual('application/zip', headers['Content-Type'])
                self.assertEqual(f'attachment; filename="opencode-{SESSION}-analysis.zip"', headers['Content-Disposition'])
                self.assertEqual(('no-store', 'nosniff', owner.nonce, str(len(body))),
                    tuple(headers[key] for key in ('Cache-Control', 'X-Content-Type-Options', 'X-CG-Instance', 'Content-Length')))
                with ZipFile(BytesIO(body)) as archive:
                    self.assertEqual(5, len(archive.infolist()))
                self.assertEqual(200, request({**job, 'action': 'cancel'})[0])
                del state.tree[LEAF]
                start = open_selection()
                self.assertEqual(202, request(start)[0])
                status, headers, error = poll(job)
                self.assertEqual(409, status)
                self.assertNotIn('Content-Disposition', headers)
                self.assertEqual({'error': 'export_descendant_unavailable'}, error)
                self.assertEqual(200, request({**job, 'action': 'cancel'})[0])
                owner.stopping.set()
                self.assertEqual(503, request(start)[0])
            finally:
                release.set()
                server.shutdown(); thread.join(3); server.server_close()

    @unittest.skipUnless(shutil.which('node'), 'optional JavaScript runtime unavailable')
    def test_picker_and_download_client_lifecycle(self):
        result = subprocess.run([shutil.which('node'), 'development/tests/integration/web_session_export.cjs'],
            cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=20)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
