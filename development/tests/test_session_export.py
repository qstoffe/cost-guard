"""Native transfer completeness, privacy boundary, cancellation and HTTP guards."""
from copy import deepcopy
import http.client
import json
from pathlib import Path
import shutil
import subprocess
from threading import Event, Thread
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from development.tests.fixtures.session_export import export_source, SESSION, TRANSFER
from src.application.session_detail import SessionDetails
from src.sources.errors import SessionExportError
from src.web.http import LoopbackServer
from src.web.observations import WebObservations

ROOT = Path(__file__).resolve().parents[2]


def selected_details(source):
    details = SessionDetails()
    token = details.open(SESSION, 'live')
    details.histories[SESSION].update(validated=details.clock(), export_identity=(
        source.source_id, source.source_instance, source.observation_epoch, SESSION))
    return details, token


class NativeExportTests(unittest.TestCase):
    def test_complete_native_payload_preserves_types_lifecycle_unicode_and_zero_assistants(self):
        with export_source() as (source, state, _):
            for messages in ([], TRANSFER['messages'], [
                    {'id': f'msg_{index}', 'type': 'assistant', 'content': [{'type': 'text', 'text': 'å' * 1000}]}
                    for index in range(700)]):
                state.transfer['messages'] = messages
                result = source.export_session(SESSION, source.observation_epoch, lambda: False)
                self.assertEqual(state.transfer, json.loads(result))
                self.assertIn('sanitize=true', state.requests[-1])
            self.assertEqual(6, len(state.requests), 'one bounded specification + one full transfer, no message pages')

    def test_unsupported_schema_bad_id_epoch_and_native_response_fail_closed(self):
        with export_source() as (source, state, _):
            for session_id in ('../ses_bad', 'ses_bad?sanitize=false', 'root', 'ses_å'):
                with self.subTest(session_id=session_id), self.assertRaisesRegex(SessionExportError, 'export_unavailable'):
                    source.export_session(session_id, source.observation_epoch, lambda: False)
            self.assertEqual([], state.requests)
            with self.assertRaisesRegex(SessionExportError, 'export_source_changed'):
                source.export_session(SESSION, 'retired-epoch', lambda: False)
            state.specification = {'paths': {}}
            with self.assertRaisesRegex(SessionExportError, 'export_unavailable'):
                source.export_session(SESSION, source.observation_epoch, lambda: False)
            self.assertEqual(['/openapi.json'], state.requests)
        for body in (b'{}', b'[]', b'{"data": {"info": {"id": "ses_wrong"}, "messages": []}}',
                b'{"data": null}', b'{"data": {}, "data": {}}', b'{"data": NaN}', b'{"data":',
                json.dumps({'data': dict(TRANSFER, messages=[{'id': 'm', 'type': 'user', 'sessionID': 'ses_other'}])}).encode(),
                json.dumps({'data': dict(TRANSFER, messages=[TRANSFER['messages'][0]] * 2)}).encode()):
            with self.subTest(body=body[:40]), export_source() as (source, state, _):
                state.body = body
                with self.assertRaisesRegex(SessionExportError, 'export_invalid_response'):
                    source.export_session(SESSION, source.observation_epoch, lambda: False)

    def test_transport_status_mime_size_truncation_and_restart_have_no_partial_success(self):
        for status, code in ((401, 'export_source_denied'), (403, 'export_source_denied'),
                (404, 'export_unavailable'), (500, 'export_source_unavailable'), (302, 'export_source_unavailable')):
            with self.subTest(status=status), export_source() as (source, state, _):
                state.status = status
                state.body = b'private source error must not escape'
                with self.assertRaisesRegex(SessionExportError, '^' + code + '$'):
                    source.export_session(SESSION, source.observation_epoch, lambda: False)
        for length in (str(16 * 1024 * 1024 + 1), 'omit'):
            with self.subTest(length=length), export_source() as (source, state, _):
                state.length = length
                if length == 'omit':
                    state.body = b' ' * (16 * 1024 * 1024 + 1)
                with self.assertRaisesRegex(SessionExportError, 'export_too_large'):
                    source.export_session(SESSION, source.observation_epoch, lambda: False)
        with export_source() as (source, state, registration):
            state.content_type = 'text/html'
            with self.assertRaisesRegex(SessionExportError, 'export_invalid_response'):
                source.export_session(SESSION, source.observation_epoch, lambda: False)
            state.content_type = 'application/json'
            state.length = '99999'
            with self.assertRaisesRegex(SessionExportError, 'export_invalid_response'):
                source.export_session(SESSION, source.observation_epoch, lambda: False)
            state.length = None
            def restart():
                value = json.loads(registration.read_text())
                value['pid'] += 1
                registration.write_text(json.dumps(value))
            state.before_export = restart
            with self.assertRaisesRegex(SessionExportError, 'export_source_changed'):
                source.export_session(SESSION, source.observation_epoch, lambda: False)

    def test_absolute_deadline_and_cancellation_close_owned_readers(self):
        with export_source() as (source, state, _):
            state.hold = True
            started = time.monotonic()
            with patch('src.sources.opencode_v2_export.EXPORT_SECONDS', .15):
                with self.assertRaises(SessionExportError):
                    source.export_session(SESSION, source.observation_epoch, lambda: False)
            self.assertLess(time.monotonic() - started, 1)
            state.release.set()
        with export_source() as (source, state, _):
            details, token = selected_details(source)
            state.before_export = lambda: details.close(token)
            with self.assertRaisesRegex(SessionExportError, 'export_cancelled|export_source_unavailable'):
                details.export(token, source, lambda: False)
        with export_source() as (source, state, _):
            details, token = selected_details(source)
            details.histories[SESSION]['export_identity'] = None
            with self.assertRaisesRegex(SessionExportError, 'export_unavailable'):
                details.export(token, source, lambda: False)
            self.assertEqual([], state.requests)


