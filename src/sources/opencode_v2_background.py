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
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from src.domain import BackgroundActivity, TerminalOutcome

from .errors import SourceDataError, SourceSchemaError, SourceUnavailableError

_JOB_KEYS = ("jobID", "shellID")
_KIND = re.compile(r"[a-z0-9_-]{1,24}")
_CANCELLED = frozenset({"killed", "cancelled", "canceled", "interrupted", "aborted"})
_FAILED = frozenset({"failed", "error", "timeout"})

@dataclass(frozen=True)
class ShellRegistry:
    """One ephemeral location observation; never exported or persisted as-is."""
    ids: frozenset[str]
    records: Mapping[str, Mapping[str, Any]]


RunningJobs = Callable[[], ShellRegistry | frozenset[str] | None]


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


def running_jobs(client: Any, directory: str, *, session_id: str = '', experimental: bool = False) -> ShellRegistry | None:
    """Jobs the service still lists as running at a location; None when unobservable."""
    try:
        value = client.json("/api/shell", query={"location[directory]": directory} if directory else None)
    except (SourceUnavailableError, SourceDataError, SourceSchemaError):
        return None
    data = value.get("data") if isinstance(value, Mapping) else None
    if not isinstance(data, list):
        return None
    records = {}
    for item in data:
        if not isinstance(item, Mapping) or not isinstance(item.get('id'), str) or item.get('status') != 'running':
            continue
        metadata = item.get('metadata') if isinstance(item.get('metadata'), Mapping) else {}
        record = {'sessionID': metadata.get('sessionID'),
                  **{key: item[key] for key in ('command', 'cwd', 'shell') if isinstance(item.get(key), str)}}
        # Contradictory duplicates must never be last-write-wins.
        records[item['id']] = record if item['id'] not in records or records[item['id']] == record else {'conflict': True}
    ids = frozenset(records)
    # This exact contract was checked on 2.2.7. The adapter opts in by source
    # version; unsupported/absent experimental routes remain a normal fallback.
    if experimental and session_id and not any(record.get('sessionID') == session_id
                                              and record.get('command') for record in records.values()):
        try:
            value = client.json('/api/experimental/job', query={
                'sessionID': session_id, 'kind': 'shell', 'status': 'running', 'descendants': 'false'})
        except (SourceUnavailableError, SourceDataError, SourceSchemaError):
            return ShellRegistry(ids, records)
        data = value.get('data') if isinstance(value, Mapping) else None
        for item in data if isinstance(data, list) else ():
            if (not isinstance(item, Mapping) or item.get('kind') != 'shell' or item.get('status') != 'running'
                    or item.get('sessionID') != session_id or not isinstance(item.get('shellID'), str)):
                continue
            key = item['shellID']
            record = {'sessionID': session_id, 'command': item.get('command')}
            previous = records.get(key)
            if previous and (previous.get('conflict') or previous.get('sessionID') not in (None, session_id)
                             or previous.get('command') not in (None, record['command'])):
                records[key] = {'conflict': True}
            else:
                records[key] = {**(previous or {}), **record}
        ids = frozenset(records)
    return ShellRegistry(ids, records)


def _starts(items: Iterable[Mapping[str, Any]], session_id: str) -> Iterable[tuple[str, str, int, str, str, str, bool, bool]]:
    for item in items:
        if item.get("type") != "assistant" or not isinstance(item.get("id"), str):
            continue
        if item.get('sessionID') not in (None, session_id):
            continue
        message_time = item.get("time") if isinstance(item.get("time"), Mapping) else {}
        for part in item.get("content") or ():
            state = part.get("state") if isinstance(part, Mapping) else None
            if not isinstance(state, Mapping):
                continue
            inputs = state.get('input') if isinstance(state.get('input'), Mapping) else {}
            if not (job := _job_id(state.get("metadata"))):
                continue
            # Missing original input can be recovered from the exact shell ID of
            # a returned call. A currently running foreground call isn't a detached job.
            if inputs.get('background') is not True and state.get('status') != 'completed':
                continue
            part_time = part.get("time") if isinstance(part.get("time"), Mapping) else {}
            started = _time(part_time.get("ran")) or _time(part_time.get("created")) or _time(message_time.get("created"))
            kind = str(part.get("name") or part.get("tool") or "").lower()
            if started:
                part_id = part.get("id") if isinstance(part.get("id"), str) else ""
                call_id = part.get("callID") if isinstance(part.get("callID"), str) else ""
                metadata = state['metadata']
                identities = {metadata[key] for key in _JOB_KEYS if isinstance(metadata.get(key), str) and metadata[key]}
                yield (job, kind if _KIND.fullmatch(kind) else "job", started, item["id"], part_id, call_id,
                       inputs.get('background') is not True,
                       len(identities) > 1 or metadata.get('sessionID') not in (None, session_id))


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
    registry: ShellRegistry | frozenset[str] | None = None
    registry_read = False
    for job, kind, started, owner, part_id, call_id, recovered, identity_conflict in _starts(items, session_id):
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
            ids = registry.ids if isinstance(registry, ShellRegistry) else registry
            if recovered and (ids is None or job not in ids):
                continue  # No original background flag: require positive live registry evidence.
            record = registry.records.get(job, {}) if isinstance(registry, ShellRegistry) else {}
            conflict = identity_conflict or record.get('conflict') or record.get('sessionID') not in (None, session_id)
            supplemental = tuple((key, record[key]) for key in ('command', 'cwd', 'shell')
                                 if isinstance(record.get(key), str)) if not conflict else ()
            activity = BackgroundActivity(identity, session_id, kind, started, owner,
                                          running=ids is None or job in ids,
                                          tool_part_id=part_id if registry is not None else "",
                                          tool_call_id=call_id if registry is not None else "",
                                          invocation_input=supplemental,
                                          invocation_reason=('Conflicting job ownership; command withheld.' if conflict else
                                              'Running registry unobservable; awaiting verified live source.' if registry is None else ''))
        previous = activities.get(identity)
        if previous is not None and (previous.owner_message_id, previous.tool_part_id, previous.tool_call_id) != (owner, activity.tool_part_id, activity.tool_call_id):
            activity = replace(previous, tool_part_id="", tool_call_id="", invocation_input=(),
                               invocation_reason='Conflicting job origins; command withheld.')
        activities[identity] = activity
    return tuple(sorted(activities.values(), key=lambda value: (value.started_at_ms, value.activity_id))), notice_ids
