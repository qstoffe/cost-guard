"""Bounded source-operation evidence and read-only recovery classification.

No raw exception messages, endpoints, source identities or payloads are retained.
The runtime operation remains authoritative even when evidence persistence fails.
"""
from __future__ import annotations

from functools import wraps
import time

from .errors import SourceError
from .connectivity_events import record


class SourceConnectivity:
    def __init__(self, generation: str):
        self.generation = generation
        self.registration = "unknown"
        self.version = "unknown"
        self.last_failure: dict[str, object] = {}
        self.attempts = self.recoveries = self.episode_attempts = 0
        self.started: float | None = None
        self.status = "unknown"

    def failed(self, error: SourceError, phase: str) -> None:
        self.attempts += 1
        self.episode_attempts += 1
        evidence = error.evidence()
        if error.phase == "registration":
            self.registration = error.code.value
        evidence["phase"] = phase if error.phase == "unknown" else error.phase
        transition = self.started is None or evidence != self.last_failure
        self.started = time.monotonic() if self.started is None else self.started
        self.status = "incompatible" if error.terminal else "unavailable" if error.readiness_retryable else "unreadable"
        self.last_failure = evidence
        if transition:
            record(self.generation, "retrying", self.status if self.status != "incompatible" else "unsupported",
                   **evidence, attempts=self.episode_attempts)

    def succeeded(self) -> None:
        if self.started is not None:
            self.recoveries += 1
            record(self.generation, "recovered", "available", **self.last_failure,
                   attempts=self.episode_attempts, duration_ms=int((time.monotonic() - self.started) * 1000))
        self.started = None
        self.episode_attempts = 0
        self.status = "healthy"

    def snapshot(self) -> dict[str, object]:
        return {"collection_status": "observed", "generation": self.generation,
                "registration": self.registration, "service_version": self.version,
                "status": self.status, "last_failure": dict(self.last_failure),
                "failed_attempts": self.attempts, "recoveries": self.recoveries,
                "degraded_ms": int((time.monotonic() - self.started) * 1000) if self.started else 0}


def observed(phase: str):
    """Observe complete source operations, not harmless compatibility-route probes."""
    def decorate(function):
        @wraps(function)
        def call(self, *args, **kwargs):
            def read():
                try:
                    return function(self, *args, **kwargs)
                except SourceError as error:
                    if not error.generation:
                        error.generation = self._connectivity.generation
                    if error.phase == "unknown":
                        error.phase = phase
                    self._connectivity.failed(error, phase)
                    raise
            recovery = self.read_recovery
            value = recovery.run(read, self.refresh_connection) if recovery is not None else read()
            self._connectivity.succeeded()
            return value
        return call
    return decorate
