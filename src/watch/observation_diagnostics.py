"""Privacy-safe Watch visibility observations preserved for a later Diagnostics run.

Only bounded counters and fixed labels are persisted; no session or prompt IDs,
text, paths, credentials, or raw provider data ever enter this file.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Mapping

from src.version import DISPLAY_VERSION

FILE = Path(__file__).resolve().parents[2] / "logs" / "recovery" / "watch-observations.json"
_COUNT_KEYS = ("sessions", "roots", "active_metadata", "hydrated_roots",
               "sampled_prompts", "older_completed", "visible_prompts", "running_prompts")
_REASONS = frozenset(("visible", "no_sessions", "no_roots", "no_sampled_prompts", "no_eligible_prompts"))
_PHASES = frozenset(("unknown", "catalog_before", "messages", "catalog_after",
                     "revision_check", "revision_changed", "complete"))
_MAX_AGE_MS = 30 * 86_400_000


def recent_events(now_ms: int | None = None) -> list[dict[str, object]]:
    now = int(time.time() * 1000) if now_ms is None else int(now_ms)
    try:
        raw = json.loads(FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return []
    if not isinstance(raw, list):
        return []
    result = []
    for item in raw[-100:]:
        if not isinstance(item, dict):
            continue
        at = item.get("at_ms")
        if (type(at) is not int or not 0 <= now - at <= _MAX_AGE_MS
                or item.get("source") not in ("v1", "v2")
                or item.get("event") not in ("scan", "source_error")):
            continue
        clean: dict[str, object] = {"at_ms": at, "source": item["source"],
                                    "event": item["event"], "version": str(item.get("version", ""))[:16]}
        for key in _COUNT_KEYS:
            value = item.get(key)
            if type(value) is int and 0 <= value <= 10_000_000:
                clean[key] = value
        if item.get("reason") in _REASONS:
            clean["reason"] = item["reason"]
        if item.get("phase") in _PHASES:
            clean["phase"] = item["phase"]
        if item.get("kind") in ("unavailable", "unreadable", "unsupported"):
            clean["kind"] = item["kind"]
        result.append(clean)
    return result[-24:]


def _record(source: str, event: str, values: Mapping[str, object]) -> None:
    if os.environ.get("COST_GUARD_TEST_MODE") == "1" or source not in ("v1", "v2"):
        return
    now = int(time.time() * 1000)
    try:
        events = recent_events(now)
        item = {"at_ms": now, "source": source, "event": event,
                "version": DISPLAY_VERSION, **values}
        if events and event == "scan" and events[-1]["event"] == "scan":
            old = {k: v for k, v in events[-1].items() if k != "at_ms"}
            new = {k: v for k, v in item.items() if k != "at_ms"}
            if old == new and now - int(events[-1]["at_ms"]) < 600_000:
                return
        FILE.parent.mkdir(parents=True, exist_ok=True)
        temp = FILE.with_name(f"{FILE.name}.{os.getpid()}.{time.time_ns()}.tmp")
        try:
            temp.write_text(json.dumps((events + [item])[-24:], separators=(",", ":")), encoding="utf-8")
            temp.replace(FILE)
        finally:
            temp.unlink(missing_ok=True)
    except OSError:
        pass


def record_scan(source: str, observation: Any, blocks: Mapping[str, Any],
                rows: Any, started_at_ms: int, now_ms: int) -> None:
    sessions = observation.sessions
    roots = observation.roots
    prompts = [prompt for block in blocks.values() for prompt in block.rows]
    reason = ("visible" if rows else "no_sessions" if not sessions else "no_roots" if not roots
              else "no_sampled_prompts" if not prompts else "no_eligible_prompts")
    _record(source, "scan", {
        "sessions": len(sessions), "roots": len(roots),
        "active_metadata": sum(item.active is True for item in sessions),
        "hydrated_roots": len(blocks), "sampled_prompts": len(prompts),
        "older_completed": sum(not p.in_progress and p.at_ms < started_at_ms for p in prompts),
        "visible_prompts": len(rows),
        "running_prompts": sum(row.prompt.in_progress for row in rows),
        "reason": reason,
    })


def record_source_error(source: str, kind: str, provider: Any) -> None:
    metadata = getattr(provider, "diagnostic_metadata", None)
    try:
        state = metadata() if callable(metadata) else {}
    except Exception:
        state = {}
    phase = state.get("last_snapshot_stage") if isinstance(state, Mapping) else None
    _record(source, "source_error", {
        "kind": kind if kind in ("unavailable", "unreadable", "unsupported") else "unsupported",
        "phase": phase if phase in _PHASES else "unknown",
    })
