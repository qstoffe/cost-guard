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

from development.tests.fixtures.windows_shell import CONSOLE_STUB
from src.launcher_feedback import release_launcher_status
from src.presentation.progress import StartupProgress
from src.web.launch_messages import failure_text

ROOT = Path(__file__).resolve().parents[2]

# Discovery/argument tests do not own cold Roslyn compilation or Win32 Ctrl+C.
# The real console boundary is exercised by the native launcher/Watch probe.
class LauncherFeedbackTests(unittest.TestCase):
    def test_web_failures_separate_outcome_cause_action_and_diagnostics(self):
        reasons = set()
        for platform in ('windows', 'macos'):
            for code in ('tray_unavailable', 'instance_start_timeout', 'configuration_unavailable',
                         'instance_conflict', 'browser_open_failed'):
                with self.subTest(platform=platform, code=code):
                    text = failure_text(code, platform)
                    outcome, reason, action, diagnostics = text.split('\n\n')
                    self.assertEqual('COST GUARD WEB IS RUNNING' if code == 'browser_open_failed'
                                     else 'COST GUARD COULD NOT START', outcome)
                    self.assertTrue(reason.startswith('Reason: '))
                    self.assertTrue(action.startswith('Next step: '))
                    self.assertTrue(diagnostics.startswith('Diagnostics: '))
                    self.assertNotIn('\x1b', text)
                    reasons.add(reason)
        self.assertEqual(6, len(reasons))  # native cause differs by OS, other causes stay shared

    def test_all_eight_launchers_have_whitespace_free_names_without_aliases(self):
        expected = {
            "windows/Legacy": {"Cost-Guard.cmd", "Cost-Guard-Watch.cmd"},
            "windows": {"Cost-Guard-Web.cmd"},
            "macos/Legacy": {"Cost-Guard.command", "Cost-Guard-Watch.command"},
            "macos": {"Cost-Guard-Web.command"},
            "development/user-tools/diagnostics/windows": {"Cost-Guard-Diagnostics.cmd"},
            "development/user-tools/diagnostics/macos": {"Cost-Guard-Diagnostics.command"},
        }
        for folder, names in expected.items():
            with self.subTest(folder=folder):
                actual = {path.name for path in (ROOT / folder).iterdir()
                          if path.suffix in (".cmd", ".command")}
                self.assertEqual(names, actual)
                for name in actual:
                    self.assertFalse(any(character.isspace() for character in name))

    def test_windows_wrappers_leave_feedback_to_the_owned_console(self):
        for filename in ("Cost-Guard.cmd", "Cost-Guard-Watch.cmd"):
            text = (ROOT / "windows/Legacy" / filename).read_text(encoding="utf-8")
            self.assertNotIn("Checking requirements...", text)
            self.assertNotIn('<nul set /p', text)
            self.assertEqual(1, text.count("start \""))
            self.assertNotIn("timeout", text.lower())

    def test_all_macos_launcher_directories_pin_lf_for_windows_source_exports(self):
        attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()
        for pattern in ("macos/*.command", "macos/Legacy/*.command",
                        "development/user-tools/diagnostics/macos/*.command"):
            self.assertIn(pattern + " text eol=lf", attributes)

    def test_powershell_feedback_precedes_console_init_and_python_checks(self):
        text = (ROOT / "src/windows_launcher.ps1").read_text(encoding="utf-8")
        feedback = text.index("Write-Host -NoNewline 'Cost Guard: Checking requirements...'")
        self.assertLess(feedback, text.index("Add-Type -TypeDefinition"))
        self.assertLess(feedback, text.index("Find-CostGuardPython"))
        self.assertIn("[Console]::IsOutputRedirected", text)
        self.assertIn("python_discovery.ps1", text)
        self.assertIn("SetConsoleCtrlHandler([IntPtr]::Zero, $false)", text)
        self.assertIn("$code = $LASTEXITCODE", text)

    def test_macos_feedback_precedes_root_resolution_and_python_checks(self):
        for filename in ("Cost-Guard.command", "Cost-Guard-Watch.command"):
            text = (ROOT / "macos/Legacy" / filename).read_text(encoding="utf-8")
            self.assertLess(text.index("Checking requirements..."), text.index("CG_ROOT="))
            self.assertLess(text.index("Checking requirements..."), text.index("cg_find_python"))
            self.assertIn("[[ -t 1 ]]", text)
            self.assertIn("COST_GUARD_LAUNCHER_STATUS=1", text)
            self.assertIn('source "$CG_ROOT/src/python_discovery.sh"', text)
            self.assertIn("cg_python_failure", text)
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
                source = Path(temporary) / 'src'
                source.mkdir()
                shutil.copyfile(ROOT / 'src/windows_launcher.ps1', source / 'windows_launcher.ps1')
                (source / 'python_discovery.ps1').write_text(
                    "function Find-CostGuardPython { return @{Executable=$null;Failure='missing'} }\n"
                    "function Get-CostGuardPythonFailure { return 'COST GUARD COULD NOT START: No usable Python 3.11+' }\n")
                driver = str(source / 'windows_launcher.ps1').replace("'", "''")
                script.write_text(CONSOLE_STUB + "\n"
                                  f". '{driver}' -Mode report\n"
                                  "exit $LASTEXITCODE\n", encoding="utf-8")
                result = subprocess.run([shell, "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(script)],
                                        capture_output=True, text=True, timeout=20)
                self.assertEqual(9009, result.returncode)
                self.assertLess(result.stdout.index("Checking requirements"), result.stdout.index("No usable Python"))
                self.assertNotIn("\x1b", result.stdout)
                self.assertNotIn("\r", result.stdout)

    @unittest.skipUnless(sys.platform == "win32", "Windows shell boundary")
    def test_windows_skips_duplicate_failures_finds_next_python_and_preserves_mode_exit(self):
        for executable in ("pwsh.exe", "powershell.exe"):
            shell = shutil.which(executable)
            if shell is None:
                continue
            for mode, argument in (("report", "cost-guard-cli.py"), ("watch", "--watch"),
                                   ("diagnostics", "--test-service-start")):
                with self.subTest(shell=executable, mode=mode), tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    bad, good, script = (root / name for name in ("bad.ps1", "good.ps1", "probe.ps1"))
                    bad.write_text("$global:Probes++; $global:LASTEXITCODE=1\n", encoding="utf-8")
                    good.write_text("if ($args -contains '-c') { $global:Probes++; $global:LASTEXITCODE=0 } "
                                    "else { Write-Output ('APP:' + ($args -join ',')); $global:LASTEXITCODE=17 }\n",
                                    encoding="utf-8")
                    source = root / 'src'
                    source.mkdir()
                    shutil.copyfile(ROOT / 'src/windows_launcher.ps1', source / 'windows_launcher.ps1')
                    (source / 'python_discovery.ps1').write_text(
                        "function Find-CostGuardPython { return @{Executable='" + str(good).replace("'", "''") + "';Arguments=@()} }\n")
                    driver = str(source / 'windows_launcher.ps1').replace("'", "''")
                    script.write_text(CONSOLE_STUB + "\n"
                                      f". '{driver}' -Mode {mode}\n"
                                      "exit $LASTEXITCODE\n", encoding="utf-8")
                    result = subprocess.run([shell, "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(script)],
                                            capture_output=True, text=True, timeout=20)
                    self.assertEqual(17, result.returncode, result.stderr)
                    self.assertIn(argument, result.stdout)
                    self.assertNotIn("\x1b", result.stdout)


if __name__ == "__main__":
    unittest.main()
