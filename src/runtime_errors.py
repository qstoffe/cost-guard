"""Minimal software-fault boundary; no config, integrations or Diagnostics imports.

Messages, source lines, locals and exception objects are never serialized. Stack
identity is useful even when an exception embeds credentials or private payloads.
Only explicit isolated owners may call recoverable(); all other faults are fatal.
"""
from __future__ import annotations

import _thread
from datetime import datetime, timedelta
import hashlib
import os
from pathlib import Path
import platform
import re
import sys
import threading
import time
from typing import Callable

_active: RuntimeErrors | None = None
_OWNED = re.compile(r"cost-guard-(?:(?:errors|metadata)-\d{4}-\d{2}-\d{2}\.log|crash-\d{8}-\d{6}-\d+(?:-\d+)?\.txt)\Z")
_RECOVERY_FILES = frozenset({"watch-recovery.json", "model-metadata.json"})


def diagnostics_hint(root: Path | None = None) -> str:
    """Absolute Diagnostics launcher for this installation/OS; never starts it."""
    try:
        base = Path(root) if root is not None else Path(__file__).resolve().parents[1]
        if sys.platform == "win32":
            target = str(base / "development" / "windows" / "Cost Guard Diagnostics.cmd")
        elif sys.platform == "darwin":
            target = str(base / "development" / "macos" / "Cost Guard Diagnostics.command")
        else:
            target = f'python3 "{base / "development" / "tools" / "collect_diagnostics.py"}"'
        return f"\nNeed help? Run Cost Guard Diagnostics:\n{target}\n"
    except BaseException:
        return ""  # Help text is optional; never mask the original failure.


def emergency(original: BaseException, reporting: BaseException, stream=None) -> None:
    """Never recurse or hide the original failure, even with a broken stderr."""
    text = (f"COST GUARD FAILED\nUnhandled {type(original).__name__}\n"
            f"Crash report could not be written: {type(reporting).__name__}\n" + diagnostics_hint())
    try:
        (stream or sys.stderr).write(text)
        (stream or sys.stderr).flush()
    except BaseException:
        try:
            os.write(2, text.encode("ascii", errors="replace"))
        except BaseException:
            pass  # Last emergency sink: exit status still reports failure.


