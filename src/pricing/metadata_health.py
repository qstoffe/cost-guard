"""Persistent, privacy-safe release-metadata health, retry schedule and failure periods.

State survives restarts in `logs/recovery/model-metadata.json` (bounded). Failure
periods are appended as JSON lines to `logs/errors/cost-guard-metadata-<date>.log`:
first failure, changed failure, bounded repeat summaries and recovery, never
one line per attempt. Only stable codes, counts, timestamps and public source
names are written: no URLs with credentials, headers, payloads or messages.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import threading

from src.version import DISPLAY_VERSION

from .release_metadata import MetadataAttempt, SourceResult

RETRY_DELAYS_MS = (60_000, 300_000, 900_000, 3_600_000)
MAX_RETRY_AFTER_MS = 6 * 3_600_000
RECHECK_MS = 3_600_000
COMPONENT = "pricing-release-metadata"
STATE_FILE = Path("logs/recovery/model-metadata.json")
_SUMMARY_ATTEMPTS = (3, 10)
_HISTORY = 24
_EVENT_KEYS = ("timestamp", "version", "component", "event", "source", "phase", "error_code",
               "previous_error_code", "http_status", "timeout_seconds", "retry_after_seconds",
               "attempts", "priced_models", "dated_models", "cache_fallback", "fingerprint",
               "duration_ms", "health", "reason")


def default_root() -> Path | None:
    """Tests never write synthetic metadata history into the real logs folder."""
    if os.environ.get("COST_GUARD_TEST_MODE") == "1":
        return None
    return Path(__file__).resolve().parents[2]


def _int(value: object) -> int | None:
    return value if type(value) is int else None


def _fingerprint(result: SourceResult) -> str:
    raw = f"{COMPONENT}|{result.source}|{result.phase}|{result.code}|{result.http_status}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def read_state(root: Path | None) -> dict:
    if root is None:
        return {}
    try:
        raw = json.loads((Path(root) / STATE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return {}
    return raw if isinstance(raw, dict) and raw.get("schema") == 1 else {}


def recent_events(root: Path, limit: int = 60) -> list[dict]:
    """Bounded whitelisted events for Diagnostics, newest last."""
    events: list[dict] = []
    try:
        files = sorted((Path(root) / "logs/errors").glob("cost-guard-metadata-????-??-??.log"))[-31:]
    except OSError:
        return events
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()[-200:]
        except (OSError, UnicodeError):
            continue
        for line in lines:
            try:
                raw = json.loads(line)
            except ValueError:
                continue
            if isinstance(raw, dict) and raw.get("component") == COMPONENT:
                events.append({key: raw[key] for key in _EVENT_KEYS if key in raw})
    return events[-limit:]


class MetadataHealthStore:
    """Single owner of the retry schedule; memory-only when root is None."""

    def __init__(self, root: Path | None) -> None:
        self.root = Path(root) if root is not None else None
        self._lock = threading.Lock()
        state = read_state(self.root)
        self.state: dict = {"schema": 1, "health": "unknown", "sources": {}, "history": [],
                            "consecutive_failures": 0}
        for key in ("health", "result_origin", "last_attempt_reason"):
            if isinstance(state.get(key), str):
                self.state[key] = state[key][:40]
        for key in ("last_attempt_ms", "last_complete_ms", "next_retry_ms", "priced_models",
                    "dated_models", "consecutive_failures"):
            if _int(state.get(key)) is not None:
                self.state[key] = state[key]
        if isinstance(state.get("sources"), dict):
            self.state["sources"] = {k: v for k, v in state["sources"].items()
                                     if isinstance(k, str) and isinstance(v, dict)}
        if isinstance(state.get("history"), list):
            self.state["history"] = [item for item in state["history"] if isinstance(item, dict)][-_HISTORY:]
        if isinstance(state.get("last_skip"), dict):
            self.state["last_skip"] = state["last_skip"]

    # -- schedule ---------------------------------------------------------
    def refresh_reason(self, *, priced: int, dated: int, retrieved_at_ms: int, now_ms: int,
                       hint: str = "") -> str:
        """Why a metadata-only refresh is due now, or "" (with a recorded skip reason)."""
        with self._lock:
            state = self.state
            if priced <= 0:
                return ""
            failing = dated <= 0 or state.get("consecutive_failures", 0) > 0
            last_attempt = _int(state.get("last_attempt_ms"))
            last_complete = _int(state.get("last_complete_ms"))
            stale = last_complete is None or now_ms - last_complete >= RECHECK_MS
            if dated <= 0:
                reason = "missing_release_dates"
            elif state.get("consecutive_failures", 0) > 0:
                reason = "retry_after_failure"
            elif last_attempt is None or last_attempt < retrieved_at_ms:
                reason = "unverified_cache"
            elif dated * 2 < priced and stale:
                reason = "incomplete_release_dates"
            elif hint and stale:
                reason = hint
            else:
                return ""
            next_retry = _int(state.get("next_retry_ms"))
            if failing and next_retry is not None and now_ms < next_retry:
                self._skip("backoff", now_ms)
                return ""
            return reason

    def skipped(self, reason: str, now_ms: int) -> None:
        with self._lock:
            self._skip(reason, now_ms)

    def _skip(self, reason: str, now_ms: int) -> None:
        previous = self.state.get("last_skip") or {}
        self.state["last_skip"] = {"reason": reason, "at_ms": now_ms}
        if previous.get("reason") != reason:
            self._persist()

    # -- results ----------------------------------------------------------
    def record(self, attempt: MetadataAttempt, now_ms: int, *, reason: str) -> None:
        with self._lock:
            state = self.state
            before = (state.get("health"), state.get("dated_models"))
            state.update(last_attempt_ms=now_ms, last_attempt_reason=reason[:40],
                         priced_models=attempt.priced_models, dated_models=attempt.dated_models,
                         health=attempt.health,
                         result_origin="cache" if attempt.cache_fallback else "network")
            for result in attempt.sources:
                self._record_source(result, attempt, now_ms)
            failing = attempt.failed or attempt.dated_models <= 0
            if failing:
                count = int(state.get("consecutive_failures", 0)) + 1
                delay = RETRY_DELAYS_MS[min(count, len(RETRY_DELAYS_MS)) - 1]
                waits = [r.retry_after_seconds * 1000 for r in attempt.sources if r.retry_after_seconds]
                delay = max([delay, *(min(MAX_RETRY_AFTER_MS, w) for w in waits)])
                state.update(consecutive_failures=count, next_retry_ms=now_ms + delay)
            else:
                state.update(consecutive_failures=0, next_retry_ms=None, last_complete_ms=now_ms)
            state.pop("last_skip", None)
            if before != (attempt.health, attempt.dated_models):
                state["history"] = [*state.get("history", []), {
                    "at_ms": now_ms, "health": attempt.health, "dated_models": attempt.dated_models,
                    "priced_models": attempt.priced_models, "origin": state["result_origin"],
                }][-_HISTORY:]
            self._persist()

    def _record_source(self, result: SourceResult, attempt: MetadataAttempt, now_ms: int) -> None:
        entry = self.state["sources"].setdefault(result.source, {})
        entry["last_result"] = {**result.as_dict(), "at_ms": now_ms}
        counts = {"priced_models": attempt.priced_models, "dated_models": attempt.dated_models,
                  "cache_fallback": attempt.cache_fallback}
        period = entry.get("period") if isinstance(entry.get("period"), dict) else None
        if result.status == "failed":
            fingerprint = _fingerprint(result)
            entry.update(last_failure_ms=now_ms, last_error=result.as_dict(),
                         consecutive_failures=int(entry.get("consecutive_failures", 0)) + 1)
            if period is None:
                period = {"started_ms": now_ms, "code": result.code, "fingerprint": fingerprint, "attempts": 1}
                self._event("failure_started", result, attempts=1, fingerprint=fingerprint, **counts)
            elif period.get("fingerprint") != fingerprint:
                previous = period.get("code")
                period.update(code=result.code, fingerprint=fingerprint, attempts=int(period.get("attempts", 0)) + 1)
                self._event("failure_changed", result, attempts=period["attempts"], fingerprint=fingerprint,
                            previous_error_code=previous, **counts)
            else:
                period["attempts"] = int(period.get("attempts", 0)) + 1
                if period["attempts"] in _SUMMARY_ATTEMPTS or period["attempts"] % 24 == 0:
                    self._event("failure_summary", result, attempts=period["attempts"],
                                fingerprint=fingerprint, duration_ms=now_ms - int(period.get("started_ms", now_ms)), **counts)
            entry["period"] = period
        elif result.status == "ok":
            entry.update(last_success_ms=now_ms, consecutive_failures=0)
            if period is not None:
                recovery = {"at_ms": now_ms, "failed_attempts": int(period.get("attempts", 0)),
                            "duration_ms": now_ms - int(period.get("started_ms", now_ms)),
                            "previous_error_code": period.get("code")}
                entry["last_recovery"] = recovery
                self._event("recovered", result, attempts=recovery["failed_attempts"],
                            duration_ms=recovery["duration_ms"], previous_error_code=recovery["previous_error_code"],
                            health=attempt.health, **counts)
            entry["period"] = None

    def _event(self, event: str, result: SourceResult, **values) -> None:
        if self.root is None:
            return
        line = {"timestamp": datetime.now().astimezone().isoformat(), "version": DISPLAY_VERSION,
                "component": COMPONENT, "event": event, "source": result.source, "phase": result.phase,
                "error_code": result.code, "http_status": result.http_status,
                "timeout_seconds": result.timeout_seconds, "retry_after_seconds": result.retry_after_seconds,
                **values}
        path = self.root / "logs/errors" / f"cost-guard-metadata-{datetime.now().astimezone():%Y-%m-%d}.log"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as target:
                target.write(json.dumps({k: v for k, v in line.items() if v is not None}, sort_keys=True) + "\n")
        except OSError:
            pass  # Logging cannot change metadata recovery or Watch behavior.

    def _persist(self) -> None:
        if self.root is None:
            return
        path = self.root / STATE_FILE
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
            temp.write_text(json.dumps({**self.state, "version": DISPLAY_VERSION}, sort_keys=True), encoding="utf-8")
            temp.replace(path)
        except OSError:
            pass

    def snapshot(self) -> dict:
        with self._lock:
            return json.loads(json.dumps(self.state))
