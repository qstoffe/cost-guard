"""Minimal Diagnostics result screen: a cleared terminal, or plain redirected text.

The interactive screen keeps only the outcome, the ZIP path and the support
instruction; everything technical lives inside the ZIP and the logs.
"""
from __future__ import annotations

import errno
import os
import sys
import zipfile

CLEAR = "\x1b[2J\x1b[3J\x1b[H"
GREEN, RED, BOLD, RESET = "\x1b[1;92m", "\x1b[1;91m", "\x1b[1m", "\x1b[0m"


def _ansi_terminal(stream) -> bool:
    """True only for a real terminal that will interpret ANSI sequences."""
    try:
        if not stream.isatty() or os.environ.get("TERM") == "dumb":
            return False
    except (AttributeError, OSError, ValueError):
        return False
    if sys.platform != "win32":
        return True
    try:  # Legacy consoles need VT processing switched on; otherwise stay plain.
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(mode.value & 0x0004) or bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except (AttributeError, OSError, ValueError):
        return False


def failure_reason(exc: BaseException) -> str:
    """Short, safe and actionable; never the raw exception message or path."""
    if isinstance(exc, OSError) and exc.errno in {errno.ENOSPC, getattr(errno, "EDQUOT", -1)}:
        return "The disk is full. Free some disk space and run Diagnostics again."
    if isinstance(exc, PermissionError):
        return "The diagnostics folder is not writable or the ZIP file is open in another program."
    if isinstance(exc, (IsADirectoryError, NotADirectoryError, FileExistsError)):
        return "The diagnostics folder contains an item that blocks the ZIP file."
    if isinstance(exc, (zipfile.BadZipFile, ValueError)):
        return "The diagnostic ZIP file could not be verified. Run Diagnostics again."
    return "The diagnostic ZIP file could not be written. Run Diagnostics again."


def render_result(stream=None, *, path=None, email: str = "", error: BaseException | None = None) -> None:
    stream = stream or sys.stdout
    ansi = _ansi_terminal(stream)
    color = ansi and not os.environ.get("NO_COLOR")

    def styled(text: str, style: str) -> str:
        return f"{style}{text}{RESET}" if color else text

    if error is None:
        lines = [styled("Diagnostic file successfully created!", GREEN), "", str(path), "",
                 styled("Please attach this file to an email and send it to:", BOLD), "",
                 styled(email, BOLD)]
    else:
        lines = [styled("Diagnostic file creation failed!", RED), "", "Reason: " + failure_reason(error)]
    # Paths are never wrapped or truncated; the terminal soft-wraps long lines
    # so the full path remains copyable at any width.
    stream.write((CLEAR if ansi else "\n") + "\n".join(lines) + "\n")
    stream.flush()
