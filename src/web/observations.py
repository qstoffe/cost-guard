"""Bounded numeric Web failure facts; no request, identity or provider payloads."""
from threading import Lock
import time

from src.source_failure_codes import FailureCode
from src.version import VERSION
from .instance_state import SCHEMA
from .process_identity import InstanceConflict

API_REASONS = frozenset({"request_denied", "authentication_required", "csrf_required",
                         "bootstrap_expired_or_used", "host_identity_changed", "instance_stopping"})
SOURCE_STATES = frozenset({"loading", "starting", "starting_opencode", "running", "retrying",
                           "recovering", "source_unavailable", "failed", "internal_error",
                           "result_too_large", "unknown"})
SOURCE_ERROR_CODES = frozenset(code.value for code in FailureCode)


class WebObservations:
    def __init__(self):
        self.lock = Lock()
        self.started = time.monotonic()
        self.next_write = 0
        self.failures = dict(denied=0, invalid=0, busy=0, unavailable=0)
        self.api_reasons = dict.fromkeys(API_REASONS, 0)
        self.source = "loading"
        self.transitions = 0
        self.write_failed = False
        self.lifecycle_write_failed = False

    def response(self, status, reason=None):
        category = ("denied" if status in (401, 403) else "busy" if status == 429
                    else "unavailable" if status >= 500 else "invalid" if status >= 400 else None)
        if category:
            with self.lock:
                self.failures[category] = min(1_000_000, self.failures[category] + 1)
                if isinstance(reason, str) and reason in API_REASONS:
                    self.api_reasons[reason] = min(1_000_000, self.api_reasons[reason] + 1)

    def lifecycle(self, store, code):
        """Advisory observations must not stop an otherwise usable host."""
        if store:
            try:
                store.log(code)
            except (OSError, InstanceConflict):
                self.lifecycle_write_failed = True

    def persist(self, host, *, final=False):
        now = time.monotonic()
        if not host.store or (not final and now < self.next_write):
            return
        self.next_write = now + 5
        with host.events.condition:
            live = host.events.current.get("live", {})
        source = live.get("state", "loading")
        if source not in SOURCE_STATES:
            source = "unknown"
        with self.lock:
            if source != self.source:
                self.transitions = min(1_000_000, self.transitions + 1)
                self.source = source
            error = live.get("error_code")
            value = dict(schema_version=2, instance_schema=SCHEMA, product_version=VERSION,
                         observed_at=int(time.time()), state=host.reason or ("ready" if host.ready else "starting"),
                         source_status=source, source_transitions=self.transitions,
                         uptime_ms=min(2**53 - 1, max(0, int((now - self.started) * 1000))),
                         api_failures=dict(self.failures), api_reasons=dict(self.api_reasons),
                         source_observed_at_ms=live.get("source_observed_at_ms"),
                         source_error=error if error in SOURCE_ERROR_CODES else None,
                         live_progress=getattr(getattr(host, "live", None), "observation_facts", None),
                         listener_port=host.server.server_port if host.ready and not final else None,
                         config_status=getattr(getattr(host, "dependencies", None), "config_status", "unchecked"),
                         lifecycle_write_failed=self.lifecycle_write_failed)
        try:
            host.store.write_diagnostics(value)
            self.write_failed = False
        except (OSError, InstanceConflict):
            # Diagnostics must not turn an otherwise safe shutdown into a failure.
            # Surface absence/staleness; never claim successful persistence.
            self.write_failed = True
