"""Real stdlib TLS/exception boundaries, safe evidence and Watch recovery."""
from contextlib import contextmanager
from dataclasses import replace
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import socket
import ssl
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import urllib.error

from development.tests.fixtures.account_workers import Provider, wait_for
from development.tests.fixtures.quota_rendering import NOW, quotas, report_text, watch_text
from development.tests.fixtures.watch_runtime import MutableSource, make_service
from src.accounts import openai_tls
from src.accounts.diagnostics import sanitized_account_observation
from src.accounts.openai_subscription import OpenAIAccountProvider, _default_usage_get, USAGE_URL
from src.accounts.refresh_loop import AccountRefreshLoop
from src.presentation import WatchRenderer
from src.reports.models import AccountProjection
from src.watch import WatchCoordinator

FIXTURE = Path(__file__).parent / "fixtures/openai-tls"
PAYLOAD = {"plan_type": "prolite", "rate_limit": {
    "primary_window": {"used_percent": 25, "limit_window_seconds": 18000, "reset_at": NOW // 1000 + 7200},
    "secondary_window": {"used_percent": 60, "limit_window_seconds": 604800, "reset_at": NOW // 1000 + 86400}}}


def certificate_error(code=10):
    error = ssl.SSLCertVerificationError(1, "PRIVATE exception/certificate/token text")
    error.verify_code = code
    error.verify_message = "PRIVATE arbitrary verification message"
    return error


@contextmanager
def windows_roots(certificate="root.pem"):
    root = ssl.PEM_cert_to_DER_cert((FIXTURE / certificate).read_text(encoding="utf-8"))
    with patch.object(openai_tls, "sys", SimpleNamespace(platform="win32")), \
            patch.object(ssl, "enum_certificates", return_value=[(root, "x509_asn", True)], create=True) as enum:
        yield enum


@contextmanager
def tls_server(certificate="server.pem"):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps(PAYLOAD).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(FIXTURE / certificate, FIXTURE / "synthetic-server-key.pem")
    server.socket = context.wrap_socket(server.socket, server_side=True)
    worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
    worker.start()
    try:
        yield f"https://localhost:{server.server_port}/usage"
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


class ManualLoop(AccountRefreshLoop):
    def start(self, now_ms):
        return False  # Drive production scheduler turns with a deterministic clock.


class OpenAITransportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.auth = self.root / "auth.json"
        self.auth.write_text(json.dumps({"openai": {
            "type": "oauth", "access": "synthetic-access", "accountId": "synthetic-account",
            "methodID": "chatgpt-browser"}}), encoding="utf-8")

    def provider(self, **kwargs):
        return OpenAIAccountProvider(auth_json_path=str(self.auth), now_ms=lambda: NOW, **kwargs)

    def test_windows_root_trust_repairs_real_expired_cached_intermediate_without_relaxing_tls(self):
        polluted = ssl.create_default_context(cadata=(FIXTURE / "root.pem").read_text() +
                                               (FIXTURE / "expired-intermediate.pem").read_text())
        with tls_server() as url, patch.dict("os.environ", {"NO_PROXY": "localhost,127.0.0.1"}):
            with patch("src.accounts.openai_subscription.usage_ssl_context", return_value=polluted):
                failed = _default_usage_get(url, "synthetic-access", "synthetic-account", 2)
            with windows_roots() as enumerated:
                context = openai_tls.usage_ssl_context()
                with patch("src.accounts.openai_subscription.usage_ssl_context", return_value=context):
                    repaired = _default_usage_get(url, "synthetic-access", "synthetic-account", 2)

        self.assertEqual((False, "tls_certificate_failure", 10, "certificate_expired"),
                         (failed.succeeded, failed.transport_category, failed.tls_verify_code, failed.tls_verify_category))
        self.assertEqual((True, 200, PAYLOAD), (repaired.succeeded, repaired.status_code, repaired.payload))
        self.assertEqual(ssl.CERT_REQUIRED, context.verify_mode)
        self.assertTrue(context.check_hostname)
        self.assertEqual(polluted.verify_flags, context.verify_flags)
        enumerated.assert_called_once_with("ROOT")

    def test_repair_still_rejects_expired_leaf_and_wrong_hostname(self):
        for certificate, wrong_host, code in (("expired-server.pem", False, 10), ("server.pem", True, 64)):
            with self.subTest(certificate=certificate, wrong_host=wrong_host), windows_roots(), \
                    tls_server(certificate) as url, patch.dict("os.environ", {"NO_PROXY": "localhost,127.0.0.1"}):
                result = _default_usage_get(url.replace("localhost", "127.0.0.1") if wrong_host else url,
                                            "synthetic-access", "synthetic-account", 2)
                self.assertFalse(result.succeeded)
                self.assertEqual("tls_certificate_failure", result.transport_category)
                self.assertEqual(code, result.tls_verify_code)

    def test_repair_still_rejects_untrusted_chain(self):
        with windows_roots("unrelated-root.pem"), tls_server() as url, \
                patch.dict("os.environ", {"NO_PROXY": "localhost,127.0.0.1"}):
            result = _default_usage_get(url, "synthetic-access", "synthetic-account", 2)
        self.assertFalse(result.succeeded)
        self.assertEqual("tls_certificate_failure", result.transport_category)
        self.assertEqual("certificate_untrusted", result.tls_verify_category)

    def test_no_windows_roots_fails_closed_before_request_without_default_store_fallback(self):
        with patch.object(openai_tls, "sys", SimpleNamespace(platform="win32")), \
                patch.object(ssl, "enum_certificates", return_value=[], create=True), \
                patch.object(ssl, "create_default_context") as default, patch("urllib.request.urlopen") as get:
            result = _default_usage_get(USAGE_URL, "synthetic-access", "synthetic-account", 2)
        self.assertFalse(result.succeeded)
        self.assertEqual("tls_certificate_failure", result.transport_category)
        default.assert_not_called()
        get.assert_not_called()

    def test_non_windows_keeps_platform_defaults_and_windows_preserves_explicit_ca_paths(self):
        with patch.object(openai_tls, "sys", SimpleNamespace(platform="darwin")), \
                patch.object(ssl, "create_default_context") as default:
            self.assertIs(default.return_value, openai_tls.usage_ssl_context())
            default.assert_called_once_with()
        with windows_roots(), patch.object(ssl, "create_default_context") as default:
            context = openai_tls.usage_ssl_context()
            context.set_default_verify_paths.assert_called_once_with()
            self.assertIn("BEGIN CERTIFICATE", default.call_args.kwargs["cadata"])

    def test_root_inventory_filters_encoding_and_non_server_purposes(self):
        root = ssl.PEM_cert_to_DER_cert((FIXTURE / "root.pem").read_text())
        entries = [(b"PRIVATE", "pkcs_7_asn", True), (b"PRIVATE", "x509_asn", {"client-only"}),
                   (root, "x509_asn", {ssl.Purpose.SERVER_AUTH.oid})]
        with patch.object(openai_tls, "sys", SimpleNamespace(platform="win32")), \
                patch.object(ssl, "enum_certificates", return_value=entries, create=True), \
                patch.object(ssl, "create_default_context", wraps=ssl.create_default_context) as default:
            context = openai_tls.usage_ssl_context()
        self.assertNotIn("PRIVATE", default.call_args.kwargs["cadata"])
        self.assertTrue(context.check_hostname)

    def test_real_transport_exceptions_survive_normalization_diagnostics_and_both_renderers(self):
        cases = ((urllib.error.URLError(certificate_error()), "tls_certificate_failure", "certificate verification failed"),
                 (certificate_error(62), "tls_certificate_failure", "certificate verification failed"),
                 (urllib.error.URLError(socket.gaierror(-2, "PRIVATE")), "dns_failure", "name lookup failed"),
                 (urllib.error.URLError(ConnectionRefusedError("PRIVATE")), "connection_failure", "connection failed"),
                 (urllib.error.URLError(TimeoutError("PRIVATE")), "timeout", "timed out"),
                 (TimeoutError("PRIVATE"), "timeout", "timed out"),
                 (urllib.error.URLError(ssl.SSLError("PRIVATE")), "tls_failure", "secure connection failed"),
                 (OSError("PRIVATE"), "network_failure", "network unavailable"))
        for error, category, text in cases:
            with self.subTest(category=category), \
                    patch("src.accounts.openai_subscription.usage_ssl_context"), \
                    patch("urllib.request.urlopen", side_effect=error) as get:
                account = self.provider().get_account_snapshots()[0]
            evidence = sanitized_account_observation(account)["quota_shape"]
            self.assertEqual(category, evidence["parser_reason"])
            self.assertEqual(0, evidence["http_status"])
            self.assertFalse(account.quotas)
            self.assertEqual("error", account.availability)
            self.assertEqual("synthetic-account", account.ref.account_id)
            request = get.call_args.args[0]
            self.assertEqual("Bearer synthetic-access", request.get_header("Authorization"))
            self.assertEqual("synthetic-account", request.get_header("Chatgpt-account-id"))
            for output in (report_text(quotas(AccountProjection(account, "OpenAI"))),
                           watch_text(quotas(AccountProjection(account, "OpenAI")), width=120)):
                self.assertIn(text, output)
                self.assertNotIn("PRIVATE", output)
                self.assertNotIn("synthetic-access", output)
            self.assertNotIn("PRIVATE", json.dumps(evidence))
            if category == "tls_certificate_failure":
                self.assertIn(evidence["tls_verify_category"], {"certificate_expired", "hostname_mismatch"})

    def test_tls_export_rejects_arbitrary_categories_and_nonbounded_codes(self):
        with patch("src.accounts.openai_subscription.usage_ssl_context"), \
                patch("urllib.request.urlopen", side_effect=urllib.error.URLError(certificate_error())):
            account = self.provider().get_account_snapshots()[0]
        for code in ("PRIVATE", True, -1, 1000000, None):
            evidence = sanitized_account_observation(replace(account, observations={
                **account.observations, "tls_verify_code": code, "tls_verify_category": "PRIVATE"}))["quota_shape"]
            self.assertNotIn("tls_verify_code", evidence)
            self.assertNotIn("tls_verify_category", evidence)
        self.assertEqual(10, sanitized_account_observation(account)["quota_shape"]["tls_verify_code"])

    def test_http_and_invalid_response_failures_remain_distinct_from_tls(self):
        for status, category in ((401, "auth_failure"), (403, "access_denied"), (429, "rate_limited"), (503, "http_failure")):
            with self.subTest(status=status), patch("src.accounts.openai_subscription.usage_ssl_context"), \
                    patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(USAGE_URL, status, "PRIVATE", {}, None)):
                account = self.provider().get_account_snapshots()[0]
                self.assertEqual((status, category), (account.observations["http_status"], account.observations["parser_reason"]))
                self.assertNotIn("tls_verify_code", account.observations)
        response = Mock(status=200)
        response.read.return_value = b"\xffPRIVATE"
        with patch("src.accounts.openai_subscription.usage_ssl_context"), patch("urllib.request.urlopen") as get:
            get.return_value.__enter__.return_value = response
            account = self.provider().get_account_snapshots()[0]
        self.assertEqual("parser_failure", account.observations["parser_reason"])

    def test_watch_publication_clears_failed_capacity_and_recovers_without_fast_certificate_retries(self):
        clock = [0.0]
        provider, neighbor = self.provider(), Provider("healthy")
        loop = ManualLoop((provider, neighbor), "fixture", clock=lambda: clock[0],
                          wall_ms=lambda: NOW + int(clock[0] * 1000))
        self.addCleanup(loop.close)
        config, selection, service, _ = make_service(str(self.root), MutableSource(), account_provider=provider,
                                                     async_accounts=True, now_ms=NOW)
        service._account_work = loop
        watch = WatchCoordinator(selection=selection, report_service=service, config=config,
                                 clock_ms=loop.wall_ms, monotonic=lambda: clock[0], record_observations=False)
        self.addCleanup(watch.close)
        stream = io.StringIO()
        renderer = WatchRenderer(config, stream=stream, interactive=False, terminal_width=160)
        response = Mock(status=200)
        response.read.return_value = json.dumps(PAYLOAD).encode()
        with patch("src.accounts.openai_subscription.usage_ssl_context"), patch("urllib.request.urlopen") as get:
            get.return_value.__enter__.return_value = response
            for moment, failed in ((0, False), (30, True), (90, False)):
                clock[0] = moment
                get.side_effect = urllib.error.URLError(certificate_error()) if failed else None
                loop.tick()
                wait_for(lambda: loop.engine.refresh[0].completed == moment or
                         any(result[1] == 0 for result in tuple(loop.engine._results.queue)))
                loop.tick()
                projection = watch.initialize().projection if moment == 0 else watch.status_projection()
                stream.seek(0)
                stream.truncate()
                watch._render(renderer, projection)
                account = next(a for a in watch.accounts.snapshots if a.ref.provider_id == "openai")
                if failed:
                    self.assertFalse(account.quotas)
                    self.assertEqual("tls_certificate_failure", account.observations["parser_reason"])
                    self.assertIn("certificate verification failed", stream.getvalue())
                    self.assertEqual(90, loop.engine.refresh[0].due)
                    for second in (31, 35, 40, 60, 89):
                        clock[0] = second
                        loop.tick()
                        if second == 60:
                            wait_for(lambda: loop.engine.refresh[1].completed == second or
                                     any(result[1] == 1 for result in tuple(loop.engine._results.queue)))
                            loop.tick()
                    self.assertEqual(2, get.call_count)
                    self.assertEqual(0, loop.engine.refresh[0].retries)
                else:
                    self.assertEqual((Decimal(".75"), Decimal(".4")), tuple(q.remaining_fraction for q in account.quotas))
                    self.assertIn("25% used", stream.getvalue())
                    self.assertIn("60% used", stream.getvalue())
                    self.assertIn("Reset", stream.getvalue())
                    self.assertNotIn("Quota error", stream.getvalue())
            self.assertEqual(3, get.call_count)
            self.assertGreaterEqual(neighbor.calls, 3)
            self.assertEqual("success", loop.engine.refresh[0].outcome)


if __name__ == "__main__":
    unittest.main()
