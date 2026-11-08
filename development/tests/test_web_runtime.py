"""Adversarial real-loopback requests and owned spawn-process report isolation."""
from __future__ import annotations

import contextlib
import errno
import http.client
import io
import json
from pathlib import Path
import socket
from threading import Event, Thread
from types import SimpleNamespace
import time
import unittest
from unittest.mock import patch
from unittest.mock import Mock
from unittest.mock import call

from development.tests.fixtures.report_process import ReportProcess
from development.tests.fixtures.web_reports import finite_report
from src.reports import ReportKind, ReportRequest
from src.web.http import LoopbackServer
from src.web.jobs import MAX_RESULT_BYTES, ProgressRelay, ReportJobs, ReportWorkerStopError, parse_report, run_report
from src.web.security import BrowserSession


class LoopbackBindingTests(unittest.TestCase):
    def test_binding_uses_numeric_loopback_without_hostname_resolution(self):
        with patch.object(socket, "getfqdn", side_effect=AssertionError("loopback must never reverse-resolve")) as resolve:
            server = LoopbackServer(Mock())
        try:
            self.assertEqual("127.0.0.1", server.server_name)
            self.assertEqual(("127.0.0.1", server.server_port), server.server_address)
            self.assertEqual(f"http://127.0.0.1:{server.server_port}", server.origin)
            resolve.assert_not_called()
        finally:
            server.server_close()


class WebRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.jobs = ReportJobs(target=finite_report)
        self.server = LoopbackServer(self.jobs)
        self.stopped = Event()

        def serve():
            while not self.stopped.is_set():
                self.server.handle_request()
                self.jobs.tick()
        self.thread = Thread(target=serve)
        self.thread.start()
        self.addCleanup(self.close)
        self.cookie = None
        self.csrf = None

    def close(self):
        self.stopped.set()
        self.thread.join(3)
        self.server.server_close()
        self.jobs.close()
        self.assertFalse(self.thread.is_alive())

    def request(self, path, value=None, *, method=None, headers=None, authenticated=True):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=8)
        body = None if value is None else json.dumps(value)
        supplied = {}
        if value is not None:
            supplied.update({"Content-Type": "application/json", "Origin": self.server.origin})
        if authenticated and self.cookie:
            supplied.update({"Cookie": self.cookie, "X-CG-CSRF": self.csrf})
        supplied.update(headers or {})
        conn.request(method or ("GET" if value is None else "POST"), path, body, supplied)
        response = conn.getresponse()
        data = response.read()
        result = response.status, dict(response.getheaders()), data
        conn.close()
        return result

    def login(self):
        status, headers, body = self.request("/api/bootstrap", {"credential": self.server.session.bootstrap()})
        self.assertEqual(200, status)
        self.assertIn("HttpOnly; SameSite=Strict", headers["Set-Cookie"])
        self.cookie = headers["Set-Cookie"].split(";", 1)[0]
        self.csrf = json.loads(body)["csrf"]

    def raw(self, data):
        with socket.create_connection(("127.0.0.1", self.server.server_port), timeout=8) as conn:
            conn.sendall(data)
            try:
                conn.shutdown(socket.SHUT_WR)
            except OSError as error:
                # Darwin can finish the peer's rejection before our half-close.
                # Still read/assert actual response bytes; other errors must fail.
                if error.errno != errno.ENOTCONN:
                    raise
            parts = []
            while chunk := conn.recv(65536):
                parts.append(chunk)
            return b"".join(parts)

    def test_raw_peer_close_race_keeps_response_and_does_not_hide_other_errors(self):
        connection = Mock()
        connection.shutdown.side_effect = OSError(errno.ENOTCONN, 'peer already closed')
        connection.recv.side_effect = [b'HTTP/1.1 403 Forbidden\r\n\r\n', b'']
        with patch.object(socket, 'create_connection') as create:
            create.return_value.__enter__.return_value = connection
            response = self.raw(b'GET /health HTTP/1.1\r\nHost: wrong\r\n\r\n')
        self.assertEqual(b'HTTP/1.1 403 Forbidden\r\n\r\n', response)
        connection.shutdown.side_effect = OSError(errno.EPERM, 'unexpected failure')
        with patch.object(socket, 'create_connection') as create:
            create.return_value.__enter__.return_value = connection
            with self.assertRaises(OSError) as caught:
                self.raw(b'request')
        self.assertEqual(errno.EPERM, caught.exception.errno)

    def wait_job(self, key):
        until = time.monotonic() + 10
        while time.monotonic() < until:
            status, _, body = self.request(f"/api/jobs/{key}")
            self.assertEqual(200, status)
            result = json.loads(body)
            if result["status"] not in {"queued", "running"}:
                return result
            time.sleep(.05)
        self.fail("bounded report did not finish")

    def test_shell_is_fixed_offline_and_honest_not_sensitive(self):
        status, headers, body = self.request("/")
        self.assertEqual(200, status)
        self.assertNotIn(b"<footer", body)
        self.assertIn(b'progress max="100" value="0"', body)
        self.assertIn(b'href="#/watch">Watch</a>', body)
        self.assertNotIn(b'href="#/live">Live</a>', body)
        self.assertIn(b'aria-valuetext="0 percent"', body)
        self.assertNotIn('≈'.encode(), body)
        self.assertIn(b'/reports.js', body)
        self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
        self.assertIn("worker-src 'none'", headers["Content-Security-Policy"])
        self.assertEqual("no-store", headers["Cache-Control"])
        self.assertNotIn(b"http://", body)
        self.assertNotIn(b"https://", body)
        self.assertEqual({"http": "ready"}, json.loads(self.request("/health")[2]))
        self.assertEqual(401, self.request("/api/status")[0])
        self.assertEqual(401, self.request("/api/reports", {"kind": "sessions"})[0])

    def test_source_readiness_admission_is_typed_protected_and_does_not_allocate_jobs(self):
        self.login()
        startup = Mock()
        owner = SimpleNamespace(source_startup=startup, stopping=Event(), nonce='test-instance', observations=Mock())
        self.server.lifecycle = owner
        for code, retryable in [('source_starting', True), ('connection_refused', True),
                ('source_permission_denied', False), ('http_auth_failure', False), ('unsupported_schema', False)]:
            with self.subTest(code=code):
                startup.report_status.return_value = dict(ready=False, error=code, retryable=retryable)
                status, _, body = self.request('/api/reports', {'kind': 'ai-stats'})
                self.assertEqual(503, status)
                self.assertEqual(dict(error=code, retryable=retryable), json.loads(body))
                self.assertEqual([], self.jobs.updates()['jobs'])
        status, _, _ = self.request('/api/reports', {'kind': 'ai-stats'}, authenticated=False)
        self.assertEqual(401, status)
        status, _, _ = self.request('/api/reports', {'kind': 'ai-stats'}, headers={'X-CG-CSRF': 'wrong'})
        self.assertEqual(403, status)
        startup.report_status.return_value = dict(ready=True, error=None, retryable=False)
        status, _, body = self.request('/api/reports', {'kind': 'ai-stats'})
        self.assertEqual(202, status)
        self.assertTrue(json.loads(body)['id'])

    def test_price_refresh_uses_protected_empty_body_action_and_bounded_jobs(self):
        from src.web.jobs import ModelsPriceRefresh
        self.assertEqual(401, self.request('/api/models/refresh', {})[0])
        self.login()
        self.assertEqual(403, self.request('/api/models/refresh', {}, headers={'X-CG-CSRF': 'wrong'})[0])
        self.assertEqual(403, self.request('/api/models/refresh', {}, headers={'Origin': 'https://elsewhere.test'})[0])
        self.assertEqual(400, self.request('/api/models/refresh', {'kind': 'normal'})[0])
        with patch.object(self.jobs, 'submit', return_value='bounded-job') as submit:
            status, _, body = self.request('/api/models/refresh', {})
        self.assertEqual(202, status)
        self.assertEqual({'id': 'bounded-job'}, json.loads(body))
        submit.assert_called_once_with(ModelsPriceRefresh())
        with patch.object(self.jobs, 'submit', side_effect=RuntimeError('busy')):
            self.assertEqual(429, self.request('/api/models/refresh', {})[0])

    def test_worker_cleanup_failure_is_unavailable_not_retryable_admission_busy(self):
        self.login()
        with patch.object(self.jobs, 'submit', side_effect=ReportWorkerStopError('report_worker_stop_timeout')):
            for path, value in [('/api/reports', {'kind': 'normal'}), ('/api/models/refresh', {})]:
                status, _, body = self.request(path, value)
                self.assertEqual(503, status)
                self.assertEqual({'error': 'report_worker_stop_timeout'}, json.loads(body))

    def test_progress_bursts_are_coalesced_without_starving_host_turns(self):
        from collections import deque
        from unittest.mock import Mock

        messages = deque(("progress", {"phase": "history", "completed": n, "total": 130})
                         for n in range(130))
        messages.append(("result", json.dumps({"error": None, "source": {"status": "acquired"}}).encode()))
        receiver = Mock()
        receiver.poll.side_effect = lambda: bool(messages)
        receiver.recv.side_effect = messages.popleft
        process = Mock()
        process.is_alive.return_value = False
        jobs = ReportJobs()
        key = jobs.submit(ReportRequest(ReportKind.TOKEN_MIX))
        jobs._jobs[key]["status"] = "running"
        jobs._active = key, process, receiver, time.monotonic()
        self.addCleanup(jobs.close)

        jobs.tick()

        self.assertEqual(64, receiver.recv.call_count)
        self.assertEqual(63, jobs.snapshot(key)["progress"]["completed"])
        self.assertEqual("running", jobs.snapshot(key)["status"])
        jobs.tick()
        self.assertEqual(128, receiver.recv.call_count)
        jobs.tick()
        self.assertEqual("complete", jobs.snapshot(key)["status"])
        self.assertEqual(129, jobs.snapshot(key)["progress"]["completed"])
        self.assertEqual(130, jobs.snapshot(key)["progress"]["sequence"])
        receiver.close.assert_called_once()

    def test_shared_favicon_is_fixed_public_offline_and_narrowly_allowed_by_csp(self):
        artwork = (Path(__file__).resolve().parents[2] / 'src/web/assets/favicon.ico').read_bytes()
        for path in ('/favicon-cg1.ico', '/favicon.ico'):
            status, headers, body = self.request(path, authenticated=False)
            self.assertEqual(status, 200)
            self.assertEqual(headers['Content-Type'], 'image/x-icon')
            self.assertEqual(headers['Cache-Control'], 'no-store')
            self.assertNotIn('Set-Cookie', headers)
            self.assertEqual(body, artwork)
            self.assertIn(f"img-src {self.server.origin}/favicon-cg1.ico {self.server.origin}/favicon.ico;",
                          headers['Content-Security-Policy'])
        status, _, html = self.request('/')
        self.assertEqual(status, 200)
        self.assertIn(b'rel="icon" href="/favicon-cg1.ico"', html)
        self.assertIn(b'<title>Cost Guard Web Beta</title>', html)
        self.assertEqual(self.request('/favicon-cg1.ico?anything')[0], 400)
        self.assertEqual(self.request('/favicon.ico', headers={'Sec-Fetch-Site': 'cross-site'})[0], 403)
        self.assertEqual(self.request('/api/status', authenticated=False)[0], 401)
        self.login()
        self.assertEqual(self.request('/assets/favicon.ico')[0], 404)

    def test_producer_progress_retains_latest_without_a_growing_ipc_queue(self):
        from src.application.contracts import ProgressEvent
        sender = Mock()
        clock = Mock(return_value=0)
        relay = ProgressRelay(sender, clock=clock)

        for completed in range(10_000):
            relay.observe(ProgressEvent("history", completed, 10_000, "account-analysis"))

        sender.send.assert_called_once_with(("progress", {
            "phase": "history", "completed": 0, "total": 10_000, "stage": "account-analysis"}))
        self.assertEqual(9999, relay.pending["completed"])
        clock.return_value = 0.11
        relay.observe(ProgressEvent("finalizing", 1, 2, "finalizing"))
        self.assertEqual(2, sender.send.call_count)
        self.assertEqual("finalizing", sender.send.call_args.args[0][1]["stage"])
        relay.observe(ProgressEvent("finalizing", 2, 2, "finalizing"))
        relay.flush()
        self.assertEqual(3, sender.send.call_count)
        self.assertEqual(2, sender.send.call_args.args[0][1]["completed"])
        self.assertIsNone(relay.pending)

    def test_bootstrap_is_one_use_expiring_and_session_is_instance_scoped(self):
        token = self.server.session.bootstrap()
        self.login()
        self.assertEqual(401, self.request("/api/bootstrap", {"credential": token})[0])
        self.assertEqual(200, self.request("/api/status")[0])
        self.assertEqual(401, self.request("/api/status", headers={"Cookie": "cg_session=wrong"})[0])
        other = BrowserSession()
        self.assertFalse(other.authenticated(self.cookie))
        expired = other.bootstrap()
        with patch("src.web.security.time.monotonic", return_value=time.monotonic() + 121):
            self.assertIsNone(other.exchange(expired))
        self.assertIsNone(other.exchange("å"))

    def test_status_exposes_loaded_product_version_not_static_assets_or_disk_changes(self):
        from src.version import DISPLAY_VERSION
        self.login()
        self.assertEqual(DISPLAY_VERSION, json.loads(self.request('/api/status')[2])['product_version'])
        with patch('src.version.DISPLAY_VERSION', 'v999.1'):
            self.assertEqual(DISPLAY_VERSION, json.loads(self.request('/api/status')[2])['product_version'])
        with patch('src.web.http.DISPLAY_VERSION', 'v91.7'):
            self.assertEqual('v91.7', json.loads(self.request('/api/status')[2])['product_version'])

    def test_cookie_renewal_covers_full_idle_window_and_all_successful_api_replies(self):
        now = Mock(return_value=1000)
        self.server.session = BrowserSession(clock=now)
        self.login()
        original_cookie, csrf = self.cookie, self.csrf
        for elapsed in (10, 3599):
            now.return_value = 1000 + elapsed
            status, headers, _ = self.request('/api/session')
            self.assertEqual(200, status)
            self.assertNotIn('Set-Cookie', headers)
        # Close immediately before renewal; return just before seven idle days.
        now.return_value += 7 * 86400 - 1
        status, headers, body = self.request('/api/session')
        self.assertEqual(200, status)
        self.assertEqual(original_cookie, headers['Set-Cookie'].split(';', 1)[0])
        self.assertEqual('HttpOnly; SameSite=Strict; Path=/; Max-Age=608400',
                         headers['Set-Cookie'].split('; ', 1)[1])
        self.assertEqual(csrf, json.loads(body)['csrf'])
        now.return_value += 7 * 86400
        status, headers, _ = self.request('/api/session')
        self.assertEqual(401, status)
        self.assertNotIn('Set-Cookie', headers)

    def test_rejected_and_public_requests_never_renew_browser_activity(self):
        now = Mock(return_value=1000)
        self.server.session = BrowserSession(clock=now)
        self.login()
        now.return_value += 3600
        cases = [('/', None, {}, 200), ('/health', None, {}, 200),
                 ('/api/status', None, {'Host': 'evil.example'}, 403),
                 ('/api/status', None, {'Origin': 'null'}, 403),
                 ('/api/session', None, {'Cookie': 'invalid=wrong'}, 401),
                 ('/api/reports', {'kind': 'sessions'}, {'X-CG-CSRF': 'wrong'}, 403),
                 ('/api/reports', {'kind': 'invalid'}, {}, 400),
                 ('/api/not-found', None, {}, 404)]
        for path, value, supplied, expected in cases:
            status, headers, _ = self.request(path, value, headers=supplied)
            self.assertEqual(expected, status)
            self.assertNotIn('Set-Cookie', headers)
        now.return_value = 1000 + 7 * 86400
        self.assertEqual(401, self.request('/api/status')[0])

    def test_real_live_poll_and_settings_write_renew_without_report_acquisition(self):
        from types import SimpleNamespace
        from src.web.events import EventHub
        now = Mock(return_value=1000)
        self.server.session = BrowserSession(clock=now)
        self.login()
        self.server.lifecycle = SimpleNamespace(events=EventHub('fixture'), nonce='fixture',
            stopping=Event(), observations=Mock())
        self.server.settings = Mock()
        self.server.settings.write.return_value = {'theme': 'web'}
        for day in range(1, 16):
            now.return_value = 1000 + day * 86400
            status, headers, _ = self.request('/api/live')
            self.assertEqual(200, status)
            self.assertIn('Max-Age=608400', headers['Set-Cookie'])
            self.assertEqual(200, self.request('/api/settings/theme', {'theme': 'web'})[0])
            self.assertNotIn('Set-Cookie', self.request('/api/live')[1])
        self.assertIsNone(self.jobs._active)
        self.assertEqual({}, self.jobs._jobs)

    def test_concurrent_same_browser_handoffs_keep_active_cookie_and_csrf(self):
        from concurrent.futures import ThreadPoolExecutor
        self.login()
        cookie, csrf = self.cookie, self.csrf
        links = [self.server.session.bootstrap(renew=True) for _ in range(4)]
        with ThreadPoolExecutor(max_workers=4) as pool:
            replies = list(pool.map(lambda token: self.request('/api/bootstrap', {'credential': token}), links))
        for status, headers, body in replies:
            self.assertEqual(200, status)
            self.assertEqual(cookie, headers['Set-Cookie'].split(';', 1)[0])
            self.assertEqual(csrf, json.loads(body)['csrf'])
        self.assertEqual(200, self.request('/api/session')[0])
        self.assertEqual(401, self.request('/api/bootstrap', {'credential': links[0]})[0])

    def test_host_origin_dns_rebinding_and_csrf_are_denied(self):
        self.login()
        for headers in ({"Host": "evil.example"}, {"Host": "localhost"}, {"Host": "127.0.0.1:1"},
                        {"Origin": "null"}, {"Origin": "https://evil.example"},
                        {"Sec-Fetch-Site": "cross-site"}):
            with self.subTest(headers=headers):
                self.assertEqual(403, self.request("/api/status", headers=headers)[0])
        for headers in ({"Origin": ""}, {"X-CG-CSRF": ""}, {"Content-Type": "text/plain"}):
            self.assertEqual(403, self.request("/api/reports", {"kind": "sessions"}, headers=headers)[0])

    def test_checkout_cookies_coexist_and_replacement_rejects_old_credentials(self):
        first = BrowserSession("a" * 32)
        second = BrowserSession("b" * 32)
        replacement = BrowserSession("a" * 32)
        jar = {}
        for session in (first, second):
            token, _ = session.exchange(session.bootstrap())
            jar[session.cookie_name] = token
        # Model a browser: both port-independent cookies are sent to both hosts.
        cookies = "; ".join(f"{name}={value}" for name, value in jar.items())
        self.assertEqual(2, len(jar))
        self.assertTrue(first.authenticated(cookies))
        self.assertTrue(second.authenticated(cookies))
        self.assertFalse(replacement.authenticated(cookies))
        token, _ = replacement.exchange(replacement.bootstrap())
        jar[replacement.cookie_name] = token
        cookies = "; ".join(f"{name}={value}" for name, value in jar.items())
        self.assertEqual(2, len(jar))
        self.assertFalse(first.authenticated(cookies))
        self.assertTrue(second.authenticated(cookies))
        self.assertTrue(replacement.authenticated(cookies))

    def test_routes_methods_parameters_traversal_and_wire_limits(self):
        self.login()
        for path in ("/../config/user-config.jsonc", "/%2e%2e/README.md", "/api/status?x=secret", "/a\\b"):
            self.assertEqual(400, self.request(path)[0])
        self.assertEqual(405, self.request("/api/status", method="DELETE")[0])
        self.assertEqual(404, self.request("/README.md")[0])
        self.assertEqual(413, self.request("/api/reports", {"kind": "a" * 5000})[0])
        for value in ({}, {"kind": "unknown"}, {"kind": "session", "session_id": ""},
                      {"kind": "sessions", "session_limit": True}, {"kind": "date", "date_text": "bad"},
                      {"kind": "date", "date_text": "2026-02-30"},
                      {"kind": "date", "date_text": "2026-10-26:2026-10-25"},
                      {"kind": "date", "date_text": "9999-12-31"},
                      {"kind": "date", "date_text": "2026-W01-1"},
                      {"kind": "sessions", "path": "PRIVATE"}, {"kind": "normal", "session_id": "x"}):
            self.assertEqual(400, self.request("/api/reports", value)[0])
        prefix = f"GET /health HTTP/1.1\r\nHost: {self.server.host}\r\n".encode()
        for suffix in (b"Host: evil\r\n\r\n", b"Transfer-Encoding: chunked\r\n\r\n",
                       b"Content-Length: 1\r\nContent-Length: 2\r\n\r\n"):
            self.assertIn(b" 403 ", self.raw(prefix + suffix))
        self.assertIn(b" 400 ", self.raw(b"GET http://evil/ HTTP/1.1\r\n\r\n"))
        self.assertEqual(b"", self.raw(prefix + b"X: " + b"x" * 17000 + b"\r\n\r\n"))

    def test_report_dto_decimal_null_and_text_are_not_reinterpreted(self):
        self.login()
        key = json.loads(self.request("/api/reports", {"kind": "session", "session_id": "root"})[2])["id"]
        result = self.wait_job(key)
        self.assertEqual("complete", result["status"])
        dto = result["result"]
        self.assertIsNone(dto["error"])
        block = dto["view"]["prompt_blocks"][0]
        self.assertEqual("0.0170300", block["total_ccost"])
        self.assertEqual("<script>PRIVATE_TEXT</script>", block["title"])
        self.assertIsNone(block["rows"][0]["incoming_context_ccost"])
        self.assertIn("source", dto)
        js = (Path(__file__).resolve().parents[2] / "src/web/assets/app.js").read_text()
        renderer = (Path(__file__).resolve().parents[2] / "src/web/assets/render.js").read_text()
        self.assertIn("node.textContent", renderer)
        self.assertNotIn("innerHTML", js)
        self.assertNotIn("innerHTML", renderer)
        self.assertLess(js.index("history.replaceState"), js.index("fetch("))

    def test_empty_and_offline_are_distinct_with_secret_free_errors_and_logs(self):
        self.login()
        with contextlib.redirect_stderr(io.StringIO()) as logs:
            empty = json.loads(self.request("/api/reports", {"kind": "sessions"})[2])["id"]
            acquired = self.wait_job(empty)
            self.assertEqual("complete", acquired["status"])
            self.assertEqual([], acquired["result"]["view"]["session_usage"])
            failed = json.loads(self.request("/api/reports", {"kind": "date", "date_text": "1970-01-01"})[2])["id"]
            unavailable = self.wait_job(failed)
            self.assertEqual("failed", unavailable["status"])
            self.assertEqual("error", unavailable["result"]["source"]["status"])
            self.assertNotIn("PRIVATE", json.dumps(unavailable))
            self.assertEqual("", logs.getvalue())

    def test_slow_report_progress_cancellation_coalescing_and_http_readiness(self):
        self.login()
        value = {"kind": "token-mix"}
        key = json.loads(self.request("/api/reports", value)[2])["id"]
        self.assertEqual(key, json.loads(self.request("/api/reports", value)[2])["id"])
        until = time.monotonic() + 5
        while time.monotonic() < until:
            state = json.loads(self.request(f"/api/jobs/{key}")[2])
            if state["progress"]["phase"] == "history":
                break
            time.sleep(.05)
        self.assertEqual("history", state["progress"]["phase"])
        started = time.monotonic()
        self.assertEqual(200, self.request("/health")[0])
        self.assertEqual(200, self.request(f"/api/jobs/{key}/cancel", {})[0])
        self.assertEqual("cancelled", self.wait_job(key)["status"])
        self.assertLess(time.monotonic() - started, 3)
        self.assertIsNone(self.jobs._active)

    def test_connection_admission_is_bounded_and_shutdown_closes_slow_clients(self):
        connections = [socket.create_connection(("127.0.0.1", self.server.server_port), timeout=8)
                       for _ in range(12)]
        try:
            for conn in connections:
                conn.sendall(b"G")
            until = time.monotonic() + 2
            while self.server._slots._value and time.monotonic() < until:
                time.sleep(.01)
            self.assertEqual(0, self.server._slots._value)
            with socket.create_connection(("127.0.0.1", self.server.server_port), timeout=8) as extra:
                self.assertEqual(b"", extra.recv(1))
            self.stopped.set()
            self.thread.join(3)
            started = time.monotonic()
            self.server.server_close()
            self.assertLess(time.monotonic() - started, 6)
        finally:
            for conn in connections:
                conn.close()

    def test_dripping_client_cannot_extend_absolute_request_deadline(self):
        started = time.monotonic()
        with socket.create_connection(("127.0.0.1", self.server.server_port), timeout=8) as conn:
            conn.sendall(b"GET /health HTTP/1.1\r\nX: ")
            while time.monotonic() - started < 6:
                try:
                    conn.sendall(b"a")
                except OSError:
                    break
                time.sleep(.05)
            try:
                self.assertEqual(b"", conn.recv(1))
            except (ConnectionAbortedError, ConnectionResetError):
                pass  # Windows may report enforced closure as abort/reset, not EOF.
        self.assertLess(time.monotonic() - started, 6.5)


