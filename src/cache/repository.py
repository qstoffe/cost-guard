"""Reconstructible cache state and atomic model sightings atop Cost Guard SQLite."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .database import CacheDatabase


@dataclass(frozen=True, slots=True)
class CacheEntry:
    namespace: str
    key: str
    payload: Any
    source_revision: str | None
    algorithm_version: str | None


class CacheRepository:
    def __init__(self, database: CacheDatabase) -> None:
        self.database = database

    def put(
        self,
        namespace: str,
        key: str,
        payload: Any,
        *,
        source_revision: str | None = None,
        algorithm_version: str | None = None,
    ) -> None:
        payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        with self.database.connect() as connection:
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

    def get(self, namespace: str, key: str) -> CacheEntry | None:
        with self.database.connect() as connection:
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

    def get_or_create_model_first_seen_at(self, model_id: str, first_seen_at: str) -> str:
        """Atomically keep the first UTC sighting for one provider-qualified model ID."""
        if not model_id:
            raise ValueError("model_id must not be empty")
        with self.database.connect() as connection:
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
