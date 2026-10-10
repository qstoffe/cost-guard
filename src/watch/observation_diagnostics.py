"""Privacy-safe Watch visibility observations preserved for a later Diagnostics run.

Only bounded counters and fixed labels are persisted; no session or prompt IDs,
text, paths, credentials, or raw provider data ever enter this file. Recording
is best-effort: it must never alter Watch control flow.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Mapping

from src.version import DISPLAY_VERSION

FILE = Path(__file__).resolve().parents[2] / "logs" / "recovery" / "watch-observations.json"
_COUNT_KEYS = ("sessions", "roots", "active_metadata", "hydrated_roots", "startup_quiet_roots",
               "sampled_prompts", "older_completed", "visible_prompts", "running_prompts")
_REASONS = frozenset(("visible", "no_sessions", "no_roots", "no_sampled_prompts", "no_eligible_prompts"))
_PHASES = frozenset(("unknown", "catalog", "catalog_before", "messages", "catalog_after",
                     "revision_check", "normalize", "revision_changed", "complete"))
_KINDS = frozenset(("unavailable", "unreadable", "unsupported"))
_MAX_AGE_MS = 30 * 86_400_000
_PER_EVENT = 12  # scans and rarer source errors are retained independently
_REPEAT_MS = 600_000
_last_scan: dict[str, tuple[tuple[object, ...], int]] = {}


def _label(value: object, allowed: frozenset[str]) -> str | None:
    return value if isinstance(value, str) and value in allowed else None


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
        source = _label(item.get("source"), frozenset(("v1", "v2")))
        event = _label(item.get("event"), frozenset(("scan", "source_error")))
        if type(at) is not int or not 0 <= now - at <= _MAX_AGE_MS or not source or not event:
            continue
        clean: dict[str, object] = {"at_ms": at, "source": source,
                                    "event": event, "version": str(item.get("version", ""))[:16]}
        for key in _COUNT_KEYS:
            value = item.get(key)
            if type(value) is int and 0 <= value <= 10_000_000:
                clean[key] = value
        for key, allowed in (("reason", _REASONS), ("phase", _PHASES), ("kind", _KINDS)):
            if label := _label(item.get(key), allowed):
                clean[key] = label
        result.append(clean)
    return _bounded(result)


def _bounded(events: list[dict[str, object]]) -> list[dict[str, object]]:
    scans = [item for item in events if item["event"] == "scan"][-_PER_EVENT:]
    errors = [item for item in events if item["event"] == "source_error"][-_PER_EVENT:]
    return sorted(scans + errors, key=lambda item: int(item["at_ms"]))  # type: ignore[arg-type]


def _record(source: str, event: str, values: Mapping[str, object]) -> None:
    if os.environ.get("COST_GUARD_TEST_MODE") == "1" or source not in ("v1", "v2"):
        return
    now = int(time.time() * 1000)
    if event == "scan":
        # In-memory de-duplication: unchanged scans touch no file for ten minutes.
        signature = tuple(sorted(values.items()))
        previous = _last_scan.get(source)
        if previous and previous[0] == signature and now - previous[1] < _REPEAT_MS:
            return
        _last_scan[source] = (signature, now)
    try:
        item = {"at_ms": now, "source": source, "event": event, "version": DISPLAY_VERSION, **values}
        FILE.parent.mkdir(parents=True, exist_ok=True)
        temp = FILE.with_name(f"{FILE.name}.{os.getpid()}.{time.time_ns()}.tmp")
        try:
            temp.write_text(json.dumps(_bounded(recent_events(now) + [item]), separators=(",", ":")),
                            encoding="utf-8")
            temp.replace(FILE)
        finally:
            temp.unlink(missing_ok=True)
    except (OSError, ValueError, TypeError):
        pass


def record_scan(source: str, observation: Any, blocks: Mapping[str, Any],
                rows: Any, started_at_ms: int, *, startup_quiet_roots: int = 0) -> None:
    """Record one source scan; status-only redraws must not call this.

    Startup-quiet roots had stable cached analysis without anything displayable,
    so they count as older completed history rather than missing samples.
    """
    if os.environ.get("COST_GUARD_TEST_MODE") == "1":
        return
    sessions = observation.sessions
    roots = observation.roots
    prompts = [prompt for block in blocks.values() for prompt in block.rows]
    reason = ("visible" if rows else "no_sessions" if not sessions else "no_roots" if not roots
              else "no_sampled_prompts" if not prompts and not startup_quiet_roots else "no_eligible_prompts")
    _record(source, "scan", {
        "sessions": len(sessions), "roots": len(roots),
        "active_metadata": sum(item.active is True for item in sessions),
        "hydrated_roots": len(blocks), "startup_quiet_roots": startup_quiet_roots,
        "sampled_prompts": len(prompts),
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
        "kind": _label(kind, _KINDS) or "unsupported",
        "phase": _label(phase, _PHASES) or "unknown",
    })
