"""Privacy-safe persisted Web facts and read-only Diagnostics integration."""
import json
import io
from contextlib import redirect_stdout
from http.cookiejar import CookieJar
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.request import build_opener, HTTPCookieProcessor, Request
from zipfile import ZipFile

from development.tools import collect_diagnostics, diagnostic_web_dependencies
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

    def test_ordinary_bundle_retains_safe_private_error_when_config_unreadable(self):
        log = self.store.directory / "logs/errors/cost-guard-errors-2026-10-01.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text("Timestamp: 2026-10-01T10:00:01+00:00\nMode: Web\n"
                       "Phase: observe\nException: PermissionError\nOS errno: 13\n"
                       "Location: src/web/host.py:10 in maintain\nPRIVATE_EXCEPTION_MESSAGE\n")
        raw = self.root / "development/logs/errors/cost-guard-errors-2026-10-01.log"
        raw.parent.mkdir(parents=True)
        raw.write_text("PRIVATE_RAW_LOG")
        with patch.object(collect_diagnostics, "ROOT", self.root), \
             patch("development.tools.diagnostic_web.private_web_directory", return_value=self.store.directory), \
             patch.object(diagnostic_web_dependencies, "config_evidence", side_effect=PermissionError(13, "PRIVATE_CONFIG")), \
             patch.object(diagnostic_web_dependencies, "local_source", return_value={"probe": {"healthy": False}}), \
             patch("src.sources.connectivity_events.recent_events", return_value=[]), redirect_stdout(io.StringIO()):
            self.assertEqual(0, collect_diagnostics.main([]))
        from src.log_paths import log_root
        with ZipFile(log_root(self.root) / "diagnostics/cost-guard-diagnostics.zip") as archive:
            self.assertEqual({"summary.txt", "diagnostics.json"}, set(archive.namelist()))
            output = archive.read("diagnostics.json")
            self.assertNotIn(b"PRIVATE", output + archive.read("summary.txt"))
            data = json.loads(output)
        self.assertEqual(("unavailable", "configuration_read", 13),
                         tuple(data["config"][key] for key in ("status", "phase", "errno")))
        errors = data["web"]["runtime_errors"]["errors"]
        self.assertEqual("recorded", errors["status"])
        self.assertIn("OS errno: 13", errors["reports"][0])
        self.assertIn("Location: src/web/host.py:10 in maintain", errors["reports"][0])
        self.assertIn("Exception: PermissionError", errors["reports"][0])

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

    def test_startup_cause_and_recovery_export_without_new_host_or_control_record_read(self):
        for reason in ("process_identity_access_denied", "process_identity_unavailable",
                       "instance_lifetime_busy", "instance_transition_busy", "corrupt_instance_state",
                       "unsafe_instance_path", "instance_control_unavailable", "stale_instance_recovered"):
            self.store.log(reason)
            with patch.object(self.store, "read", side_effect=AssertionError("Never read control state")):
                evidence = self.evidence()
            self.assertEqual("not_observed", evidence["status"])
            self.assertIsNone(evidence["snapshot"])
            self.assertEqual(reason, evidence["latest_lifecycle"]["code"])
            self.assertIn(reason, evidence["lifecycle_codes"])
            self.assertFalse(self.store.state_path.exists())

    def test_old_ready_snapshot_does_not_hide_later_startup_failure(self):
        self.host.observations.persist(self.host)
        path = self.store.directory / "diagnostics.json"
        snapshot = json.loads(path.read_bytes())
        snapshot.update(state="ready", observed_at=1)
        path.write_text(json.dumps(snapshot))
        (self.store.directory / "lifecycle.log").write_text(
            "1 ready\n2 process_identity_access_denied\n3 PRIVATE_TOKEN\n"
            + "9" * 100 + " ready\n")
        evidence = self.evidence()
        self.assertEqual("ready", evidence["snapshot"]["state"])
        self.assertGreater(evidence["age_seconds"], 0)
        self.assertEqual({"observed_at": 2, "code": "process_identity_access_denied"},
                         evidence["latest_lifecycle"])
        self.assertTrue(evidence["stale"])
        self.assertEqual("unknown", evidence["host_probe"]["status"])
        self.assertNotIn("PRIVATE", json.dumps(evidence))


if __name__ == "__main__":
    unittest.main()
