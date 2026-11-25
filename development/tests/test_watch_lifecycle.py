"""Watch intentional stops versus terminal failures, and Windows shell ownership."""
from pathlib import Path
import unittest
from unittest import mock

from development.tests.fixtures.watch_runtime import Recorder, watch_for
from src.sources.errors import SourceDataError, SourceSchemaError

ROOT = Path(__file__).resolve().parents[2]


class WatchLifecycleTests(unittest.TestCase):
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


class WindowsShellContractTests(unittest.TestCase):
    def test_all_launchers_use_persistent_separate_console_handoff(self):
        launchers = {
            "development/user-tools/diagnostics/windows/Cost-Guard-Diagnostics.cmd": "diagnostics",
        }
        for name, mode in launchers.items():
            with self.subTest(launcher=name):
                text = (ROOT / name).read_text(encoding="utf-8")
                self.assertIn('%costguard_shell% -NoLogo -NoProfile -NoExit', text)
                self.assertNotIn('/b %costguard_shell%', text)
                self.assertIn('src\\windows_launcher.ps1" -Mode ' + mode, text)
                self.assertIn("exit /b %errorlevel%", text)
                self.assertNotIn("call :detect_python", text, "Python probes belong after batch handoff")
                self.assertNotIn("pause", text)
                self.assertNotIn("Read-Host", text)
        driver = (ROOT / "src/windows_launcher.ps1").read_text(encoding="utf-8")
        self.assertIn("SetConsoleCtrlHandler([IntPtr]::Zero, $false)", driver,
                      "explicitly enable Ctrl+C before Python, including legacy direct callers")
        self.assertIn("Find-CostGuardPython", driver)
        self.assertIn("Get-CostGuardPythonFailure", driver)
        self.assertIn("$global:LASTEXITCODE = $code", driver)
        self.assertNotIn("Read-Host", driver)
        self.assertNotRegex(driver, r"(?m)^\s*exit\b")


if __name__ == "__main__":
    unittest.main()
