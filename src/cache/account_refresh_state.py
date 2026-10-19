"""Latest writer's Watch evidence; atomic, bounded and privacy allowlisted."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import time

from src.version import DISPLAY_VERSION

STATE_FILE = Path("cache/state/watch-account-refresh.json")
NUMBERS = frozenset({"local_discovery_ms", "candidate_providers", "provider_jobs_started", "worker_limit",
                     "acquisition_elapsed_ms", "blocked_lanes", "publication_delay_seconds", "display_age_seconds",
                     "attempt_age_seconds", "completion_age_seconds", "observation_age_seconds", "publication_age_seconds",
                     "acquisition_seconds", "effective_interval_seconds", "scheduling_delay_seconds",
                     "worker_wait_seconds",
                     "retry_count", "timeout_count", "failure_count"})
LABELS = {"scheduler_state": {"running", "stopped"}, "outcome": {"success", "timeout", "transient_failure", "durable_failure", "unavailable"},
          "freshness": {"fresh", "stale", "unavailable"}, "display_state": {"fresh", "stale", "unavailable"},
          "upstream_freshness": {"unknown"}}


def _numeric_fields(raw, limits):
    if not isinstance(raw, dict):
        return {}
    return {key: value for key, maximum in limits.items() if key in raw
            and ((value := raw[key]) is None or type(value) in (int, float)
                 and 0 <= value <= maximum and math.isfinite(value))}


def _observation(raw):
    result = _numeric_fields(raw, {"observed_at_ms": 10**15, "remaining_percent": 100,
                                  "reset_at_ms": 10**15, "acquisition_seconds": 10**9})
    if not isinstance(raw, dict):
        return result
    if isinstance(raw.get("outcome"), str) and raw["outcome"] in LABELS["outcome"]:
        result["outcome"] = raw["outcome"]
    for flag in ("value_changed", "reset_changed"):
        if raw.get(flag) is None or type(raw.get(flag)) is bool:
            result[flag] = raw.get(flag)
    return result


def _quota_series(raw):
    result = _numeric_fields(raw, {"series_id": 10**12, "window_id": 64, "duration_seconds": 10**12,
                                  "last_successful_retrieval_ms": 10**15, "last_value_change_ms": 10**15,
                                  "value_change_age_seconds": 10**12, "observed_unchanged_seconds": 10**12,
                                  "last_watch_publication_ms": 10**15})
    if not isinstance(raw, dict):
        return result
    provider = raw.get("provider_id")
    result["provider_id"] = provider if isinstance(provider, str) and provider in {
        "claude-code", "github-copilot", "openai", "anthropic", "minimax", "deepseek", "openrouter"} else "other"
    history = raw.get("history")
    result["history"] = [_observation(item) for item in history[-64:]] if isinstance(history, list) else []
    return result


def _quota_evidence(raw):
    if not isinstance(raw, dict):
        return {}
    run_id = raw.get("run_id")
    if not isinstance(run_id, str) or len(run_id) != 32 or any(c not in "0123456789abcdef" for c in run_id):
        return {}
    result = _numeric_fields(raw, {"captured_at_ms": 10**15})
    result.update(run_id=run_id, origin="watch" if raw.get("origin") == "watch" else "report",
                  upstream_freshness="unknown", history_limit=64, series_limit=64)
    series = raw.get("series")
    result["series"] = [_quota_series(item) for item in series[-64:]] if isinstance(series, list) else []
    return result


def _scalars(raw: object) -> dict:
    if not isinstance(raw, dict):
        return {}
    result = {}
    for key, value in raw.items():
        if key in NUMBERS and (value is None or type(value) in (int, float) and 0 <= value <= 10**12 and math.isfinite(value)):
            result[key] = value
        elif key in LABELS and isinstance(value, str) and value in LABELS[key]:
            result[key] = value
    return result


def _clean(raw: object) -> dict:
    result = _scalars(raw)
    if not isinstance(raw, dict):
        return result
    providers = raw.get("providers", {})
    if isinstance(providers, dict):
        result["providers"] = {str(i): _scalars(providers[str(i)]) for i in range(128) if str(i) in providers}
    watch = raw.get("watch", {})
    accounts = watch.get("accounts", []) if isinstance(watch, dict) else []
    if isinstance(accounts, list):
        result["watch"] = {"accounts": [_scalars(item) for item in accounts[:128]]}
    if "quota_observations" in raw:
        result["quota_observations"] = _quota_evidence(raw["quota_observations"])
    return result


def persist_refresh_state(root: Path, evidence: dict) -> None:
    path = root / STATE_FILE
    temp = path.with_name(f"{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        state = {"schema": 1, "version": DISPLAY_VERSION, "recorded_at_ms": time.time_ns() // 1_000_000,
                 "evidence": _clean(evidence)}
        temp.write_text(json.dumps(state, allow_nan=False), encoding="utf-8")
        temp.replace(path)
    except OSError:
        pass  # Advisory evidence must not change quota behavior.
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def read_refresh_state(root: Path) -> dict:
    path = root / STATE_FILE
    try:
        if path.stat().st_size > 2_097_152:
            return {}
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return {}
    if not isinstance(state, dict) or state.get("schema") != 1 or type(state.get("recorded_at_ms")) is not int:
        return {}
    version = state.get("version")
    return {"recorded_at_ms": state["recorded_at_ms"], "version": version
            if isinstance(version, str) and version.removeprefix("v").replace(".", "").isdigit() and len(version) <= 16 else "unknown",
            "evidence": _clean(state.get("evidence"))}
