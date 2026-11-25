"""Early launcher feedback, Python-independent errors and clean Python handoff."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from development.tests.fixtures.windows_shell import CONSOLE_STUB
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
        self.assertIn("[Console]::IsInputRedirected", text)
        self.assertIn("python_discovery.ps1", text)
        self.assertIn("SetConsoleCtrlHandler([IntPtr]::Zero, $false)", text)
        self.assertIn("$code = $LASTEXITCODE", text)

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
                                  f". '{driver}' -Mode diagnostics\n"
                                  "exit $LASTEXITCODE\n", encoding="utf-8")
                result = subprocess.run([shell, "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(script)],
                                        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=20)
                self.assertEqual(9009, result.returncode)
                self.assertLess(result.stdout.index("Checking requirements"), result.stdout.index("No usable Python"))
                self.assertNotIn("\x1b", result.stdout)
                self.assertNotIn("\r", result.stdout)

    @unittest.skipUnless(sys.platform == "win32", "Windows shell boundary")
    def test_windows_passes_diagnostics_target_and_preserves_exit_code(self):
        for executable in ("pwsh.exe", "powershell.exe"):
            shell = shutil.which(executable)
            if shell is None:
                continue
            with self.subTest(shell=executable), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                good, script = root / "python.ps1", root / "probe.ps1"
                good.write_text("Write-Output ('APP:' + ($args -join ',')); $global:LASTEXITCODE=17\n",
                                encoding="utf-8")
                source = root / 'src'
                source.mkdir()
                shutil.copyfile(ROOT / 'src/windows_launcher.ps1', source / 'windows_launcher.ps1')
                (source / 'python_discovery.ps1').write_text(
                    "function Find-CostGuardPython { return @{Executable='" + str(good).replace("'", "''") + "';Arguments=@()} }\n")
                driver = str(source / 'windows_launcher.ps1').replace("'", "''")
                script.write_text(CONSOLE_STUB + f"\n. '{driver}' -Mode diagnostics\nexit $LASTEXITCODE\n",
                                  encoding="utf-8")
                result = subprocess.run([shell, "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(script)],
                                        capture_output=True, text=True, timeout=20,
                                        creationflags=subprocess.CREATE_NO_WINDOW)
                self.assertEqual(17, result.returncode, result.stderr)
                self.assertIn(r"APP:development\tools\collect_diagnostics.py", result.stdout.splitlines())


if __name__ == "__main__":
    unittest.main()
