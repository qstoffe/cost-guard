"""Watch intentional stops versus terminal failures, and Windows shell ownership."""
from contextlib import contextmanager
from dataclasses import replace
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from development.tests.test_step8_watch import MutableSource, make_service
from development.tests.test_watch_source_recovery import Recorder
from src import bootstrap
from src.sources.errors import SourceDataError, SourceSchemaError
from src.watch import WatchCoordinator
from src.watch.coordinator import WatchedSessionEnded

ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def watch_for(*, scoped=False):
    with tempfile.TemporaryDirectory() as td:
        source = MutableSource()
        config, selection, service, _ = make_service(td, source)
        watch = WatchCoordinator(selection=selection, report_service=service, config=config,
                                 session_id="root" if scoped else None, clock_ms=lambda: 2200)
        yield watch, source


def bootstrap_watch(watch):
    """Use the real Watch loop with only composition wired to local fixtures."""
    output = io.StringIO()
    with mock.patch.object(bootstrap, "_select_source", return_value=watch.selection), \
         mock.patch.object(bootstrap, "WatchCoordinator", return_value=watch), \
         mock.patch.object(bootstrap, "ReportService", return_value=watch.report_service), \
         mock.patch.object(bootstrap, "CacheDatabase"), mock.patch.object(bootstrap, "CacheRepository"), \
         mock.patch.object(bootstrap, "GitHubCopilotPricingProvider"), \
         mock.patch.object(bootstrap, "_account_providers", return_value=()), \
         mock.patch("sys.stdout", output):
        code = bootstrap.main(["--watch"])
    return code, output.getvalue()


class WatchLifecycleTests(unittest.TestCase):
    def test_unexpected_errors_reach_bootstrap_as_nonzero(self):
        for scoped in (False, True):
            errors = (ValueError("unexpected projection failure"), RuntimeError("unexpected"),
                      OSError("unexpected"), SourceSchemaError("unsupported"),
                      ValueError("OpenCode session 'root' was not found or is archived."))
            for error in errors:
                with self.subTest(scoped=scoped, error=type(error).__name__), watch_for(scoped=scoped) as (watch, _):
                    with mock.patch.object(watch, "_advance", side_effect=error):
                        code, output = bootstrap_watch(watch)
                    self.assertEqual(1, code)
                    self.assertIn("Cost Guard - Runtime error", output)
                    self.assertIn(str(error), output)

    def test_global_watch_does_not_swallow_a_scoped_lifecycle_exception(self):
        with watch_for() as (watch, _):
            with mock.patch.object(watch, "_advance", side_effect=WatchedSessionEnded("not a scoped Watch")):
                code, output = bootstrap_watch(watch)
        self.assertEqual(1, code)
        self.assertIn("Runtime error", output)

    def test_terminal_errors_propagate_and_cleanup_event_pump(self):
        errors = (ValueError("unexpected"), RuntimeError("unexpected"), OSError("unexpected"),
                  SourceSchemaError("unsupported"), SourceDataError("terminal unreadable"))
        for error in errors:
            with self.subTest(error=type(error).__name__), watch_for() as (watch, _):
                initial = watch.initialize()
                pump = mock.Mock()
                watch._event_pump = pump
                renderer = Recorder()
                with mock.patch.object(watch, "_advance", side_effect=error):
                    with self.assertRaises(type(error)) as raised:
                        watch.run_forever(renderer, initial_cycle=initial)
                self.assertIs(error, raised.exception)
                pump.stop.assert_called_once()

    def test_ctrl_c_is_a_clean_watch_stop_and_releases_pump(self):
        with watch_for() as (watch, _):
            initial = watch.initialize()
            watch._event_pump = mock.Mock()
            renderer = Recorder()
            with mock.patch.object(watch, "_advance", side_effect=KeyboardInterrupt):
                watch.run_forever(renderer, initial_cycle=initial)
            self.assertEqual(["Watch stopped."], renderer.finished)
            watch._event_pump.stop.assert_called_once()
            with mock.patch.object(watch, "_advance", side_effect=KeyboardInterrupt):
                code, output = bootstrap_watch(watch)
            self.assertEqual(0, code)
            self.assertIn("Watch stopped.", output)
            self.assertNotIn("Runtime error", output)

    def test_ctrl_c_during_watch_initialization_is_also_intentional(self):
        with watch_for() as (watch, _), mock.patch.object(watch, "initialize", side_effect=KeyboardInterrupt):
            code, output = bootstrap_watch(watch)
        self.assertEqual(0, code)
        self.assertIn("Watch stopped.", output)
        self.assertNotIn("Runtime error", output)

    def test_scoped_session_disappears_or_archives_nonfatally_after_start(self):
        for archived in (False, True):
            with self.subTest(archived=archived), watch_for(scoped=True) as (watch, source):
                initial = watch.initialize()
                sessions = tuple(replace(item, archived_at_ms=2250) if item.session_id == "root" else item
                                 for item in source.snapshot.sessions) if archived else ()
                source.snapshot = replace(source.snapshot, sessions=sessions, source_revision="gone")
                renderer = Recorder()
                with mock.patch.object(watch, "_v1_wait"):
                    watch.run_forever(renderer, initial_cycle=initial)
                self.assertEqual(1, len(renderer.finished))
                self.assertIn("not found or is archived", renderer.finished[0])

    def test_initial_invalid_scoped_selection_still_fails(self):
        with watch_for(scoped=True) as (watch, source):
            source.snapshot = replace(source.snapshot, sessions=())
            code, output = bootstrap_watch(watch)
        self.assertEqual(1, code)
        self.assertIn("not found or is archived", output)


class WindowsShellContractTests(unittest.TestCase):
    def test_all_launchers_share_persistent_same_console_handoff(self):
        launchers = {
            "windows/Cost Guard.cmd": "report",
            "windows/Cost Guard Watch.cmd": "watch",
            "development/windows/Cost Guard Diagnostics.cmd": "diagnostics",
        }
        for name, mode in launchers.items():
            with self.subTest(launcher=name):
                text = (ROOT / name).read_text(encoding="utf-8")
                self.assertIn('/b powershell.exe -NoLogo -NoProfile -NoExit', text)
                self.assertIn('src\\windows_launcher.ps1" -Mode ' + mode, text)
                self.assertIn("exit /b 0", text)
                self.assertNotIn("call :detect_python", text, "Python probes belong after batch handoff")
                self.assertNotIn("pause", text)
                self.assertNotIn("Read-Host", text)
        driver = (ROOT / "src/windows_launcher.ps1").read_text(encoding="utf-8")
        self.assertIn("SetConsoleCtrlHandler([IntPtr]::Zero, $false)", driver,
                      "start /b inherits ignored Ctrl+C; explicitly enable it before Python")
        self.assertIn("sys.version_info >= (3,11)", driver)
        self.assertIn("Install Python 3.11+", driver)
        self.assertIn("$global:LASTEXITCODE = $code", driver)
        self.assertNotIn("Read-Host", driver)
        self.assertNotRegex(driver, r"(?m)^\s*exit\b")


if __name__ == "__main__":
    unittest.main()
