"""Finite source-failure confirmation; never evidence of a successful read."""
import time
from uuid import uuid4

from src.sources.errors import FailureCode, SourceError, SourceUnavailableError


SOURCE_CONFIRM_SECONDS = 5.0  # One existing selected-source retry interval.


class SourceStatus:
    def __init__(self, monotonic=time.monotonic):
        self.monotonic = monotonic
        self.failed_at = None
        self.retryable = False
        self.verifying = False
        self.check_id = 0
        self.reachability_failed_at = None
        self.failed_checks = 0
        self.reachable = False
        self.health_owner = uuid4().hex

    def fail(self, error):
        self.check_id += 1
        self.reachable = False
        # Only real selected-source transport failures corroborate an outage.
        # Revision/schema/auth, local permissions and rich-worker faults do not.
        transport = isinstance(error, SourceError) and (
            error.code in {FailureCode.REGISTRATION_MISSING, FailureCode.ENDPOINT_UNRESPONSIVE,
                FailureCode.REFUSED, FailureCode.RESET, FailureCode.DISCONNECTED, FailureCode.TIMEOUT,
                FailureCode.V1_MISSING} or error.code == FailureCode.HTTP and error.http_status in (502, 503, 504))
        if transport:
            if self.reachability_failed_at is None:
                self.reachability_failed_at = self.monotonic()
            self.failed_checks += 1
        else:
            self.reachability_failed_at = None
            self.failed_checks = 0
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
        self.check_id += 1
        self.reachable = True
        self.reachability_failed_at = None
        self.failed_checks = 0
        self.failed_at = None
        self.retryable = False
        self.verifying = False

    def reachability(self):
        return dict(owner=self.health_owner, check_id=self.check_id, reachable=self.reachable, failed_checks=self.failed_checks,
            unavailable_seconds=int(max(0, self.monotonic() - self.reachability_failed_at))
                if self.reachability_failed_at is not None else 0)

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
