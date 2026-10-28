"""Manual native console experiment. Requires explicit bounded UI approval.

Run only in a disposable clone. Creates only synthetic console contents; prints
aggregate observations, never raw console buffers. Not part of automated suites.
"""
import ctypes
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / '.console-probe'
K = ctypes.WinDLL('kernel32', use_last_error=True)
K.GetStdHandle.restype = w.HANDLE
K.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, w.LPVOID, w.DWORD, w.DWORD, w.HANDLE]
K.CreateFileW.restype = w.HANDLE
K.WriteConsoleInputW.argtypes = [w.HANDLE, w.LPVOID, w.DWORD, ctypes.POINTER(w.DWORD)]
K.CloseHandle.argtypes = [w.HANDLE]


def wait_file(path, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding='utf-8-sig'))
            except (ValueError, PermissionError):
                pass
        time.sleep(.1)
    raise TimeoutError(path.name)


def bridge(pid, action, text=''):
    result = subprocess.run([sys.executable, __file__, 'bridge', str(pid), action, text],
                            creationflags=subprocess.CREATE_NO_WINDOW, capture_output=True,
                            text=True, timeout=10)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return json.loads(result.stdout)


def console_action(pid, action, text):
    K.FreeConsole()
    if not K.AttachConsole(pid):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        ids = (w.DWORD * 64)()
        count = K.GetConsoleProcessList(ids, 64)
        if action == 'members':
            return {'members': list(ids[:count])}
        if action == 'interrupt':
            K.SetConsoleCtrlHandler(None, True)
            if not K.GenerateConsoleCtrlEvent(0, 0):
                raise ctypes.WinError(ctypes.get_last_error())
            return {'interrupt': True}
        if action == 'snapshot' or action == 'resize':
            class COORD(ctypes.Structure):
                _fields_ = [('X', ctypes.c_short), ('Y', ctypes.c_short)]
            class RECT(ctypes.Structure):
                _fields_ = [('Left', ctypes.c_short), ('Top', ctypes.c_short),
                            ('Right', ctypes.c_short), ('Bottom', ctypes.c_short)]
            class INFO(ctypes.Structure):
                _fields_ = [('size', COORD), ('cursor', COORD), ('attributes', w.WORD),
                            ('window', RECT), ('maximum', COORD)]
            K.GetConsoleScreenBufferInfo.argtypes = [w.HANDLE, ctypes.POINTER(INFO)]
            K.ReadConsoleOutputCharacterW.argtypes = [w.HANDLE, w.LPWSTR, w.DWORD,
                                                     COORD, ctypes.POINTER(w.DWORD)]
            handle = K.CreateFileW('CONOUT$', 0xC0000000, 3, None, 3, 0, None)
            info = INFO()
            if not K.GetConsoleScreenBufferInfo(handle, ctypes.byref(info)):
                raise ctypes.WinError(ctypes.get_last_error())
            if action == 'resize':
                K.SetConsoleWindowInfo.argtypes = [w.HANDLE, w.BOOL, ctypes.POINTER(RECT)]
                K.SetConsoleScreenBufferSize.argtypes = [w.HANDLE, COORD]
                width = int(text)
                rectangle = RECT(0, 0, min(width, info.window.Right + 1) - 1, 24)
                if not K.SetConsoleWindowInfo(handle, True, ctypes.byref(rectangle)):
                    raise ctypes.WinError(ctypes.get_last_error())
                if not K.SetConsoleScreenBufferSize(handle, COORD(width, max(100, info.size.Y))):
                    raise ctypes.WinError(ctypes.get_last_error())
                K.CloseHandle(handle)
                return {'resized': width}
            count = min(info.size.X * info.size.Y, 1000000)
            buffer = ctypes.create_unicode_buffer(count)
            read = w.DWORD()
            if not K.ReadConsoleOutputCharacterW(handle, buffer, count, COORD(0, 0), ctypes.byref(read)):
                raise ctypes.WinError(ctypes.get_last_error())
            content = buffer.value
            K.CloseHandle(handle)
            return {'width': info.size.X, 'progress': 'isolated progress' in content,
                    'progress_rows': content.count('isolated progress'),
                    'watch_stopped': 'Watch stopped.' in content,
                    'requirements': 'Checking requirements' in content,
                    'product_heading': 'Cost Guard v' in content,
                    'batch_question': 'Terminate batch job' in content,
                    'input_ok': 'OWNED_INPUT_OK' in content,
                    'missing_python': 'could not find Python' in content,
                    'crash': 'command exited with code 1' in content}
        # Target only this experiment's console input; no desktop-wide keys.
        class CHAR(ctypes.Union):
            _fields_ = [('UnicodeChar', w.WCHAR), ('AsciiChar', ctypes.c_char)]
        class KEY(ctypes.Structure):
            _fields_ = [('down', w.BOOL), ('repeat', w.WORD), ('vk', w.WORD),
                        ('scan', w.WORD), ('char', CHAR), ('control', w.DWORD)]
        class EVENT(ctypes.Union):
            _fields_ = [('key', KEY), ('padding', ctypes.c_byte * 16)]
        class INPUT(ctypes.Structure):
            _fields_ = [('type', w.WORD), ('event', EVENT)]
        text = text or "Write-Output 'OWNED_INPUT_OK'\r"
        records = (INPUT * (len(text) * 2))()
        for index, character in enumerate(text):
            for release in (0, 1):
                record = records[index * 2 + release]
                record.type = 1
                record.event.key.down = not release
                record.event.key.repeat = 1
                record.event.key.vk = 13 if character == '\r' else 0
                record.event.key.char.UnicodeChar = character
        handle = K.CreateFileW('CONIN$', 0xC0000000, 3, None, 3, 0, None)
        written = w.DWORD()
        if not K.WriteConsoleInputW(handle, records, len(records), ctypes.byref(written)):
            raise ctypes.WinError(ctypes.get_last_error())
        K.CloseHandle(handle)
        return {'typed': written.value}
    finally:
        K.FreeConsole()