class ExportHttpTests(unittest.TestCase):
    def test_protected_post_exact_selection_headers_limits_and_shutdown(self):
        with export_source() as (source, state, _):
            details, token = selected_details(source)
            owner = SimpleNamespace(root=ROOT, nonce='export-host', observations=WebObservations(), stopping=Event(),
                live=SimpleNamespace(details=details, driver=SimpleNamespace(coordinator=SimpleNamespace(
                    report_service=SimpleNamespace(source=source)))))
            server = LoopbackServer(SimpleNamespace(), owner)
            thread = Thread(target=server.serve_forever, args=(.02,)); thread.start()
            cookie, csrf = server.session.exchange(server.session.bootstrap())
            def request(body=None, *, method='POST', extra=None, authenticated=True):
                connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
                headers = {'Origin': server.origin, 'Content-Type': 'application/json', 'X-CG-CSRF': csrf,
                    'X-CG-Instance': owner.nonce}
                if authenticated:
                    headers['Cookie'] = server.session.cookie_name + '=' + cookie
                headers.update(extra or {})
                connection.request(method, '/api/detail/export', json.dumps(body) if body is not None else None, headers)
                response = connection.getresponse()
                result = response.status, dict(response.getheaders()), response.read()
                connection.close()
                return result
            try:
                for extra, status in (({'Origin': 'https://foreign.invalid'}, 403), ({'Sec-Fetch-Site': 'cross-site'}, 403),
                        ({'X-CG-CSRF': 'wrong'}, 403), ({'Host': 'foreign.invalid'}, 403), ({'X-CG-Instance': 'retired'}, 409)):
                    self.assertEqual(status, request({'token': token}, extra=extra)[0])
                self.assertEqual(401, request({'token': token}, authenticated=False)[0])
                self.assertEqual(404, request(method='GET')[0])
                for body in ({'token': token, 'path': '../out'}, {'session_id': SESSION}, {'token': ['bad']}):
                    self.assertEqual(400, request(body)[0])
                self.assertEqual(410, request({'token': 'a' * 32})[0])
                self.assertEqual([], state.requests, 'all security failures precede native work')
                status, headers, body = request({'token': token})
                self.assertEqual(200, status)
                self.assertEqual(TRANSFER, json.loads(body))
                self.assertEqual('no-store', headers['Cache-Control'])
                self.assertEqual('nosniff', headers['X-Content-Type-Options'])
                self.assertEqual('application/json; charset=utf-8', headers['Content-Type'])
                self.assertEqual(f'attachment; filename="opencode-{SESSION}-sanitized.json"', headers['Content-Disposition'])
                self.assertEqual(owner.nonce, headers['X-CG-Instance'])
                self.assertTrue(server.exports.slot.acquire(False))
                self.assertEqual(429, request({'token': token})[0])
                server.exports.slot.release()
                owner.stopping.set()
                self.assertEqual(503, request({'token': token})[0])
            finally:
                server.shutdown(); thread.join(3); server.server_close()

    @unittest.skipUnless(shutil.which('node'), 'optional JavaScript runtime unavailable')
    def test_picker_and_download_client_lifecycle(self):
        result = subprocess.run([shutil.which('node'), 'development/tests/integration/web_session_export.cjs'],
            cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=20)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
