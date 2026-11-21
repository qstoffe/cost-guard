"""Small, optional history accelerators; callers own source qualification."""
from hashlib import sha256
import json
import sqlite3

from .repository import CacheEntry

WAIT_MS = 25
MAX_AGE_MS = 30 * 86_400_000


def sealed(value, *, limit):
    text = json.dumps(value, separators=(',', ':'), sort_keys=True, ensure_ascii=True, allow_nan=False)
    if len(text) <= limit:
        return [sha256(text.encode('ascii')).hexdigest(), value]
    return None


def unseal(payload, *, limit):
    if not isinstance(payload, list) or len(payload) != 2 or sealed(payload[1], limit=limit) != payload:
        raise ValueError('invalid warm history data')
    return payload[1]


def restore(repository, namespace, key, algorithm, revision, *, limit):
    try:
        row = repository.get(namespace, key, busy_timeout_ms=WAIT_MS)
        if row is not None and (row.algorithm_version, row.source_revision) == (algorithm, revision):
            return unseal(row.payload, limit=limit)
    except (OSError, sqlite3.Error, ValueError, TypeError, OverflowError, RecursionError):
        pass
    return None


def publish(repository, namespace, key, algorithm, revision, value, *, limit):
    try:
        payload = sealed(value, limit=limit)
        if payload is not None:
            repository.put_many((CacheEntry(namespace, key, payload, revision, algorithm),), busy_timeout_ms=WAIT_MS)
    except (OSError, sqlite3.Error, ValueError, TypeError, OverflowError, RecursionError):
        pass  # A failed acceleration must not invalidate the freshly computed view.
