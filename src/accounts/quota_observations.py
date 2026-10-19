"""Bounded run-local quota evidence, independent of scheduling and stale policy."""
from __future__ import annotations

from collections import OrderedDict, deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from threading import Lock
from uuid import uuid4

from src.domain import AccountSnapshot, QuotaComponent
from .refresh_policy import transient_failure

HISTORY_LIMIT = 64  # 31.5 minutes between oldest/newest normal 30-second polls.
SERIES_LIMIT = 64
PROVIDERS = frozenset({"claude-code", "github-copilot", "openai", "anthropic", "minimax", "deepseek", "openrouter"})


def acquisition_outcome(account: AccountSnapshot) -> str:
    if account.availability in {"available", "partial"}:
        return "success"
    if account.observations.get("parser_reason") == "timeout":
        return "timeout"
    if transient_failure(account):
        return "transient_failure"
    return "unavailable" if account.availability == "unavailable" else "durable_failure"


@dataclass
class _Series:
    series_id: int
    provider_id: str
    window_id: int | None
    duration_seconds: int | None
    history: deque[dict[str, object]] = field(default_factory=lambda: deque(maxlen=HISTORY_LIMIT))
    signature: tuple[Decimal, int | None] | None = None
    last_success_ms: int | None = None
    last_value_change_ms: int | None = None
    unchanged_since_ms: int | None = None
    last_publication_ms: int | None = None

    def observe(self, at_ms: int, duration: float | None, outcome: str, quota: QuotaComponent | None = None) -> None:
        fraction = quota.remaining_fraction if quota is not None else None
        percent = float(fraction * 100) if fraction is not None else None
        reset = quota.reset_at_ms if quota is not None else None
        changed = reset_changed = None
        if outcome == "success":
            self.last_success_ms = at_ms
            if percent is not None:
                signature = (fraction, reset)
                changed = fraction != self.signature[0] if self.signature is not None else None
                reset_changed = reset != self.signature[1] if self.signature is not None else None
                if self.signature is None or changed:
                    self.unchanged_since_ms = at_ms
                if changed:
                    self.last_value_change_ms = at_ms
                self.signature = signature
        self.history.append({"observed_at_ms": at_ms, "remaining_percent": percent,
                             "reset_at_ms": reset, "acquisition_seconds": round(max(0.0, duration), 3)
                             if duration is not None else None,
                             "outcome": outcome, "value_changed": changed, "reset_changed": reset_changed})

    def evidence(self, now_ms: int) -> dict[str, object]:
        def age(at):
            return max(0.0, (now_ms - at) / 1000) if at is not None else None

        return {"series_id": self.series_id, "provider_id": self.provider_id,
                "window_id": self.window_id, "duration_seconds": self.duration_seconds,
                "last_successful_retrieval_ms": self.last_success_ms,
                "last_value_change_ms": self.last_value_change_ms,
                "value_change_age_seconds": age(self.last_value_change_ms),
                "observed_unchanged_seconds": age(self.unchanged_since_ms),
                "last_watch_publication_ms": self.last_publication_ms,
                "history": [dict(item) for item in self.history]}


class QuotaObservations:
    """Private identities only partition series; exported IDs are run-local ordinals.

    A fresh run never imports prior values or identities. The atomic persistence
    owner may export the latest writer, but histories from writers are never mixed.
    """

    def __init__(self, *, continuous: bool = False):
        self.run_id = uuid4().hex
        self.origin = "watch" if continuous else "report"
        self._series: OrderedDict[tuple, _Series] = OrderedDict()
        self._next_id = 0
        self._lock = Lock()

    def _get(self, key: tuple, provider_id: str, window_id: int | None, duration: int | None) -> _Series:
        if key not in self._series:
            self._next_id += 1
            self._series[key] = _Series(self._next_id, provider_id if provider_id in PROVIDERS else "other",
                                        window_id, duration)
            if len(self._series) > SERIES_LIMIT:
                self._series.popitem(last=False)
        self._series.move_to_end(key)
        return self._series[key]

    def record(self, slot: int, revision: object, accounts: Sequence[AccountSnapshot], *,
               at_ms: int, duration: float | None, outcome: str, provider_id: str = "other") -> None:
        with self._lock:
            self._record(slot, revision, accounts, at_ms=at_ms, duration=duration, outcome=outcome, provider_id=provider_id)

    def _record(self, slot: int, revision: object, accounts: Sequence[AccountSnapshot], *,
                at_ms: int, duration: float | None, outcome: str, provider_id: str) -> None:
        for account in accounts:
            prefix = (slot, revision, account.key)
            status = "timeout" if outcome == "timeout" else acquisition_outcome(account)
            if account.quotas and status == "success":
                for index, quota in enumerate(account.quotas[:SERIES_LIMIT]):
                    # Labels remain memory-only; never export arbitrary provider text.
                    key = (*prefix, quota.label, quota.period, quota.scope, quota.model_id, quota.duration_seconds)
                    series = self._get(key, account.ref.provider_id, index, quota.duration_seconds)
                    series.observe(at_ms, duration, status, quota)
            else:
                matches = [series for key, series in self._series.items() if key[:3] == prefix]
                if not matches:
                    matches = [self._get((*prefix, None), account.ref.provider_id, None, None)]
                for series in matches:
                    series.observe(at_ms, duration, status)
        if not accounts:
            series = self._get((slot, revision, None, None), provider_id, None, None)
            series.observe(at_ms, duration, outcome)

    def published(self, observations: Mapping[tuple[str, str, str], int], at_ms: int) -> None:
        with self._lock:
            for key, series in self._series.items():
                if key[2] in observations and any(item["observed_at_ms"] == observations[key[2]]
                                                 and item["outcome"] == "success" for item in series.history):
                    series.last_publication_ms = at_ms

    def diagnostics(self, now_ms: int) -> dict[str, object]:
        with self._lock:
            return {"run_id": self.run_id, "origin": self.origin, "captured_at_ms": now_ms,
                    "upstream_freshness": "unknown", "history_limit": HISTORY_LIMIT,
                    "series_limit": SERIES_LIMIT,
                    "series": [series.evidence(now_ms) for series in self._series.values()]}
