"""Hidden Windows discovery behavior and narrow portable launcher safety checks."""
import os
from pathlib import Path
import re
import subprocess
import sys
import shutil
import tempfile
import unittest

from development.tests.fixtures.windows_shell import CONSOLE_STUB

ROOT = Path(__file__).resolve().parents[2]


class WindowsLauncherTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Windows Python selection behavior')
    def test_shared_resolver_skips_aliases_deduplicates_and_classifies_evidence(self):
        for shell in ('powershell.exe', 'pwsh.exe'):
            if not shutil.which(shell):
                continue
            with self.subTest(shell=shell), tempfile.TemporaryDirectory(prefix='Python å space ') as directory:
                root = Path(directory)
                script = root / 'probe.ps1'
                script.write_text(r'''param($Source, $Python)
$ErrorActionPreference = 'Stop'
. $Source
$script:Scenario = 'fallback'
$script:Calls = @()
function Get-CostGuardPythonCandidates {
    if ($script:Scenario -eq 'missing') { return @() }
    if ($script:Scenario -eq 'old') { return 'C:\fixture\old.exe' }
    if ($script:Scenario -eq 'broken') { return 'C:\fixture\broken.exe' }
    'C:\Users\fixture\AppData\Local\Microsoft\WindowsApps\python.exe'
    'C:\fixture\old.exe'; 'C:\fixture\OLD.exe'
    'C:\fixture\broken.exe'; 'C:\fixture\wrong-platform.exe'
    'C:\fixture\not-an-interpreter.ps1'
    $Python
}
$realProbe = ${function:Invoke-CostGuardPythonProcess}
function Invoke-CostGuardPythonProcess {
    param($Executable, $Arguments, $Timeout, $Activity)
    $script:Calls += $Executable
    if ($Executable -eq 'C:\fixture\broken.exe') { return $null }
    if ($Executable -eq 'C:\fixture\old.exe') { return @{Code=0;Output='[3,10,"win32","C:\\fixture\\old.exe"]'} }
    if ($Executable -eq 'C:\fixture\wrong-platform.exe') { return @{Code=0;Output='[3,13,"linux","/bin/python"]'} }
    & $realProbe $Executable $Arguments $Timeout $Activity
}
$found = Find-CostGuardPython
if ($found.Executable -ne $Python -or $found.Arguments.Count) { throw 'No real interpreter selected' }
if ($script:Calls.Count -ne 4) { throw ('Alias/duplicate/unrelated file probed: ' + $script:Calls.Count) }
foreach ($scenario in @('missing','old','broken')) {
    $script:Scenario = $scenario
    $found = Find-CostGuardPython
    if ($found.Executable -or $found.Failure -ne $scenario) { throw 'Incorrect evidence classification' }
    $text = Get-CostGuardPythonFailure $found.Failure
    if ($text -notmatch 'START\n\nReason: .+\n\nNext step:') { throw 'Dense failure text' }
}
Write-Output 'DISCOVERY_PASS'
''', encoding='utf-8-sig')
                result = subprocess.run([shell, '-NoProfile', '-NonInteractive', '-File', str(script),
                    str(ROOT / 'src/python_discovery.ps1'), sys.executable], capture_output=True,
                    text=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn('DISCOVERY_PASS', result.stdout)

    @unittest.skipUnless(os.name == 'nt', 'Windows native installation lookup')
    def test_canonical_non_path_install_with_spaces_and_unicode_is_executable(self):
        with tempfile.TemporaryDirectory(prefix='Python å space ') as directory:
            root = Path(directory)
            executable = root / 'Programs/Python/Python313/python.exe'
            executable.parent.parent.mkdir(parents=True)
            # Link only the interpreter directory; no installation, PATH or registry mutation.
            subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(executable.parent),
                            str(Path(sys.executable).parent)], check=True, capture_output=True,
                            creationflags=subprocess.CREATE_NO_WINDOW)
            actual = executable
            script = root / 'probe.ps1'
            script.write_text(r'''param($Source, $Python)
$ErrorActionPreference = 'Stop'
. $Source
function Get-Command { return @() }
function Get-CostGuardRegisteredPython { return @() }
$found = Find-CostGuardPython
if (-not $found.Executable) { throw 'Non-PATH interpreter missed' }
Write-Output $found.Executable
''', encoding='utf-8-sig')
            result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-File', str(script),
                str(ROOT / 'src/python_discovery.ps1'), str(actual)], env=dict(os.environ, LOCALAPPDATA=str(root), WINDIR=''),
                capture_output=True, text=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn('python.exe', result.stdout)

    def test_terminal_entrypoints_keep_separate_persistent_console(self):
        for path in ("windows/Legacy/Cost-Guard.cmd", "windows/Legacy/Cost-Guard-Watch.cmd",
                     "development/user-tools/diagnostics/windows/Cost-Guard-Diagnostics.cmd"):
            with self.subTest(path=path):
                text = (ROOT / path).read_text(encoding="utf-8")
                start = next(line for line in text.splitlines() if re.match(r'^\s*start\s', line, re.I))
                self.assertNotIn(" /b ", start.lower())
                self.assertNotIn(" /wait ", start.lower())
                self.assertNotIn("Checking requirements", text)
                self.assertNotIn("COST_GUARD_LAUNCHER_STATUS", text)
                self.assertRegex(start, r'(?i)\s-NoExit\b')

    @unittest.skipUnless(os.name == 'nt', 'Windows batch shell fallback')
    def test_entrypoints_select_available_shell_and_propagate_start_result(self):
        for relative in ('windows/Legacy/Cost-Guard.cmd', 'windows/Legacy/Cost-Guard-Watch.cmd',
                         'development/user-tools/diagnostics/windows/Cost-Guard-Diagnostics.cmd'):
            for available, expected in ((0, 'pwsh.exe'), (1, 'powershell.exe')):
                with self.subTest(path=relative, available=available), tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    (root / 'where.cmd').write_text(f'@exit /b {available}\n')
                    (root / 'start.cmd').write_text('@echo %*\n@exit /b 23\n')
                    # cmd's START is builtin. Replace only that command verb with
                    # an explicit capture boundary; execute real fallback/control flow.
                    source = (ROOT / relative).read_text()
                    source = re.sub(r'(?im)^\s*start\b', 'call "%~dp0start.cmd"', source)
                    source = re.sub(r'(?im)^\s*where\b', 'call "%~dp0where.cmd"', source)
                    batch = root / 'launcher.cmd'
                    batch.write_text(source)
                    result = subprocess.run(['cmd.exe', '/d', '/c', str(batch)], cwd=root,
                                            env=dict(os.environ, PATH=str(root)), capture_output=True,
                                            text=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
                    self.assertEqual(23, result.returncode, result.stderr)
                    self.assertIn(expected, result.stdout)


if __name__ == "__main__":
    unittest.main()
