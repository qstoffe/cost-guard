"""Native process birth identity; no process-name/port based termination."""
import ctypes
import os
from pathlib import Path
import signal
import subprocess


class InstanceConflict(RuntimeError):
    """An instance cannot safely be identified or stopped (no raw diagnostic text)."""


def _windows_handle(pid, terminate=False):
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000 | (1 if terminate else 0), False, pid)
    if not handle:
        if ctypes.get_last_error() == 87:
            return kernel, None
        raise InstanceConflict("process_identity_unavailable")
    return kernel, handle


def _windows_identity(kernel, handle):
    from ctypes import wintypes
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    times = [wintypes.FILETIME() for _ in range(4)]
    if not kernel.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
        raise InstanceConflict("process_identity_unavailable")
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    code = wintypes.DWORD()
    if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
        raise InstanceConflict("process_identity_unavailable")
    if code.value != 259:
        return None
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    size = wintypes.DWORD(32768)
    image = ctypes.create_unicode_buffer(size.value)
    if not kernel.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(size)):
        raise InstanceConflict("process_identity_unavailable")
    return {"birth": str((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime),
            "image": os.path.normcase(os.path.realpath(image.value))}


def process_identity(pid):
    if type(pid) is not int or pid <= 0:
        raise InstanceConflict("invalid_process")
    if os.name == "nt":
        kernel, handle = _windows_handle(pid)
        if not handle:
            return None
        try:
            return _windows_identity(kernel, handle)
        finally:
            kernel.CloseHandle(handle)
    try:
        if Path("/proc/self/stat").exists():
            text = Path(f"/proc/{pid}/stat").read_text()
            fields = text[text.rfind(")") + 2:].split()
            if fields[0] == "Z":
                return None
            return {"birth": fields[19], "image": os.path.realpath(f"/proc/{pid}/exe")}
        # macOS in-box ps; no command line or environment is collected/logged.
        result = subprocess.run(["/bin/ps", "-p", str(pid), "-o", "lstart=", "-o", "comm="],
                                capture_output=True, text=True, timeout=2, check=False)
        value = result.stdout.strip()
        if not value and result.returncode == 1:
            return None
        if result.returncode or len(value) < 26:
            raise InstanceConflict("process_identity_unavailable")
        return {"birth": value[:24], "image": value[24:].strip()}
    except FileNotFoundError:
        return None
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InstanceConflict("process_identity_unavailable") from exc


def terminate_owned(pid, identity):
    if os.name == "nt":
        from ctypes import wintypes
        kernel, handle = _windows_handle(pid, terminate=True)
        if not handle:
            return
        try:
            if _windows_identity(kernel, handle) != identity:
                raise InstanceConflict("process_identity_changed")
            kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
            if not kernel.TerminateProcess(handle, 1):
                raise InstanceConflict("process_stop_unavailable")
        finally:
            kernel.CloseHandle(handle)
    elif hasattr(os, "pidfd_open") and hasattr(signal, "pidfd_send_signal"):
        try:
            fd = os.pidfd_open(pid)
        except ProcessLookupError:
            return
        try:
            if process_identity(pid) != identity:
                raise InstanceConflict("process_identity_changed")
            signal.pidfd_send_signal(fd, signal.SIGKILL)
        finally:
            os.close(fd)
    else:
        # No atomic process handle on this platform: refuse a PID-reuse race.
        raise InstanceConflict("safe_force_stop_unavailable")
