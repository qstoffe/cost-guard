"""Privacy-safe persisted Web facts and read-only Diagnostics integration."""
import json
from http.cookiejar import CookieJar
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.request import build_opener, HTTPCookieProcessor, Request

from development.tools.diagnostic_web import web_evidence
from src.web.host import WebHost
from src.web.instance_state import InstanceStore
from src.web.jobs import ReportJobs


class WebDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve() / "checkout"
        self.root.mkdir()
        self.home = Path(self.tmp.name).resolve() / "data"
        self.store = InstanceStore(self.root, data_home=self.home)
        self.host = WebHost(self.root, store=self.store, jobs=ReportJobs())
        self.addCleanup(self.host.close)

    def evidence(self):
        return web_evidence(self.root, data_home=self.home)

    def test_missing_is_not_success_and_collection_never_creates_files(self):
        before = set(self.store.directory.iterdir())
        self.assertEqual("not_observed", self.evidence()["status"])
        self.assertEqual(before, set(self.store.directory.iterdir()))

    def test_real_http_cookie_jar_keeps_both_checkouts_authorized(self):
        other_root = Path(self.tmp.name) / "other"
        other_root.mkdir()
        other = WebHost(other_root, jobs=ReportJobs())
        self.addCleanup(other.close)
        self.host.start()
        other.start()
        jar = CookieJar()
        browser = build_opener(HTTPCookieProcessor(jar))
        for host in (self.host, other):
            origin = host.server.origin
            body = json.dumps({"credential": host.server.session.bootstrap()}).encode()
            request = Request(origin + "/api/bootstrap", data=body,
                              headers={"Origin": origin, "Content-Type": "application/json"})
            with browser.open(request, timeout=3) as response:
                self.assertEqual(200, response.status)
        self.assertEqual(2, len(jar))
        for host in (self.host, other):
            with browser.open(host.server.origin + "/api/status", timeout=3) as response:
                self.assertEqual(200, response.status)
                self.assertNotIn(host.control, response.read().decode())

    def test_bounded_counters_source_failure_and_shutdown_survive_state_cleanup(self):
        for status in (401, 403, 400, 429, 503, 200):
            self.host.observations.response(status)
        self.host.events.publish("live", {"state": "source_unavailable", "view": "PRIVATE_PROMPT"})
        self.host.observations.persist(self.host)
        first = self.evidence()
        self.assertEqual("recorded", first["status"])
        self.assertEqual({"denied": 2, "invalid": 1, "busy": 1, "unavailable": 1},
                         first["snapshot"]["api_failures"])
        self.assertEqual("source_unavailable", first["snapshot"]["source_status"])
        self.host.close()
        self.assertEqual("menu", self.evidence()["snapshot"]["state"])
        self.assertFalse(self.store.state_path.exists())
        self.assertNotIn("PRIVATE", json.dumps(self.evidence()))
        self.assertNotIn(self.host.control, json.dumps(self.evidence()))
        self.assertNotIn(self.host.nonce, json.dumps(self.evidence()))

    def test_untrusted_log_and_snapshot_fields_are_not_exported(self):
        self.host.observations.persist(self.host)
        path = self.store.directory / "diagnostics.json"
        value = json.loads(path.read_bytes())
        value["prompt"] = "PRIVATE_PROMPT"
        path.write_text(json.dumps(value))
        (self.store.directory / "lifecycle.log").write_text("1 browser_open_failed\n2 PRIVATE_SECRET\n")
        result = self.evidence()
        self.assertEqual({"browser_open_failed": 1}, result["lifecycle_codes"])
        self.assertNotIn("PRIVATE", json.dumps(result))
        value["state"] = "PRIVATE_EXCEPTION"
        path.write_text(json.dumps(value))
        self.assertEqual("unavailable", self.evidence()["status"])
        path.write_bytes(b"x" * 4097)
        self.assertEqual("unavailable", self.evidence()["status"])

    def test_persistence_failure_is_explicit_without_breaking_shutdown(self):
        with patch.object(self.store, "write_diagnostics", side_effect=OSError("PRIVATE")):
            self.host.observations.persist(self.host, final=True)
            self.assertEqual("unavailable", self.host.public_status()["diagnostics"])
            self.host.close()
        self.assertEqual("not_observed", self.evidence()["status"])


if __name__ == "__main__":
    unittest.main()
