"""Static regression checks for Windows launchers (runnable without Windows)."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class WindowsLauncherTests(unittest.TestCase):
    def test_python_probe_handles_multiple_matches_and_requires_python_311(self):
        text = (ROOT / "src/windows_launcher.ps1").read_text(encoding="utf-8")
        self.assertIn("Get-Command $candidate.Name -All -CommandType Application", text)
        self.assertIn("foreach ($application in @(", text)
        self.assertIn("& $application.Source @arguments -c", text)
        self.assertIn("sys.version_info >= (3,11)", text)
        self.assertIn("if ($python) { break }", text)
        self.assertIn("if ($LASTEXITCODE -eq 0)", text)
        self.assertIn("if (-not $python)", text)

    def test_all_windows_entrypoints_select_shell_with_fallback(self):
        for path in ("windows/Cost Guard.cmd", "windows/Cost Guard Watch.cmd",
                     "development/user-tools/diagnostics/windows/Cost Guard Diagnostics.cmd"):
            with self.subTest(path=path):
                text = (ROOT / path).read_text(encoding="utf-8")
                self.assertIn("where pwsh.exe >nul 2>nul", text)
                self.assertIn('set "costguard_shell=pwsh.exe"', text)
                self.assertIn('set "costguard_shell=powershell.exe"', text)
                start = next(line for line in text.splitlines() if line.startswith('start "'))
                self.assertIn(" %costguard_shell% ", start)
                self.assertNotIn(" /b ", start.lower())
                self.assertNotIn(" /wait ", start.lower())
                self.assertNotIn("Checking requirements", text)
                self.assertNotIn("COST_GUARD_LAUNCHER_STATUS", text)
                self.assertIn("exit /b %errorlevel%", text)
                self.assertIn("-NoExit -ExecutionPolicy Bypass", text)


if __name__ == "__main__":
    unittest.main()
