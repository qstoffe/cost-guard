"""Durable Web display evidence, independent of disposable cache lifecycle."""
from contextlib import closing, contextmanager
from dataclasses import dataclass, field
import json
import sqlite3
from threading import Lock

from .signature import dependency_signature


APPLICATION_ID = 0x43475732  # CGW2
SCHEMA = 2
EVIDENCE_ENVELOPE = 'web-fact-envelope/1'
LEGACY_IMPORT = 'import-fr000778'
REPORT_CHECKPOINTS = 'shared-history'


def source_partition(generation, instance, epoch=None):
    if not isinstance(instance, str) or not instance:
        return None
    if generation == 'v1':
        return dependency_signature(('OpenCode', generation, instance))
    if generation == 'v2' and isinstance(epoch, str) and epoch:
        return dependency_signature(('OpenCode', generation, instance, epoch))
    return None


def scope_partition(scope):
    kind, instance, epoch = scope
    return source_partition({'opencode-v1': 'v1', 'opencode-v2': 'v2'}.get(kind), instance, epoch)


@dataclass(frozen=True, slots=True)
class ArchiveFact:
    revision: str
    observed_ms: int
    value: dict
    partition: str = field(default='', compare=False)

    @property
    def history_rank(self):
        return history_rank(self.partition, self.observed_ms, self.revision)


def history_rank(partition, observed_ms, revision):
    return not partition.startswith(LEGACY_IMPORT), observed_ms, partition, revision


