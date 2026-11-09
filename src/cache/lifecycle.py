"""Opt-in cache retention, bounded demand touches and one opportunistic prune batch.

    This owner only writes Cost Guard's disposable database. It has no source,
    timer, worker, JSON index, vacuum or checkpoint authority.
"""
from collections import OrderedDict
import sqlite3
from threading import RLock
import time

HOUR_MS = 3_600_000
RETENTION_MS = 30 * 24 * HOUR_MS
TOUCH_ROWS = 64
PRUNE_ROWS = 8
NAMESPACES = frozenset({'derived-analysis', 'web-token-mix-evidence', 'ai-stats-evidence',
    'ai-stats-coverage-2', 'ai-stats-transient', 'matched-first-runs', 'session-summary', 'session-ccost-v1'})
# The one-hour grace compensates for coalesced touches without shortening the
# rolling retention interval. Neither a write nor passive observation is a view.
EXPIRY = 'max(activity_ms, used_ms + 3600000)'


def publish(connection, namespace, key, revision, scope):
    """Called inside payload publication's transaction, including replacements."""
    if namespace not in NAMESPACES:
        return
    if scope is None or not revision:
        connection.execute('DELETE FROM cache_entry_lifecycle WHERE namespace=? AND cache_key=?', (namespace, key))
        return
    connection.execute('''INSERT INTO cache_entry_lifecycle
        (namespace,cache_key,root_key,source_revision,activity_ms) VALUES(?,?,?,?,?)
        ON CONFLICT(namespace,cache_key) DO UPDATE SET
        used_ms=CASE WHEN root_key=excluded.root_key THEN used_ms ELSE NULL END,
        root_key=excluded.root_key,source_revision=excluded.source_revision,activity_ms=excluded.activity_ms''',
        (namespace, key, scope.root_key, revision, scope.activity_ms))


class CacheLifecycle:
    def __init__(self, database, *, wall_clock=time.time, clock=time.monotonic):
        self.database, self.wall_clock, self.clock = database, wall_clock, clock
        self.lock = RLock()
        self.pending = OrderedDict()
        self.noted = OrderedDict()
        self.cursor = (0, '', '')

    def note_use(self, roots):
        """Demand boundary only. No SQLite work or locks on every cache read."""
        now = int(self.wall_clock() * 1000)
        with self.lock:
            for root in roots:
                previous = self.noted.get(root)
                if previous is not None and 0 <= now - previous < HOUR_MS:
                    continue
                self.pending[root] = now
                self.noted[root] = now
                self.noted.move_to_end(root)
            while len(self.noted) > 16_384:
                self.noted.popitem(last=False)

    def flush(self):
        """At most 64 entry updates, zero busy wait; failed/pending uses protect roots."""
        with self.lock:
            roots = tuple(self.pending)[:64]
            if not roots:
                return 0
            try:
                with self.database.connect(operation='lifecycle-touch', busy_timeout_ms=0) as connection:
                    connection.execute('PRAGMA wal_autocheckpoint=0')
                    rows = []
                    for root in roots:
                        used = self.pending[root]
                        batch = connection.execute('''SELECT rowid FROM cache_entry_lifecycle
                            WHERE root_key=? AND (used_ms IS NULL OR used_ms<?) LIMIT ?''',
                            (root, used - HOUR_MS, TOUCH_ROWS - len(rows))).fetchall()
                        rows.extend((used, row[0]) for row in batch)
                        if len(rows) == TOUCH_ROWS:
                            break
                    connection.executemany('UPDATE cache_entry_lifecycle SET used_ms=? WHERE rowid=?', rows)
                # Retire only roots whose complete bounded update is now known.
                # A full batch may still have a tail; one later turn confirms it.
                if len(rows) < TOUCH_ROWS:
                    for root in roots:
                        self.pending.pop(root, None)
                return len(rows)
            except (OSError, sqlite3.Error):
                return 0

    def flush_pending(self):
        """Finite CLI handoff: finish bounded batches, stop at the first failure."""
        while self.pending:
            before = len(self.pending)
            changed = self.flush()
            if not changed and len(self.pending) == before:
                break

    def prune(self, revisions, *, allowed=lambda: True, now_ms=None):
        """One indexed candidate window/transaction; fresh caller evidence gates deletion.

        Revisions maps source-qualified root digests to current, *inactive* tree
        revisions. Missing/changed/unknown roots defer. Advance past deferrals so
        they cannot starve later candidates. SQLite errors/cancellation roll back.
        """
        now = int(self.wall_clock() * 1000) if now_ms is None else now_ms
        cutoff = now - RETENTION_MS
        deadline = self.clock() + 0.020
        with self.lock:
            if not allowed():
                return 0
            try:
                with self.database.connect(operation='lifecycle-prune', busy_timeout_ms=0) as connection:
                    connection.execute('PRAGMA wal_autocheckpoint=0')
                    connection.set_progress_handler(lambda: int(self.clock() >= deadline or not allowed()), 100)
                    connection.execute('BEGIN IMMEDIATE')
                    rows = connection.execute(f'''SELECT namespace,cache_key,root_key,source_revision,{EXPIRY}
                        FROM cache_entry_lifecycle WHERE activity_ms IS NOT NULL AND used_ms IS NOT NULL
                        AND {EXPIRY}<? AND ({EXPIRY},namespace,cache_key)>(?,?,?)
                        ORDER BY {EXPIRY},namespace,cache_key LIMIT ?''', (cutoff, *self.cursor, PRUNE_ROWS)).fetchall()
                    deleted = 0
                    for namespace, key, root, revision, expiry in rows:
                        if root not in self.pending and revisions.get(root) == revision and allowed():
                            deleted += connection.execute('''DELETE FROM cache_entries
                                WHERE namespace=? AND cache_key=? AND source_revision=?''',
                                (namespace, key, revision)).rowcount
                    if not allowed() or self.clock() >= deadline:
                        connection.rollback()
                        return 0
                    connection.set_progress_handler(None, 0)
                self.cursor = (rows[-1][4], rows[-1][0], rows[-1][1]) if rows else (0, '', '')
                return deleted
            except (OSError, sqlite3.Error):
                return 0