def run(label, shell='pwsh.exe', scenario='watch', width='120', host='console'):
    case = BASE / label
    (case / 'src').mkdir(parents=True)
    (case / 'windows').mkdir()
    shutil.copyfile(ROOT / 'src/windows_launcher.ps1', case / 'src/windows_launcher.ps1')
    relative = {'watch': 'windows/Cost-Guard-Watch.cmd',
                'diagnostics': 'development/user-tools/diagnostics/windows/Cost-Guard-Diagnostics.cmd'}.get(
                    scenario, 'windows/Cost-Guard.cmd')
    target = case / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    wrapper = (ROOT / relative).read_text(encoding='utf-8')
    if shell == 'powershell.exe':
        wrapper = wrapper.replace('where pwsh.exe', 'where cost_guard_absent_shell.exe')
    target.write_text(wrapper, encoding='utf-8')
    driver = case / 'src/windows_launcher.ps1'
    content = driver.read_text(encoding='utf-8')
    content = content.replace("$code = 1", "@{pid=$PID} | ConvertTo-Json -Compress | Set-Content -Encoding UTF8 '" +
                              str(case / 'owner-started.json') + "'\n$code = 1", 1)
    driver.write_text(content, encoding='utf-8')
    with driver.open('a', encoding='utf-8') as stream:
        stream.write("\n@{pid=$PID;code=$LASTEXITCODE} | ConvertTo-Json -Compress | Set-Content -Encoding UTF8 '" +
                     str(case / 'owner-ready.json') + "'\n")
    if scenario == 'missing':
        content = driver.read_text(encoding='utf-8')
        content = content.replace("$ErrorActionPreference = 'Stop'", "$ErrorActionPreference = 'Stop'\nfunction Get-Command { return @() }")
        driver.write_text(content, encoding='utf-8')
    (case / 'cost-guard.py').write_text('''import json, os, time
from pathlib import Path
Path('worker.json').write_text(json.dumps({'pid': os.getpid(), 'owner': os.getppid()}))
try:
    for i in range(100 if '--watch' in __import__('sys').argv else 20):
        print('Cost Guard isolated progress %d' % i, flush=True)
        time.sleep(.2)
except KeyboardInterrupt:
    Path('cancel.json').write_text('{}')
Path('finished.json').write_text('{}')
''', encoding='utf-8')
    if scenario == 'crash':
        with (case / 'cost-guard.py').open('a', encoding='utf-8') as stream:
            stream.write("raise ValueError('isolated launcher crash')\n")
    if scenario == 'diagnostics':
        diagnostics = case / 'development/tools/collect_diagnostics.py'
        diagnostics.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(case / 'cost-guard.py', diagnostics)
    prompt = "'[synthetic git:main] PS> '" if 'decorated' in label else "'PS> '"
    script = case / 'parent.ps1'
    script.write_text(f'''$ErrorActionPreference = 'Stop'
Import-Module PSReadLine -ErrorAction SilentlyContinue
function prompt {{
    @{{pid=$PID}} | ConvertTo-Json -Compress | Set-Content -Encoding UTF8 '{case / 'prompt.json'}'
    {prompt}
}}
Set-Location -LiteralPath '{case}'
& '{target}'
@{{pid=$PID}} | ConvertTo-Json -Compress | Set-Content -Encoding UTF8 '{case / 'returned.json'}'
''', encoding='utf-8')
    command = [shell, '-NoLogo', '-NoProfile', '-NoExit', '-ExecutionPolicy', 'Bypass', '-File', str(script)]
    if host == 'terminal':
        command = ['wt.exe', '-w', 'new', 'new-tab', '--', *command]
    elif host == 'conhost':
        command = ['conhost.exe', *command]
    elif host == 'cmd':
        batch = case / 'parent.cmd'
        batch.write_text('@echo off\r\nprompt TEST_CMD$G\r\ncall "' + str(target) + '"\r\n' +
                         'echo {"pid":0}>"' + str(case / 'cmd-returned.json') + '"\r\n', encoding='utf-8')
        command = ['cmd.exe', '/d', '/k', str(batch)]
    parent = None
    if host == 'explorer':
        os.startfile(target, 'open')
    else:
        parent = subprocess.Popen(command, creationflags=subprocess.CREATE_NEW_CONSOLE)
    try:
        worker_info = None if scenario == 'missing' else wait_file(case / 'worker.json')
        worker = (wait_file(case / 'owner-started.json')['pid'] if worker_info is None else worker_info['pid'])
        if host == 'cmd':
            wait_file(case / 'cmd-returned.json')
            caller = parent.pid
        elif host == 'explorer':
            caller = None
        else:
            caller = wait_file(case / 'returned.json')['pid']
            wait_file(case / 'prompt.json')
        members = bridge(worker, 'members')['members']
        shared = caller in members
        if caller is not None:
            bridge(caller, 'type', 'echo OWNED_INPUT_OK\r')
        owner = wait_file(case / 'owner-started.json')['pid']
        bridge(owner, 'resize', width)
        before = bridge(owner, 'snapshot')
        # Width changes run in the child only; exercise real console layout, no user profile changes.
        if caller is not None:
            bridge(caller, 'type', 'echo CALLER_ALIVE\r')
        if scenario == 'watch':
            time.sleep(1)
            after = bridge(owner, 'snapshot')
            assert after['progress_rows'] > before['progress_rows'], (before, after)
            bridge(worker, 'interrupt')
            wait_file(case / 'cancel.json', 10)
        if scenario != 'missing':
            wait_file(case / 'finished.json', 10)
            if scenario != 'watch':
                ready = wait_file(case / 'owner-ready.json', 10)
                assert ready['code'] == (1 if scenario == 'crash' else 0), ready
        time.sleep(1)
        bridge(owner, 'type', "@{code=$LASTEXITCODE} | ConvertTo-Json -Compress | Set-Content -Encoding UTF8 '" + str(case / 'input.json') + "'\r")
        actual = wait_file(case / 'input.json', 15)
        assert actual['code'] == (9009 if scenario == 'missing' else 1 if scenario == 'crash' else 0), actual
        snapshot = bridge(owner, 'snapshot')
        assert not snapshot['batch_question'], snapshot
        assert snapshot['width'] == int(width), snapshot
        print(json.dumps({'case': label, 'caller_prompt_while_working': caller is not None,
                          'shared_console': shared, 'ctrl_c_received': scenario == 'watch',
                          'console_processes': len(members), 'child_prompt_input': True,
                          'exit_code': actual['code'], 'snapshot': snapshot}), flush=True)
    finally:
        if (case / 'owner-started.json').exists():
            owner = json.loads((case / 'owner-started.json').read_text(encoding='utf-8-sig'))['pid']
            subprocess.run(['taskkill', '/PID', str(owner), '/T', '/F'], capture_output=True, timeout=10)
        # Only descendants of the exact process created by this case.
        if parent is not None:
            subprocess.run(['taskkill', '/PID', str(parent.pid), '/T', '/F'],
                           capture_output=True, timeout=10)
        if (case / 'returned.json').exists():
            caller = json.loads((case / 'returned.json').read_text(encoding='utf-8-sig'))['pid']
            subprocess.run(['taskkill', '/PID', str(caller), '/T', '/F'], capture_output=True, timeout=10)


if __name__ == '__main__':
    if sys.argv[1] == 'bridge':
        print(json.dumps(console_action(int(sys.argv[2]), sys.argv[3], sys.argv[4])))
    else:
        run(*sys.argv[1:])
