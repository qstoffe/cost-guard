"""Adversarial real-loopback requests and owned spawn-process report isolation."""
from __future__ import annotations

import contextlib
import http.client
import io
import json
from pathlib import Path
import socket
from threading import Event, Thread
import time
import unittest
from unittest.mock import patch
from unittest.mock import Mock

from development.tests.fixtures.web_reports import finite_report
from src.reports import ReportKind, ReportRequest
from src.web.http import LoopbackServer
from src.web.jobs import MAX_RESULT_BYTES, ReportJobs, parse_report, run_report
from src.web.security import BrowserSession


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
            conn.shutdown(socket.SHUT_WR)
            parts = []
            while chunk := conn.recv(65536):
                parts.append(chunk)
            return b"".join(parts)

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
        self.assertIn(b"Live shares one host-owned engine", body)
        self.assertIn(b"Search/sort/page controls never change report scope or totals", body)
        self.assertIn(b'/reports.js', body)
        self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
        self.assertIn("worker-src 'none'", headers["Content-Security-Policy"])
        self.assertEqual("no-store", headers["Cache-Control"])
        self.assertNotIn(b"http://", body)
        self.assertNotIn(b"https://", body)
        self.assertEqual({"http": "ready"}, json.loads(self.request("/health")[2]))
        self.assertEqual(401, self.request("/api/status")[0])
        self.assertEqual(401, self.request("/api/reports", {"kind": "sessions"})[0])

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
        receiver.close.assert_called_once()

    def test_bootstrap_is_one_use_expiring_and_session_is_instance_scoped(self):
        token = self.server.session.bootstrap()
        self.login()
        self.assertEqual(401, self.request("/api/bootstrap", {"credential": token})[0])
        self.assertEqual(200, self.request("/api/status")[0])
        self.assertEqual(401, self.request("/api/status", headers={"Cookie": "cg_session=wrong"})[0])
        other = BrowserSession()
        self.assertFalse(other.authenticated(self.cookie))
        with patch("src.web.security.time.monotonic", return_value=time.monotonic() + 121):
            self.assertIsNone(other.exchange(other.bootstrap()))
        self.assertIsNone(other.exchange("å"))

    def test_host_origin_dns_rebinding_and_csrf_are_denied(self):
        self.login()
        for headers in ({"Host": "evil.example"}, {"Host": "localhost"}, {"Host": "127.0.0.1:1"},
                        {"Origin": "null"}, {"Origin": "https://evil.example"},
                        {"Sec-Fetch-Site": "cross-site"}):
            with self.subTest(headers=headers):
                self.assertEqual(403, self.request("/api/status", headers=headers)[0])
        for headers in ({"Origin": ""}, {"X-CG-CSRF": ""}, {"Content-Type": "text/plain"}):
            self.assertEqual(403, self.request("/api/reports", {"kind": "sessions"}, headers=headers)[0])

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

    def test_report_hard_deadline_and_close_stop_only_owned_work(self):
        jobs = ReportJobs(target=finite_report, deadline=.1)
        self.addCleanup(jobs.close)
        key = jobs.submit(ReportRequest(ReportKind.TOKEN_MIX))
        jobs.tick()
        process = jobs._active[1]
        time.sleep(.15)
        jobs.tick()
        self.assertEqual("failed", jobs.snapshot(key)["status"])
        self.assertEqual("report_timeout", jobs.snapshot(key)["error"])
        self.assertIsNone(jobs._active)
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
