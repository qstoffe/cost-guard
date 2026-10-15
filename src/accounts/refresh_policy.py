"""Monotonic per-provider freshness budgets, bounded retries and safe evidence."""
from __future__ import annotations

from dataclasses import dataclass

from src.domain import AccountSnapshot

REFRESH_SECONDS = 30.0
WATCH_TIMEOUT_SECONDS = 20.0
RETRY_SECONDS = (5.0, 10.0, 20.0)
FAILURE_INTERVAL_SECONDS = 60.0
TRANSIENT_REASONS = frozenset({"network_failure", "transport_failure", "timeout", "discovery_failure"})


def transient_failure(item: AccountSnapshot) -> bool:
    return (item.availability == "error"
            and item.observations.get("http_status") not in (401, 403)
            and (item.observations.get("parser_reason") in TRANSIENT_REASONS
                 or item.observations.get("http_status") in (408, 429, 500, 502, 503, 504)))


@dataclass
class ProviderRefresh:
    """No identity/response data is exported; each instance owns one adapter lane."""

    revision: object
    due: float = 0.0
    normal_due: float = 0.0
    started: float | None = None
    completed: float | None = None
    observed: float | None = None
    published: float | None = None
    interval: float = 0.0
    scheduling_delay: float = 0.0
    duration: float = 0.0
    worker_wait: float = 0.0
    retries: int = 0
    timeouts: int = 0
    failures: int = 0
    retry_index: int = 0
    outcome: str = "unavailable"
    retry_scheduled: bool = False

    def begin(self, now: float, *, full: bool = True, retry: bool | None = None) -> None:
        self.retries += int(self.retry_scheduled if retry is None else retry)
        self.retry_scheduled = False
        self.interval = now - self.started if self.started is not None else 0.0
        self.scheduling_delay = max(0.0, now - self.due) if self.started is not None else 0.0
        self.started = now
        self.due = now + REFRESH_SECONDS
        if full:
            if self.normal_due and now >= self.normal_due:
                self.normal_due += (int((now - self.normal_due) // REFRESH_SECONDS) + 1) * REFRESH_SECONDS
            else:
                self.normal_due = self.due
            self.due = self.normal_due

    def complete(self, accounts: tuple[AccountSnapshot, ...], now: float, *, timeout: bool = False) -> None:
        self.completed = now
        self.duration = max(0.0, now - self.started) if self.started is not None else 0.0
        self.timeouts += int(timeout)
        successful = any(item.availability in {"available", "partial"} for item in accounts)
        retryable = timeout or any(transient_failure(item) for item in accounts)
        if successful:
            self.observed = now  # Unchanged native values are a new observation too.
        if retryable:
            self.outcome = "timeout" if timeout else "transient_failure"
            self.failures += 1
            if self.retry_index < len(RETRY_SECONDS):
                self.due = now + RETRY_SECONDS[self.retry_index]
                self.retry_index += 1
                self.retry_scheduled = True
            else:
                self.due = now + FAILURE_INTERVAL_SECONDS
        elif successful:
            self.outcome = "success"
            self.retry_index = 0
            self.retry_scheduled = False
            # Start anchored, never completion + interval or a catch-up burst.
            self.due = max(self.due, now + 0.1)
        else:
            self.outcome = "durable_failure" if accounts else "unavailable"
            self.retry_index = 0
            self.retry_scheduled = False
            self.due = now + FAILURE_INTERVAL_SECONDS

    def diagnostics(self, now: float) -> dict[str, object]:
        def age(value):
            return round(max(0.0, now - value), 3) if value is not None else None

        return {"attempt_age_seconds": age(self.started), "completion_age_seconds": age(self.completed),
                "observation_age_seconds": age(self.observed), "publication_age_seconds": age(self.published),
                "acquisition_seconds": round(self.duration, 3), "effective_interval_seconds": round(self.interval, 3),
                "scheduling_delay_seconds": round(self.scheduling_delay, 3), "outcome": self.outcome,
                "worker_wait_seconds": round(self.worker_wait, 3),
                "retry_count": self.retries, "timeout_count": self.timeouts, "failure_count": self.failures,
                "upstream_freshness": "unknown",
                "freshness": "unavailable" if self.observed is None else
                "stale" if now - self.observed > 60 or self.outcome != "success" else "fresh"}
