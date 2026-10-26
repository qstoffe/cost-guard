"""Renderer-independent cadence and recovery over the existing Watch mechanisms.

One owner calls tick; subscribers never touch the mutable coordinator/service.
CLI retains its terminal wait adapter and uses the same initialize/poll/enrich
operations. Hints trigger authoritative reads, never usage or completion.
"""
from dataclasses import replace
import time

from src.sources.errors import SourceError
from src.sources.connectivity_events import record as record_recovery
from .observation_diagnostics import record_source_error
from .coordinator import SOURCE_RETRY_SECONDS, SOURCE_UNREADABLE_RETRIES, source_failure_kind


class LiveAcquisition:
    def __init__(self, coordinator, *, monotonic=time.monotonic):
        self.coordinator = coordinator
        self.monotonic = monotonic
        self.deadline = 0.0
        self.frame = None
        self.error = None
        self.terminal = False
        self.unreadable = 0
        self.hints = set()
        self.resync = False
        self.observed_at_ms = None
        self.recovery_started = None

    def tick(self):
        owner = self.coordinator
        now = self.monotonic()
        if self.terminal:
            return None
        # Drain a bounded number even if the producer is continuously busy.
        pump = owner._event_pump
        if pump is not None:
            for _ in range(128):
                event = pump.get(0)
                if event is None:
                    break
                self.resync |= event.resync_required
                if event.change is not None and event.change.session_id:
                    if len(self.hints) < 1024:
                        self.hints.add(event.change.session_id)
                    else:
                        self.resync = True
            if self.resync or self.hints:
                self.deadline = min(self.deadline, now + 5)
        try:
            if now >= self.deadline:
                if self.error is not None:
                    refresh = getattr(owner.source, "refresh_connection", None)
                    if callable(refresh):
                        refresh()
                cycle = owner.acquire_cycle(force_resync=self.resync or self.error is not None,
                                            hinted_session_ids=tuple(self.hints))
                if owner.live and (self.resync or self.error is not None):
                    owner._start_event_pump()
                if self.error is not None:
                    record_recovery(owner.selection.selected, "recovered", source_failure_kind(self.error) or "unsupported",
                        **self.error.evidence(), duration_ms=int((self.monotonic() - self.recovery_started) * 1000))
                self.error = None
                self.unreadable = 0
                self.hints.clear()
                self.resync = False
                self.frame = cycle.projection
                self.observed_at_ms = self.frame.now_ms
                self.deadline = self.monotonic() + owner._wait_delay_seconds(self.frame.active_count)
            elif self.error is not None:
                # Retain the last good frame and its active/unknown lifecycle.
                if self.frame is None:
                    return None
                self.frame = replace(owner.status_projection(),
                    status="Source unavailable; last observation retained", status_active=True)
            elif owner.today_ccost.history_pending:
                self.frame = owner.acquire_cycle(enrich=True).projection
            else:
                self.frame = owner.status_projection(seconds_until_check=max(0, int(self.deadline - now)))
        except SourceError as error:
            kind = source_failure_kind(error)
            if self.error is None:
                self.recovery_started = self.monotonic()
                owner.source_recoveries += 1
                record_source_error(owner.selection.selected, kind or "unsupported", owner.source)
                record_recovery(owner.selection.selected, "retrying" if kind else "failed", kind or "unsupported",
                                **error.evidence())
            self.error = error
            owner.last_source_recovery_kind = kind or "unsupported"
            self.unreadable = self.unreadable + 1 if kind == "unreadable" else 0
            self.terminal = kind is None or self.unreadable > SOURCE_UNREADABLE_RETRIES
            if owner._event_pump is not None:
                owner._event_pump.stop()
                owner._event_pump = None
            if owner.observation is None:
                owner._discard_initialization()
            self.deadline = self.monotonic() + SOURCE_RETRY_SECONDS
            if self.frame is not None:
                self.frame = replace(self.frame, status="Source unavailable; last observation retained",
                                     status_active=True)
        return self.frame

    def close(self):
        self.coordinator.close()
