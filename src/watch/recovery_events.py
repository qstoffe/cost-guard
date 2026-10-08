"""Bounded privacy-safe record of Watch source recovery transitions.

Records contain no endpoint, account, session ID, path, exception text or payload.
Failure to record a recovery cannot alter Watch's actual control flow.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
import os
from src.version import DISPLAY_VERSION

ROOT = Path(__file__).resolve().parents[2]
FILE = ROOT / "diagnostics" / "recovery" / "watch-recovery.json"
_ALLOWED_EVENTS = frozenset({"retrying", "recovered", "failed"})
_ALLOWED_SOURCES = frozenset({"v1", "v2"})
_ALLOWED_KINDS = frozenset({"available", "unavailable", "unreadable", "unsupported"})


def recent_events(now_ms: int | None = None) -> list[dict[str, object]]:
    now = int(time.time() * 1000) if now_ms is None else int(now_ms)
    try:
        raw = json.loads(FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return []
    if not isinstance(raw, list):
        return []
    events: list[dict[str, object]] = []
    for event in raw[-100:]:
        if not isinstance(event, dict):
            continue
        at = event.get("at_ms")
        if (type(at) is int and 0 <= now - at <= 30 * 86_400_000
            and event.get("source") in _ALLOWED_SOURCES
            and event.get("event") in _ALLOWED_EVENTS
            and event.get("kind") in _ALLOWED_KINDS):
            events.append({
                "at_ms": at, "source": event["source"],
                "event": event["event"], "kind": event["kind"],
                "version": str(event.get("version") or "legacy"),
            })
    return events[-24:]


def record(source: str, event: str, kind: str) -> None:
    if os.environ.get("COST_GUARD_TEST_MODE") == "1":
        return
    if source not in _ALLOWED_SOURCES or event not in _ALLOWED_EVENTS or kind not in _ALLOWED_KINDS:
        return
    now = int(time.time() * 1000)
    try:
        FILE.parent.mkdir(parents=True, exist_ok=True)
        entries = recent_events(now)
        entries.append({"at_ms": now, "source": source, "event": event, "kind": kind, "version": DISPLAY_VERSION})
        temp = FILE.with_suffix(".tmp")
        temp.write_text(json.dumps(entries[-24:], separators=(",", ":")), encoding="utf-8")
        temp.replace(FILE)
    except OSError:
        return
