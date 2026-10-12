"""Short shared retry budget for report startup and initial read-only acquisition.

Watch owns its existing five-second lifecycle instead. No subprocess, Desktop
launch, generation switching or authentication retry occurs in this mechanism.
"""
from __future__ import annotations

import time
from typing import Callable

from .errors import SourceError

REPORT_RETRY_BUDGET_SECONDS = 4.0
REPORT_MAX_FAILURES = 3
REPORT_RETRY_INTERVAL_SECONDS = 0.5


class ReadRecovery:
    def __init__(self, *, monotonic: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        self.monotonic = monotonic
        self.sleep = sleep
        self.deadline: float | None = None
        self.failures = 0
        self.retrying = False
        self.last_error: SourceError | None = None

    def request_timeout(self) -> float:
        if self.retrying and self.deadline is not None:
            remaining = self.deadline - self.monotonic()
            if remaining <= 0 and self.last_error is not None:
                raise self.last_error
            return max(0.001, min(1.0, remaining))
        return 1.0

    def run(self, read: Callable, refresh: Callable | None = None, *, initial_error: SourceError | None = None):
        self.retrying = False
        while True:
            try:
                if initial_error is not None:
                    error, initial_error = initial_error, None
                    raise error
                value = read()
                self.retrying = False
                return value
            except SourceError as error:
                if not error.readiness_retryable:
                    raise
                self.failures += 1
                self.last_error = error
                if self.deadline is None:
                    self.deadline = self.monotonic() + REPORT_RETRY_BUDGET_SECONDS
                remaining = self.deadline - self.monotonic()
                if self.failures >= REPORT_MAX_FAILURES or remaining <= REPORT_RETRY_INTERVAL_SECONDS:
                    raise
                self.sleep(REPORT_RETRY_INTERVAL_SECONDS)
                if self.monotonic() >= self.deadline:
                    raise
                self.retrying = True
                if refresh is not None:
                    refresh(timeout_seconds=self.request_timeout())
