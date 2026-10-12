"""Typed, message-safe source failures shared by acquisition and recovery."""
from __future__ import annotations

import http.client
import socket
from enum import StrEnum


class FailureCode(StrEnum):
    UNKNOWN = "unknown_source_failure"
    REGISTRATION_MISSING = "registration_missing"
    REGISTRATION_INVALID = "registration_invalid"
    REGISTRATION_UNREADABLE = "registration_unreadable"
    ENDPOINT_UNRESPONSIVE = "endpoint_unresponsive"
    REFUSED = "connection_refused"
    RESET = "connection_reset"
    DISCONNECTED = "connection_disconnected"
    TIMEOUT = "connection_timeout"
    AUTH = "http_auth_failure"
    HTTP = "http_status_failure"
    VERSION = "unsupported_version"
    SCHEMA = "unsupported_schema"
    DATA = "invalid_data"
    CONCURRENT = "concurrent_source_change"
    V1_MISSING = "v1_database_missing"
    V1_UNREADABLE = "v1_database_unreadable"


READINESS_CODES = frozenset({
    FailureCode.REGISTRATION_MISSING, FailureCode.REGISTRATION_UNREADABLE,
    FailureCode.ENDPOINT_UNRESPONSIVE, FailureCode.REFUSED, FailureCode.RESET,
    FailureCode.DISCONNECTED, FailureCode.TIMEOUT,
})
TERMINAL_CODES = frozenset({FailureCode.AUTH, FailureCode.VERSION, FailureCode.SCHEMA,
                            FailureCode.REGISTRATION_INVALID})


class SourceError(RuntimeError):
    """A stable classification; details never contain arbitrary transport text."""

    default_code = FailureCode.UNKNOWN

    def __init__(self, message: str, *, code: FailureCode | str | None = None,
                 phase: str = "unknown", exception_type: str = "",
                 http_status: int | None = None, generation: str = ""):
        super().__init__(message)
        self.code = FailureCode(code) if code is not None else self.default_code
        self.phase = phase
        self.exception_type = exception_type
        self.http_status = http_status
        self.generation = generation

    @property
    def readiness_retryable(self) -> bool:
        return self.code in READINESS_CODES or (self.code == FailureCode.HTTP and self.http_status in (502, 503, 504))

    @property
    def watch_retryable(self) -> bool:
        return self.readiness_retryable or self.code in {FailureCode.V1_MISSING, FailureCode.V1_UNREADABLE}

    @property
    def terminal(self) -> bool:
        return self.code in TERMINAL_CODES or isinstance(self, SourceSchemaError)

    def evidence(self) -> dict[str, object]:
        return {"category": self.code.value, "phase": self.phase,
                "exception_type": self.exception_type, "http_status": self.http_status}


class SourceUnavailableError(SourceError):
    """The requested source is absent or cannot currently be read."""


class SourceSchemaError(SourceError):
    """A deterministic unsupported source contract; never indefinitely retried."""

    default_code = FailureCode.SCHEMA


class SourceDataError(SourceError):
    """Source data cannot be normalized safely."""

    default_code = FailureCode.DATA


class SourceConcurrentChangeError(SourceDataError):
    """Valid data changed while reading; no partial snapshot may escape."""

    default_code = FailureCode.CONCURRENT


class SourceResyncRequiredError(SourceUnavailableError):
    """A non-replayable stream ended; callers must resnapshot authoritative state."""

    default_code = FailureCode.DISCONNECTED


def transport_failure(exc: BaseException, *, phase: str) -> SourceUnavailableError:
    if isinstance(exc, ConnectionRefusedError):
        code = FailureCode.REFUSED
    elif isinstance(exc, http.client.RemoteDisconnected):
        code = FailureCode.DISCONNECTED
    elif isinstance(exc, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
        code = FailureCode.RESET
    elif isinstance(exc, (TimeoutError, socket.timeout)):
        code = FailureCode.TIMEOUT
    elif isinstance(exc, OSError):
        code = FailureCode.ENDPOINT_UNRESPONSIVE
    else:
        code = FailureCode.UNKNOWN
    return SourceUnavailableError("OpenCode V2 service could not be reached", code=code,
                                  phase=phase, exception_type=type(exc).__name__, generation="v2")


def http_failure(status: int, *, phase: str) -> SourceUnavailableError:
    return SourceUnavailableError(f"OpenCode V2 API returned HTTP {status}",
        code=FailureCode.AUTH if status in (401, 403) else FailureCode.HTTP,
        phase=phase, http_status=status, generation="v2")


def compatibility_failure(error: SourceError) -> bool:
    """Only unsupported routes/shapes justify probing older read contracts."""
    return (error.code == FailureCode.SCHEMA or
            (error.code == FailureCode.HTTP and error.http_status in (400, 404, 405, 422)))
