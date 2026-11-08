"""Explicit, source-qualified lifecycle evidence; never infer roots from cache keys."""
from dataclasses import dataclass
import hashlib
import json


def root_key(provenance, session_id):
    value = (provenance.source_type, provenance.source_generation, provenance.source_instance, session_id)
    return hashlib.sha256(json.dumps(value, separators=(',', ':')).encode('utf-8')).hexdigest()


@dataclass(frozen=True, slots=True)
class SessionScope:
    root_key: str
    activity_ms: int | None


def snapshot_scope(snapshot):
    """Only complete, quiescent trees establish a last *actual* activity time.

    Session creation/update/archive clocks are deliberately absent. Missing message
    or execution timing, unfinished children and partial/custom sources keep the
    entry ineligible. No source acquisition or startup backfill happens here.
    """
    times = [message.created_at_ms for message in snapshot.messages]
    times.extend(event.created_at_ms for event in snapshot.events)
    times.extend(invocation.created_at_ms for invocation in snapshot.invocations)
    times.extend(invocation.completed_at_ms for invocation in snapshot.invocations)
    required = times
    complete = (snapshot.complete and bool(required)
        and all(type(value) is int and value > 0 for value in required)
        and not any(session.active is True for session in snapshot.sessions)
        and not any(work.running for work in snapshot.background))
    times.extend(message.completed_at_ms for message in snapshot.messages if message.completed_at_ms is not None)
    times.extend(part.updated_at_ms for part in snapshot.parts)
    times.extend(work.ended_at_ms for work in snapshot.background if work.ended_at_ms is not None)
    activity = max(times) if complete and all(type(value) is int and value > 0 for value in times) else None
    return SessionScope(root_key(snapshot.root.provenance, snapshot.root.session_id), activity)
