"""Read-only discovery of compatible candidates in the legacy v2 cache.

The caller still has to bind the source and decide compatibility. Discovery
does not write, renew, truncate, or retire the legacy file and its sidecars.
"""
from contextlib import closing
from dataclasses import dataclass
import json
import sqlite3

from .session_scope import root_key


NAMESPACE = "session-summary"
PAGE_LIMIT = 32
MAX_PAYLOAD_BYTES = 128 * 1024


@dataclass(frozen=True, slots=True)
class LegacyCandidate:
    cache_key: str
    source_revision: str
    algorithm_version: str
    session_id: str
    payload: dict


@dataclass(frozen=True, slots=True)
class LegacyPage:
    next_key: str | None
    candidates: tuple[LegacyCandidate, ...] = ()
    unbound: int = 0
    unreadable: int = 0


def session_candidates(database, provenance, *, after="", limit=PAGE_LIMIT):
    """Read a bounded page for one already bound source, with honest gaps.

    Deleted roots can still match the durable source/root digest. An absent
    digest is not identity proof. The opaque cache key is retained for the
    caller to establish field/pricing compatibility, not treated as a version.
    """
    if not provenance.source_instance or not isinstance(after, str) or type(limit) is not int or not 1 <= limit <= PAGE_LIMIT:
        raise ValueError("invalid_legacy_scope")
    target = database.paths.database.absolute().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(target, uri=True, isolation_level=None, timeout=0.15)) as db:
        db.execute("PRAGMA query_only=ON")
        rows = db.execute("""
            SELECT e.cache_key, e.source_revision, e.algorithm_version,
                s.root_key, s.source_revision,
                CASE WHEN length(CAST(e.payload_json AS BLOB))<=? THEN e.payload_json END
            FROM cache_entries AS e LEFT JOIN cache_entry_lifecycle AS s
                ON s.namespace=e.namespace AND s.cache_key=e.cache_key
            WHERE e.namespace=? AND e.cache_key>?
            ORDER BY e.cache_key LIMIT ?
        """, (MAX_PAYLOAD_BYTES, NAMESPACE, after, limit + 1)).fetchall()
    if not rows:
        return LegacyPage(None)
    candidates, unbound, unreadable = [], 0, 0
    for key, revision, algorithm, digest, digest_revision, raw in rows[:limit]:
        if not (digest and revision and revision == digest_revision and algorithm):
            unbound += 1
            continue
        try:
            payload = json.loads(raw)
            session_id = payload["session_id"]
            if not isinstance(session_id, str) or not 0 < len(session_id) <= 200:
                raise ValueError("invalid_session_id")
        except (KeyError, TypeError, ValueError, RecursionError):
            unreadable += 1
            continue
        if root_key(provenance, session_id) != digest:
            unbound += 1
            continue
        candidates.append(LegacyCandidate(key, revision, algorithm, session_id, payload))
    return LegacyPage(rows[limit - 1][0] if len(rows) > limit else None, tuple(candidates), unbound, unreadable)
