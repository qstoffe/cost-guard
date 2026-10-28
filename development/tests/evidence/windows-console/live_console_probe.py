"""Manual real-installation smoke; requires explicit bounded UI approval.

Run only in a disposable clone, after reviewing console_probe.py. Does not stop
OpenCode; terminates only the exact smoke-owned shell tree. Output is aggregate.
"""
import json
from pathlib import Path
import subprocess
import sys
import time
from console_probe import bridge, wait_file, ROOT, BASE

mode = sys.argv[1]
result = BASE / ('live-' + mode + '.json')
driver = ROOT / 'src/windows_launcher.ps1'
command = f"& '{driver}' -Mode {mode}; @{{code=$LASTEXITCODE}} | ConvertTo-Json -Compress | Set-Content -Encoding UTF8 '{result}'"
owner = subprocess.Popen(['pwsh.exe', '-NoLogo', '-NoProfile', '-NoExit', '-ExecutionPolicy',
                          'Bypass', '-Command', command], creationflags=subprocess.CREATE_NEW_CONSOLE)
try:
    time.sleep(3)
    bridge(owner.pid, 'resize', '120')
    if mode == 'watch':
        time.sleep(12)
        bridge(owner.pid, 'interrupt')
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if len(bridge(owner.pid, 'members')['members']) <= 2:
                break
            time.sleep(.2)
        else:
            raise TimeoutError('Watch process did not exit')
    else:
        wait_file(result, 120)
    time.sleep(1)
    output = BASE / ('live-' + mode + '-input.json')
    bridge(owner.pid, 'type', "@{code=$LASTEXITCODE} | ConvertTo-Json -Compress | Set-Content -Encoding UTF8 '" + str(output) + "'\r")
    status = wait_file(output, 15)
    snapshot = bridge(owner.pid, 'snapshot')
    assert not snapshot['batch_question'], snapshot
    assert status['code'] == 0, status
    print(json.dumps({'mode': mode, 'status': status, 'prompt_input': True, 'snapshot': snapshot}))
finally:
    subprocess.run(['taskkill', '/PID', str(owner.pid), '/T', '/F'], capture_output=True, timeout=10)
