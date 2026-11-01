"""Approval-only owned Windows console-buffer probe; not direct visual proof.

Runs the real PowerShell launcher in a source-shaped delayed fixture, without a
host/browser. Inspect only the console created by this probe. Never auto-run in CI.
"""
import argparse
import ctypes as c
from ctypes import wintypes as w
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
LABEL = 'Starting CostGuard web... '


class Coord(c.Structure):
    _fields_ = [('X', c.c_short), ('Y', c.c_short)]


class Rect(c.Structure):
    _fields_ = [(name, c.c_short) for name in ('Left', 'Top', 'Right', 'Bottom')]


class BufferInfo(c.Structure):
    _fields_ = [('size', Coord), ('cursor', Coord), ('attributes', w.WORD),
                ('window', Rect), ('maximum', Coord)]


def bind(kernel, name, result, arguments):
    function = getattr(kernel, name)
    function.restype, function.argtypes = result, arguments
    return function


def capture(code):
    with tempfile.TemporaryDirectory(prefix='web console å ') as directory:
        root = Path(directory)
        web = root / 'src/web'
        web.mkdir(parents=True)
        source = (ROOT / 'src/web/windows_launch.ps1').read_text()
        source = source.replace("[Environment]::GetFolderPath('LocalApplicationData')", '$env:LOCALAPPDATA')
        script = web / 'windows_launch.ps1'
        script.write_text(source, encoding='utf-8-sig')
        # Slow BOTH discovery and startup, exercising the same production animator.
        (root / 'sitecustomize.py').write_text('import time; time.sleep(1.5)\n')
        (root / 'cost-guard-web.py').write_text(f'''
import time
for stage in ('Checking safe configuration', 'Waiting for host readiness', 'Opening your default browser'):
    print('Cost Guard startup: ' + stage + ' (1.0s elapsed)', flush=True)
    time.sleep(0.7)
if {code}: print('Cost Guard Web Beta: Web is running; use Open Cost Guard to retry.', flush=True)
raise SystemExit({code})
''')
        wrapper = root / 'probe.ps1'
        wrapper.write_text('''param($Interpreter, $Source)
$ErrorActionPreference = 'Stop'
function Get-Command {
    param($Name, [switch]$All, $CommandType, $ErrorAction)
    if ($Name -eq 'python.exe') { return @([pscustomobject]@{Source=$Interpreter}) }
    return @()
}
function Add-Type { throw 'No dialog in buffer probe' }
function Read-Host { return '' }
$env:LOCALAPPDATA = $PSScriptRoot
$env:PYTHONPATH = $PSScriptRoot
Write-Host 'Retained output sentinel'
& $Source
[IO.File]::WriteAllText((Join-Path $PSScriptRoot 'result'), [string]$LASTEXITCODE)
Start-Sleep -Seconds 30
''', encoding='utf-8-sig')
        kernel = c.WinDLL('kernel32', use_last_error=True)
        free = bind(kernel, 'FreeConsole', w.BOOL, [])
        attach = bind(kernel, 'AttachConsole', w.BOOL, [w.DWORD])
        create = bind(kernel, 'CreateFileW', w.HANDLE,
            [w.LPCWSTR, w.DWORD, w.DWORD, w.LPVOID, w.DWORD, w.DWORD, w.HANDLE])
        close = bind(kernel, 'CloseHandle', w.BOOL, [w.HANDLE])
        info = bind(kernel, 'GetConsoleScreenBufferInfo', w.BOOL, [w.HANDLE, c.POINTER(BufferInfo)])
        read = bind(kernel, 'ReadConsoleOutputCharacterW', w.BOOL,
            [w.HANDLE, w.LPWSTR, w.DWORD, Coord, c.POINTER(w.DWORD)])
        attributes = bind(kernel, 'ReadConsoleOutputAttribute', w.BOOL,
            [w.HANDLE, c.POINTER(w.WORD), w.DWORD, Coord, c.POINTER(w.DWORD)])
        child = subprocess.Popen(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
            '-File', str(wrapper), sys.executable, str(script)], cwd=root,
            creationflags=subprocess.CREATE_NEW_CONSOLE)
        handle = None
        try:
            free()  # Only this disposable probe process, never another process's console.
            deadline = time.monotonic() + 20
            while not attach(child.pid):
                if child.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('owned_console_attach_failed')
                time.sleep(0.02)
            handle = create('CONOUT$', 0x80000000, 3, None, 3, 0, None)
            if handle == w.HANDLE(-1).value:
                raise RuntimeError('owned_console_open_failed')
            baseline = None
            glyphs = set()
            samples = 0
            while time.monotonic() < deadline:
                data = BufferInfo()
                assert info(handle, c.byref(data))
                count = data.size.X * min(data.size.Y, 12)
                text = c.create_unicode_buffer(count + 1)
                colors = (w.WORD * count)()
                copied = w.DWORD()
                assert read(handle, text, count, Coord(0, 0), c.byref(copied))
                assert attributes(handle, colors, count, Coord(0, 0), c.byref(copied))
                content = text.value
                position = content.find(LABEL)
                if position >= 0:
                    assert content.count(LABEL) == 1
                    cell = position + len(LABEL)
                    glyph = content[cell]
                    if glyph in '|/-\\':
                        normalized = content[:cell] + ' ' + content[cell + 1:]
                        # Console reads are not atomic with SetCursorPosition/Write.
                        # Accept either position inside/just after the spinner cell;
                        # ignore transition samples while cleanup starts a new line.
                        if data.cursor.Y == cell // data.size.X and data.cursor.X in (cell % data.size.X, cell % data.size.X + 1):
                            snapshot = (normalized, tuple(colors))
                            if baseline is None:
                                baseline = snapshot
                            assert snapshot == baseline, 'Only spinner cell may change, not attributes/other output'
                            glyphs.add(glyph)
                            samples += 1
                if (root / 'result').exists():
                    assert (root / 'result').read_text() == str(code)
                    assert baseline is not None and len(glyphs) == 4 and samples > 10
                    assert content.startswith('Retained output sentinel')
                    assert content[cell] == ' ', 'Spinner must clear before exit/error'
                    assert 'Cost Guard startup:' not in content
                    if code:
                        assert content.index('Cost Guard Web Beta:') > cell
                        assert 'Diagnostics:' in content
                    break
                time.sleep(0.03)
            else:
                raise RuntimeError('owned_console_probe_timeout')
            return {'exit_code': code, 'animated_samples': samples, 'glyphs': sorted(glyphs),
                    'only_one_cell_changed': True, 'attributes_unchanged': True,
                    'cleanup_before_error_or_exit': True, 'direct_visual_observation': 'unverified'}
        finally:
            # Let the bounded fixture's Python child finish before closing its
            # status console, including when an evidence assertion failed.
            deadline = time.monotonic() + 15
            while child.poll() is None and not (root / 'result').exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            if handle is not None:
                close(handle)
            free()
            if child.poll() is None:
                child.terminate()  # Exact probe-owned fixture/status process only.
            child.wait(timeout=5)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-native-ui', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.allow_native_ui:
        parser.error('Current bounded native UI approval is required')
    result = {'delayed_success': capture(0), 'delayed_browser_failure': capture(4)}
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
