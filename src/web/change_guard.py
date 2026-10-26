"""Best-effort runtime metadata guard, not an atomic-update or reload protocol."""
import os
from pathlib import Path
import stat
import time


class SourceGuard:
    # Explicit runtime surface; documentation/configuration and development are not code.
    FILES = ("cost-guard.py", "cost-guard-web.py", "pyproject.toml", "requirements.txt",
             "config/default-config.jsonc")
    TREES = ("src", "windows/Beta", "macos/Beta")
    SUFFIXES = {".py", ".pyw", ".html", ".css", ".js", ".json", ".svg", ".ico",
                ".png", ".ps1", ".cmd", ".command", ".applescript", ".cs"}
    SKIP = {"__pycache__", ".git", ".venv", "venv", "node_modules", "cache", "logs",
            "diagnostics", "development"}

    def __init__(self, root, *, clock=time.monotonic, interval=5):
        self.root = Path(root).resolve(strict=True)
        self.clock = clock
        self.interval = interval
        self.baseline = self._snapshot()  # Failure here prevents serving normal work.
        self.next_check = clock() + interval
        self.status = "unchanged"

    @staticmethod
    def _safe(info):
        return not (stat.S_ISLNK(info.st_mode) or
                    getattr(info, "st_file_attributes", 0) & 0x400)  # Windows reparse point

    def _snapshot(self):
        result = {}

        def add(path, info):
            if not self._safe(info):
                # Record the link itself, never traverse/read its target.
                result[path.relative_to(self.root).as_posix()] = ("link", info.st_mtime_ns, info.st_size)
            elif stat.S_ISREG(info.st_mode):
                result[path.relative_to(self.root).as_posix()] = (info.st_mtime_ns, info.st_size)

        def walk(path):
            try:
                info = path.lstat()
            except FileNotFoundError:
                return
            if not self._safe(info) or not stat.S_ISDIR(info.st_mode):
                add(path, info)
                return
            with os.scandir(path) as entries:
                for entry in entries:
                    if entry.name in self.SKIP:
                        continue
                    item = Path(entry.path)
                    info = entry.stat(follow_symlinks=False)
                    if self._safe(info) and stat.S_ISDIR(info.st_mode):
                        walk(item)
                    elif item.suffix.lower() in self.SUFFIXES:
                        add(item, info)

        for name in self.FILES:
            path = self.root / name
            unsafe = False
            for parent in reversed(path.relative_to(self.root).parents):
                ancestor = self.root / parent
                try:
                    info = ancestor.lstat()
                except FileNotFoundError:
                    unsafe = True
                    break
                if not self._safe(info):
                    add(ancestor, info)
                    unsafe = True
                    break
            if unsafe:
                continue
            try:
                add(path, path.lstat())
            except FileNotFoundError:
                pass
        for name in self.TREES:
            # Check each ancestor; even a new Beta parent must not escape through a link.
            path = self.root
            for part in Path(name).parts:
                path /= part
                try:
                    info = path.lstat()
                except FileNotFoundError:
                    break
                if not self._safe(info):
                    add(path, info)
                    break
            else:
                walk(path)
        return result

    def check(self):
        if self.status == "source_changed":
            return self.status
        if self.clock() < self.next_check:
            return self.status
        self.next_check = self.clock() + self.interval
        try:
            current = self._snapshot()
        except OSError:
            self.status = "source_check_unavailable"
            return self.status  # Retain original baseline and retry, not proven modification.
        self.status = "source_changed" if current != self.baseline else "unchanged"
        return self.status
