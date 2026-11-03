"""Operational isolation/backoff for optional model notices, never general cache success."""
from __future__ import annotations

import sqlite3

from src.runtime_errors import recoverable, recovered

NOTICE_BUSY_TIMEOUT_MS = 50
_RETRY_MS = (60_000, 300_000, 900_000, 3_600_000)
_RESOURCE_CODES = frozenset({
    sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED, sqlite3.SQLITE_READONLY,
    sqlite3.SQLITE_IOERR, sqlite3.SQLITE_FULL, sqlite3.SQLITE_CANTOPEN,
    sqlite3.SQLITE_PERM, sqlite3.SQLITE_NOMEM,
})


def operational_cache_failure(exc: Exception) -> bool:
    if isinstance(exc, OSError):
        return True
    code = getattr(exc, "sqlite_errorcode", None)
    if type(code) is int:
        return isinstance(exc, sqlite3.Error) and code & 255 in _RESOURCE_CODES
    # Older runtimes/injected errors may lack structured evidence. Never parse
    # private text. SQLITE_ERROR (SQL/schema), corruption and programming errors
    # with known codes are deliberately NOT classified as resource outages.
    return isinstance(exc, sqlite3.OperationalError)


class NoticeCacheHealth:
    """One bounded failure episode; retries never depend on provider poll cadence."""

    def __init__(self, component: str):
        self.component = component
        self.status = "unknown"
        self.failures = 0
        self.next_retry_ms = 0
        self.error: dict[str, object] = {}

    def attempt(self, work, now_ms: int, *, phase: str):
        if now_ms < self.next_retry_ms:
            return False, None
        try:
            result = work()
        except (OSError, sqlite3.Error) as exc:
            if not operational_cache_failure(exc):
                raise
            self.failures += 1
            self.status = "unavailable"
            self.next_retry_ms = now_ms + _RETRY_MS[min(self.failures - 1, len(_RETRY_MS) - 1)]
            actual_phase = getattr(exc, "cache_phase", phase)
            if actual_phase not in {"connect", "pragma", "read", "write", "commit"}:
                actual_phase = phase
            exc.cache_phase = actual_phase
            code = getattr(exc, "sqlite_errorcode", None)
            self.error = {"phase": actual_phase, "category": type(exc).__name__,
                          "sqlite_code": code if type(code) is int else None}
            recoverable(exc, self.component)
            return False, None
        recovered(self.component)
        self.status = "ok"
        self.failures = self.next_retry_ms = 0
        self.error = {}
        return True, result

    def diagnostics(self):
        return {"status": self.status, "failed_attempts": self.failures,
                "next_retry_ms": self.next_retry_ms or None, **self.error}


class ModelSightings:
    """Shared report/Watch first-sighting evidence; failed inserts are not timestamps."""

    def __init__(self, repository):
        self.repository = repository
        self.health = NoticeCacheHealth("model-first-sighting-cache")
        self._pending: dict[str, str] = {}
        self._observed: dict[str, str] = {}

    def first_seen_at(self, model_id: str, timestamp: str, now_ms: int) -> str | None:
        if model_id in self._observed:
            return self._observed[model_id]
        if model_id not in self._pending and len(self._pending) >= 512:
            self._pending.pop(next(iter(self._pending)))
        timestamp = self._pending.setdefault(model_id, timestamp)
        ok, value = self.health.attempt(lambda: self.repository.get_or_create_model_first_seen_at(
            model_id, timestamp, busy_timeout_ms=NOTICE_BUSY_TIMEOUT_MS), now_ms, phase="write")
        if ok:
            self._pending.pop(model_id, None)
            if len(self._observed) >= 512:
                self._observed.pop(next(iter(self._observed)))
            self._observed[model_id] = value
        return value if ok else None
