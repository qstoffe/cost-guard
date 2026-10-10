"""Watch account publication/retry lifecycle; never source hydration or rendering."""
from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from src.accounts.acquisition import AccountUpdate
from src.domain import AccountSnapshot

from .accounts import AccountKey, durable_quota_failure, reconcile_accounts, recovery_account_keys

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
            return expired
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
        self._last_fresh = fresh
        if not self.work.accounts_pending:
            self.last_started_ms = completed_ms
        unseen = {item.key for item in fresh if item.availability == "error" and not durable_quota_failure(item)
                  and item.key not in self.seen_ms and item.key not in self._first_retried}
        if unseen and not recovering:
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
