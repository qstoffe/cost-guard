"""Synthetic Windows Beta contracts; no real icon, browser or UI is started."""
import contextlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from threading import Event
import unittest
from unittest.mock import Mock, patch

from src.web import windows_launch
from src.web.native_windows import WindowsHost, preflight
from src.web.process_identity import InstanceConflict
from src.web.tray_icon import icon_bits
from src.web.win32_tray import OPEN, EXIT
from src.web.startup import StartupProgress

ROOT = Path(__file__).resolve().parents[2]


class WindowsWebTests(unittest.TestCase):
    def test_startup_progress_is_flushed_timed_and_allowlisted(self):
        with patch('src.web.startup.time.monotonic', side_effect=[10, 12.5]), \
                patch('builtins.print') as output:
            progress = StartupProgress()
            progress('config')
        output.assert_called_once_with(
            'Cost Guard startup: Checking safe configuration (2.5s elapsed)', flush=True)
        with self.assertRaises(KeyError):
            progress('http://private/#bootstrap=secret')

    def test_configuration_failure_stops_before_native_or_browser_work(self):
        output = io.StringIO()
        with patch.object(windows_launch, 'InstanceStore'), \
                patch.object(windows_launch, 'load_configuration', side_effect=windows_launch.ConfigError('private')), \
                patch('src.web.native_windows.preflight') as preflight, \
                patch.object(windows_launch, 'launch') as launch, contextlib.redirect_stdout(output):
            self.assertEqual(windows_launch.launch_windows(ROOT), 1)
        preflight.assert_not_called()
        launch.assert_not_called()
        self.assertIn('Checking safe configuration', output.getvalue())
        self.assertIn('Check config/user-config.jsonc', output.getvalue())
        self.assertNotIn('private', output.getvalue())

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
        command = (ROOT / "windows/Beta/Cost-Guard-Web.cmd").read_text()
        script = (ROOT / "src/web/windows_launch.ps1").read_text()
        self.assertIn('%~dp0..\\..\\src\\web\\windows_launch.ps1', command)
        self.assertIn("exit /b %errorlevel%", command)
        self.assertNotIn("-NoExit", command)
        self.assertNotIn("Set-ExecutionPolicy", script)
        self.assertNotIn("Set-Location", script)
        self.assertIn("(3,11)", script)
        self.assertIn("--launch-windows", script)
        self.assertIn('start "" /min', command)
        self.assertIn('-WindowStyle Hidden', command)
        self.assertIn('-Detached <nul >nul 2>nul', command)
        self.assertNotIn('/wait', '\n'.join(line for line in command.splitlines() if not line.startswith('rem ')))
        self.assertIn('if (-not $Detached -and', script)

    @unittest.skipUnless(os.name == 'nt', 'Native Windows asynchronous handoff')
    def test_batch_exits_before_slow_delegate_and_delegate_has_no_visible_console(self):
        # Exercise the unchanged batch in a source-shaped Unicode/space fixture.
        # The delegate is deliberately blocked; no Web host, icon or browser starts.
        with tempfile.TemporaryDirectory(prefix='web handoff å ') as directory:
            root = Path(directory)
            beta = root / 'windows/Beta'
            web = root / 'src/web'
            beta.mkdir(parents=True)
            web.mkdir(parents=True)
            batch = beta / 'Cost-Guard-Web.cmd'
            shutil.copyfile(ROOT / 'windows/Beta/Cost-Guard-Web.cmd', batch)
            (web / 'visibility.py').write_text('''import ctypes as c
from pathlib import Path
k = c.WinDLL('kernel32'); u = c.WinDLL('user32')
k.GetConsoleWindow.restype = c.c_void_p
u.IsWindowVisible.argtypes = [c.c_void_p]
Path(__file__).with_name('visible').write_text(str(bool(u.IsWindowVisible(k.GetConsoleWindow()))))
''', encoding='utf-8')
            python = sys.executable.replace("'", "''")
            (web / 'windows_launch.ps1').write_text('''param([switch]$Detached)
$ErrorActionPreference = 'Stop'
if (-not $Detached) { throw 'Missing detached mode' }
[IO.File]::WriteAllText((Join-Path $PSScriptRoot 'entered'), 'entered')
& 'PYTHON' (Join-Path $PSScriptRoot 'visibility.py')
if ($LASTEXITCODE -ne 0) { [IO.File]::WriteAllText((Join-Path $PSScriptRoot 'failed'), 'visibility_python_failed') }
$deadline = [DateTime]::UtcNow.AddSeconds(10)
while (-not (Test-Path (Join-Path $PSScriptRoot 'release')) -and [DateTime]::UtcNow -lt $deadline) { Start-Sleep -Milliseconds 20 }
[IO.File]::WriteAllText((Join-Path $PSScriptRoot 'done'), 'done')
'''.replace('PYTHON', python), encoding='utf-8-sig')
            child = subprocess.Popen(['cmd.exe', '/d', '/c', str(batch)], cwd=root,
                                     stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                self.assertEqual(child.wait(timeout=5), 0)
                # A loaded hosted runner can take longer to start PowerShell/Python
                # than the product's immediate batch handoff. Do not conflate them.
                deadline = time.monotonic() + 15
                while not (web / 'visible').exists() and not (web / 'failed').exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertFalse((web / 'failed').exists(), 'Delegate visibility interpreter failed')
                self.assertTrue((web / 'visible').exists(),
                                'Delegate visibility stage not reached; entered=' + str((web / 'entered').exists()))
                self.assertEqual((web / 'visible').read_text(), 'False')
                self.assertFalse((web / 'done').exists(), 'Batch waited for blocked delegate')
            finally:
                (web / 'release').touch()
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=5)
                deadline = time.monotonic() + 12
                while not (web / 'done').exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue((web / 'done').exists(), 'Delegate did not finish its bounded probe')
                child.communicate(timeout=3)

    @unittest.skipUnless(os.name == "nt", "Windows PowerShell discovery contract")
    def test_stalled_python_discovery_is_bounded_and_joins_only_its_probe(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'sitecustomize.py').write_text('''import os, time
from pathlib import Path
Path(__file__).with_name('pid').write_text(str(os.getpid()))
time.sleep(30)
''', encoding='utf-8')
            probe = root / 'probe.ps1'
            probe.write_text('''param($Source, $Python)
$ErrorActionPreference = 'Stop'
$tokens = $null; $errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($Source, [ref]$tokens, [ref]$errors)
$function = $ast.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Find-BetaPython'}, $true)
Invoke-Expression $function.Extent.Text
function Get-Command {
    param($Name, [switch]$All, $CommandType, $ErrorAction)
    if ($Name -eq 'python.exe') { return @([pscustomobject]@{Source=$Python}) }
    return @()
}
$env:PYTHONPATH = $PSScriptRoot
$timer = [Diagnostics.Stopwatch]::StartNew()
if (Find-BetaPython) { throw 'Stalled interpreter accepted' }
if ($timer.Elapsed.TotalSeconds -gt 9) { throw 'Discovery exceeded bound' }
$ownedPid = [int][IO.File]::ReadAllText((Join-Path $PSScriptRoot 'pid'))
try { $process = [Diagnostics.Process]::GetProcessById($ownedPid) } catch { $process = $null }
if ($process -and -not $process.HasExited) { throw 'Owned stalled probe leaked' }
Write-Output 'STALL_PASS'
''', encoding='utf-8-sig')
            result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                                     '-File', str(probe), str(ROOT / 'src/web/windows_launch.ps1'),
                                     sys.executable], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('STALL_PASS', result.stdout)

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
Write-Output 'STAGE:parse'
$tokens = $null; $errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($Source, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'Invalid production PowerShell syntax' }
$realLauncher = (Get-Command py.exe -CommandType Application -ErrorAction SilentlyContinue).Source
$function = $ast.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Find-BetaPython'}, $true)
Invoke-Expression $function.Extent.Text
function Get-Command { return @() }
if (Find-BetaPython) { throw 'Missing Python must not succeed' }
Write-Output 'STAGE:direct-python'
function Get-Command {
    param($Name, [switch]$All, $CommandType, $ErrorAction)
    if ($Name -eq 'py.exe') { return @([pscustomobject]@{Source=$OldPython}) }
    return @([pscustomobject]@{Source=$OldPython}, [pscustomobject]@{Source=$Python})
}
$found = Find-BetaPython
if ($found.Executable -ne $Python -or $found.Arguments.Count -ne 0) { throw 'PATH fallback failed' }
if ($realLauncher) {
    Write-Output 'STAGE:py-launcher'
    function Get-Command { return @([pscustomobject]@{Source=$realLauncher}) }
    $found = Find-BetaPython
    $python = $found.Executable
    $assignment = $ast.Find({param($node) $node -is [Management.Automation.Language.AssignmentStatementAst] -and $node.Left.Extent.Text -like '*$pythonArgs'}, $true)
    Invoke-Expression $assignment.Extent.Text
    $result = & $python @pythonArgs -c 'print(1234567)'
    if ($result -ne '1234567') { throw 'Single py -3 argument lost native command' }
}
$logging = $ast.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Write-BetaStartupRecord'}, $true)
Write-Output 'STAGE:private-log'
Invoke-Expression $logging.Extent.Text
$directory = Join-Path (Split-Path -Parent $OldPython) 'private log'
Write-BetaStartupRecord -Directory $directory -Failure python_unavailable
$acl = [IO.DirectoryInfo]::new($directory).GetAccessControl()
if (-not $acl.AreAccessRulesProtected) { throw 'Log directory must be private' }
$text = [IO.File]::ReadAllText((Join-Path $directory 'startup.log'))
if ($text -notmatch '^\d{4}-\d{2}-\d{2}T[\d:]+ python_unavailable$') { throw 'Non-allowlisted log' }
Write-Output 'DISCOVERY_PASS'
''', encoding="utf-8")
            # This harness includes shell/AST startup, several real Python
            # processes and private DACL I/O, not the product's 15s host wait.
            try:
                result = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                                         "-File", str(probe), str(ROOT / "src/web/windows_launch.ps1"),
                                         str(old), sys.executable], input="", capture_output=True, text=True, timeout=30)
            except subprocess.TimeoutExpired as error:
                output = error.stdout or b""
                if isinstance(output, bytes):
                    output = output.decode('utf-8', errors='replace')
                stages = [line for line in output.splitlines() if line.startswith('STAGE:')]
                self.fail('Bounded PowerShell discovery harness timeout; ' + ', '.join(stages))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DISCOVERY_PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
