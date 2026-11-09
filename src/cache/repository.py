"""Reconstructible cache state and atomic model sightings atop Cost Guard SQLite."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .database import CacheDatabase, DEFAULT_BUSY_TIMEOUT_MS
from .model_notices import ModelSightings
from .lifecycle import CacheLifecycle, publish
from .session_scope import SessionScope


@dataclass(frozen=True, slots=True)
class CacheEntry:
    namespace: str
    key: str
    payload: Any
    source_revision: str | None
    algorithm_version: str | None
    session_scope: SessionScope | None = None


class CacheRepository:
    def __init__(self, database: CacheDatabase) -> None:
        self.database = database
        self.model_sightings = ModelSightings(self)
        self.lifecycle = CacheLifecycle(database)

    def put(
        self,
        namespace: str,
        key: str,
        payload: Any,
        *,
        source_revision: str | None = None,
        algorithm_version: str | None = None,
        busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
        session_scope: SessionScope | None = None,
    ) -> None:
        payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        with self.database.connect(operation="write", busy_timeout_ms=busy_timeout_ms) as connection:
            connection.execute(
                """INSERT INTO cache_entries(
                       namespace, cache_key, payload_json, source_revision, algorithm_version, updated_at_utc
                   ) VALUES(?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(namespace, cache_key) DO UPDATE SET
                       payload_json=excluded.payload_json,
                       source_revision=excluded.source_revision,
                       algorithm_version=excluded.algorithm_version,
                       updated_at_utc=CURRENT_TIMESTAMP""",
                (namespace, key, payload_json, source_revision, algorithm_version),
            )
            publish(connection, namespace, key, source_revision, session_scope)

    def get(self, namespace: str, key: str, *, busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS) -> CacheEntry | None:
        with self.database.connect(operation="read", busy_timeout_ms=busy_timeout_ms) as connection:
            row = connection.execute(
                """SELECT payload_json, source_revision, algorithm_version
                   FROM cache_entries WHERE namespace=? AND cache_key=?""",
                (namespace, key),
            ).fetchone()
        if row is None:
            return None
        try:
            payload = json.loads(row[0])
        except (json.JSONDecodeError, TypeError):
            return None
        return CacheEntry(namespace, key, payload, row[1], row[2])

    def get_or_create_model_first_seen_at(
        self, model_id: str, first_seen_at: str, *, busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    ) -> str:
        """Atomically keep the first UTC sighting for one provider-qualified model ID."""
        if not model_id:
            raise ValueError("model_id must not be empty")
        with self.database.connect(operation="write", busy_timeout_ms=busy_timeout_ms) as connection:
            connection.execute(
                """INSERT OR IGNORE INTO model_first_sightings(model_id, first_seen_at)
                   VALUES(?, ?)""",
                (model_id, first_seen_at),
            )
            row = connection.execute(
                "SELECT first_seen_at FROM model_first_sightings WHERE model_id=?", (model_id,)
            ).fetchone()
        if row is None:
            raise RuntimeError("first-sighting insert was not readable")
        return str(row[0])

    def get_many(self, namespace: str, keys, *, busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS) -> dict[str, CacheEntry]:
        """Bounded SQL batches on one connection; malformed disposable JSON is a miss."""
        keys = tuple(dict.fromkeys(keys))
        result = {}
        if not keys:
            return result
        with self.database.connect(operation="read", busy_timeout_ms=busy_timeout_ms) as connection:
            for start in range(0, len(keys), 500):
                chunk = keys[start:start + 500]
                placeholders = ",".join("?" for _key in chunk)
                rows = connection.execute(
                    "SELECT cache_key,payload_json,source_revision,algorithm_version FROM cache_entries "
                    f"WHERE namespace=? AND cache_key IN ({placeholders})", (namespace, *chunk)).fetchall()
                for key, payload, revision, algorithm in rows:
                    try:
                        result[key] = CacheEntry(namespace, key, json.loads(payload), revision, algorithm)
                    except (json.JSONDecodeError, TypeError):
                        pass
        return result

    def put_many(self, entries, *, busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS) -> None:
        """Atomically publish a caller-bounded batch of independent reconstructible entries."""
        entries = tuple(entries)
        rows = [(entry.namespace, entry.key,
            json.dumps(entry.payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
            entry.source_revision, entry.algorithm_version) for entry in entries]
        if not rows:
            return
        with self.database.connect(operation="write", busy_timeout_ms=busy_timeout_ms) as connection:
            connection.executemany("""INSERT INTO cache_entries(
                namespace,cache_key,payload_json,source_revision,algorithm_version,updated_at_utc)
                VALUES(?,?,?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(namespace,cache_key) DO UPDATE SET
                payload_json=excluded.payload_json,source_revision=excluded.source_revision,
                algorithm_version=excluded.algorithm_version,updated_at_utc=CURRENT_TIMESTAMP""", rows)
            for entry in entries:
                publish(connection, entry.namespace, entry.key, entry.source_revision, entry.session_scope)
