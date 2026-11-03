"""Hidden synthetic launcher shells and cleanup of explicitly published child PIDs."""
import contextlib
from pathlib import Path
import subprocess
import time

from src.web.process_identity import process_identity, terminate_owned


CONSOLE_STUB = (
    "class CostGuardLauncherConsole { static [bool] SetConsoleCtrlHandler("
    "[IntPtr]$handler, [bool]$add) { return $true } }\n"
)


@contextlib.contextmanager
def owned_shell(arguments, root: Path):
    """All fixture descendants publish pid before blocking on root/release.

    Readiness permits 30s for cmd + cold PowerShell + AST/native startup under
    concurrent Full load. Release/exit has its own 10s bound, not a racing timer.
    The fixture also has a 60s emergency lifetime if the controller disappears.
    """
    process = subprocess.Popen(arguments, cwd=root, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    children = {}

    def remember_child():
        marker = root / "pid"
        if marker.exists():
            try:
                pid = int(marker.read_text(encoding="utf-8-sig"))
            except ValueError:
                return  # The child may still be writing its readiness record.
            if pid in children:
                return
            identity = process_identity(pid)
            if identity is not None:
                children[pid] = identity

    try:
        yield process, remember_child
    finally:
        (root / "release").touch()
        remember_child()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()  # Popen retains the exact shell handle.
            process.wait(timeout=5)
        remember_child()  # Also catch a child that entered during late shell startup.
        for pid, identity in children.items():
            if process_identity(pid) == identity:
                terminate_owned(pid, identity)
            deadline = time.monotonic() + 5
            while process_identity(pid) == identity and time.monotonic() < deadline:
                time.sleep(0.02)
            if process_identity(pid) == identity:
                raise AssertionError("Owned synthetic launcher child did not exit")
        process.communicate(timeout=5)


def wait_for_marker(process, marker: Path, remember_child, *, timeout=30):
    deadline = time.monotonic() + timeout
    while not marker.exists() and process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.02)
    remember_child()
    if not marker.exists():
        raise AssertionError(f"Harness startup failed before {marker.name}; shell exit={process.poll()}")


def shell_output(process, remember_child, *, timeout=30):
    """Observe published child identities while draining a finite discovery probe."""
    deadline = time.monotonic() + timeout
    while True:
        remember_child()
        remaining = deadline - time.monotonic()
        try:
            return process.communicate(timeout=max(0, min(0.1, remaining)))
        except subprocess.TimeoutExpired:
            if remaining <= 0:
                raise
