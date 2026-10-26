"""Bounded numeric Web failure facts; no request, identity or provider payloads."""
from threading import Lock
import time

from src.version import VERSION
from .instance_state import SCHEMA
from .process_identity import InstanceConflict


class WebObservations:
    def __init__(self):
        self.lock = Lock()
        self.started = time.monotonic()
        self.next_write = 0
        self.failures = dict(denied=0, invalid=0, busy=0, unavailable=0)
        self.source = "loading"
        self.transitions = 0
        self.write_failed = False

    def response(self, status):
        category = ("denied" if status in (401, 403) else "busy" if status == 429
                    else "unavailable" if status >= 500 else "invalid" if status >= 400 else None)
        if category:
            with self.lock:
                self.failures[category] = min(1_000_000, self.failures[category] + 1)

    def persist(self, host, *, final=False):
        now = time.monotonic()
        if not host.store or (not final and now < self.next_write):
            return
        self.next_write = now + 5
        with host.events.condition:
            source = host.events.current.get("live", {}).get("state", "loading")
        if source not in {"loading", "running", "recovering", "source_unavailable", "failed",
                          "internal_error", "result_too_large"}:
            source = "unknown"
        with self.lock:
            if source != self.source:
                self.transitions = min(1_000_000, self.transitions + 1)
                self.source = source
            value = dict(schema_version=1, instance_schema=SCHEMA, product_version=VERSION,
                         observed_at=int(time.time()), state=host.reason or ("ready" if host.ready else "starting"),
                         source_status=source, source_transitions=self.transitions,
                         uptime_ms=min(2**53 - 1, max(0, int((now - self.started) * 1000))),
                         api_failures=dict(self.failures))
        try:
            host.store.write_diagnostics(value)
            self.write_failed = False
        except (OSError, InstanceConflict):
            # Diagnostics must not turn an otherwise safe shutdown into a failure.
            # Surface absence/staleness; never claim successful persistence.
            self.write_failed = True
