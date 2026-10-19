"""Bounded provider work: workers acquire; the caller alone applies observations.

Daemon workers have no terminal or report state. Timed-out jobs retain their
worker slot until the call really ends; retries never multiply stuck requests.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from copy import copy
from queue import Empty, Queue
import threading
import time
from typing import Callable, Sequence

from src.domain import AccountRef, AccountSnapshot, AccountUsageStatus
from src.runtime_errors import recoverable, recovered
from .base import normalize_quota
from .discovery import AccountCandidate, AccountDiscovery
from .refresh_policy import ProviderRefresh, WATCH_TIMEOUT_SECONDS, transient_failure
from .quota_observations import QuotaObservations

WORKERS = 4
PROVIDER_TIMEOUT_SECONDS = 45.0
REPORT_REMAINING_WAIT_SECONDS = 15.0


@dataclass(frozen=True, slots=True)
class AccountUpdate:
    snapshots: tuple[AccountSnapshot, ...]
    observed_keys: tuple[tuple[str, str, str], ...]
    observed_at_ms: tuple[tuple[tuple[str, str, str], int], ...] = ()


@dataclass(slots=True)
class _Attempt:
    sequence: int
    candidate: AccountCandidate
    deadline: float
    expired: bool = False


def _failure(candidate: AccountCandidate, previous: Sequence[AccountSnapshot], source_id: str,
             now_ms: int, *, internal: bool = False, timeout: bool = False) -> tuple[AccountSnapshot, ...]:
    provider_id = candidate.provider.provider_id
    if candidate.records is not None:
        old = {(s.ref.source_instance, s.ref.source_account): s.ref for s in previous}
        refs = tuple(old.get((r.ref.source_instance, r.ref.source_account), replace(r.ref, provider_id=provider_id))
                     for r in candidate.records)
    else:
        refs = tuple(item.ref for item in previous)
    if not refs:
        refs = (AccountRef(source_id, provider_id, source_account=f"adapter:{candidate.slot}"),)
    reason = ("ERROR: Optional account provider refresh failed internally" if internal else
              "Account request timed out" if timeout else "Account request unavailable")
    prior = {item.key: item for item in previous}
    return tuple(replace(prior.get(ref.key) or AccountSnapshot(
                     ref, now_ms, getattr(candidate.provider, "display_name", provider_id),
                     capacity_kind=getattr(candidate.provider, "capacity_kind", "usage_limit")),
                 fetched_at_ms=now_ms, quotas=(), billing=(), availability="error", reason=reason,
                 status=AccountUsageStatus.UNKNOWN, warnings=(), usage_attribution_complete=False,
                 observations={"parser_reason": "software_failure" if internal else "timeout" if timeout else "network_failure"})
                 for ref in refs)


class AccountAcquisition:
    def __init__(self, providers: Sequence[object], source_id: str, *, workers: int = WORKERS,
                 timeout: float = PROVIDER_TIMEOUT_SECONDS, clock: Callable[[], float] = time.monotonic,
                 continuous: bool = False, wall_ms: Callable[[], int] | None = None):
        self.discovery = AccountDiscovery(providers)
        self.source_id, self.timeout, self.clock = source_id, timeout, clock
        self.continuous = continuous
        self.wall_ms = wall_ms or (lambda: time.time_ns() // 1_000_000)
        self.limit = max(1, len(providers)) if continuous else max(1, min(WORKERS, workers))
        if continuous:
            self.timeout = min(timeout, WATCH_TIMEOUT_SECONDS)
        self.refresh: dict[int, ProviderRefresh] = {}
        self.observations = QuotaObservations(continuous=continuous)
        self._desired: dict[int, AccountCandidate] = {}
        self._observed_at_ms: dict[tuple[str, str, str], int] = {}
        self._stop = threading.Event()
        self._jobs: Queue = Queue(self.limit)
        self._results: Queue = Queue()
        self._threads: list[threading.Thread] = []
        self._sequence = 0
        self._waiting: dict[int, AccountCandidate] = {}
        self._running: dict[int, _Attempt] = {}
        self._snapshots: dict[int, tuple[AccountSnapshot, ...]] = {}
        self._changed_keys: set[tuple[str, str, str]] = set()
        self.checks_started = 0
        self.discovery_seconds = 0.0
        self.providers_discovered = 0
        self._started_at: float | None = None

    @property
    def snapshots(self) -> tuple[AccountSnapshot, ...]:
        by_key = {item.key: item for slot in sorted(self._snapshots) for item in self._snapshots[slot]}
        return tuple(by_key.values())

    @property
    def pending(self) -> bool:
        waiting = any(slot not in self._running and (not self.continuous or self.clock() >= self.refresh[slot].due)
                      for slot in self._waiting)
        return waiting or any(not attempt.expired for attempt in self._running.values())

    def _publish(self, slot: int, snapshots: tuple[AccountSnapshot, ...], *, observed=None) -> None:
        self._snapshots[slot] = snapshots
        self._changed_keys.update(item.key for item in snapshots if observed is None or item.key in observed)
        present = {item.key for values in self._snapshots.values() for item in values}
        self._observed_at_ms = {key: value for key, value in self._observed_at_ms.items() if key in present}

    def _retry_candidate(self, candidate: AccountCandidate) -> AccountCandidate:
        if not self.continuous or not self.refresh[candidate.slot].retry_scheduled or not candidate.records:
            return candidate
        failed = {(item.ref.source_instance, item.ref.source_account)
                  for item in self._snapshots.get(candidate.slot, ()) if transient_failure(item)}
        records = tuple(record for record in candidate.records
                        if (record.ref.source_instance, record.ref.source_account) in failed)
        if not records:
            return candidate
        provider = copy(candidate.provider)
        provider.credential_records = records
        return replace(candidate, provider=provider, records=records)

    def _apply(self, candidate: AccountCandidate, accounts: tuple[AccountSnapshot, ...]) -> None:
        """A targeted retry observes only its pinned records, not cached neighbors."""
        previous = self._snapshots.get(candidate.slot, ())
        locators = {(r.ref.source_instance, r.ref.source_account) for r in candidate.records or ()}
        desired = self._desired.get(candidate.slot)
        targeted = desired is not None and candidate.records != desired.records
        untouched = tuple(item for item in previous if targeted
                          and (item.ref.source_instance, item.ref.source_account) not in locators)
        incoming = {item.key for item in accounts + untouched}
        removed = tuple(replace(item, quotas=(), billing=(), plan=None, availability="unavailable",
                                reason="Account no longer configured", observations={"parser_reason": "auth_failure"})
                        for item in previous if item.key not in incoming and item.availability != "unavailable")
        self._publish(candidate.slot, accounts + untouched + removed, observed={item.key for item in accounts + removed})

    def _timeout(self, attempt: _Attempt, now_ms: int, completed_at: float) -> None:
        candidate = attempt.candidate
        accounts = _failure(candidate, self._snapshots.get(candidate.slot, ()), self.source_id, now_ms, timeout=True)
        self._apply(candidate, accounts)
        self.refresh[candidate.slot].complete((), completed_at, timeout=True)
        self._record(attempt, accounts, now_ms)

    def _record(self, attempt, accounts, observed_ms):
        state = self.refresh[attempt.candidate.slot]
        self.observations.record(attempt.candidate.slot, attempt.candidate.revision, accounts,
                                 at_ms=observed_ms, duration=state.duration, outcome=state.outcome,
                                 provider_id=attempt.candidate.provider.provider_id)

    def start(self, now_ms: int) -> bool:
        if self._stop.is_set():
            return False
        started = self.clock()
        if self._started_at is None:
            self._started_at = started
        candidates = self.discovery.discover()
        self.discovery_seconds = max(0.0, self.clock() - started)
        self.providers_discovered = len(candidates)
        desired = {item.slot: item for item in candidates}
        self._desired = desired
        for slot, candidate in desired.items():
            state = self.refresh.get(slot)
            if state is None or state.revision != candidate.revision:
                self.refresh[slot] = ProviderRefresh(candidate.revision)
                if state is not None and slot in self._snapshots:
                    self._publish(slot, tuple(replace(item, quotas=(), billing=(), availability="unavailable",
                                                     reason="Account credentials changed; verification pending",
                                                     observations={"parser_reason": "auth_failure"})
                                              for item in self._snapshots[slot]))
        # Explicitly disappeared credentials must not remain verified capacity.
        for slot, previous in tuple(self._snapshots.items()):
            candidate = desired.get(slot)
            if slot in self.discovery.failed_slots and candidate is None:
                self._publish(slot, tuple(replace(item, fetched_at_ms=now_ms, quotas=(), billing=(), availability="error",
                                                 reason="Account discovery unavailable", observations={"parser_reason": "discovery_failure"})
                                          for item in previous))
                continue
            locators = {(r.ref.source_instance, r.ref.source_account) for r in candidate.records or ()} if candidate else set()
            if candidate is not None and candidate.records is None:
                continue  # Other identity sources own their signed-out contract.
            removed = tuple(replace(item, fetched_at_ms=now_ms, quotas=(), billing=(), plan=None,
                                    availability="unavailable", reason="Account no longer configured",
                                    observations={"parser_reason": "auth_failure"})
                            if (item.ref.source_instance, item.ref.source_account) not in locators else item for item in previous)
            if removed != previous:
                self._publish(slot, removed)
        for slot, attempt in self._running.items():
            current = desired.get(slot)
            if current is None or current.revision != attempt.candidate.revision:
                attempt.expired = True  # Ignore output pinned to removed/changed credentials.
        self._waiting = {slot: item for slot, item in desired.items()
                         if slot not in self._running or self._running[slot].expired}
        self._schedule()
        return any(item.records for item in candidates)

    def _schedule(self) -> None:
        if self._stop.is_set():
            return
        for slot, candidate in tuple(self._waiting.items()):
            if len(self._running) >= self.limit:
                break
            if slot in self._running:
                continue
            state = self.refresh[slot]
            # Targeted retries must not postpone healthy credentials in the same
            # adapter indefinitely: their regular full inventory still runs.
            healthy = any(item.availability in {"available", "partial"} for item in self._snapshots.get(slot, ()))
            periodic = self.continuous and healthy and self.clock() >= state.normal_due
            if self.continuous and self.clock() < state.due and not periodic:
                continue
            selected = candidate if periodic else self._retry_candidate(candidate)
            self._sequence += 1
            attempt = _Attempt(self._sequence, selected, self.clock() + self.timeout)
            self._running[slot] = attempt
            if periodic:
                state.due = min(state.due, state.normal_due)
            state.begin(self.clock(), full=selected.records == candidate.records,
                        retry=state.retry_scheduled and not periodic)
            del self._waiting[slot]
            self._jobs.put_nowait((attempt.sequence, selected, self._snapshots.get(slot, ()), self.clock()))
            self.checks_started += 1
        while len(self._threads) < min(self.limit, len(self._running)):
            thread = threading.Thread(target=self._worker, name="cost-guard-account-quota", daemon=True)
            self._threads.append(thread)
            thread.start()

    def _worker(self) -> None:
        while not self._stop.is_set():
            try:
                sequence, candidate, previous, dispatched_at = self._jobs.get(timeout=0.1)
            except Empty:
                continue
            if self._stop.is_set():
                return
            provider = candidate.provider
            worker_wait = max(0.0, self.clock() - dispatched_at)
            component = f"account-provider-{candidate.slot}"
            now_ms = self.wall_ms()
            try:
                health = provider.probe()
                if not (health.available and health.healthy):
                    accounts = _failure(candidate, previous, self.source_id, now_ms) if previous else ()
                elif hasattr(provider, "get_account_snapshots"):
                    accounts = tuple(provider.get_account_snapshots())
                else:
                    ref = AccountRef(self.source_id, provider.provider_id, source_account=f"adapter:{candidate.slot}")
                    accounts = (normalize_quota(provider.get_quota_snapshot(), ref,
                                getattr(provider, "display_name", provider.provider_id)),)
                if any(not isinstance(item, AccountSnapshot) for item in accounts):
                    raise TypeError("Invalid provider snapshot")
            except Exception as exc:
                internal = not isinstance(exc, OSError)
                if internal and not self._stop.is_set():
                    recoverable(exc, component)
                accounts = _failure(candidate, previous, self.source_id, now_ms, internal=internal)
            else:
                if not self._stop.is_set():
                    recovered(component)
            if not self._stop.is_set():
                self._results.put((sequence, candidate.slot, accounts, self.clock(), self.wall_ms(), worker_wait))

    def poll(self, now_ms: int) -> AccountUpdate | None:
        if self._stop.is_set():
            return None
        while True:
            try:
                sequence, slot, accounts, completed_at, observed_ms, worker_wait = self._results.get_nowait()
            except Empty:
                break
            attempt = self._running.get(slot)
            if attempt is None or attempt.sequence != sequence:
                continue
            del self._running[slot]
            if not attempt.expired:
                self.refresh[slot].worker_wait = worker_wait
            if not attempt.expired and completed_at > attempt.deadline:
                self._timeout(attempt, now_ms, completed_at)
            elif not attempt.expired:
                # Accounts absent in a completed, successful inventory are no
                # longer configured; pending providers are never treated absent.
                self._apply(attempt.candidate, accounts)
                self.refresh[slot].complete(accounts, completed_at)
                self._record(attempt, accounts, observed_ms)
                self._observed_at_ms.update((item.key, observed_ms) for item in accounts
                                            if item.availability in {"available", "partial"})
        for slot, attempt in self._running.items():
            if not attempt.expired and self.clock() >= attempt.deadline:
                attempt.expired = True
                self._timeout(attempt, now_ms, self.clock())
        if self.continuous:
            self._waiting = {slot: item for slot, item in self._desired.items() if slot not in self._running}
        self._schedule()
        if not self._changed_keys:
            return None
        update = AccountUpdate(self.snapshots, tuple(self._changed_keys), tuple(self._observed_at_ms.items()))
        self._changed_keys.clear()
        return update

    def finish(self, now_ms: int, *, remaining_wait: float = REPORT_REMAINING_WAIT_SECONDS) -> tuple[AccountSnapshot, ...]:
        deadline = self.clock() + max(0.0, remaining_wait)
        while self.pending and self.clock() < deadline:
            self.poll(now_ms)
            if self.pending:
                self._stop.wait(min(0.02, max(0.0, deadline - self.clock())))
        self.poll(now_ms)
        for slot, attempt in self._running.items():
            if not attempt.expired:
                attempt.expired = True
                accounts = _failure(attempt.candidate, self._snapshots.get(slot, ()), self.source_id, now_ms, timeout=True)
                self._publish(slot, accounts)
                self.refresh[slot].complete((), self.clock(), timeout=True)
                self._record(attempt, accounts, int(self.wall_ms()))
        for slot, candidate in self._waiting.items():
            accounts = _failure(candidate, self._snapshots.get(slot, ()), self.source_id, now_ms, timeout=True)
            self._publish(slot, accounts)
            self.observations.record(slot, candidate.revision, accounts, at_ms=int(self.wall_ms()),
                                     duration=None, outcome="timeout", provider_id=candidate.provider.provider_id)
        return self.snapshots

    def cancel(self) -> None:
        """Thread-safe signal; only the acquisition owner clears mutable work."""
        self._stop.set()

    def close(self) -> None:
        self._stop.set()
        self._waiting.clear()
        self._running.clear()
        for queue in (self._jobs, self._results):
            while True:
                try:
                    queue.get_nowait()
                except Empty:
                    break
        self.discovery.close()
        # No join of in-flight HTTP. Idle workers exit in <=0.1s; bounded
        # daemon workers cannot keep the process/terminal alive at shutdown.

    def diagnostics(self, *, include_observations: bool = True) -> dict[str, object]:
        """Allowlisted performance evidence only; jobs are not HTTP-call counts."""
        evidence = {"local_discovery_ms": round(self.discovery_seconds * 1000, 2),
                "candidate_providers": self.providers_discovered,
                "provider_jobs_started": self.checks_started, "worker_limit": self.limit,
                "acquisition_elapsed_ms": round(max(0.0, self.clock() - self._started_at) * 1000, 2)
                 if self._started_at is not None else 0.0,
                "providers": {str(slot): state.diagnostics(self.clock()) for slot, state in self.refresh.items()}}
        if include_observations:
            evidence["quota_observations"] = self.observations.diagnostics(int(self.wall_ms()))
        return evidence