class RuntimeErrors:
    def __init__(self, root: Path, *, mode: str = "startup", stream=None):
        self.root = Path(root).resolve()
        self.mode, self.phase = mode, "initialization"
        self.stream = stream
        self.version = "unknown"
        self._lock = threading.RLock()
        self._episodes: dict[str, dict] = {}
        self._pending: tuple[BaseException, str, str] | None = None
        self._pending_reported = False
        self._old_hooks = None

    def _path(self, filename: str) -> str:
        try:
            return Path(filename).resolve().relative_to(self.root).as_posix()
        except (OSError, ValueError):
            return "<external>/" + Path(filename).name

    def _stack(self, exc: BaseException) -> str:
        """Full chained stack structure, without unsafe message/source text."""
        result, seen = [], set()
        def visit(value):
            if id(value) in seen:
                return
            seen.add(id(value))
            linked = value.__cause__ or (None if value.__suppress_context__ else value.__context__)
            if linked is not None:
                visit(linked)
                result.append("Chained exception:")
            result.append("Traceback (most recent call last):")
            tb = value.__traceback__
            while tb is not None:
                code = tb.tb_frame.f_code
                result.append(f"  {self._path(code.co_filename)}:{tb.tb_lineno} in {code.co_name}")
                tb = tb.tb_next
            if isinstance(value, SyntaxError):
                result.append(f"  {self._path(value.filename or '<import>')}:{value.lineno} in <import>")
            result.append(f"{type(value).__name__}: [message omitted for privacy]")
            if isinstance(value, BaseExceptionGroup):
                for child in value.exceptions:
                    visit(child)
        visit(exc)
        return "\n".join(result)

    def _identity(self, exc: BaseException, component: str) -> tuple[str, str]:
        tb, frame, local_frame = exc.__traceback__, "<no frame>", ""
        while tb is not None:
            code = tb.tb_frame.f_code
            path = self._path(code.co_filename)
            frame = f"{path}:{tb.tb_lineno} in {code.co_name}"
            if not path.startswith("<external>") and path != "src/runtime_errors.py":
                local_frame = frame
            tb = tb.tb_next
        frame = local_frame or frame
        digest = hashlib.sha256(f"{component}|{type(exc).__name__}|{frame}".encode()).hexdigest()[:16]
        return digest, frame

    def _log_path(self) -> Path:
        return self.root / "logs/errors" / f"cost-guard-errors-{datetime.now().astimezone():%Y-%m-%d}.log"

    def _append(self, text: str) -> Path:
        path = self._log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as target:
            target.write(text + "\n\n")
        return path

    def _details(self, exc: BaseException, component: str, severity: str, thread: str) -> str:
        fingerprint, frame = self._identity(exc, component)
        # Unknown future roots may name threads after private account/session
        # data. Keep known product names; identify everything else by hash.
        if thread not in {"MainThread", "cost-guard-v2-events", "cost-guard-startup-progress", "claude-metadata",
                          "cost-guard-model-metadata"}:
            thread = "thread#" + hashlib.sha256(thread.encode()).hexdigest()[:12]
        return (f"Timestamp: {datetime.now().astimezone().isoformat()}\nCost Guard: {self.version}\n"
                f"Mode: {self.mode}\nPhase: {self.phase}\nSeverity: {severity}\nComponent: {component}\n"
                f"Execution root: {thread}\nException: {type(exc).__name__}\nLocation: {frame}\n"
                f"Fingerprint: {fingerprint}\nOccurrence: 1\n{self._stack(exc)}")

    def _close(self, component: str, outcome: str) -> None:
        episode = self._episodes.get(component)
        if episode is None:
            return
        self._append(f"Timestamp: {datetime.now().astimezone().isoformat()}\nCost Guard: {self.version}\nFingerprint: {episode['fingerprint']}\nComponent: {component}\n"
                     f"Repeated {episode['repeats']} additional times over "
                     f"{time.monotonic() - episode['start']:.1f}s.\n{outcome}")
        del self._episodes[component]

    def _record_recoverable(self, exc: Exception, component: str) -> None:
        """Caller MUST expose ERROR and discard/isolate the failed result."""
        with self._lock:
            fingerprint, _ = self._identity(exc, component)
            old = self._episodes.get(component)
            if old is not None and old["fingerprint"] == fingerprint:
                old["repeats"] += 1
                if time.monotonic() - old["start"] >= 60:
                    self._close(component, "Component still degraded.")
                    self._episodes[component] = dict(fingerprint=fingerprint, start=time.monotonic(), repeats=0)
                return
            self._close(component, "Failure changed.")
            if len(self._episodes) >= 128:
                self._close(next(iter(self._episodes)), "Bounded episode eviction.")
            self._append(self._details(exc, component, "recoverable", threading.current_thread().name))
            self._episodes[component] = dict(fingerprint=fingerprint, start=time.monotonic(), repeats=0)

    def recoverable(self, exc: Exception, component: str) -> None:
        try:
            self._record_recoverable(exc, component)
        except BaseException as reporting:
            emergency(exc, reporting, self.stream)
            raise exc from None  # Reporter failure cannot replace the defect.

    def recovered(self, component: str) -> None:
        with self._lock:
            self._close(component, "Component later recovered.")

    def flush(self) -> None:
        with self._lock:
            for component in tuple(self._episodes):
                self._close(component, "Process execution ended.")

    def fatal(self, exc: BaseException, component: str = "application", thread: str | None = None) -> int:
        try:
            with self._lock:
                directory = self.root / "logs/crashes"
                directory.mkdir(parents=True, exist_ok=True)
                stem = f"cost-guard-crash-{datetime.now():%Y%m%d-%H%M%S}-{os.getpid()}"
                # Exclusive creation is safe across processes and same-second crashes.
                for suffix in range(1000):
                    crash = directory / (stem + (f"-{suffix}" if suffix else "") + ".txt")
                    try:
                        target = crash.open("x", encoding="utf-8")
                        break
                    except FileExistsError:
                        continue
                else:
                    raise FileExistsError("Crash filename capacity exceeded")
                with target:
                    details = self._details(exc, component, "fatal", thread or threading.current_thread().name)
                    log = self._log_path().relative_to(self.root)
                    target.write(f"{details}\nPython: {platform.python_version()} {platform.python_implementation()}\n"
                                 f"OS: {platform.system()} {platform.release()}\nPID: {os.getpid()}\nError log: {log}\n")
                self._append(details + f"\nCrash report: {crash.relative_to(self.root)}")
                _, frame = self._identity(exc, component)
                output = self.stream or sys.stderr
                color = bool(getattr(output, "isatty", lambda: False)())
                output.write(("\x1b[31m" if color else "") + "\nCOST GUARD FAILED\n" +
                             f"Unhandled {type(exc).__name__}\n{frame}\n\nCrash report:\n"
                             f"{crash.relative_to(self.root)}\n" + ("\x1b[0m" if color else "")
                             + ("" if self.mode == "Diagnostics" else diagnostics_hint(self.root)))
                output.flush()
        except BaseException as reporting:
            emergency(exc, reporting, self.stream)
        return 1

    def cleanup(self) -> None:
        """Bounded owned-file cleanup; never creates directories or logs."""
        cutoff = (datetime.now().astimezone() - timedelta(days=30)).timestamp()
        for folder in ("errors", "crashes", "recovery"):
            try:
                directory = self.root / "logs" / folder
                if directory.is_symlink() or directory.parent.is_symlink():
                    continue
                with os.scandir(directory) as entries:
                    for index, entry in enumerate(entries):
                        if index >= 2048:
                            break
                        try:
                            if ((_OWNED.fullmatch(entry.name) or (folder == "recovery" and entry.name in _RECOVERY_FILES)) and not entry.is_symlink()
                                    and entry.is_file(follow_symlinks=False) and entry.stat().st_mtime < cutoff):
                                os.unlink(entry.path)
                        except OSError:
                            pass  # Disposable diagnostics maintenance, not application state.
            except OSError:
                pass

    def _coordinate(self, exc: BaseException, component: str, thread: str) -> None:
        # Unknown worker/finalizer roots have no isolation contract. Preserve the
        # original traceback and wake the main boundary, not default traceback UI.
        with self._lock:
            if self._pending is None:
                self._pending = (exc, component, thread)
                self.fatal(exc, component, thread)
                self._pending_reported = True
        if threading.current_thread() is not threading.main_thread():
            _thread.interrupt_main()

    def check_pending(self) -> None:
        with self._lock:
            pending = self._pending
        if pending is not None:
            raise pending[0]

    def install(self) -> None:
        global _active
        _active = self
        self._old_hooks = sys.excepthook, threading.excepthook, sys.unraisablehook
        sys.excepthook = lambda kind, exc, tb: self.fatal(exc.with_traceback(tb), "sys.excepthook")
        def worker(args):
            try:
                self._coordinate(args.exc_value.with_traceback(args.exc_traceback), "unclassified-worker", getattr(args.thread, "name", "unknown"))
            except BaseException as reporting:
                emergency(args.exc_value, reporting, self.stream)
        def unraisable(args):
            # Never inspect repr(object), err_msg, or finalizer-local data.
            try:
                exc = args.exc_value.with_traceback(args.exc_traceback)
                self._coordinate(exc, "unraisable", threading.current_thread().name)
            except BaseException as reporting:
                emergency(args.exc_value, reporting, self.stream)
        threading.excepthook, sys.unraisablehook = worker, unraisable

    def uninstall(self) -> None:
        global _active
        if self._old_hooks is not None:
            sys.excepthook, threading.excepthook, sys.unraisablehook = self._old_hooks
        _active = None

    def run(self, application: Callable[[], int], *, preserve_hooks: bool = False) -> int:
        try:
            self.install()
            self.cleanup()
            # Stable metadata is optional; a damaged version module is still
            # owned by this boundary, rather than a dependency of the reporter.
            from .version import DISPLAY_VERSION
            self.version = DISPLAY_VERSION
            result = application()
            self.check_pending()
            self.flush()
            return result
        except KeyboardInterrupt:
            if self._pending is not None:
                return 1 if self._pending_reported else self.fatal(*self._pending)
            try:
                self.flush()
            except BaseException as exc:
                return self.fatal(exc)
            return 130  # Watch owns its own clean "Watch stopped." handling.
        except BaseException as exc:
            if self._pending is not None:
                return 1 if self._pending_reported else self.fatal(*self._pending)
            return self.fatal(exc)
        finally:
            try:
                self.flush()
            except BaseException:
                pass  # The original fatal incident has priority over summary I/O.
            if not preserve_hooks:
                self.uninstall()


def recoverable(exc: Exception, component: str) -> None:
    if _active is not None:
        _active.check_pending()
        _active.recoverable(exc, component)


def recovered(component: str) -> None:
    if _active is not None:
        _active.recovered(component)


def check_pending() -> None:
    if _active is not None:
        _active.check_pending()


def context(*, mode: str | None = None, phase: str | None = None) -> None:
    if _active is not None:
        if mode is not None:
            _active.mode = mode
        if phase is not None:
            _active.phase = phase
