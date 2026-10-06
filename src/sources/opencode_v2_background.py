"""Normalize OpenCode V2 background jobs into source-neutral activities.

A backgrounded tool call returns immediately with ``state.input.background``
and a native job identity in ``state.metadata``. Its end is a later persisted
``synthetic`` notice whose metadata names the same job; OpenCode then resumes
the model automatically. A job without a notice is still running only while the
service's location-scoped shell registry lists it. Native identities stay here.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Any, Callable, Iterable, Mapping, Sequence

from src.domain import BackgroundActivity, TerminalOutcome

from .errors import SourceDataError, SourceUnavailableError

_JOB_KEYS = ("jobID", "shellID")
_KIND = re.compile(r"[a-z0-9_-]{1,24}")
_CANCELLED = frozenset({"killed", "cancelled", "canceled", "interrupted", "aborted"})
_FAILED = frozenset({"failed", "error", "timeout"})

RunningJobs = Callable[[], frozenset[str] | None]


def _job_id(metadata: Any) -> str | None:
    if not isinstance(metadata, Mapping):
        return None
    for key in _JOB_KEYS:
        value = metadata.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _time(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        return None
    return int(value)


def _outcome(metadata: Mapping[str, Any]) -> TerminalOutcome | None:
    state = str(metadata.get("state") or "").lower()
    if state in _CANCELLED:
        return TerminalOutcome.CANCELLATION
    if state in _FAILED:
        return TerminalOutcome.FAILURE
    if state == "completed":
        exit_code = metadata.get("exit")
        if isinstance(exit_code, (int, float)) and not isinstance(exit_code, bool):
            return TerminalOutcome.SUCCESS if exit_code == 0 else TerminalOutcome.FAILURE
    return None  # ended, but the outcome is not one Cost Guard can name


def completion_notice_job(item: Mapping[str, Any]) -> str | None:
    """Return the job a persisted synthetic background-completion notice ends."""
    return _job_id(item.get("metadata")) if item.get("type") == "synthetic" else None


def running_jobs(client: Any, directory: str) -> frozenset[str] | None:
    """Jobs the service still lists as running at a location; None when unobservable."""
    try:
        value = client.json("/api/shell", query={"location[directory]": directory} if directory else None)
    except (SourceUnavailableError, SourceDataError):
        return None
    data = value.get("data") if isinstance(value, Mapping) else None
    if not isinstance(data, list):
        return None
    return frozenset(item["id"] for item in data if isinstance(item, Mapping) and isinstance(item.get("id"), str)
                     and str(item.get("status", "")).lower() == "running")


def _starts(items: Iterable[Mapping[str, Any]]) -> Iterable[tuple[str, str, int, str]]:
    for item in items:
        if item.get("type") != "assistant" or not isinstance(item.get("id"), str):
            continue
        message_time = item.get("time") if isinstance(item.get("time"), Mapping) else {}
        for part in item.get("content") or ():
            state = part.get("state") if isinstance(part, Mapping) else None
            if not isinstance(state, Mapping) or not isinstance(state.get("input"), Mapping):
                continue
            if state["input"].get("background") is not True or not (job := _job_id(state.get("metadata"))):
                continue
            part_time = part.get("time") if isinstance(part.get("time"), Mapping) else {}
            started = _time(part_time.get("ran")) or _time(part_time.get("created")) or _time(message_time.get("created"))
            kind = str(part.get("name") or part.get("tool") or "").lower()
            if started:
                yield job, kind if _KIND.fullmatch(kind) else "job", started, item["id"]


def background_activities(
    items: Sequence[Mapping[str, Any]], *, session_id: str, running_jobs: RunningJobs,
) -> tuple[tuple[BackgroundActivity, ...], frozenset[str]]:
    """Pair job starts with completion notices; ask the registry only if needed.

    ``running_jobs`` returns the native jobs still running for this session's
    location, or None when that cannot be observed; uncertainty keeps a job
    running rather than inventing an end. Also returns the notice message IDs.
    """
    notices = {job: item for item in items if (job := completion_notice_job(item))}
    notice_ids = frozenset(str(item["id"]) for item in notices.values() if isinstance(item.get("id"), str))
    activities: dict[str, BackgroundActivity] = {}
    registry: frozenset[str] | None = None
    registry_read = False
    for job, kind, started, owner in _starts(items):
        identity = "bg:" + hashlib.sha256(f"{session_id}\0{job}".encode("utf-8")).hexdigest()[:20]
        notice = notices.get(job)
        if notice is not None:
            metadata = notice.get("metadata")
            notice_time = notice.get("time") if isinstance(notice.get("time"), Mapping) else {}
            activity = BackgroundActivity(
                identity, session_id, kind, started, owner, running=False,
                ended_at_ms=_time(notice_time.get("created")), outcome=_outcome(metadata),
                completion_event_id=str(notice.get("id")) if notice.get("id") else None,
            )
        else:
            if not registry_read:
                registry, registry_read = running_jobs(), True
            activity = BackgroundActivity(identity, session_id, kind, started, owner,
                                          running=registry is None or job in registry)
        activities.setdefault(identity, activity)
    return tuple(sorted(activities.values(), key=lambda value: (value.started_at_ms, value.activity_id))), notice_ids
