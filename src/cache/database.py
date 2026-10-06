"""Disposable generation-named SQLite cache database."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

CACHE_SCHEMA_GENERATION = 2
CACHE_FILENAME = f"cost-guard-cache-v{CACHE_SCHEMA_GENERATION}.sqlite3"
DEFAULT_BUSY_TIMEOUT_MS = 5000


@dataclass(frozen=True, slots=True)
class CachePaths:
    directory: Path
    database: Path


def cache_paths(package_root: Path, generation: int = CACHE_SCHEMA_GENERATION) -> CachePaths:
    directory = package_root / "cache"
    return CachePaths(directory, directory / f"cost-guard-cache-v{generation}.sqlite3")


class CacheDatabase:
    """Owns schema creation and configured short-lived SQLite connections."""

    def __init__(self, package_root: Path, generation: int = CACHE_SCHEMA_GENERATION) -> None:
        self.package_root = package_root
        self.generation = generation
        self.paths = cache_paths(package_root, generation)

    def initialize(self) -> Path:
        self.paths.directory.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS cache_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS cache_entries (
                    namespace TEXT NOT NULL,
                    cache_key TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    source_revision TEXT,
                    algorithm_version TEXT,
                    updated_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (namespace, cache_key)
                );
                """
            )
            connection.execute(
                """INSERT INTO cache_metadata(key, value, updated_at_utc)
                   VALUES('schema_generation', ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at_utc=CURRENT_TIMESTAMP""",
                (str(self.generation),),
            )
        return self.paths.database

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Yield one configured connection and always close it after commit/rollback."""
        self.paths.directory.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(
            self.paths.database,
            timeout=DEFAULT_BUSY_TIMEOUT_MS / 1000,
            isolation_level="DEFERRED",
        )
        try:
            connection.execute(f"PRAGMA busy_timeout={DEFAULT_BUSY_TIMEOUT_MS}")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.execute("PRAGMA foreign_keys=ON")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()
