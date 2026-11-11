"""Opt-in real read-only installation host; private pipe, no desktop launch or inference."""
import json
import multiprocessing
from pathlib import Path
import sys
from threading import Timer

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.web.host import WebHost


def main():
    if sys.platform == 'win32':
        executable = Path(sys.executable).with_name('pythonw.exe')
        if not executable.is_file():
            raise RuntimeError('probe_gui_interpreter_unavailable')
        multiprocessing.set_executable(str(executable))
    host = WebHost(ROOT)
    # This probe never opens a browser/GUI, exports source records, changes source
    # data, or stops the shared OpenCode service. Its cache belongs to this clone.
    deadline = Timer(600, host.stop)
    try:
        host.start()
        host.publish_ready()
        deadline.start()
        print(json.dumps({'url': host.browser_url()}), flush=True)
        for line in sys.stdin:
            command = json.loads(line)['command']
            if command == 'stop':
                break
            if command != 'jobs-status':
                raise ValueError('unknown_probe_command')
            print(json.dumps({'jobs': [dict(status=row['status'], error=row['error'],
                progress=row['progress'], slices=row.get('slices', 0)) for row in host.jobs._jobs.values()],
                'host_failed': host.failure is not None}), flush=True)
    finally:
        deadline.cancel()
        host.close()


if __name__ == '__main__':
    main()
