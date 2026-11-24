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
SCHEMA = 3
EVIDENCE_ENVELOPE = 'web-fact-envelope/1'
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
        return self.observed_ms, self.partition, self.revision


class WebArchive:
    def __init__(self, directory, *, previous_directory=None, retire_previous=False, notify_sessions=None,
                 retain_writer=False):
        self.path = (directory / WEB_ARCHIVE_FILENAME).absolute()
        self._uri = self.path.as_uri()
        self._lock = Lock()
        self._generations = {}
        self._writer_lock = Lock() if retain_writer else None
        self._writer = None
        self._writer_closed = False
        self._runtime_owner = None
        self.notify_sessions = notify_sessions
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

    def note_publication(self, domains, *, session_times=None):
        with self._lock:
            for domain in domains:
                self._generations[domain] = self._generations.get(domain, 0) + 1
            if self.notify_sessions is not None and session_projection.SESSIONS_DOMAIN in domains:
                self.notify_sessions(session_times)

    @staticmethod
    def _history_index(db):
        db.execute('''CREATE INDEX IF NOT EXISTS fact_history_by_cursor
                      ON fact_cursors (domain, cursor)''')
        db.execute('''CREATE INDEX IF NOT EXISTS fact_history_by_item
                      ON fact_cursors (domain, item, cursor)''')

    def _open(self, *, write, check_same_thread=True):
        mode = 'rw' if write else 'ro'
        db = sqlite3.connect(f'{self._uri}?mode={mode}', uri=True, timeout=0.1,
                             check_same_thread=check_same_thread)
        try:
            if not write:
                db.execute('PRAGMA query_only=ON')
                db.execute('BEGIN')
            if (db.execute('PRAGMA application_id').fetchone()[0],
                    db.execute('PRAGMA user_version').fetchone()[0]) != (APPLICATION_ID, SCHEMA):
                raise sqlite3.DatabaseError('unrecognized report cache')
            return db
        except BaseException:
            db.close()
            raise

    @contextmanager
    def _connect(self, *, write=False):
        if write and self._writer_lock is not None:
            # Only writers share this connection. Retaining it avoids paying a
            # last-close WAL checkpoint on each small, fully durable commit.
            with self._writer_lock:
                if self._writer_closed:
                    raise sqlite3.ProgrammingError('report cache writer is closed')
                if self._writer is None:
                    db = self._open(write=True, check_same_thread=False)
                    try:
                        db.execute('PRAGMA synchronous=FULL')
                    except BaseException:
                        db.close()
                        raise
                    self._writer = db
                with self._writer as db:
                    yield db
            return
        with closing(self._open(write=write)) as db, db:
            yield db

    def close_writer(self):
        if self._writer_lock is not None:
            with self._writer_lock:
                self._writer_closed = True
                if self._writer is not None:
                    self._writer.close()
                    self._writer = None

    def initialize(self):
        self._initialize_schema()
        if self._runtime_owner is not None:
            self._prune_abandoned_runtime()
        if self._retire_paths:
            self._retire_obsolete()

    def bind_exclusive_runtime(self, *, sessions, details):
        """Only a launcher holding the checkout's lifetime lock can reclaim old runs."""
        self._runtime_owner = sessions, details

    def _prune_abandoned_runtime(self):
        sessions, details = self._runtime_owner
        with self._connect(write=True) as db:
            db.execute('DELETE FROM session_runtime WHERE run<>?', (sessions,))
            db.execute('DELETE FROM session_pending WHERE run<>?', (sessions,))
            db.execute('DELETE FROM session_live WHERE run<>?', (sessions,))
            db.execute('DELETE FROM detail_runtime WHERE run<>?', (details,))
        self._runtime_owner = None

    @staticmethod
    def _create_detail_runtime(db):
        db.execute('''CREATE TABLE detail_runtime (
            run TEXT NOT NULL, item TEXT NOT NULL, status TEXT NOT NULL, projection TEXT,
            PRIMARY KEY (run, item)
        ) WITHOUT ROWID''')

    def _initialize_schema(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=0.1)) as db, db:
            current_id = db.execute('PRAGMA application_id').fetchone()[0]
            current_version = db.execute('PRAGMA user_version').fetchone()[0]
            if (current_id, current_version) == (APPLICATION_ID, SCHEMA):
                if db.execute('PRAGMA journal_mode').fetchone()[0] != 'wal':
                    raise sqlite3.DatabaseError('report cache requires WAL')
                return
            if current_id == APPLICATION_ID and current_version in (1, 2):
                db.execute('BEGIN IMMEDIATE')
                current_version = db.execute('PRAGMA user_version').fetchone()[0]
                if current_version == 1:
                    session_projection.create_runtime_schema(db)
                if current_version in (1, 2):
                    self._create_detail_runtime(db)
                    db.execute(f'PRAGMA user_version={SCHEMA}')
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
            session_projection.create_runtime_schema(db)
            self._create_detail_runtime(db)
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
            cursor, rows = self._history_item_rows(db, domain, key, after)
            if not rows:
                return cursor, ()
        return max((row[0] for row in rows), default=cursor), tuple(self._historical_facts(row[1:] for row in rows))

    @staticmethod
    def _history_item_rows(db, domain, key, after):
        cursor = db.execute('SELECT MAX(cursor) FROM fact_cursors WHERE domain=? AND item=?',
                             (domain, key)).fetchone()[0] or 0
        if cursor <= after:
            return after, ()
        rows = db.execute('''SELECT c.cursor, f.item, f.revision, f.observed_ms, f.value, f.partition
             FROM fact_cursors AS c JOIN facts AS f USING (partition, domain, algorithm, item)
             WHERE c.domain=? AND c.item=?
              ORDER BY f.observed_ms DESC, c.partition DESC, f.revision DESC''', (domain, key)).fetchall()
        return cursor, rows

    def detail_snapshot(self, domain, run, key):
        with self._connect() as db:
            frame = db.execute('SELECT status, projection FROM detail_runtime WHERE run=? AND item=?',
                               (run, key)).fetchone()
            _, rows = self._history_item_rows(db, domain, key, 0)
        return (tuple(json.loads(raw) if raw is not None else None for raw in frame) if frame else (None, None),
                tuple(fact for _, fact in self._historical_facts(row[1:] for row in rows)))

    def publish_detail_runtime(self, run, key, status, *, projection=None):
        def encode(value):
            return json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(',', ':'))

        value = encode(projection) if projection is not None else None
        with self._connect(write=True) as db:
            db.execute('''INSERT INTO detail_runtime VALUES (?, ?, ?, ?)
                ON CONFLICT(run, item) DO UPDATE SET status=excluded.status,
                    projection=COALESCE(excluded.projection, detail_runtime.projection)''',
                (run, key, encode(status), value))

    def clear_detail_runtime(self, run, key=None):
        with self._connect(write=True) as db:
            if key is None:
                db.execute('DELETE FROM detail_runtime WHERE run=?', (run,))
            else:
                db.execute('DELETE FROM detail_runtime WHERE run=? AND item=?', (run, key))

    def history_cursor(self, domain):
        if not self.path.is_file():
            return 0
        with self._connect() as db:
            return db.execute('SELECT MAX(cursor) FROM fact_cursors WHERE domain=?', (domain,)).fetchone()[0] or 0

    def history_item_cursors(self, domain, keys):
        if not keys or not self.path.is_file():
            return {}
        placeholders = ','.join('?' for _ in keys)
        with self._connect() as db:
            rows = db.execute(f'''SELECT item, MAX(cursor) FROM fact_cursors
                WHERE domain=? AND item IN ({placeholders}) GROUP BY item''', (domain, *keys))
            return dict(rows)

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

    def publish_batch(self, partition, domains):
        if not partition:
            return False
        return self._publish_batch(partition, domains)

    def publish_session(self, partition, domains, item, keys, last_at, latest_at, *, run=None):
        if not partition:
            return False
        return self._publish_batch(partition, domains, ready_session=(item, keys, last_at, latest_at, run))

    def ready_sessions_page(self, **page):
        with self._connect() as db:
            total, offset, values = session_projection.read_ready(db, **page)
            return total, offset, tuple(self._historical_facts(values))

    def sessions_page(self, **page):
        with self._connect() as db:
            total, offset, values, live, cached, runtime, pending = session_projection.read_ready(db, **page)
            return total, offset, tuple(self._historical_facts(values)), live, cached, runtime, pending

    def update_sessions_runtime(self, run, *, state, terminal, reset_pending, pending, live):
        times = None
        with self._connect(write=True) as db:
            db.execute('BEGIN IMMEDIATE')
            if self.notify_sessions is not None and not live and not reset_pending and len(pending) <= 64:
                previous = db.execute('SELECT state, terminal FROM session_runtime WHERE run=?', (run,)).fetchone()
                if previous == (state, terminal):
                    times = self._pending_times(db, run, pending)
            session_projection.update_runtime(db, run, state=state, terminal=terminal, reset_pending=reset_pending,
                                              pending=pending, live=live)
        self.note_publication((session_projection.SESSIONS_DOMAIN,), session_times=times)

    @staticmethod
    def _pending_times(db, run, pending):
        times = []
        for key, current in pending.items():
            previous = db.execute('SELECT activity_ms FROM session_pending WHERE run=? AND item=?',
                                  (run, key)).fetchone()
            for value in (previous, current):
                if value is None:
                    continue
                if value[0] is None:
                    return None
                times.append(value[0])
        return tuple(times)

    def close_sessions_runtime(self, run):
        with self._connect(write=True) as db:
            session_projection.close_runtime(db, run)

    def _publish_batch(self, partition, domains, *, ready_session=None):
        values = [(partition, domain, key, EVIDENCE_ENVELOPE, fact.revision, fact.observed_ms,
                    json.dumps(fact.value, ensure_ascii=True, allow_nan=False, separators=(',', ':')))
                   for domain, facts in domains.items() for key, fact in facts.items()]
        changed = set()
        session_times = None
        with self._connect(write=True) as db:
            db.execute('BEGIN IMMEDIATE')
            admitted = []
            for value in values:
                previous = db.execute('''SELECT revision, observed_ms FROM facts
                    WHERE partition=? AND domain=? AND item=? AND algorithm=?''', value[:4]).fetchone()
                if previous is not None:
                    old_revision, old_observed = previous
                    if old_observed >= value[5] and old_revision != value[4]:
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
                    item, keys, last_at, latest_at, run = ready_session
                    if item == value[2]:
                        if self.notify_sessions is not None:
                            previous = db.execute('SELECT last_activity_ms, latest_activity_ms '
                                                  'FROM ready_sessions WHERE item=?', (item,)).fetchone()
                            pending = self._pending_times(db, run, {item: None}) if run is not None else ()
                            if pending is not None:
                                session_times = (*pending, *(at for at in
                                    (*previous, last_at, latest_at) if at is not None)) if previous else (
                                    *pending, *(at for at in (last_at, latest_at) if at is not None))
                        session_projection.save_ready(db, item, partition, value[3], value[4], value[5],
                                                      keys, last_at, latest_at)
                        if run is not None:
                            removed = db.execute('DELETE FROM session_pending WHERE run=? AND item=?', (run, item))
                            if removed.rowcount:
                                changed.add(session_projection.SESSIONS_DOMAIN)
        if changed:
            self.note_publication(changed, session_times=session_times)
        return True
