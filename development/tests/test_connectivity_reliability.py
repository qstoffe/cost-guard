"""Deterministic startup/read recovery, classification and privacy regressions."""
from __future__ import annotations

from contextlib import closing
import http.client
import io
import json
import os
import socket
import sqlite3
import ssl
import tempfile
import threading
import time
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock, patch

from development.fixtures.opencode_v2_service import FakeV2Service, fixture, source_with_service
from development.tools.diagnostic_connectivity import connectivity_summary
from development.tools.diagnostic_logs import create_bundle
from src import bootstrap
from src.presentation.source_errors import source_error_message
from src.pricing.release_metadata import classify_transport
from src.sources import connectivity_events
from src.sources.discovery import ServiceRegistrationCandidate, ServiceRegistrationError, read_v2_service_registration
from src.sources.errors import (FailureCode, SourceConcurrentChangeError,
                                SourceSchemaError, SourceUnavailableError, http_failure, transport_failure)
from src.sources.opencode_v1 import OpenCodeV1Source
from src.sources.opencode_v2 import OpenCodeV2Source
from src.sources.opencode_v2_transport import V2Endpoint, V2HttpClient
from src.sources.opencode_v2_wire import fetch_messages
from src.sources.read_recovery import ReadRecovery
from src.sources.selection import SourceSelector
from src.watch.observers import LiveEventPump


class Clock:
    def __init__(self):
        self.now = 0.0
        self.waits = []

    def sleep(self, seconds):
        self.waits.append(seconds)
        self.now += seconds

    def budget(self):
        return ReadRecovery(monotonic=lambda: self.now, sleep=self.sleep)


def offline():
    return SourceUnavailableError("OpenCode V2 service could not be reached", code=FailureCode.REFUSED,
                                  phase="probe", generation="v2")


