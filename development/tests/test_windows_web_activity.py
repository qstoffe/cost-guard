"""Real PowerShell redirected startup/failure contracts, without native UI."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(os.name == 'nt', 'Windows PowerShell output contract')
class WindowsWebActivityTests(unittest.TestCase):
    def test_redirected_launch_drains_delayed_stages_and_preserves_failure_status(self):
        for mode, code in (('success', 0), ('browser', 4), ('startup', 1), ('missing', 1), ('exception', 1)):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(prefix='web activity å ') as directory:
                root = Path(directory)
                web = root / 'src/web'
                web.mkdir(parents=True)
                source = (ROOT / 'src/web/windows_launch.ps1').read_text()
                # Redirect only the OS profile-root lookup; retain real private-log code.
                source = source.replace("[Environment]::GetFolderPath('LocalApplicationData')", '$env:LOCALAPPDATA')
                (web / 'windows_launch.ps1').write_text(source, encoding='utf-8-sig')
                (root / 'src/python_discovery.ps1').write_bytes((ROOT / 'src/python_discovery.ps1').read_bytes())
                (web / 'launch_messages.json').write_bytes((ROOT / 'src/web/launch_messages.json').read_bytes())
                (root / 'cost-guard-web.py').write_text(f'''
import sys, time
if sys.argv[1:] != ['--launch-windows']:
    raise SystemExit(99)
print('Cost Guard startup: Checking safe configuration (0.0s elapsed)', flush=True)
print('untrusted raw exception https://private/#secret', flush=True)
time.sleep(0.4)
print('Cost Guard startup: Opening your default browser (0.4s elapsed)', flush=True)
if {code}:
    print('Cost Guard failure: browser_open_failed', flush=True)
    print('Cost Guard: private https://private/#secret', flush=True)
raise SystemExit({code})
''', encoding='utf-8')
                probe = root / 'probe.ps1'
                probe.write_text('''param($Interpreter, $Source, $Mode)
$ErrorActionPreference = 'Stop'
# Override only the candidate inventory, not the production process/version probe.
$resolver = Join-Path (Split-Path -Parent (Split-Path -Parent $Source)) 'python_discovery.ps1'
[IO.File]::AppendAllText($resolver, @'

function Get-CostGuardPythonCandidates {
    if ($Mode -eq 'missing') { return @() }
    if ($Mode -eq 'exception') { throw 'private exception https://private/#secret' }
    $Interpreter
}
'@)
# Test only the non-UI fallback; never display a dialog or write a real profile log.
function Add-Type { [IO.File]::WriteAllText((Join-Path $PSScriptRoot 'unexpected-ui'), 'called'); throw 'UI disabled by test' }
function Read-Host { throw 'Redirected launch must never prompt' }
$env:LOCALAPPDATA = $PSScriptRoot
& $Source
exit $LASTEXITCODE
''', encoding='utf-8-sig')
                result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                    '-File', str(probe), sys.executable, str(web / 'windows_launch.ps1'), mode],
                    input='', capture_output=True, timeout=15)
                self.assertEqual(result.returncode, code, result.stderr)
                text = result.stdout.decode('utf-8', errors='replace')
                self.assertEqual(text.count('Starting CostGuard web...'), 1)
                self.assertFalse(any(byte < 32 and byte not in (10, 13) for byte in result.stdout))
                self.assertNotIn(b'\r', result.stdout.replace(b'\r\n', b''))
                self.assertNotIn('Cost Guard startup:', text)
                self.assertNotIn('private', text)
                self.assertEqual(result.stderr, b'')
                self.assertFalse((root / 'unexpected-ui').exists(), 'Redirected failure must not attempt a dialog')
                if code:
                    if mode in ('browser', 'startup'):
                        self.assertIn('Web is running, but the default browser could not open.', text)
                        self.assertIn('COST GUARD WEB IS RUNNING\n\nReason:', text.replace('\r\n', '\n'))
                    if mode == 'missing':
                        self.assertIn('No usable Python 3.11+ installation could be located', text)
                    self.assertIn('Diagnostics:', text)
                    record = root / 'CostGuard/Web/launcher/startup.log'
                    failure = 'python_unavailable' if mode in ('missing', 'exception') else 'launcher_failed'
                    self.assertRegex(record.read_text(), r'^\d{4}-\d\d-\d\dT[\d:]+ ' + failure + '$')
                else:
                    self.assertEqual(text.strip(), 'Starting CostGuard web...')


if __name__ == '__main__':
    unittest.main()
