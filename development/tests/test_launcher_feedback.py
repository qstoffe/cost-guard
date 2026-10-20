"""Early launcher feedback, Python-independent errors and clean Python handoff."""
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.launcher_feedback import release_launcher_status
from src.presentation.progress import StartupProgress

ROOT = Path(__file__).resolve().parents[2]


class LauncherFeedbackTests(unittest.TestCase):
    def test_windows_wrappers_write_before_shell_detection_without_new_process(self):
        for filename in ("Cost Guard.cmd", "Cost Guard Watch.cmd"):
            text = (ROOT / "windows" / filename).read_text(encoding="utf-8")
            self.assertLess(text.index("Checking requirements..."), text.index("where pwsh.exe"))
            self.assertIn('<nul set /p "=Cost Guard:', text)
            self.assertEqual(1, text.count("start \""))
            self.assertNotIn("timeout", text.lower())

    def test_powershell_feedback_precedes_console_init_and_python_checks(self):
        text = (ROOT / "src/windows_launcher.ps1").read_text(encoding="utf-8")
        feedback = text.index("Write-Host -NoNewline 'Cost Guard: Checking requirements...'")
        self.assertLess(feedback, text.index("Add-Type -TypeDefinition"))
        self.assertLess(feedback, text.index("Get-Command $candidate.Name"))
        self.assertIn("[Console]::IsOutputRedirected", text)
        self.assertIn("$tested.Add($application.Source)", text)
        self.assertIn("SetConsoleCtrlHandler([IntPtr]::Zero, $false)", text)
        self.assertIn("$code = $LASTEXITCODE", text)

    def test_macos_feedback_precedes_root_resolution_and_python_checks(self):
        for filename in ("Cost Guard.command", "Cost Guard Watch.command"):
            text = (ROOT / "macos" / filename).read_text(encoding="utf-8")
            self.assertLess(text.index("Checking requirements..."), text.index("CG_ROOT="))
            self.assertLess(text.index("Checking requirements..."), text.index("find_python()"))
            self.assertIn("[[ -t 1 ]]", text)
            self.assertIn("COST_GUARD_LAUNCHER_STATUS=1", text)
            self.assertIn("sys.version_info >= (3,11)", text)
            self.assertIn("${tested[$executable]-}", text)
            self.assertIn("could not find Python 3.11", text)
            self.assertNotIn("sleep ", text)

    def test_python_handoff_consumes_one_row_once_without_ansi_or_newline(self):
        output = io.StringIO()
        output.isatty = lambda: True
        with patch.dict(os.environ, COST_GUARD_LAUNCHER_STATUS="1"), patch.object(sys, "stdout", output):
            release_launcher_status()
            first = output.getvalue()
            release_launcher_status()
        self.assertEqual("\r" + " " * 40 + "\r", first)
        self.assertEqual(first, output.getvalue())

    def test_redirected_handoff_adds_no_controls_and_progress_keeps_stage(self):
        output = io.StringIO()
        with patch.dict(os.environ, COST_GUARD_LAUNCHER_STATUS="1"), patch.object(sys, "stdout", output):
            progress = StartupProgress(output, interactive=False)
            progress.update("Selecting OpenCode source")
            progress.stop()
        self.assertEqual("Cost Guard: Selecting OpenCode source\n", output.getvalue())

    @unittest.skipUnless(sys.platform == "win32", "Windows shell boundary")
    def test_windows_missing_python_is_clear_in_both_shells_without_starting_app(self):
        for executable in ("pwsh.exe", "powershell.exe"):
            shell = shutil.which(executable)
            if shell is None:
                continue
            with self.subTest(shell=executable), tempfile.TemporaryDirectory() as temporary:
                script = Path(temporary) / "probe.ps1"
                driver = str(ROOT / "src/windows_launcher.ps1").replace("'", "''")
                script.write_text("function Get-Command { return @() }\n"
                                  f". '{driver}' -Mode report\n"
                                  "exit $LASTEXITCODE\n", encoding="utf-8")
                result = subprocess.run([shell, "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(script)],
                                        capture_output=True, text=True, timeout=20)
                self.assertEqual(9009, result.returncode)
                self.assertLess(result.stdout.index("Checking requirements"), result.stdout.index("could not find Python"))
                self.assertNotIn("\x1b", result.stdout)
                self.assertNotIn("\r", result.stdout)

    @unittest.skipUnless(sys.platform == "win32", "Windows shell boundary")
    def test_windows_skips_duplicate_failures_finds_next_python_and_preserves_mode_exit(self):
        for executable in ("pwsh.exe", "powershell.exe"):
            shell = shutil.which(executable)
            if shell is None:
                continue
            for mode, argument in (("report", "cost-guard.py"), ("watch", "--watch"),
                                   ("diagnostics", "--test-service-start")):
                with self.subTest(shell=executable, mode=mode), tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    bad, good, script = (root / name for name in ("bad.ps1", "good.ps1", "probe.ps1"))
                    bad.write_text("$global:Probes++; $global:LASTEXITCODE=1\n", encoding="utf-8")
                    good.write_text("if ($args -contains '-c') { $global:Probes++; $global:LASTEXITCODE=0 } "
                                    "else { Write-Output ('APP:' + ($args -join ',')); $global:LASTEXITCODE=17 }\n",
                                    encoding="utf-8")
                    driver = str(ROOT / "src/windows_launcher.ps1").replace("'", "''")
                    sources = [str(path).replace("'", "''") for path in (bad, bad, good)]
                    choices = ",".join("[pscustomobject]@{Source='" + path + "'}" for path in sources)
                    script.write_text(f"$global:Probes=0\nfunction Get-Command {{ return @({choices}) }}\n"
                                      f". '{driver}' -Mode {mode}\n"
                                      "Write-Output ('PROBES:' + $global:Probes)\nexit $LASTEXITCODE\n", encoding="utf-8")
                    result = subprocess.run([shell, "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(script)],
                                            capture_output=True, text=True, timeout=20)
                    self.assertEqual(17, result.returncode, result.stderr)
                    self.assertIn("PROBES:2", result.stdout)
                    self.assertIn(argument, result.stdout)
                    self.assertNotIn("\x1b", result.stdout)


if __name__ == "__main__":
    unittest.main()