class WebArchive:
    def __init__(self, directory):
        self.path = directory / 'cost-guard-web-history-v1.sqlite3'
        self._lock = Lock()
        self._generations = {}

    def generation(self, domain):
        with self._lock:
            return self._generations.get(domain, 0)

    @staticmethod
    def _history_index(db):
        db.execute('''CREATE INDEX IF NOT EXISTS fact_history_by_cursor
                      ON fact_cursors (domain, cursor)''')
        db.execute('''CREATE INDEX IF NOT EXISTS fact_history_by_item
                      ON fact_cursors (domain, item, cursor)''')

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
            with closing(sqlite3.connect(self.path, timeout=0.1)) as db:
                if (db.execute('PRAGMA application_id').fetchone()[0],
                        db.execute('PRAGMA user_version').fetchone()[0]) == (APPLICATION_ID, SCHEMA):
                    self._history_index(db)
                    return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=0.1)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            current_id = db.execute('PRAGMA application_id').fetchone()[0]
            current_version = db.execute('PRAGMA user_version').fetchone()[0]
            if (current_id, current_version) == (APPLICATION_ID, SCHEMA):
                self._history_index(db)
                return
            if current_id or current_version or db.execute('SELECT 1 FROM sqlite_schema LIMIT 1').fetchone():
                if (current_id, current_version) != (APPLICATION_ID, 1):
                    raise sqlite3.DatabaseError('unrecognized Web history archive')
                # The upgrade is additive. Existing algorithm tags remain on disk;
                # the shared projections decide what fields they can still decode.
            else:
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
            # Keep one cursor per current item, not an unbounded mutation log.
            # Replacing a cursor moves the item forward without duplicating payloads.
            db.execute('''CREATE TABLE fact_cursors (
                cursor INTEGER PRIMARY KEY AUTOINCREMENT,
                partition TEXT NOT NULL,
                domain TEXT NOT NULL,
                algorithm TEXT NOT NULL,
                item TEXT NOT NULL,
                UNIQUE (partition, domain, algorithm, item)
            )''')
            db.execute('''CREATE INDEX fact_cursor_range
                          ON fact_cursors (partition, domain, algorithm, cursor)''')
            self._history_index(db)
            db.execute('''INSERT INTO fact_cursors (partition, domain, algorithm, item)
                          SELECT partition, domain, algorithm, item FROM facts''')
            db.execute(f'PRAGMA application_id={APPLICATION_ID}')
            db.execute(f'PRAGMA user_version={SCHEMA}')
            db.commit()
            db.execute('PRAGMA journal_mode=WAL')

    def import_checkpoint(self, domain, item):
        with self._connect() as db:
            row = db.execute('''SELECT revision FROM facts
                WHERE partition=? AND domain=? AND algorithm=? AND item=?''',
                (LEGACY_IMPORT, domain, EVIDENCE_ENVELOPE, item)).fetchone()
        return row[0] if row else None

    def record_import_checkpoint(self, domain, item, stamp):
        with self._connect(write=True) as db:
            db.execute('''INSERT INTO facts VALUES (?, ?, ?, ?, ?, 0, '{}')
                ON CONFLICT(partition, domain, algorithm, item) DO UPDATE SET revision=excluded.revision''',
                (LEGACY_IMPORT, domain, item, EVIDENCE_ENVELOPE, stamp))

    def history_rows(self, domain):
        """Iterate every readable fact; callers select a decodable logical winner."""
        if not self.path.is_file():
            return
        with self._connect() as db:
            rows = db.execute('''SELECT item, revision, observed_ms, value, partition
                FROM facts WHERE domain=?''', (domain,))
            yield from self._historical_facts(rows)

    def history_changes(self, domain, after, *, limit=64):
        if not self.path.is_file():
            return after, (), False
        with self._connect() as db:
            rows = db.execute('''SELECT c.cursor, f.item, f.revision, f.observed_ms, f.value, f.partition
                FROM fact_cursors AS c JOIN facts AS f USING (partition, domain, algorithm, item)
                WHERE c.domain=? AND c.cursor>? ORDER BY c.cursor LIMIT ?''',
                (domain, after, limit + 1)).fetchall()
        batch = rows[:limit]
        return (batch[-1][0] if batch else after, tuple(self._historical_facts(row[1:] for row in batch)),
                len(rows) > limit)

    def history_item(self, domain, key, after):
        if not self.path.is_file():
            return after, ()
        with self._connect() as db:
            cursor = db.execute('SELECT MAX(cursor) FROM fact_cursors WHERE domain=? AND item=?',
                                (domain, key)).fetchone()[0] or 0
            if cursor <= after:
                return after, ()
            rows = db.execute('''SELECT c.cursor, f.item, f.revision, f.observed_ms, f.value, f.partition
                FROM fact_cursors AS c JOIN facts AS f USING (partition, domain, algorithm, item)
                WHERE c.domain=? AND c.item=?
                ORDER BY (substr(c.partition, 1, ?)<>?) DESC, f.observed_ms DESC, c.partition DESC, f.revision DESC''',
                (domain, key, len(LEGACY_IMPORT), LEGACY_IMPORT)).fetchall()
        return max((row[0] for row in rows), default=cursor), tuple(self._historical_facts(row[1:] for row in rows))

    def history_cursor(self, domain):
        if not self.path.is_file():
            return 0
        with self._connect() as db:
            return db.execute('SELECT MAX(cursor) FROM fact_cursors WHERE domain=?', (domain,)).fetchone()[0] or 0

    @staticmethod
    def _historical_facts(rows):
        for key, revision, observed, raw, partition in rows:
            try:
                value = json.loads(raw)
            except (ValueError, TypeError):
                continue
            if isinstance(value, dict):
                yield key, ArchiveFact(revision, observed, value, partition)

    def publish(self, partition, domain, facts):
        return self.publish_batch(partition, {domain: facts})

    def import_batch(self, partition, domains):
        """Already readable legacy facts win conflicting observations without retrying."""
        if not partition.startswith(LEGACY_IMPORT):
            raise ValueError('legacy import partition required')
        self._publish_batch(partition, domains, retain_conflicts=True)

    def publish_batch(self, partition, domains):
        if not partition:
            return False
        return self._publish_batch(partition, domains, retain_conflicts=False)

    def _publish_batch(self, partition, domains, *, retain_conflicts):
        values = [(partition, domain, key, EVIDENCE_ENVELOPE, fact.revision, fact.observed_ms,
                    json.dumps(fact.value, ensure_ascii=True, allow_nan=False, separators=(',', ':')))
                   for domain, facts in domains.items() for key, fact in facts.items()]
        changed = set()
        with self._connect(write=True) as db:
            db.execute('BEGIN IMMEDIATE')
            admitted = []
            for value in values:
                previous = db.execute('''SELECT revision, observed_ms FROM facts
                    WHERE partition=? AND domain=? AND item=? AND algorithm=?''', value[:4]).fetchone()
                if previous is not None:
                    old_revision, old_observed = previous
                    if old_observed >= value[5] and old_revision != value[4]:
                        if retain_conflicts:
                            continue
                        return False
                    if old_observed > value[5]:
                        continue  # Same revision: keep newer detail, don't lose other domains.
                admitted.append(value)
            for value in admitted:
                cursor = db.execute('''INSERT INTO facts VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(partition, domain, algorithm, item) DO UPDATE SET
                        revision=excluded.revision, observed_ms=excluded.observed_ms, value=excluded.value
                 WHERE facts.revision<>excluded.revision OR facts.value<>excluded.value
                    ''', value)
                if cursor.rowcount:
                    db.execute('INSERT OR REPLACE INTO fact_cursors (partition, domain, item, algorithm) VALUES (?, ?, ?, ?)',
                               value[:4])
                    changed.add(value[1])
                else:
                    db.execute('''UPDATE facts SET observed_ms=?
                        WHERE partition=? AND domain=? AND item=? AND algorithm=? AND observed_ms<?''',
                        (value[5], *value[:4], value[5]))
        if changed:
            with self._lock:
                for domain in changed:
                    self._generations[domain] = self._generations.get(domain, 0) + 1
        return True
