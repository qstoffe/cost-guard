"""Durable Web display evidence, independent of disposable cache lifecycle."""
from contextlib import closing, contextmanager
from dataclasses import dataclass, field
import json
import logging
import sqlite3
from threading import Lock

from . import session_projection
from .legacy_report_cache import retire_cache
from .signature import dependency_signature


APPLICATION_ID = 0x43475231  # CGR1
SCHEMA = 1
EVIDENCE_ENVELOPE = 'web-fact-envelope/1'
LEGACY_IMPORT = 'import-fr000778'
REPORT_CHECKPOINTS = 'shared-history'
WEB_ARCHIVE_FILENAME = 'cost-guard-report-v1.sqlite3'
PREVIOUS_ARCHIVE_FILENAME = 'cost-guard-web-history-v1.sqlite3'
LOG = logging.getLogger(__name__)


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
    def __init__(self, directory, *, previous_directory=None, retire_previous=False):
        self.path = (directory / WEB_ARCHIVE_FILENAME).absolute()
        self._uri = self.path.as_uri()
        self._lock = Lock()
        self._generations = {}
        self._retire_paths = {}
        if retire_previous:
            self._retire_paths[self.path.with_name(PREVIOUS_ARCHIVE_FILENAME)] = dict(
                application_id=0x43475732, versions=(1, 2))
            self._retire_paths[self.path.with_name('cost-guard-display-v1.sqlite3')] = dict(
                application_id=0x43474448, versions=(1,))
            self._retire_paths[self.path.with_name('cost-guard-cache-v2.sqlite3')] = dict(generation=2)
            if previous_directory is not None:
                self._retire_paths[(previous_directory / PREVIOUS_ARCHIVE_FILENAME).absolute()] = dict(
                    application_id=0x43475732, versions=(1, 2))

    def generation(self, domain):
        with self._lock:
            return self._generations.get(domain, 0)

    def note_publication(self, domains):
        with self._lock:
            for domain in domains:
                self._generations[domain] = self._generations.get(domain, 0) + 1

    @staticmethod
    def _history_index(db):
        db.execute('''CREATE INDEX IF NOT EXISTS fact_history_by_cursor
                      ON fact_cursors (domain, cursor)''')
        db.execute('''CREATE INDEX IF NOT EXISTS fact_history_by_item
                      ON fact_cursors (domain, item, cursor)''')

    @contextmanager
    def _connect(self, *, write=False):
        mode = 'rw' if write else 'ro'
        with closing(sqlite3.connect(f'{self._uri}?mode={mode}', uri=True, timeout=0.1)) as db, db:
            if not write:
                db.execute('PRAGMA query_only=ON')
                db.execute('BEGIN')
            if (db.execute('PRAGMA application_id').fetchone()[0],
                    db.execute('PRAGMA user_version').fetchone()[0]) != (APPLICATION_ID, SCHEMA):
                raise sqlite3.DatabaseError('unrecognized report cache')
            yield db

    def initialize(self):
        self._initialize_schema()
        if self._retire_paths:
            self._retire_obsolete()

    def _initialize_schema(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=0.1)) as db, db:
            current_id = db.execute('PRAGMA application_id').fetchone()[0]
            current_version = db.execute('PRAGMA user_version').fetchone()[0]
            if (current_id, current_version) == (APPLICATION_ID, SCHEMA):
                if db.execute('PRAGMA journal_mode').fetchone()[0] != 'wal':
                    raise sqlite3.DatabaseError('report cache requires WAL')
                return
            if current_id or current_version or db.execute('SELECT 1 FROM sqlite_schema LIMIT 1').fetchone():
                raise sqlite3.DatabaseError('unrecognized report cache')
            if db.execute('PRAGMA journal_mode=WAL').fetchone()[0] != 'wal':
                raise sqlite3.DatabaseError('report cache requires WAL')
            db.execute('BEGIN IMMEDIATE')
            if (db.execute('PRAGMA application_id').fetchone()[0],
                    db.execute('PRAGMA user_version').fetchone()[0]) == (APPLICATION_ID, SCHEMA):
                return
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
            db.execute('CREATE TABLE report_metadata (name TEXT PRIMARY KEY) WITHOUT ROWID')
            session_projection.create_schema(db)
            db.execute(f'PRAGMA application_id={APPLICATION_ID}')
            db.execute(f'PRAGMA user_version={SCHEMA}')

    def _retire_obsolete(self):
        try:
            with self._connect() as db:
                if db.execute("SELECT 1 FROM report_metadata WHERE name='pre-report-cache-retired'").fetchone():
                    return
            complete = True
            for path, identity in self._retire_paths.items():
                try:
                    retire_cache(path, **identity)
                except (OSError, sqlite3.Error):
                    LOG.warning('obsolete_report_cache_retirement_pending: %s', path.name)
                    complete = False
            if complete:
                with self._connect(write=True) as db:
                    db.execute("INSERT OR IGNORE INTO report_metadata VALUES ('pre-report-cache-retired')")
        except (OSError, sqlite3.Error):
            LOG.warning('obsolete_report_cache_retirement_pending')

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

    def history_item_count(self, domain: str) -> int:
        """Count distinct retained keys across partitions without decoding any facts."""
        with self._connect() as db:
            return db.execute('SELECT COUNT(DISTINCT item) FROM fact_cursors WHERE domain=?', (domain,)).fetchone()[0]

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

    def publish_session(self, partition, domains, item, keys, last_at, latest_at):
        if not partition:
            return False
        return self._publish_batch(partition, domains, retain_conflicts=False,
                                   ready_session=(item, keys, last_at, latest_at))

    def ready_sessions_page(self, **page):
        with self._connect() as db:
            total, offset, values = session_projection.read_ready(db, **page)
            return total, offset, tuple(self._historical_facts(values))

    def _publish_batch(self, partition, domains, *, retain_conflicts, ready_session=None):
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
                if ready_session is not None and value[1] == session_projection.SESSIONS_DOMAIN:
                    item, keys, last_at, latest_at = ready_session
                    if item == value[2]:
                        session_projection.save_ready(db, item, partition, value[3], value[4], value[5],
                                                      keys, last_at, latest_at)
        if changed:
            self.note_publication(changed)
        return True