class StartupRecoveryTests(unittest.TestCase):
    def test_desktop_offline_with_leftover_incompatible_v1_is_not_a_crash(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with closing(sqlite3.connect(root / "legacy.db")) as db:
                db.execute("create table leftover (value text)")
                db.commit()
            selector = SourceSelector(v1_factory=lambda: OpenCodeV1Source(root / "legacy.db"),
                                      v2_factory=lambda: OpenCodeV2Source(root / "service.json"))
            stream = io.StringIO()
            clock = Clock()
            with patch.object(bootstrap, "SourceSelector", return_value=selector), \
                 patch.object(bootstrap, "ReadRecovery", side_effect=clock.budget), \
                 patch.object(bootstrap, "find_opencode_executable", return_value=None), \
                 patch.object(bootstrap.shutil, "which", return_value=None), \
                 patch.object(bootstrap, "has_opencode_installation_evidence", return_value=True), \
                 patch.object(bootstrap, "StartupProgress"), patch.object(bootstrap, "CacheDatabase") as cache, \
                 patch.object(bootstrap.sys, "stdout", stream):
                status = bootstrap.main([])
            text = stream.getvalue()
            self.assertEqual(1, status)
            self.assertIn("Cost Guard - OpenCode unavailable", text)
            self.assertIn("start OpenCode Desktop once", text)
            self.assertIn("may continue running", text)
            self.assertIn("Diagnostics", text)
            self.assertNotIn("Runtime error", text)
            self.assertNotIn("legacy tables", text)
            self.assertNotIn("session, message, part", text)
            cache.assert_not_called()
            self.assertEqual([0.5, 0.5], clock.waits)

    def test_selection_retry_refreshes_discovery_without_repeated_cli(self):
        clock = Clock()
        selector = Mock()
        selection = Mock(selected="v2")
        selector.select.side_effect = [offline(), offline(), selection]
        with patch.object(bootstrap, "SourceSelector", return_value=selector), \
             patch.object(bootstrap, "ReadRecovery", side_effect=clock.budget), \
             patch.object(bootstrap, "find_opencode_executable", return_value="opencode"), \
             patch.object(bootstrap.subprocess, "run", return_value=Mock(returncode=0)) as run:
            result = bootstrap._select_source("v2")
        self.assertIs(selection, result)
        self.assertEqual(3, selector.select.call_count)
        self.assertEqual(1, run.call_count)
        self.assertEqual([0.5, 0.5], clock.waits)

    def test_report_budget_bounds_failures_and_total_retry_time(self):
        clock = Clock()
        read = Mock(side_effect=offline())
        refresh = Mock()
        with self.assertRaises(SourceUnavailableError):
            clock.budget().run(read, refresh)
        self.assertEqual(3, read.call_count)
        self.assertEqual([0.5, 0.5], clock.waits)
        self.assertEqual(2, refresh.call_count)
        clock = Clock()
        def slow():
            clock.now += 3
            raise offline()
        with self.assertRaises(SourceUnavailableError):
            clock.budget().run(slow, refresh)
        self.assertEqual([0.5], clock.waits, "a deadline, not just an attempt counter")

    def test_healthy_selection_never_waits_or_starts_cli(self):
        selected = Mock(selected="v2")
        with patch.object(bootstrap, "SourceSelector") as selector, \
             patch.object(bootstrap, "find_opencode_executable") as executable, \
             patch.object(bootstrap.subprocess, "run") as run:
            selector.return_value.select.return_value = selected
            self.assertIs(selected, bootstrap._select_source("auto"))
        executable.assert_not_called()
        run.assert_not_called()

    def test_schema_and_auth_failures_do_not_wake_cli_or_retry(self):
        for error in (SourceSchemaError("unsupported"), http_failure(401, phase="probe"),
                      SourceUnavailableError("bad registration", code=FailureCode.REGISTRATION_INVALID)):
            with self.subTest(error=error.code), patch.object(bootstrap, "SourceSelector") as selector, \
                 patch.object(bootstrap.subprocess, "run") as run:
                selector.return_value.select.side_effect = error
                with self.assertRaises(type(error)):
                    bootstrap._select_source("v2")
                self.assertEqual(1, selector.return_value.select.call_count)
                run.assert_not_called()

    def test_catalog_failure_after_probe_retries_only_the_source_read(self):
        with source_with_service() as (source, service, _):
            self.assertTrue(source.probe().healthy)
            clock = Clock()
            source.read_recovery = clock.budget()
            client = source._client()
            json_read = client.json
            failures = [offline()]
            def read(path, **kwargs):
                if path == "/api/session" and failures:
                    raise failures.pop()
                return json_read(path, **kwargs)
            with patch.object(client, "json", side_effect=read):
                sessions = source.list_sessions()
            self.assertTrue(sessions)
            self.assertEqual([0.5], clock.waits)
            self.assertEqual(1, source.diagnostic_metadata()["connectivity"]["recoveries"])
            self.assertLess(len(service.requests), 15)

    def test_retry_deadline_applies_to_each_http_request_not_only_between_snapshots(self):
        clock = Clock()
        budget = clock.budget()
        attempts = []
        def read():
            attempts.append(clock.now)
            if len(attempts) == 1:
                raise offline()
            for _ in range(10):
                budget.request_timeout()
                clock.now += 1
        with self.assertRaises(SourceUnavailableError):
            budget.run(read)
        self.assertEqual(2, len(attempts))
        self.assertLessEqual(clock.now, 4.5)
        self.assertEqual([0.5], clock.waits)
        # An expired recovery budget never prevents a later healthy first read.
        self.assertEqual("healthy", budget.run(lambda: "healthy"))

    def test_typed_v1_errors_have_distinct_guidance(self):
        for code, title in ((FailureCode.SCHEMA, "V1 incompatible"), (FailureCode.V1_MISSING, "V1 unavailable")):
            heading, text = source_error_message(code.value, "v1", False, "private schema detail")
            self.assertIn(title, heading)
            self.assertNotIn("private", text)
            self.assertNotIn("V2 background", text)


class ConnectivityClassificationTests(unittest.TestCase):
    def test_loopback_exception_categories_do_not_leak_messages(self):
        cases = ((ConnectionRefusedError("secret endpoint"), FailureCode.REFUSED),
                 (ConnectionResetError("secret"), FailureCode.RESET),
                 (ConnectionAbortedError("secret"), FailureCode.RESET),
                 (TimeoutError("secret"), FailureCode.TIMEOUT),
                 (http.client.RemoteDisconnected("secret"), FailureCode.DISCONNECTED),
                 (http.client.HTTPException("secret"), FailureCode.UNKNOWN))
        for exception, expected in cases:
            with self.subTest(expected=expected):
                error = transport_failure(exception, phase="catalog")
                self.assertEqual(expected, error.code)
                self.assertEqual("catalog", error.phase)
                self.assertNotIn("secret", str(error))
                self.assertNotIn("secret", json.dumps(error.evidence()))

    def test_http_failures_keep_status_and_auth_is_terminal(self):
        for status in (401, 403, 404, 500, 503):
            error = http_failure(status, phase="probe")
            self.assertEqual(status, error.http_status)
            self.assertEqual(status in (401, 403), error.terminal)
            self.assertEqual(status == 503, error.readiness_retryable)

    def test_registration_missing_invalid_unreadable_are_distinct(self):
        with tempfile.TemporaryDirectory() as td:
            candidate = ServiceRegistrationCandidate(Path(td) / "service.json", "test")
            for body, code in ((None, FailureCode.REGISTRATION_MISSING), ("{", FailureCode.REGISTRATION_INVALID),
                               ('{"url":"http://localhost:bad","pid":1}', FailureCode.REGISTRATION_INVALID)):
                if body is not None:
                    candidate.path.write_text(body, encoding="utf-8")
                source = OpenCodeV2Source(candidate=candidate)
                self.assertEqual(code, source.probe().failure_code)
            with patch.object(Path, "read_text", side_effect=PermissionError("secret")):
                with self.assertRaises(ServiceRegistrationError) as error:
                    read_v2_service_registration(candidate)
                self.assertEqual(FailureCode.REGISTRATION_UNREADABLE, error.exception.code)

    def test_v2_outage_does_not_probe_alternative_message_routes(self):
        client = Mock()
        client.json.side_effect = offline()
        with self.assertRaises(SourceUnavailableError):
            fetch_messages(client, session_id="private", directory="private")
        self.assertEqual(1, client.json.call_count)

    def test_external_https_categories_include_certificate_and_unknown(self):
        cases = ((socket.gaierror("secret"), "dns_failure"),
                 (ConnectionRefusedError("secret"), "connection_failure"),
                 (TimeoutError("secret"), "timeout"),
                 (ssl.SSLCertVerificationError("secret"), "tls_certificate_verification_failure"),
                 (ssl.SSLError("secret"), "tls_failure"),
                 (http.client.HTTPException("secret"), "unknown_transport_failure"))
        for reason, category in cases:
            with self.subTest(category=category):
                error = classify_transport(urllib.error.URLError(reason), 2)
                self.assertEqual(category, error.code)
                self.assertNotIn("secret", str(error))


class V2RestartTests(unittest.TestCase):
    def test_changed_registration_closes_old_pool_and_refreshes_catalog(self):
        with source_with_service() as (source, _, registration), FakeV2Service(fixture(), password="new") as restarted:
            source.list_sessions()
            old = source._client()
            self.assertTrue(old._idle)
            registration.write_text(json.dumps({"url": restarted.url, "pid": 4242,
                "version": "2.0.18", "password": "new"}), encoding="utf-8")
            self.assertTrue(source.list_sessions())
            self.assertIsNot(old, source._client())
            self.assertEqual([], old._idle)
            self.assertTrue(restarted.requests)

    def test_retired_event_pump_closes_its_stream_and_thread(self):
        stopped = threading.Event()
        opened = threading.Event()
        class Source:
            def iter_changes(self):
                opened.set()
                stopped.wait(2)
                return
                yield  # an empty generator after cancellation

            def close_changes(self):
                stopped.set()
        pump = LiveEventPump(Source())
        pump.start()
        self.assertTrue(opened.wait(1))
        pump.stop()
        self.assertFalse(pump._thread.is_alive())
        self.assertIsNone(pump.get(0))

    def test_http_stream_cancellation_closes_only_owned_loopback_sockets(self):
        endpoint = V2Endpoint("http://127.0.0.1:1", None, 1, "opencode", None, Path("service.json"))
        client = V2HttpClient(endpoint)
        connection = Mock()
        client._streams.add(connection)
        client.close_events()
        connection.sock.shutdown.assert_called_once_with(socket.SHUT_RDWR)
        connection.close.assert_called_once()

    def test_intentional_stream_close_is_not_a_source_incident(self):
        endpoint = V2Endpoint("http://127.0.0.1:1", None, 1, "opencode", None, Path("service.json"))
        client = V2HttpClient(endpoint)
        connection = Mock()
        def cancelled(_connection, _path, _stopped):
            client.close_events()
            raise SourceUnavailableError("closed", code=FailureCode.DISCONNECTED)
            yield
        with patch.object(client, "_new_connection", return_value=connection), \
             patch.object(client, "_sse", side_effect=cancelled):
            self.assertEqual([], list(client.sse("/api/event")))
        self.assertEqual({}, client._stream_stops)
        self.assertEqual(set(), client._streams)

    def test_cancel_before_first_stream_read_never_opens_a_connection(self):
        stopped = threading.Event()
        stopped.set()
        endpoint = V2Endpoint("http://127.0.0.1:1", None, 1, "opencode", None, Path("service.json"))
        client = V2HttpClient(endpoint)
        with patch.object(client, "_new_connection") as connect:
            self.assertEqual([], list(client.sse("/api/event", stop_event=stopped)))
        connect.assert_not_called()
        source = OpenCodeV2Source("service.json")
        with patch.object(source, "_client") as connect:
            self.assertEqual([], list(source.iter_changes_until(stopped)))
        connect.assert_not_called()

    def test_stale_retry_is_bounded_and_bad_connection_is_not_reused(self):
        endpoint = V2Endpoint("http://127.0.0.1:1", None, 1, "opencode", None, Path("service.json"))
        client = V2HttpClient(endpoint)
        stale, fresh = Mock(), Mock()
        stale.request.side_effect = http.client.RemoteDisconnected("private")
        fresh.request.side_effect = ConnectionResetError("private")
        client._idle.append(stale)
        with patch.object(client, "_new_connection", return_value=fresh) as create:
            with self.assertRaises(SourceUnavailableError) as result:
                client.json("/api/info", phase="probe")
        self.assertEqual(FailureCode.RESET, result.exception.code)
        self.assertEqual(1, client.stats["stale_retries"])
        self.assertEqual(1, create.call_count)
        self.assertEqual([], client._idle)
        fresh.close.assert_called()

    def test_concurrent_snapshot_never_returns_partial_history(self):
        with source_with_service() as (source, _, _):
            revisions = ["before", "after", "before", "after", "before", "after"]
            with patch.object(source, "_revision", side_effect=revisions):
                with self.assertRaises(SourceConcurrentChangeError) as error:
                    source.load_session_snapshot("ses_root")
            self.assertEqual(FailureCode.CONCURRENT, error.exception.code)
            self.assertEqual("snapshot", error.exception.phase)
            source.refresh_connection()
            with patch.object(source, "_revision", side_effect=["before", "after", "same", "same"]):
                self.assertTrue(source.load_session_snapshot("ses_root").messages)


class IncidentEvidenceTests(unittest.TestCase):
    def test_recovered_history_remains_bounded_sanitized_and_after_bundle(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            file = root / "logs/recovery/watch-recovery.json"
            with patch.object(connectivity_events, "FILE", file), patch.dict(os.environ, {"COST_GUARD_TEST_MODE": "0"}):
                for _ in range(50):
                    connectivity_events.record("v2", "retrying", "unavailable", category="connection_refused",
                        phase="catalog", exception_type="ConnectionRefusedError", endpoint="private", auth="private")
                self.assertEqual(1, len(connectivity_events.recent_events()))
                connectivity_events.record("v2", "recovered", "available", category="connection_refused",
                    phase="catalog", attempts=3, duration_ms=10000, payload="private")
                events = connectivity_events.recent_events()
                self.assertEqual("recovered", events[-1]["event"])
                self.assertEqual(10000, events[-1]["duration_ms"])
                self.assertNotIn("private", file.read_text(encoding="utf-8"))
                os.utime(file, (time.time() - 120, time.time() - 120))
                create_bundle(root / "diagnostics/bundle.zip", root=root, json_bytes=b"{}", text_bytes=b"ok")
                self.assertEqual(events, connectivity_events.recent_events())

    def test_diagnostics_summary_separates_sources_metadata_and_validation(self):
        data = {"sources": {"v2": {"probe": {"healthy": True}},
                            "v1": {"probe": {"failure_code": "unsupported_schema"}}},
                "watch_source_recovery_events": [{"source": "v2", "event": "recovered"}],
                "model_metadata": {"summary": {"failing_sources": ["models.dev"], "cache_fallback": True}}}
        text = "\n".join(connectivity_summary(data))
        self.assertIn("temporarily unavailable but recovered", text)
        self.assertIn("V1 connectivity: incompatible", text)
        self.assertIn("cached fallback", text)
        self.assertIn("Validation/test failures are independent", text)


if __name__ == "__main__":
    unittest.main()
