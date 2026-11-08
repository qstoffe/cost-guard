"""Finite source-failure confirmation; never evidence of a successful read."""
import time

from src.sources.errors import FailureCode, SourceError, SourceUnavailableError


SOURCE_CONFIRM_SECONDS = 5.0  # One existing selected-source retry interval.


class SourceStatus:
    def __init__(self, monotonic=time.monotonic):
        self.monotonic = monotonic
        self.failed_at = None
        self.retryable = False
        self.verifying = False

    def fail(self, error):
        self.verifying = isinstance(error, SourceError) and error.code == FailureCode.CONCURRENT
        retryable = isinstance(error, SourceError) and not error.terminal and (
            error.watch_retryable or error.code == FailureCode.CONCURRENT or
            isinstance(error, SourceUnavailableError) and error.code == FailureCode.UNKNOWN)
        if self.failed_at is None:
            self.failed_at = self.monotonic()
            self.retryable = retryable
        else:
            self.retryable = self.retryable and retryable

    def clear(self):
        self.failed_at = None
        self.retryable = False
        self.verifying = False

    def state(self, *, retained=False, confirming_initial=False):
        if self.failed_at is None:
            return None
        if self.verifying:
            # Revision churn is incomplete proof, not an unreachable source.
            # Keep retrying with the existing owner cadence regardless of age.
            return 'retrying'
        if (retained or confirming_initial) and self.retryable and self.monotonic() - self.failed_at < SOURCE_CONFIRM_SECONDS:
            return "retrying"
        return "unavailable"
