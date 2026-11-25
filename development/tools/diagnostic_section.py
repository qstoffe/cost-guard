"""Fault isolation and numeric error evidence, independent of product subsystems."""
from importlib import import_module
import sqlite3
import time

from src.runtime_errors import recoverable


def error_codes(exc):
    return {key: code for key in ("errno", "winerror", "sqlite_errorcode")
            if type(code := getattr(exc, key, None)) is int and 0 <= code < 2**32}


def section(call, *, phase):
    start = time.monotonic()
    try:
        return call()
    except Exception as exc:
        # A failing section (including imports), or a failing optional logger,
        # must not prevent publishing evidence from surviving sections.
        if not isinstance(exc, (OSError, ValueError, sqlite3.Error)):
            try:
                recoverable(exc, f"diagnostics-{phase}")
            except Exception:
                pass
        cause = exc.__cause__
        result = {"status": "unavailable", "phase": phase, "error_type": type(exc).__name__,
                  "elapsed_ms": round((time.monotonic() - start) * 1000, 2),
                  **error_codes(cause if cause is not None else exc)}
        if cause is not None:
            result["cause_type"] = type(cause).__name__
        return result


def load_section(module, function, *args, phase):
    return section(lambda: getattr(import_module(module), function)(*args), phase=phase)
