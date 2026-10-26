"""User-private, checkout-keyed instance records and OS-held transition locks."""
from contextlib import contextmanager
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
import uuid

from .process_identity import InstanceConflict

SCHEMA = 1


def checkout_identity(root):
    canonical = os.path.normcase(str(Path(root).resolve(strict=True)))
    return hashlib.sha256(os.fsencode(canonical)).hexdigest()


def _safe(path):
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise InstanceConflict("unsafe_instance_path")
    return info


def _private(path):
    _safe(path)
    if os.name == "nt":
        from ctypes import wintypes
        advapi = ctypes.WinDLL("advapi32", use_last_error=True)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        descriptor = ctypes.c_void_p()
        advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p]
        advapi.SetFileSecurityW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p]
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        # Protected DACL: only the owner, inherited by newly created children.
        if not advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW(
                "D:P(A;OICI;FA;;;OW)", 1, ctypes.byref(descriptor), None):
            raise InstanceConflict("private_state_unavailable")
        try:
            if not advapi.SetFileSecurityW(str(path), 0x80000004, descriptor):
                raise InstanceConflict("private_state_unavailable")
        finally:
            kernel.LocalFree(descriptor)
    else:
        if path.stat().st_uid != os.getuid():
            raise InstanceConflict("foreign_instance_path")
        path.chmod(0o700 if path.is_dir() else 0o600)


class InstanceStore:
    def __init__(self, root, *, data_home=None):
        self.key = checkout_identity(root)
        if data_home is None:
            if os.name == "nt":
                value = os.environ.get("LOCALAPPDATA")
                if not value:
                    raise InstanceConflict("local_app_data_unavailable")
                data_home = Path(value)
            elif os.uname().sysname == "Darwin":
                data_home = Path.home() / "Library/Application Support"
            else:
                data_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
        base = Path(data_home)
        if not base.is_absolute():
            raise InstanceConflict("invalid_app_data")
        base.mkdir(parents=True, exist_ok=True)
        # Reject reparse ancestors instead of silently redirecting private state.
        for item in (base, *base.parents):
            _safe(item)
        self.directory = base / "CostGuard" / "Web" / self.key
        for item in (base / "CostGuard", base / "CostGuard/Web", self.directory):
            item.mkdir(exist_ok=True)
            _private(item)
        self.state_path = self.directory / "instance.json"

    @contextmanager
    def lock(self, timeout=20, *, lifetime=False):
        path = self.directory / ("host.lock" if lifetime else "transition.lock")
        if path.exists() or path.is_symlink():
            _safe(path)
        fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
        stream = os.fdopen(fd, "r+b", buffering=0)
        try:
            _private(path)
            if os.fstat(fd).st_size == 0:
                stream.write(b"0")
            deadline = time.monotonic() + timeout
            while True:
                try:
                    stream.seek(0)
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise InstanceConflict("instance_transition_busy") from None
                    time.sleep(0.05)
            try:
                yield
            finally:
                stream.seek(0)
                if os.name == "nt":
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            stream.close()  # Also releases OS lock on exceptions/crash.

    def read(self):
        try:
            info = _safe(self.state_path)
        except FileNotFoundError:
            return None
        if not stat.S_ISREG(info.st_mode) or info.st_size > 4096:
            raise InstanceConflict("corrupt_instance_state")
        try:
            value = json.loads(self.state_path.read_bytes())
            valid = (isinstance(value, dict) and value.get("schema") == SCHEMA
                     and value.get("checkout") == self.key
                     and re.fullmatch(r"[a-f0-9]{32}", value.get("nonce", ""))
                     and re.fullmatch(r"[a-f0-9]{64}", value.get("control", ""))
                     and type(value.get("pid")) is int and value["pid"] > 0
                     and isinstance(value.get("process"), dict)
                     and set(value["process"]) == {"birth", "image"}
                     and all(isinstance(v, str) and v for v in value["process"].values())
                     and type(value.get("port")) is int and 0 < value["port"] < 65536
                     and value.get("address") == "127.0.0.1"
                     and isinstance(value.get("build"), str)
                     and type(value.get("ready_ns")) is int)
            if not valid:
                raise ValueError()
            return value
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise InstanceConflict("corrupt_instance_state") from None

    def write(self, value):
        path = self.directory / (uuid.uuid4().hex + ".tmp")
        try:
            with open(path, "xb") as stream:
                _private(path)
                stream.write(json.dumps(value, allow_nan=False).encode("utf-8"))
                stream.flush()
                os.fsync(stream.fileno())
            if self.state_path.exists() or self.state_path.is_symlink():
                _safe(self.state_path)
            os.replace(path, self.state_path)
        finally:
            path.unlink(missing_ok=True)

    def remove(self, nonce):
        current = self.read()
        if current and current["nonce"] == nonce:
            self.state_path.unlink()

    def log(self, code):
        # No exceptions, URLs, paths, bootstrap credentials or source data in diagnostics.
        if code not in {"starting", "ready", "stopped", "source_changed",
                        "source_check_unavailable", "runtime_fault", "gui_unavailable",
                        "tray_unavailable", "instance_start_timeout", "browser_open_failed",
                        "configuration_unavailable", "instance_conflict", "gui_or_server_start_failed",
                        "app_preparation_failed"}:
            code = "runtime_fault"
        path = self.directory / "lifecycle.log"
        if path.exists():
            if _safe(path).st_size > 32768:
                path.unlink()
        with open(path, "a", encoding="ascii") as stream:
            _private(path)
            stream.write(f"{int(time.time())} {code}\n")
