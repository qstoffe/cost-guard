"""Hidden Windows discovery behavior and narrow portable launcher safety checks."""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from development.tests.fixtures.windows_shell import CONSOLE_STUB

ROOT = Path(__file__).resolve().parents[2]


class WindowsLauncherTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Windows Python selection behavior')
    def test_python_probe_rejects_old_accepts_minimum_and_preserves_launcher_arguments(self):
        for scenario in ('fallback', 'launcher'):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                for name, version in (('old', '(3,10)'), ('supported', '(3,11)')):
                    (root / (name + '.ps1')).write_text(f'''if ($args -contains '-c') {{
    $index = [array]::IndexOf($args, '-c')
    $code = 'import sys; sys.version_info={version}; ' + $args[$index + 1]
    & $env:FIXTURE_PYTHON -c $code
    [IO.File]::AppendAllText((Join-Path $PSScriptRoot 'probes'), '{name}:' + $LASTEXITCODE + ':' + ($args[0]) + "`n")
}} else {{
    Write-Output ('APP:' + ($args -join ','))
    $global:LASTEXITCODE = 17
}}
''', encoding='utf-8-sig')
                script = root / 'probe.ps1'
                script.write_text(CONSOLE_STUB + '''
function Get-Command {
    param($Name, [switch]$All, $CommandType, $ErrorAction)
    if ($Name -eq 'py.exe') {
        $choice = if ($env:FIXTURE_SCENARIO -eq 'launcher') { 'supported.ps1' } else { 'old.ps1' }
        return @([pscustomobject]@{Source=(Join-Path $PSScriptRoot $choice)})
    }
    return @([pscustomobject]@{Source=(Join-Path $PSScriptRoot 'old.ps1')},
             [pscustomobject]@{Source=(Join-Path $PSScriptRoot 'supported.ps1')})
}
& $env:FIXTURE_SOURCE -Mode watch
exit $LASTEXITCODE
''', encoding='utf-8-sig')
                env = dict(os.environ, FIXTURE_PYTHON=sys.executable, FIXTURE_SCENARIO=scenario,
                           FIXTURE_SOURCE=str(ROOT / 'src/windows_launcher.ps1'))
                result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-File', str(script)],
                                        env=env, capture_output=True, text=True, timeout=30,
                                        creationflags=subprocess.CREATE_NO_WINDOW)
                self.assertEqual(17, result.returncode, result.stderr)
                expected = ['old:1:-3', 'supported:0:-c'] if scenario == 'fallback' else ['supported:0:-3']
                self.assertEqual(expected, (root / 'probes').read_text().splitlines())
                self.assertIn('APP:' + ('-3,' if scenario == 'launcher' else '') + 'cost-guard-cli.py,--watch', result.stdout)

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
