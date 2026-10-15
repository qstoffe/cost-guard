"""Watch account publication/retry lifecycle; never source hydration or rendering."""
from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from src.accounts.acquisition import AccountUpdate
from src.domain import AccountSnapshot

from .accounts import AccountKey, age_accounts, durable_quota_failure, reconcile_accounts, recovery_account_keys

QUOTA_REFRESH_MS = 60_000
QUOTA_RECOVERY_SECONDS = 60.0
QUOTA_RETRY_SECONDS = (5.0, 10.0, 20.0)


class AccountRefreshWork(Protocol):
    """Only ReportService's bounded, main-thread account-work surface is needed."""

    def set_now_ms(self, now_ms: int) -> None: ...
    def begin_account_refresh(self) -> None: ...
    def poll_account_refresh(self) -> AccountUpdate | None: ...
    @property
    def accounts_pending(self) -> bool: ...
    def close_accounts(self) -> None: ...


class WatchAccountRefresh:
    """One owner for capacity, successful-observation timestamps and retry state.

    Workers remain owned by the injected report service. Callers supply wall
    time for provider cadence and a monotonic clock for bounded retry/grace.
    Expiry/publication cannot manufacture a provider observation. Source events
    do not force account requests; only resume explicitly arms fast recovery.
    """

    def __init__(self, work: AccountRefreshWork, *, clock_ms: Callable[[], int],
                 monotonic: Callable[[], float]) -> None:
        self.work = work
        self.clock_ms = clock_ms
        self.monotonic = monotonic
        self.snapshots: tuple[AccountSnapshot, ...] = ()
        self.seen_ms: dict[AccountKey, int] = {}
        self.stale = False
        self.recovering_keys: tuple[AccountKey, ...] = ()
        self.recovery_until: float | None = None
        self.retry_at: float | None = None
        self.retry_index = 0
        self.last_started_ms: int | None = None
        self._last_fresh: tuple[AccountSnapshot, ...] = ()
        self._first_retried: set[AccountKey] = set()
        self._closed = False

    def begin(self, now_ms: int) -> None:
        self.work.begin_account_refresh()
        self.last_started_ms = now_ms

    def resume(self) -> None:
        self.recovery_until = self.monotonic() + QUOTA_RECOVERY_SECONDS
        self.retry_at = self.monotonic()
        self.retry_index = 0

    def _end_recovery(self) -> None:
        self.recovery_until = self.retry_at = None
        self.recovering_keys = ()

    def wait_delay(self, normal_delay: float) -> float:
        delay = normal_delay
        for target in (self.retry_at, self.recovery_until):
            if target is not None:
                delay = min(delay, max(0.0, target - self.monotonic()))
        return delay

    def refresh(self, *, now_ms: int, force: bool = False) -> bool:
        """Publish individual completions; return whether capacity state changed."""
        if self._closed:
            return False
        expired = self.recovery_until is not None and self.monotonic() >= self.recovery_until
        if expired:
            self._end_recovery()
            self.snapshots, self.seen_ms, self.stale = reconcile_accounts(
                self.snapshots, self._last_fresh, self.seen_ms, now_ms=now_ms, update_seen=False,
            )
        retry_due = self.retry_at is not None and self.monotonic() >= self.retry_at
        self.work.set_now_ms(now_ms)
        due = self.last_started_ms is None or now_ms - self.last_started_ms >= QUOTA_REFRESH_MS
        if force or retry_due or due:
            self.begin(now_ms)
            if retry_due:
                self.retry_at = None
        update = self.work.poll_account_refresh()
        if update is None:
            aged = age_accounts(self.snapshots, self.seen_ms, now_ms=now_ms)
            changed = aged != self.snapshots
            self.snapshots = aged
            self.stale = any(item.availability == "stale" for item in aged)
            return expired or changed
        self._publish(update)
        return True

    def _publish(self, update: AccountUpdate) -> None:
        fresh = update.snapshots
        completed_ms = int(self.clock_ms())
        recovering = self.recovery_until is not None and self.monotonic() < self.recovery_until
        previous = self.snapshots
        self.snapshots, self.seen_ms, self.stale = reconcile_accounts(
            previous, fresh, self.seen_ms, now_ms=completed_ms, recovering=recovering,
            observed_keys=update.observed_keys,
        )
        # A mailbox may have waited during hydration: completion, not drain time,
        # is the observation epoch. A retained/cached value cannot advance it.
        observed = dict(update.observed_at_ms)
        for item in self.snapshots:
            if item.key in update.observed_keys and item.key in observed and item.availability in {"available", "partial"}:
                self.seen_ms[item.key] = observed[item.key]
        self.snapshots = age_accounts(self.snapshots, self.seen_ms, now_ms=completed_ms)
        self.stale = any(item.availability == "stale" for item in self.snapshots)
        self._last_fresh = fresh
        self._first_retried.difference_update(item.key for item in fresh if item.availability in {"available", "partial"})
        unseen = {item.key for item in fresh if item.availability == "error" and not durable_quota_failure(item)
                  and item.key not in self._first_retried}
        if unseen and not recovering and self.recovery_until is None:
            self._first_retried |= unseen
            self.recovery_until = self.monotonic() + QUOTA_RECOVERY_SECONDS
            self.retry_index = 0
            recovering = True
        if not recovering:
            self._end_recovery()
            return
        self.recovering_keys = recovery_account_keys(previous, fresh, self.snapshots)
        self._schedule_retry(update)

    def _schedule_retry(self, update: AccountUpdate) -> None:
        if not self.recovering_keys:
            if not self.work.accounts_pending:
                self._end_recovery()
            return
        observed_failure = any(key in update.observed_keys for key in self.recovering_keys)
        if observed_failure or (self.retry_at is None and not self.work.accounts_pending):
            if self.retry_index < len(QUOTA_RETRY_SECONDS):
                self.retry_at = self.monotonic() + QUOTA_RETRY_SECONDS[self.retry_index]
                self.retry_index += 1

    def close(self) -> None:
        self._closed = True
        self.work.close_accounts()

    def diagnostics(self) -> dict[str, object]:
        now = int(self.clock_ms())
        return {"accounts": [{"observation_age_seconds": max(0.0, (now - self.seen_ms[item.key]) / 1000)
                              if item.key in self.seen_ms else None,
                              "display_state": "stale" if item.availability == "stale" else
                              "fresh" if item.availability in {"available", "partial"} else "unavailable"}
                             for item in self.snapshots]}
