"""Bounded privacy-safe record of source connectivity transitions.

Records contain no endpoint, account, session ID, path, exception text or payload.
Failure to record a recovery cannot alter Watch's actual control flow.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
import os
from src.version import DISPLAY_VERSION
from .errors import FailureCode

ROOT = Path(__file__).resolve().parents[2]
FILE = ROOT / "logs" / "recovery" / "watch-recovery.json"
_ALLOWED_EVENTS = frozenset({"retrying", "recovered", "failed"})
_ALLOWED_SOURCES = frozenset({"v1", "v2"})
_ALLOWED_KINDS = frozenset({"available", "unavailable", "unreadable", "unsupported"})
_PHASES = frozenset({"unknown", "registration", "probe", "catalog", "snapshot", "event_stream",
                     "report", "selection", "initialization", "messages", "catalog_after"})
_EXCEPTION_TYPES = frozenset({"ConnectionRefusedError", "ConnectionResetError", "ConnectionAbortedError",
    "BrokenPipeError", "TimeoutError", "RemoteDisconnected", "OSError", "PermissionError",
    "FileNotFoundError", "JSONDecodeError", "UnicodeDecodeError", "HTTPException", "IncompleteRead"})


def _evidence(values: dict) -> dict[str, object]:
    clean: dict[str, object] = {}
    for key, allowed in (("category", {code.value for code in FailureCode}),
                         ("phase", _PHASES), ("exception_type", _EXCEPTION_TYPES)):
        value = values.get(key)
        if isinstance(value, str) and value in allowed:
            clean[key] = value
    for key in ("attempts", "duration_ms", "http_status", "stale_retries"):
        value = values.get(key)
        if type(value) is int and 0 <= value <= 10_000_000_000:
            clean[key] = value
    return clean


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
        labels = (event.get("source"), event.get("event"), event.get("kind"))
        if (type(at) is int and 0 <= now - at <= 30 * 86_400_000
            and all(isinstance(label, str) for label in labels)  # unhashable values are ignored
            and event.get("source") in _ALLOWED_SOURCES
            and event.get("event") in _ALLOWED_EVENTS
            and event.get("kind") in _ALLOWED_KINDS):
            events.append({
                "at_ms": at, "source": event["source"],
                "event": event["event"], "kind": event["kind"],
                "version": str(event.get("version") or "legacy")[:16],
                **_evidence(event),
            })
    return events[-24:]


def record(source: str, event: str, kind: str, **evidence) -> None:
    if os.environ.get("COST_GUARD_TEST_MODE") == "1":
        return
    if source not in _ALLOWED_SOURCES or event not in _ALLOWED_EVENTS or kind not in _ALLOWED_KINDS:
        return
    now = int(time.time() * 1000)
    try:
        FILE.parent.mkdir(parents=True, exist_ok=True)
        entries = recent_events(now)
        item = {"at_ms": now, "source": source, "event": event, "kind": kind,
                "version": DISPLAY_VERSION, **_evidence(evidence)}
        # Selection constructs fresh source objects; suppress repeated outage entries.
        if entries and event == "retrying":
            previous = entries[-1]
            if (now - int(previous["at_ms"]) < 600_000 and
                    all(previous.get(key) == item.get(key) for key in
                        ("source", "event", "kind", "category", "phase"))):
                return
        entries.append(item)
        temp = FILE.with_name(f"{FILE.name}.{os.getpid()}.{time.time_ns()}.tmp")  # concurrent Watches
        try:
            temp.write_text(json.dumps(entries[-24:], separators=(",", ":")), encoding="utf-8")
            temp.replace(FILE)
        finally:
            temp.unlink(missing_ok=True)
    except OSError:
        return