class JobBoundaryTests(unittest.TestCase):
    def test_valid_terminal_ipc_publishes_before_natural_exit_without_termination(self):
        for message, expected in [
                (('result', json.dumps(dict(error=None, source=dict(status='acquired'))).encode()), 'complete'),
                (('error', 'report_unavailable'), 'failed')]:
            with self.subTest(message=message[0]):
                child = ReportProcess(messages=[message])
                jobs = ReportJobs(context=child.context)
                key = jobs.submit(ReportRequest())
                jobs.tick()

                jobs.tick()
                published = jobs.snapshot(key)['status']
                child.alive = False
                jobs.tick()

                self.assertEqual(expected, published)
                self.assertIsNone(jobs._active)
                child.process.join.assert_not_called()
                child.process.terminate.assert_not_called()
                child.process.kill.assert_not_called()
                child.receiver.close.assert_called_once()
                child.process.close.assert_called_once()
                self.assertEqual([], jobs._retiring)
                jobs.close()

    def test_completed_stats_slice_retires_while_logical_job_starts_its_fresh_child(self):
        result = dict(error=None, source=dict(status='acquired'),
            view=dict(ai_stats=[], ai_stats_work=dict(completed=1)))
        child = ReportProcess(messages=[('result', json.dumps(result).encode())])
        next_child = ReportProcess(exit_after_join=1)
        child.context.Pipe.side_effect = [(child.receiver, child.sender), (next_child.receiver, next_child.sender)]
        child.context.Process.side_effect = [child.process, next_child.process]
        jobs = ReportJobs(context=child.context)
        self.addCleanup(jobs.close)
        key = jobs.submit(ReportRequest(ReportKind.AI_STATS))
        jobs.tick()

        jobs.tick()
        retiring = [owner['process'] for owner in jobs._retiring]
        child.alive = False
        jobs.tick()

        self.assertEqual([child.process], retiring)
        self.assertEqual('running', jobs.snapshot(key)['status'])
        self.assertEqual(2, jobs.snapshot(key)['work']['slices'])
        self.assertIs(next_child.process, jobs._active[1])
        child.process.terminate.assert_not_called()
        child.process.close.assert_called_once()
        next_child.process.close.assert_not_called()
        next_child.receiver.close.assert_not_called()

    def test_history_continuation_retires_its_slice_while_a_fresh_child_keeps_the_observation(self):
        from src.web.report_control import ManagedReport
        proof = dict(signature='a' * 64, completed=256, total=550)
        child = ReportProcess(messages=[('checkpoint', proof),
            ('result', json.dumps(dict(error=dict(code='history_continue'))).encode())])
        next_child = ReportProcess(exit_after_join=1)
        child.context.Pipe.side_effect = [(child.receiver, child.sender), (next_child.receiver, next_child.sender)]
        child.context.Process.side_effect = [child.process, next_child.process]
        jobs = ReportJobs(context=child.context)
        self.addCleanup(jobs.close)
        key = jobs.submit(ManagedReport(ReportKind.TOKEN_MIX))
        jobs.tick()

        jobs.tick()
        retiring = [owner['process'] for owner in jobs._retiring]
        child.alive = False
        jobs.tick()

        first, second = (spawn.kwargs['args'][2] for spawn in child.context.Process.call_args_list)
        self.assertEqual([child.process], retiring)
        self.assertIs(next_child.process, jobs._active[1])
        self.assertEqual(proof, jobs._jobs[key]['continued'])
        self.assertEqual(2, jobs.snapshot(key)['work']['slices'])
        self.assertEqual(first.observation_ms, second.observation_ms)
        child.process.join.assert_not_called()
        child.process.terminate.assert_not_called()
        child.process.close.assert_called_once()
        next_child.process.close.assert_not_called()

    @staticmethod
    def owned_children(count):
        children = [ReportProcess(exit_after_join=1) for _ in range(count)]
        context = children[0].context
        context.Pipe.side_effect = [(child.receiver, child.sender) for child in children]
        context.Process.side_effect = [child.process for child in children]
        return context, children

    def test_unadmitted_background_startup_yields_once_to_waiting_foreground_until_durable_progress(self):
        from src.web.report_control import ManagedReport
        context, (background, foreground, restarted) = self.owned_children(3)
        jobs = ReportJobs(context=context)
        self.addCleanup(jobs.close)
        warm = jobs.submit(ManagedReport(ReportKind.TOKEN_MIX))
        jobs.prioritize({warm: 2})
        jobs.tick()
        demand = jobs.submit(ManagedReport(ReportKind.COMPARISONS))
        jobs.prioritize({warm: 2, demand: 0})

        jobs.tick()
        interrupted = jobs.snapshot(warm)['status']
        foreground.messages.append(('result', json.dumps(dict(error=None, source=dict(status='acquired'))).encode()))
        jobs.tick()
        again = jobs.submit(ManagedReport(ReportKind.SESSIONS))
        jobs.prioritize({warm: 2, again: 0})
        jobs.tick()
        restarted.messages.extend([('admit', None), ('checkpoint', dict(signature='b' * 64, completed=4, total=10))])
        jobs.tick()

        requests = [spawn.kwargs['args'][2] for spawn in context.Process.call_args_list]
        self.assertEqual('queued', interrupted)
        background.process.terminate.assert_called_once()
        background.receiver.send.assert_not_called()
        background.process.close.assert_called_once()
        self.assertEqual([ReportKind.TOKEN_MIX, ReportKind.COMPARISONS, ReportKind.TOKEN_MIX],
            [request.kind for request in requests])
        self.assertEqual(requests[0].observation_ms, requests[2].observation_ms)
        restarted.process.terminate.assert_not_called()
        restarted.receiver.send.assert_called_once_with('run')
        self.assertEqual(warm, jobs._active[0])
        self.assertNotIn('startup_interrupted', jobs._jobs[warm])

    def test_background_warming_advances_between_foreground_bursts_and_regains_one_interruption(self):
        from src.web.report_control import ManagedReport
        done = json.dumps(dict(error=None, source=dict(status='acquired'))).encode()
        advanced = json.dumps(dict(error=None, source=dict(status='acquired'),
            view=dict(ai_stats=[], ai_stats_work=dict(completed=1)))).encode()
        context, (first, burst, resumed, next_slice, _) = self.owned_children(5)
        jobs = ReportJobs(context=context)
        self.addCleanup(jobs.close)
        warm = jobs.submit(ManagedReport(ReportKind.AI_STATS))
        jobs.prioritize({warm: 2})
        jobs.tick()
        demand = jobs.submit(ManagedReport(ReportKind.COMPARISONS))
        jobs.prioritize({warm: 2, demand: 0})
        jobs.tick()
        burst.messages.append(('result', done))
        jobs.tick()
        burst.alive = False
        resumed.messages.extend([('admit', None), ('result', advanced)])
        jobs.tick()
        again = jobs.submit(ManagedReport(ReportKind.SESSIONS))
        jobs.prioritize({warm: 2, again: 0})

        jobs.tick()

        requests = [spawn.kwargs['args'][2] for spawn in context.Process.call_args_list]
        self.assertEqual([ReportKind.AI_STATS, ReportKind.COMPARISONS, ReportKind.AI_STATS, ReportKind.AI_STATS,
            ReportKind.SESSIONS], [request.kind for request in requests])
        self.assertEqual(1, len({(request.observation_ms, request.scan) for request in requests if
            request.kind is ReportKind.AI_STATS}))
        first.process.terminate.assert_called_once()
        resumed.process.terminate.assert_not_called()
        next_slice.process.terminate.assert_called_once()
        self.assertEqual(1, jobs._jobs[warm]['covered'])
        self.assertEqual(2, jobs._jobs[warm]['startup_interruptions'])
        self.assertEqual('queued', jobs.snapshot(warm)['status'])
        self.assertEqual(again, jobs._active[0])

    def test_admission_grant_and_startup_interruption_follow_the_host_decision_order(self):
        from src.web.report_control import ManagedReport
        for case in ('pending-admit', 'granted', 'promoted', 'requested-demand'):
            with self.subTest(case=case):
                context, (background, _) = self.owned_children(2)
                jobs = ReportJobs(context=context)
                warm = jobs.submit(ManagedReport(ReportKind.TOKEN_MIX))
                jobs.prioritize({warm: 2})
                jobs.tick()
                background.messages.append(('admit', None))
                if case == 'granted':
                    jobs.tick()
                demand = jobs.submit(ManagedReport(ReportKind.COMPARISONS))
                jobs.prioritize({warm: 0 if case == 'promoted' else 2,
                                 demand: 1 if case == 'requested-demand' else 0})

                jobs.tick()

                interrupted = case == 'pending-admit'
                grant = [] if interrupted else [call('free' if case == 'promoted' else 'run')]
                self.assertEqual(interrupted, background.process.terminate.called)
                self.assertEqual(grant, background.receiver.send.call_args_list)
                self.assertEqual(demand if interrupted else warm, jobs._active[0])
                jobs.close()

    def test_requested_managed_startup_is_admitted_at_spawn_without_a_second_grant(self):
        from src.web.report_control import ManagedReport
        child = ReportProcess(messages=[('admit', None)], exit_after_join=1)
        jobs = ReportJobs(context=child.context)
        self.addCleanup(jobs.close)
        jobs.submit(ManagedReport(ReportKind.TOKEN_MIX))
        jobs.tick()
        granted = list(child.receiver.send.call_args_list)

        jobs.tick()

        self.assertEqual([call('free')], granted)
        self.assertEqual([call('free')], child.receiver.send.call_args_list)

    def test_uncontended_foreground_runs_unparked_until_equal_priority_work_requests_one_yield(self):
        from src.web.report_control import ManagedReport
        context, (child, rival) = self.owned_children(2)
        jobs = ReportJobs(context=context)
        self.addCleanup(jobs.close)
        key = jobs.submit(ManagedReport(ReportKind.TOKEN_MIX))
        jobs.prioritize({key: 0})
        jobs.tick()
        child.messages.append(('progress', dict(phase='history', completed=1, total=3)))
        jobs.tick()
        jobs.tick()
        alone = list(child.receiver.send.call_args_list)
        other = jobs.submit(ManagedReport(ReportKind.COMPARISONS))
        jobs.prioritize({key: 0, other: 0})
        jobs.tick()
        jobs.tick()
        requested = list(child.receiver.send.call_args_list)
        child.messages.append(('yield', None))

        jobs.tick()
        jobs.tick()

        self.assertEqual([call('free')], alone)
        self.assertEqual([call('free'), call('yield')], requested)
        self.assertIn(key, jobs._parked)
        self.assertEqual(other, jobs._active[0])
        self.assertEqual([call('free'), call('yield')], rival.receiver.send.call_args_list)

    def test_resume_grant_follows_current_priority_and_demotion_requests_pacing(self):
        from src.web.report_control import ManagedReport
        context, (child,) = self.owned_children(1)
        jobs = ReportJobs(context=context)
        self.addCleanup(jobs.close)
        key = jobs.submit(ManagedReport(ReportKind.TOKEN_MIX))
        jobs.prioritize({key: 0})
        with patch('src.web.jobs.time.monotonic', return_value=10):
            jobs.tick()
            jobs.prioritize({key: 2})
            jobs.tick()
            child.messages.append(('yield', None))
            jobs.tick()
            jobs.prioritize({key: 0})
            child.messages.append(('yield', None))

            jobs.tick()

        self.assertEqual([call('free'), call('yield'), call('run'), call('free')],
            child.receiver.send.call_args_list)
        self.assertEqual(key, jobs._active[0])

    def test_pending_yield_request_does_not_disturb_terminal_publication_or_the_next_grant(self):
        from src.web.report_control import ManagedReport
        context, (child, successor) = self.owned_children(2)
        jobs = ReportJobs(context=context)
        self.addCleanup(jobs.close)
        key = jobs.submit(ManagedReport(ReportKind.TOKEN_MIX))
        other = jobs.submit(ManagedReport(ReportKind.COMPARISONS))
        jobs.prioritize({key: 0, other: 0})
        jobs.tick()
        jobs.tick()
        child.messages.append(('result', json.dumps(dict(error=None, source=dict(status='acquired'))).encode()))

        jobs.tick()
        jobs.tick()

        self.assertEqual('complete', jobs.snapshot(key)['status'])
        self.assertEqual([call('free'), call('yield')], child.receiver.send.call_args_list)
        self.assertEqual([call('free')], successor.receiver.send.call_args_list)
        self.assertEqual(other, jobs._active[0])

    def test_free_quantum_parks_only_on_request_while_paced_quantum_parks_every_slice(self):
        from itertools import count
        from src.web.report_control import Quantum
        pending = ['free']
        connection = Mock()
        connection.poll.side_effect = lambda: bool(pending)
        connection.recv.side_effect = lambda: pending.pop(0)
        quantum = Quantum(connection, .5, clock=Mock(side_effect=count()))
        quantum.admit()

        quantum.checkpoint()
        quantum.checkpoint()
        unrequested = list(connection.send.call_args_list)
        pending.extend(['yield', 'run'])
        quantum.checkpoint()
        pending.append('free')
        quantum.checkpoint()
        pending.append('invalid')

        with self.assertRaisesRegex(RuntimeError, '^invalid_worker_control$'):
            quantum.checkpoint()
        self.assertEqual([call(('admit', None))], unrequested)
        self.assertEqual([call(('admit', None)), call(('yield', None)), call(('yield', None))],
            connection.send.call_args_list)

    def test_managed_worker_waits_for_admission_before_acquisition(self):
        from src.web.report_control import ManagedReport
        for reply, admitted in (('run', True), ('stop', False)):
            with self.subTest(reply=reply):
                events = Mock()
                events.sender.recv.return_value = reply
                events.app.execute.return_value.to_json.return_value = dict(error=None)
                with patch('src.web.composition.application', return_value=events.app):
                    run_report(events.sender, ManagedReport(ReportKind.TOKEN_MIX))

                self.assertEqual([call.sender.send(('admit', None)), call.sender.recv()], events.mock_calls[:2])
                self.assertEqual(admitted, events.app.execute.called)
                if not admitted:
                    events.sender.send.assert_called_with(('error', 'report_unavailable'))

    def test_exhausted_natural_grace_escalates_on_fixed_deadlines_without_blocking(self):
        child = ReportProcess(messages=[('error', 'report_unavailable')])
        jobs = ReportJobs(context=child.context)
        jobs.submit(ReportRequest())
        with patch('src.web.jobs.time.monotonic', return_value=10):
            jobs.tick()
            jobs.tick()

        for now in (10.9, 11.0, 11.5, 11.9):
            with patch('src.web.jobs.time.monotonic', return_value=now):
                jobs.tick()
        terminated = child.process.terminate.call_count
        child.alive = False
        with patch('src.web.jobs.time.monotonic', return_value=12.0):
            jobs.tick()

        self.assertEqual(1, terminated)
        child.process.join.assert_not_called()
        child.process.kill.assert_not_called()
        child.process.close.assert_called_once()
        self.assertEqual([], jobs._retiring)

    def test_cancel_shutdown_and_invalid_ipc_force_stop_without_grace(self):
        for action in ('cancel', 'shutdown', 'unknown', 'invalid-result', 'invalid-error', 'eof'):
            with self.subTest(action=action):
                messages = {'unknown': [('other', 'not-terminal')], 'invalid-result': [('result', b'{}')],
                    'invalid-error': [('error', {})], 'eof': [('error', 'unused')]}.get(action, ())
                child = ReportProcess(messages=messages, exit_after_join=1)
                if action == 'eof':
                    child.receiver.recv.side_effect = EOFError
                jobs = ReportJobs(context=child.context)
                key = jobs.submit(ReportRequest())
                with patch('src.web.jobs.time.monotonic', return_value=0):
                    jobs.tick()

                with patch('src.web.jobs.time.monotonic', return_value=0):
                    if action == 'cancel':
                        jobs.cancel(key)
                    elif action == 'shutdown':
                        jobs.close()
                    else:
                        jobs.tick()

                self.assertEqual([call.is_alive(), call.terminate(), call.join(timeout=1)],
                    child.process.mock_calls[1:4])
                child.process.join.assert_called_once_with(timeout=1)
                child.process.close.assert_called_once()
                self.assertIsNone(jobs._active)

    def test_unconfirmed_retirement_latches_failure_retains_owner_and_allows_bounded_cleanup_retry(self):
        child = ReportProcess(messages=[('result', json.dumps(dict(error=None,
            source=dict(status='acquired'))).encode())])
        jobs = ReportJobs(context=child.context)
        request = ReportRequest(ReportKind.COMPARISONS)
        key = jobs.submit(request)
        with patch('src.web.jobs.time.monotonic', return_value=10):
            jobs.tick()
            jobs.tick()  # Publishes and retires before the child exits.
        published = jobs.snapshot(key)['status']
        owner = jobs._retiring[0]

        for now in (11, 12):
            with patch('src.web.jobs.time.monotonic', return_value=now):
                jobs.tick()
        with patch('src.web.jobs.time.monotonic', return_value=13), \
                self.assertRaisesRegex(ReportWorkerStopError, '^report_worker_stop_timeout$') as caught:
            jobs.tick()

        self.assertEqual('complete', published)
        self.assertEqual([owner], jobs._retiring)
        child.process.terminate.assert_called_once()
        child.process.kill.assert_called_once()
        child.process.join.assert_not_called()
        child.receiver.close.assert_not_called()
        child.process.close.assert_not_called()
        for operation in (lambda: jobs.submit(request), lambda: jobs.snapshot(key), jobs.tick,
                jobs.readiness, jobs.updates, lambda: jobs.cancel(key)):
            with self.assertRaises(ReportWorkerStopError) as latched:
                operation()
            self.assertIs(caught.exception, latched.exception)
        with self.assertRaises(ReportWorkerStopError):
            jobs.close()
        self.assertEqual([owner], jobs._retiring)
        self.assertEqual([call(timeout=1)] * 2, child.process.join.call_args_list)

        child.alive = False
        jobs.close()
        jobs.close()

        self.assertEqual([], jobs._retiring)
        child.receiver.close.assert_called_once()
        child.process.close.assert_called_once()
        with self.assertRaises(ReportWorkerStopError):
            jobs.snapshot(key)  # Even the already-published valid report cannot conceal the fault.

    def test_retirees_count_as_resident_children_and_withhold_only_fresh_launches(self):
        from src.web.report_control import ManagedReport
        jobs = ReportJobs(context=ReportProcess().context)
        parked = [jobs.submit(ManagedReport(kind)) for kind in (ReportKind.TOKEN_MIX, ReportKind.COMPARISONS)]
        fresh = jobs.submit(ReportRequest(ReportKind.SESSIONS))
        retirees = [dict(process=Mock(), receiver=Mock(), stage=0, deadline=float('inf')) for _ in range(2)]
        for retiree in retirees:
            retiree['process'].is_alive.return_value = True
        for key in parked:
            jobs._parked[key] = Mock(), Mock()
        jobs._retiring.extend(retirees)
        jobs.prioritize({fresh: 0, parked[0]: 1, parked[1]: 1})

        jobs.tick()
        resumed = jobs._active[0]
        jobs._active = None
        jobs._jobs[resumed]['status'] = 'paused-for-test'
        jobs._parked[parked[1]] = Mock(), Mock()
        jobs._jobs[parked[1]]['status'] = 'paused-for-test'
        retirees[1]['process'].is_alive.return_value = False
        jobs.tick()

        self.assertIn(resumed, parked)
        self.assertEqual('running', jobs.snapshot(fresh)['status'])
        self.assertEqual([retirees[0]], jobs._retiring)
        retirees[0]['receiver'].close.assert_not_called()
        retirees[1]['receiver'].close.assert_called_once()

    def test_worker_compacts_json_without_dropping_provenance_or_raising_limit(self):
        values = {"rows": [{"a": 1, "b": 2}] * 4}
        self.assertGreater(len(json.dumps(values).encode("ascii")), 70)
        sender, app = Mock(), Mock()
        app.execute.return_value.to_json.return_value = values
        with patch("src.web.composition.application", return_value=app), patch("src.web.jobs.MAX_RESULT_BYTES", 70):
            run_report(sender, ReportRequest())
        (kind, payload), = sender.send.call_args.args
        self.assertEqual("result", kind)
        self.assertLessEqual(len(payload), 70)
        self.assertEqual(values, json.loads(payload))
        sender.close.assert_called_once()

    def test_worker_result_limit_and_unexpected_error_are_sanitized(self):
        sender = Mock()
        result = Mock()
        result.to_json.return_value = {"large": "x" * MAX_RESULT_BYTES}
        app = Mock()
        app.execute.return_value = result
        with patch("src.web.composition.application", return_value=app):
            run_report(sender, ReportRequest())
        sender.send.assert_called_once_with(("error", "result_too_large"))
        sender.close.assert_called_once()
        sender.reset_mock()
        with patch("src.web.composition.application", side_effect=RuntimeError("PRIVATE token/path")):
            run_report(sender, ReportRequest())
        sender.send.assert_called_once_with(("error", "report_unavailable"))

    def test_queue_backpressure_retention_and_closed_admission(self):
        jobs = ReportJobs(target=finite_report)
        self.addCleanup(jobs.close)
        keys = [jobs.submit(ReportRequest(ReportKind.SESSION, session_id=str(i))) for i in range(4)]
        with self.assertRaisesRegex(RuntimeError, "busy"):
            jobs.submit(ReportRequest(ReportKind.NORMAL))
        for key in keys:
            jobs.cancel(key)
        for i in range(20):
            key = jobs.submit(ReportRequest(ReportKind.SESSION, session_id=str(i)))
            jobs.cancel(key)
        self.assertIsNone(jobs.snapshot(keys[0]))
        self.assertEqual(16, len(jobs._jobs))
        jobs.close()
        with self.assertRaisesRegex(RuntimeError, "stopping"):
            jobs.submit(ReportRequest(ReportKind.NORMAL))

    def test_slow_valid_report_survives_days_of_elapsed_work_and_completes_automatically(self):
        jobs = ReportJobs(target=finite_report)
        self.addCleanup(jobs.close)
        key = jobs.submit(ReportRequest(ReportKind.SESSION, session_id='root'))
        jobs.tick()
        owner, process, receiver, started = jobs._active
        jobs._active = owner, process, receiver, started - 2 * 86400
        end = time.monotonic() + 10

        while time.monotonic() < end:
            jobs.tick()
            result = jobs.snapshot(key)
            if result['status'] not in {'queued', 'running'}:
                break
            time.sleep(.01)

        self.assertEqual('complete', result['status'], result['error'])
        self.assertIsNone(result['result']['error'])
        self.assertTrue(result['result']['view']['prompt_blocks'])
        self.assertEqual(1, result['work']['slices'])
        self.assertIsNone(jobs._active)
        while jobs._retiring and time.monotonic() < end:
            jobs.tick()  # Published first; the owned child is then reaped without blocking.
            time.sleep(.01)
        self.assertTrue(process._closed)

    def test_report_parser_allowlists_native_modes_and_parameters(self):
        self.assertEqual(ReportKind.ALL_MODELS, parse_report({"kind": "all-models"}).kind)
        self.assertEqual("root", parse_report({"kind": "session", "session_id": "root"}).session_id)
        with self.assertRaises(ValueError):
            parse_report({"kind": "sessions", "session_limit": -1})
        with self.assertRaises(ValueError):
            parse_report({"kind": "session", "session_id": "../private"})


if __name__ == "__main__":
    unittest.main()
