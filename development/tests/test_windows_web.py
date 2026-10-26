"""Synthetic Windows Beta contracts; no real icon, browser or UI is started."""
import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Event
import unittest
from unittest.mock import Mock, patch

from src.web import windows_launch
from src.web.native_windows import WindowsHost, preflight
from src.web.process_identity import InstanceConflict
from src.web.tray_icon import icon_bits
from src.web.win32_tray import OPEN, EXIT

ROOT = Path(__file__).resolve().parents[2]


class WindowsWebTests(unittest.TestCase):
    def owner(self):
        return Mock(stopping=Event(), stopped=Event())

    def test_original_icon_has_transparent_margin_and_opaque_shield(self):
        mask, pixels = icon_bits()
        self.assertEqual(len(mask), 128)
        self.assertEqual(len(pixels), 4096)
        self.assertIn(255, pixels[3::4])
        self.assertEqual(pixels[:128], bytes(128))

    def test_preflight_failure_releases_native_resources(self):
        tray = Mock()
        tray.install.side_effect = InstanceConflict("tray_unavailable")
        with patch("src.web.native_windows.Tray", return_value=tray):
            with self.assertRaisesRegex(InstanceConflict, "tray_unavailable"):
                preflight()
        tray.close.assert_called_once()

    def test_failed_preflight_does_not_stop_or_launch_existing_instance(self):
        store = Mock()
        with patch.object(windows_launch, "InstanceStore", return_value=store), \
                patch.object(windows_launch, "load_configuration"), \
                patch("src.web.native_windows.preflight", side_effect=InstanceConflict("tray_unavailable")), \
                patch.object(windows_launch, "launch") as launch, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(windows_launch.launch_windows(ROOT), 1)
        launch.assert_not_called()
        store.log.assert_called_once_with("tray_unavailable")

    def test_browser_failure_is_actionable_and_does_not_stop_host(self):
        store = Mock()
        output = io.StringIO()
        with patch.object(windows_launch, "InstanceStore", return_value=store), \
                patch.object(windows_launch, "load_configuration"), \
                patch("src.web.native_windows.preflight"), \
                patch.object(windows_launch, "launch", return_value=Mock(browser_opened=False)), \
                contextlib.redirect_stdout(output):
            self.assertEqual(windows_launch.launch_windows(ROOT), 4)
        self.assertIn("Web is running", output.getvalue())
        store.log.assert_called_once_with("browser_open_failed")

    def test_open_is_async_coalesced_and_exit_does_not_wait_for_browser(self):
        owner = self.owner()
        entered, release = Event(), Event()

        def browser(**_):
            entered.set()
            release.wait(3)
            return True

        owner.open_browser.side_effect = browser
        adapter = WindowsHost(tray=Mock())
        try:
            adapter.dispatch(owner, [OPEN])
            self.assertTrue(entered.wait(1))
            adapter.dispatch(owner, [OPEN, OPEN])
            adapter.dispatch(owner, [EXIT])
            owner.stop.assert_called_once_with("menu")
            owner.open_browser.assert_called_once()
        finally:
            release.set()
            adapter.open_thread.join(3)
            adapter.close()

    def test_native_readiness_follows_install_and_host_loss_ends_loop(self):
        owner = self.owner()
        tray = Mock()
        calls = []
        tray.install.side_effect = lambda: calls.append("installed")
        owner.publish_ready.side_effect = lambda: calls.append("ready")

        def poll():
            owner.stopped.set()
            return []

        tray.poll.side_effect = poll
        adapter = WindowsHost(tray)
        adapter.run(owner)
        adapter.close()
        self.assertEqual(calls, ["installed", "ready"])
        tray.close.assert_called_once()

    def test_unexpected_browser_worker_fault_is_handed_to_host_not_orphaned(self):
        owner = self.owner()
        fault = SystemExit("private")
        owner.open_browser.side_effect = fault
        adapter = WindowsHost(tray=Mock())
        adapter.dispatch(owner, [OPEN])
        adapter.open_thread.join(3)
        self.assertFalse(adapter.open_thread.is_alive())
        self.assertIs(owner.failure, fault)
        owner.stop.assert_called_once_with("runtime_fault")

    def test_install_failure_never_publishes_readiness(self):
        owner = self.owner()
        tray = Mock()
        tray.install.side_effect = InstanceConflict("tray_unavailable")
        with self.assertRaises(InstanceConflict):
            WindowsHost(tray).run(owner)
        owner.publish_ready.assert_not_called()

    def test_launcher_is_relative_and_does_not_change_stable_terminal_contract(self):
        command = (ROOT / "windows/Beta/Cost Guard Web.cmd").read_text()
        script = (ROOT / "src/web/windows_launch.ps1").read_text()
        self.assertIn('%~dp0..\\..\\src\\web\\windows_launch.ps1', command)
        self.assertIn("exit /b %errorlevel%", command)
        self.assertNotIn("-NoExit", command)
        self.assertNotIn("Set-ExecutionPolicy", script)
        self.assertNotIn("Set-Location", script)
        self.assertIn("(3,11)", script)
        self.assertIn("--launch-windows", script)

    @unittest.skipUnless(os.name == "nt", "Windows PowerShell discovery contract")
    def test_real_powershell_discovery_missing_old_then_supported_and_multiple_paths(self):
        # Extract the one production function using PowerShell's AST. Do not run UI.
        with tempfile.TemporaryDirectory() as directory:
            old = Path(directory) / "old python.ps1"
            old.write_text("$global:LASTEXITCODE = 1\n")
            probe = Path(directory) / "probe.ps1"
            probe.write_text(r'''
param($Source, $OldPython, $Python)
$ErrorActionPreference = 'Stop'
$tokens = $null; $errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($Source, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'Invalid production PowerShell syntax' }
$realLauncher = (Get-Command py.exe -CommandType Application -ErrorAction SilentlyContinue).Source
$function = $ast.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Find-BetaPython'}, $true)
Invoke-Expression $function.Extent.Text
function Get-Command { return @() }
if (Find-BetaPython) { throw 'Missing Python must not succeed' }
function Get-Command {
    param($Name, [switch]$All, $CommandType, $ErrorAction)
    if ($Name -eq 'py.exe') { return @([pscustomobject]@{Source=$OldPython}) }
    return @([pscustomobject]@{Source=$OldPython}, [pscustomobject]@{Source=$Python})
}
$found = Find-BetaPython
if ($found.Executable -ne $Python -or $found.Arguments.Count -ne 0) { throw 'PATH fallback failed' }
if ($realLauncher) {
    function Get-Command { return @([pscustomobject]@{Source=$realLauncher}) }
    $found = Find-BetaPython
    $python = $found.Executable
    $assignment = $ast.Find({param($node) $node -is [Management.Automation.Language.AssignmentStatementAst] -and $node.Left.Extent.Text -like '*$pythonArgs'}, $true)
    Invoke-Expression $assignment.Extent.Text
    $result = & $python @pythonArgs -c 'print(1234567)'
    if ($result -ne '1234567') { throw 'Single py -3 argument lost native command' }
}
$logging = $ast.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Write-BetaStartupRecord'}, $true)
Invoke-Expression $logging.Extent.Text
$directory = Join-Path (Split-Path -Parent $OldPython) 'private log'
Write-BetaStartupRecord -Directory $directory -Failure python_unavailable
$acl = [IO.DirectoryInfo]::new($directory).GetAccessControl()
if (-not $acl.AreAccessRulesProtected) { throw 'Log directory must be private' }
$text = [IO.File]::ReadAllText((Join-Path $directory 'startup.log'))
if ($text -notmatch '^\d{4}-\d{2}-\d{2}T[\d:]+ python_unavailable$') { throw 'Non-allowlisted log' }
Write-Output 'DISCOVERY_PASS'
''', encoding="utf-8")
            result = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                                     "-File", str(probe), str(ROOT / "src/web/windows_launch.ps1"),
                                     str(old), sys.executable], input="", capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DISCOVERY_PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
