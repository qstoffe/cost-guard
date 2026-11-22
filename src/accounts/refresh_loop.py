"""Bounded account-only clock, independent of source hydration and terminal wakes."""
from __future__ import annotations

import threading
import time

from .acquisition import AccountAcquisition, AccountUpdate


class AccountRefreshLoop:
    """One scheduler plus at most one worker per configured adapter, no overflow.

    The scheduler alone touches discovery/acquisition. The main thread consumes a
    coalesced mailbox; a stalled renderer/source cannot grow a queue of results.
    A timed-out call keeps its lane until it really returns, never a replacement
    thread or a second call for the same adapter/credential generation.
    """

    def __init__(self, providers, source_id, *, clock=time.monotonic, wall_ms=None, evidence_sink=None):
        self.clock = clock
        self.wall_ms = wall_ms or (lambda: time.time_ns() // 1_000_000)
        self.engine = AccountAcquisition(providers, source_id, continuous=True, clock=clock, wall_ms=self.wall_ms)
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._update: AccountUpdate | None = None
        self._diagnostics: dict[str, object] = {}
        self._discovery_at = float("-inf")
        self._pending = False
        self._published: dict[int, float] = {}
        self._slot_keys: dict[int, set[tuple[str, str, str]]] = {}
        self._revisions: dict[int, object] = {}
        self._publication_delay = 0.0
        self._display: dict[str, object] = {}
        self._display_at: int | None = None
        self._evidence_sink = evidence_sink
        self._evidence_at = float("-inf")

    def start(self, now_ms: int) -> bool:
        if self._thread is None and not self._stop.is_set():
            self._thread = threading.Thread(target=self._run, name="cost-guard-account-refresh", daemon=True)
            self._thread.start()
        return False  # Background work never invokes terminal progress.

    def _run(self) -> None:
        try:
            while not self._stop.is_set():
                self.tick()
                self._stop.wait(0.1)
        finally:
            self.engine.close()

    def tick(self) -> None:
        """One deterministic scheduler turn; also used with controlled clocks."""
        if self._stop.is_set():
            return
        now, wall = self.clock(), int(self.wall_ms())
        # Discover before draining results so obsolete credentials never publish.
        if now >= self._discovery_at:
            self.engine.start(wall)
            self._discovery_at = now + 5.0
        update = self.engine.poll(wall)
        with self._lock:
            self._pending = self.engine.pending
            if update is not None:
                keys = set(update.observed_keys)
                if self._update is not None:
                    keys.update(self._update.observed_keys)
                self._update = AccountUpdate(update.snapshots, tuple(keys), update.observed_at_ms)
                self._slot_keys = {slot: {item.key for item in snapshots} for slot, snapshots in self.engine._snapshots.items()}
            for slot, state in self.engine.refresh.items():
                if slot in self._revisions and self._revisions[slot] != state.revision:
                    self._published.pop(slot, None)
                self._revisions[slot] = state.revision
                state.published = self._published.get(slot)
            self._diagnostics = {**self.engine.diagnostics(include_observations=False),
                                 "providers": {str(slot): state.diagnostics(now)
                                               for slot, state in self.engine.refresh.items()},
                                 "blocked_lanes": sum(attempt.expired for attempt in self.engine._running.values()),
                                 "scheduler_state": "running", "publication_delay_seconds": self._publication_delay,
                                 "watch": self._display,
                                 "display_age_seconds": max(0.0, (wall - self._display_at) / 1000)
                                 if self._display_at is not None else None}
            evidence = self._diagnostics
        if self._evidence_sink is not None and now >= self._evidence_at:
            self._evidence_sink({**evidence, "quota_observations": self.engine.observations.diagnostics(wall)})
            self._evidence_at = now + 5.0

    def set_display(self, evidence: dict[str, object]) -> None:
        with self._lock:
            self._display = evidence
            self._display_at = int(self.wall_ms())

    def poll(self, now_ms: int) -> AccountUpdate | None:
        with self._lock:
            update, self._update = self._update, None
            if update is not None:
                # Publication is consumption by Watch, not completion on a worker.
                successful = {item.key for item in update.snapshots if item.key in update.observed_keys
                              and item.availability in {"available", "partial"}}
                for slot, keys in self._slot_keys.items():
                    if keys & successful:
                        self._published[slot] = self.clock()
                observed = dict(update.observed_at_ms)
                if successful:
                    self.engine.observations.published({key: observed[key] for key in successful if key in observed}, now_ms)
                    self._publication_delay = max(
                        (max(0.0, (now_ms - observed[key]) / 1000) for key in successful if key in observed),
                        default=0.0)
                self._diagnostics["publication_delay_seconds"] = self._publication_delay
            return update

    @property
    def pending(self) -> bool:
        with self._lock:
            return self._pending

    def diagnostics(self) -> dict[str, object]:
        with self._lock:
            return {**self._diagnostics, "quota_observations": self.engine.observations.diagnostics(int(self.wall_ms()))}

    def close(self) -> None:
        self._stop.set()
        self.engine.cancel()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        else:
            self.engine.close()
        with self._lock:
            self._update = None
