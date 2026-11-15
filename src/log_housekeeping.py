"""Quiet bounded retention, independent of source/cache acquisition and UI demand."""
from __future__ import annotations

import math
from datetime import datetime
import os
from pathlib import Path
import stat
from threading import Event, Lock, Thread
import time

from .log_paths import (WRITE_LOCK, directory_handle, file_lock, log_bases, log_root,
                        owned_directories, owned_name, safe, safe_path)

RETENTION_SECONDS = 30 * 86400
DAILY_SECONDS = 86400
_PASS_LOCK = Lock()


def fingerprint(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def _remove(root, directory, name, descriptor, cutoff):
    path = directory / name
    info = os.stat(name, dir_fd=descriptor, follow_symlinks=False) if descriptor is not None else path.lstat()
    if (not safe(info) or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or not math.isfinite(info.st_mtime) or info.st_mtime >= cutoff):
        return
    if not WRITE_LOCK.acquire(blocking=False):
        return
    try:
        flags = os.O_RDWR | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
        fd = os.open(name if descriptor is not None else path, flags, dir_fd=descriptor)
        with os.fdopen(fd, "r+b") as target, file_lock(target, blocking=False):
            if fingerprint(os.fstat(target.fileno())) != fingerprint(info):
                return
            current = (os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                       if descriptor is not None else path.lstat())
            if (not safe_path(root, directory) or not safe(current)
                    or fingerprint(current) != fingerprint(info)):
                return
            if os.name != "nt":
                os.unlink(name, dir_fd=descriptor)
                return
        # Windows open handles deny unlink/replacement; close our own handle first.
        if safe_path(root, path) and fingerprint(path.lstat()) == fingerprint(info):
            path.unlink()
    finally:
        WRITE_LOCK.release()


def prune_logs(root: Path, *, now=None, stopping=None, budget_seconds=5):
    """One finite attempt, no creation, logging, recursive deletion or same-run retry."""
    if os.environ.get("COST_GUARD_TEST_MODE") == "1" or not _PASS_LOCK.acquire(blocking=False):
        return
    root = Path(root).absolute()
    deadline = time.monotonic() + budget_seconds
    try:
        wall_time = time.time() if now is None else now
        cutoff = wall_time - RETENTION_SECONDS
        if not math.isfinite(cutoff):
            return
        today = datetime.fromtimestamp(wall_time).astimezone()
        for directory, kind in owned_directories(root):
            if stopping is not None and stopping.is_set() or time.monotonic() >= deadline:
                return
            try:
                with directory_handle(root, directory) as descriptor:
                    with os.scandir(descriptor if descriptor is not None else directory) as entries:
                        for index, entry in enumerate(entries):
                            if (index >= 2048 or time.monotonic() >= deadline
                                    or stopping is not None and stopping.is_set()):
                                break
                            if (entry.name.endswith(f"-{today:%Y-%m-%d}.log")
                                    or entry.name.startswith(f"cost-guard-crash-{today:%Y%m%d}-")):
                                continue  # Current-day reporting remains protected after clock changes.
                            if index and index % 32 == 0 and stopping is not None:
                                if stopping.wait(0.01):
                                    return  # Yield CPU/IO capacity; never poll for source-idleness.
                            if owned_name(entry.name, kind, disposable=True):
                                try:
                                    _remove(root, directory, entry.name, descriptor, cutoff)
                                except (OSError, ValueError, OverflowError):
                                    pass
            except OSError:
                pass
        # Child-first rmdir only; unknown contents, races and all failures survive.
        directories = [path for path, _ in owned_directories(root)]
        directories.extend((*log_bases(root), log_root(root) / "diagnostics"))
        for directory in sorted(set(directories), key=lambda path: len(path.parts), reverse=True):
            if stopping is not None and stopping.is_set() or time.monotonic() >= deadline:
                return
            try:
                if safe_path(root, directory):
                    with directory_handle(root, directory.parent) as descriptor:
                        if descriptor is None:
                            directory.rmdir()
                        else:
                            os.rmdir(directory.name, dir_fd=descriptor)
            except OSError:
                pass
    except (OSError, ValueError, OverflowError):
        pass
    finally:
        _PASS_LOCK.release()


class LogHousekeeping:
    """One daemon per lifetime, interruptible delay/daily waits and bounded shutdown."""
    def __init__(self, root, *, delay=60, interval=DAILY_SECONDS, prune=prune_logs):
        self.root = Path(root).absolute()
        self.delay, self.interval, self.prune = delay, interval, prune
        self.stopping = Event()
        self.thread = None
        self.lock = Lock()

    def start(self):
        with self.lock:
            if self.thread is not None or self.stopping.is_set() or os.environ.get("COST_GUARD_TEST_MODE") == "1":
                return
            try:
                self.thread = Thread(target=self._run, name="cost-guard-log-housekeeping", daemon=True)
                self.thread.start()
            except Exception:
                self.stopping.set()  # Optional maintenance never prevents startup.

    def _run(self):
        if self.stopping.wait(self.delay):
            return
        while not self.stopping.is_set():
            try:
                self.prune(self.root, stopping=self.stopping)
            except Exception:
                pass  # No fatal fault handoff, warning or immediate retry.
            if self.stopping.wait(self.interval):
                return

    def close(self):
        self.stopping.set()
        if self.thread is not None and self.thread.ident is not None:
            self.thread.join(timeout=0.1)
