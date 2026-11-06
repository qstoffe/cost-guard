"""Host-only bounded wake, independently proven readiness and process-free retries."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import os
import subprocess
import tempfile
from threading import Event
import unittest
from unittest.mock import Mock, patch

from development.tests.fixtures.opencode_v2_service import FakeV2Service, fixture
from src import opencode_service
from src.config import ConfigError
from src.sources.errors import FailureCode, SourceUnavailableError
from src.sources.opencode_v2 import OpenCodeV2Source
from src.sources.read_recovery import ReadRecovery
from src.sources.selection import SourceSelector
from src.web import source_startup
from src.web.source_startup import SourceStartup


def unavailable(code=FailureCode.REFUSED, **kwargs):
    return SourceUnavailableError("private failure", code=code, generation="v2", **kwargs)


class SourceStartupTests(unittest.TestCase):
    def setUp(self):
        self.publish = Mock()
        self.stopping = Event()
        self.startup = SourceStartup(Path("."), self.publish, self.stopping)
        self.selector = Mock()
        self.config = self.enterContext(patch.object(source_startup, "load_configuration",
            return_value=Mock(values={"openCode": {"source": "auto"}})))
        self.enterContext(patch.object(source_startup, "SourceSelector", return_value=self.selector))
        self.find = self.enterContext(patch.object(source_startup, "find_opencode_executable", return_value="opencode"))
        self.wake = self.enterContext(patch.object(source_startup, "wake_cli_service"))
        self.waits = []
        self.enterContext(patch.object(source_startup, "ReadRecovery",
            side_effect=lambda **_: ReadRecovery(sleep=self.waits.append)))

    def test_healthy_v2_and_auto_v1_preserve_selection_without_wake_or_wait(self):
        for generation in ("v2", "v1"):
            with self.subTest(generation=generation):
                startup = SourceStartup(Path("."), self.publish, self.stopping)
                selection = Mock(selected=generation)
                self.selector.select.return_value = selection
                self.assertIs(selection, startup.prepare())
                self.assertTrue(startup.finished.is_set())
        self.find.assert_not_called()
        self.wake.assert_not_called()
        self.publish.assert_not_called()
        self.assertEqual([], self.waits)

    def test_one_wake_and_fresh_probes_recover_without_manual_refresh(self):
        self.assertEqual({'ready': False, 'error': 'source_starting', 'retryable': True}, self.startup.report_status())
        selection = Mock(selected="v2")
        self.selector.select.side_effect = [unavailable(), unavailable(), selection]
        self.assertIs(selection, self.startup.prepare())
        self.assertIsNone(self.startup.prepare())
        self.wake.assert_called_once_with("opencode", timeout=5)
        self.assertEqual(3, self.selector.select.call_count)
        self.assertEqual([0.5, 0.5], self.waits)
        self.assertEqual({'ready': True, 'error': None, 'retryable': False}, self.startup.report_status())
        self.assertEqual(["starting_opencode", "starting"], [c.args[1]["state"] for c in self.publish.call_args_list])

    def test_exit_success_is_not_readiness_and_failure_ends_starting(self):
        self.selector.select.side_effect = unavailable()
        with self.assertRaises(SourceUnavailableError):
            self.startup.prepare()
        self.assertTrue(self.startup.finished.is_set())
        self.assertEqual(3, self.selector.select.call_count)
        self.assertEqual("starting", self.publish.call_args.args[1]["state"])
        self.assertIsNone(self.startup.prepare())
        self.wake.assert_called_once()

    def test_failed_or_timed_out_cli_still_requires_actual_health_proof(self):
        self.wake.side_effect = unavailable()
        selection = Mock(selected="v2")
        self.selector.select.side_effect = [unavailable(), selection]
        self.assertIs(selection, self.startup.prepare())
        self.assertEqual(2, self.selector.select.call_count)

    def test_ineligible_failures_never_launch_or_retry(self):
        cases = [("v1", unavailable()), ("v2", unavailable(FailureCode.REGISTRATION_INVALID)),
            ("auto", unavailable(FailureCode.REGISTRATION_UNREADABLE)),
            ("v2", unavailable(FailureCode.AUTH)), ("v2", unavailable(FailureCode.SCHEMA)),
            ("v2", unavailable(FailureCode.VERSION)), ("v2", unavailable(FailureCode.HTTP, http_status=503)),
            ("v2", unavailable(FailureCode.ENDPOINT_UNRESPONSIVE, exception_type="PermissionError"))]
        for mode, error in cases:
            with self.subTest(mode=mode, code=error.code):
                startup = SourceStartup(Path("."), self.publish, self.stopping)
                self.config.return_value.values = {"openCode": {"source": mode}}
                self.selector.select.side_effect = error
                with self.assertRaises(SourceUnavailableError):
                    startup.prepare()
                self.assertTrue(startup.finished.is_set())
                status = startup.report_status()
                self.assertFalse(status['ready'])
                self.assertEqual('source_permission_denied' if error.exception_type == 'PermissionError' else error.code.value,
                    status['error'])
                if error.exception_type == 'PermissionError':
                    self.assertFalse(status['retryable'])
        self.wake.assert_not_called()
        self.find.assert_not_called()
        self.assertEqual([], self.waits)

    def test_configuration_validation_precedes_all_source_and_process_work(self):
        self.config.side_effect = ConfigError("invalid configuration")
        with self.assertRaises(ConfigError):
            self.startup.prepare()
        self.selector.select.assert_not_called()
        self.find.assert_not_called()
        self.wake.assert_not_called()

    def test_missing_executable_and_stopping_are_process_free(self):
        self.selector.select.side_effect = unavailable()
        self.find.return_value = None
        with self.assertRaises(SourceUnavailableError):
            self.startup.prepare()
        self.stopping.set()
        with self.assertRaises(SourceUnavailableError):
            SourceStartup(Path("."), self.publish, self.stopping).prepare()
        self.wake.assert_not_called()
        self.publish.assert_not_called()

    def test_concurrent_entries_and_later_live_recovery_never_repeat_wake(self):
        entered, release = Event(), Event()
        def wake(*args, **kwargs):
            entered.set()
            if not release.wait(2):
                raise RuntimeError("test_gate_timeout")
        self.wake.side_effect = wake
        selected = Mock(selected="v2")
        self.selector.select.side_effect = [unavailable(), selected]
        with ThreadPoolExecutor(max_workers=3) as workers:
            first = workers.submit(self.startup.prepare)
            try:
                self.assertTrue(entered.wait(1))
                self.assertFalse(self.startup.finished.is_set())
                others = [workers.submit(self.startup.prepare) for _ in range(2)]
            finally:
                release.set()
            self.assertIs(selected, first.result(timeout=2))
            self.assertEqual([None, None], [future.result(timeout=2) for future in others])
        with patch("src.web.composition.live_acquisition") as acquire:
            self.startup.acquire()
            acquire.assert_called_once_with(selection=None)
        self.wake.assert_called_once()

    def test_real_registration_and_authenticated_api_are_reprobed_after_wake(self):
        with tempfile.TemporaryDirectory() as td, FakeV2Service(fixture()) as service:
            registration = Path(td) / "service.json"
            selector = SourceSelector(inspect_migration_gap=False,
                v2_factory=lambda: OpenCodeV2Source(registration, timeout_seconds=0.2))
            self.config.return_value.values = {"openCode": {"source": "v2"}}
            def wake(*args, **kwargs):
                registration.write_text(json.dumps({"url": service.url, "pid": 4242,
                    "password": "secret"}), encoding="utf-8")
            self.wake.side_effect = wake
            with patch.object(source_startup, "SourceSelector", return_value=selector):
                selection = self.startup.prepare()
            self.addCleanup(selection.source.close_reads)
            self.assertEqual("v2", selection.selected)
            self.assertTrue(selection.selected_health.healthy)
            self.assertEqual(["/api/info"], [path for path, _ in service.requests])
            self.wake.assert_called_once()


class WakeProcessTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows batch argument parsing")
    def test_real_hidden_batch_shim_with_spaces_and_unicode(self):
        with tempfile.TemporaryDirectory(prefix="wake space å ") as td:
            shim = Path(td) / "opencode.cmd"
            shim.write_text('@echo off\nif not "%1 %2 %3"=="api get /api/info" exit /b 2\nexit /b 0\n', encoding="utf-8")
            opencode_service.wake_cli_service(str(shim), timeout=2)

    def test_native_command_is_bounded_silent_and_hidden_on_windows(self):
        for system in ("nt", "posix"):
            with self.subTest(system=system), patch.object(opencode_service.os, "name", system), \
                 patch.object(opencode_service.subprocess, "CREATE_NO_WINDOW", 0x08000000, create=True), \
                 patch.object(opencode_service.subprocess, "run", return_value=Mock(returncode=0)) as run:
                opencode_service.wake_cli_service("/installed/opencode", timeout=5)
                self.assertEqual(["/installed/opencode", "api", "get", "/api/info"], run.call_args.args[0])
                options = run.call_args.kwargs
                self.assertEqual(5, options["timeout"])
                self.assertEqual(subprocess.DEVNULL, options["stdin"])
                self.assertEqual(subprocess.DEVNULL, options["stdout"])
                self.assertEqual(subprocess.DEVNULL, options["stderr"])
                self.assertFalse(options.get("shell", False))
                self.assertEqual(0x08000000 if system == "nt" else None, options.get("creationflags"))

    def test_process_failures_have_sanitized_bounded_fallback(self):
        for error in (OSError("private"), subprocess.TimeoutExpired("private", 5)):
            with self.subTest(error=type(error).__name__), \
                 patch.object(opencode_service.subprocess, "run", side_effect=error):
                with self.assertRaises(SourceUnavailableError) as failure:
                    opencode_service.wake_cli_service("opencode", timeout=5)
                self.assertNotIn("private", str(failure.exception))

    def test_batch_install_paths_never_interpret_expansion_or_operators(self):
        for character in '&|<>^%!"\r\n':
            with self.subTest(character=character), patch.object(opencode_service.subprocess, "run") as run:
                with self.assertRaises(SourceUnavailableError):
                    opencode_service.wake_cli_service(f"C:/tools{character}/opencode.cmd")
                run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
