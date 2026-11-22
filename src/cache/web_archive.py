"""Durable Web display evidence, independent of disposable cache lifecycle."""
from contextlib import closing, contextmanager
from dataclasses import dataclass
import json
import sqlite3

from src.analysis.cache import ANALYSIS_ALGORITHM_VERSION, dependency_signature


APPLICATION_ID = 0x43475732  # CGW2
SCHEMA = 1


def source_partition(generation, instance):
    if generation in {'v1', 'v2'} and isinstance(instance, str) and instance:
        return dependency_signature(('OpenCode', generation, instance))
    return None


@dataclass(frozen=True, slots=True)
class ArchiveFact:
    revision: str
    observed_ms: int
    value: dict


class WebArchive:
    def __init__(self, root):
        self.path = root / 'cache' / 'cost-guard-web-history-v1.sqlite3'

    @contextmanager
    def _connect(self, *, write=False):
        uri = self.path.resolve().as_uri()
        mode = 'rw' if write else 'ro'
        with closing(sqlite3.connect(f'{uri}?mode={mode}', uri=True, timeout=0.1)) as db, db:
            if (db.execute('PRAGMA application_id').fetchone()[0],
                    db.execute('PRAGMA user_version').fetchone()[0]) != (APPLICATION_ID, SCHEMA):
                raise sqlite3.DatabaseError('unrecognized Web history archive')
            yield db

    def initialize(self):
        if self.path.exists():
            with self._connect():
                return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=0.1)) as db, db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('BEGIN IMMEDIATE')
            current_id = db.execute('PRAGMA application_id').fetchone()[0]
            current_version = db.execute('PRAGMA user_version').fetchone()[0]
            if (current_id, current_version) == (APPLICATION_ID, SCHEMA):
                return
            if current_id or current_version or db.execute('SELECT 1 FROM sqlite_schema LIMIT 1').fetchone():
                raise sqlite3.DatabaseError('unrecognized Web history archive')
            db.execute('''CREATE TABLE facts (
                partition TEXT NOT NULL,
                domain TEXT NOT NULL,
                item TEXT NOT NULL,
                algorithm TEXT NOT NULL,
                revision TEXT NOT NULL,
                observed_ms INTEGER NOT NULL,
                value TEXT NOT NULL,
                PRIMARY KEY (partition, domain, algorithm, item)
            ) WITHOUT ROWID''')
            db.execute(f'PRAGMA application_id={APPLICATION_ID}')
            db.execute(f'PRAGMA user_version={SCHEMA}')

    def read(self, partition, domain, *, item=None):
        if not partition or not self.path.is_file():
            return {}
        sql = '''SELECT item, revision, observed_ms, value FROM facts
                 WHERE partition=? AND domain=? AND algorithm=?'''
        values = (partition, domain, ANALYSIS_ALGORITHM_VERSION)
        if item is not None:
            sql += ' AND item=?'
            values += (item,)
        with self._connect() as db:
            rows = db.execute(sql, values).fetchall()
        facts = {}
        for key, revision, observed, encoded in rows:
            try:
                value = json.loads(encoded)
            except (ValueError, TypeError):
                continue
            if isinstance(value, dict):
                facts[key] = ArchiveFact(revision, observed, value)
        return facts

    def publish(self, partition, domain, facts):
        if not partition or not facts:
            return
        values = [(partition, domain, key, ANALYSIS_ALGORITHM_VERSION, fact.revision, fact.observed_ms,
                   json.dumps(fact.value, ensure_ascii=True, allow_nan=False, separators=(',', ':')))
                  for key, fact in facts.items()]
        with self._connect(write=True) as db:
            db.executemany('''INSERT INTO facts VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(partition, domain, algorithm, item) DO UPDATE SET
                    revision=excluded.revision, observed_ms=excluded.observed_ms, value=excluded.value
                WHERE facts.observed_ms < excluded.observed_ms
                   OR (facts.observed_ms = excluded.observed_ms AND facts.revision = excluded.revision)
            ''', values)
