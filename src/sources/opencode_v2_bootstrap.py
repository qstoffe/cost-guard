"""Startup-only root inventory hints from a compatible local V2 SQLite snapshot."""
from contextlib import closing
from dataclasses import dataclass
import sqlite3
from time import monotonic


_MESSAGE_INDEX_PREFIX = ('session_id', 'type', 'seq')
_INVENTORY_SQL = """
SELECT s.id, s.title, s.time_created, s.time_updated,
       (SELECT m.seq FROM session_message m WHERE m.session_id=s.id AND m.type='user'
        ORDER BY m.seq DESC LIMIT 1),
       (SELECT m.time_created FROM session_message m WHERE m.session_id=s.id AND m.type='user'
        ORDER BY m.seq DESC LIMIT 1),
       (SELECT m.seq FROM session_message m WHERE m.session_id=s.id AND m.type='idle'
        ORDER BY m.seq DESC LIMIT 1),
       (SELECT m.time_created FROM session_message m WHERE m.session_id=s.id AND m.type='idle'
        ORDER BY m.seq DESC LIMIT 1)
FROM session_v2 s
WHERE s.parent_id IS NULL
"""


@dataclass(frozen=True, slots=True)
class RootHint:
    title: str
    created_ms: int
    updated_ms: int
    priority_ms: int | None


@dataclass(frozen=True, slots=True)
class BootstrapInventory:
    epoch: str
    roots: dict[str, RootHint]

    def priorities(self, epoch, observed_roots):
        if epoch != self.epoch:
            return {}
        # Match the whole root roster. An API row changed after bootstrap can
        # still be processed, but must not use the older activity hint.
        if observed_roots.keys() != self.roots.keys():
            return {}
        if any(root.created_at_ms != self.roots[key].created_ms for key, root in observed_roots.items()):
            return {}
        return {key: hint.priority_ms for key, root in observed_roots.items()
                if (hint := self.roots[key]).priority_ms is not None
                and root.title == hint.title and root.updated_at_ms == hint.updated_ms}


def _schema_supported(db):
    for table, required in (
        ('session_v2', {'id', 'title', 'parent_id', 'time_created', 'time_updated'}),
        ('session_message', {'session_id', 'type', 'seq', 'time_created'}),
    ):
        if not required <= {row[1] for row in db.execute('SELECT * FROM pragma_table_info(?)', (table,))}:
            return False
    for entry in db.execute("PRAGMA index_list('session_message')"):
        if entry[4]:  # A partial index does not establish a bound for both probes.
            continue
        columns = tuple(row[2] for row in db.execute('SELECT * FROM pragma_index_info(?)', (entry[1],)))
        if columns[:3] == _MESSAGE_INDEX_PREFIX:
            return True
    return False


def _activity_hint(user_seq, user_at, idle_seq, idle_at):
    if type(user_seq) is not int or type(user_at) is not int or user_at <= 0:
        return None
    if type(idle_seq) is int and idle_seq > user_seq and type(idle_at) is int and idle_at >= user_at:
        return idle_at
    return user_at


def read_inventory(path, epoch, *, seconds=1.0):
    """Return ordering hints only; never publish activity or source revisions."""
    if path is None or not epoch or not path.is_absolute() or path.drive.startswith('\\\\'):
        return None
    deadline = monotonic() + seconds
    try:
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=0.1)) as db:
            db.set_progress_handler(lambda: monotonic() >= deadline, 1000)
            db.execute('PRAGMA query_only=ON')
            db.execute('PRAGMA trusted_schema=OFF')
            db.execute('BEGIN')
            if not _schema_supported(db):
                return None
            roots = {}
            for key, title, created, updated, user_seq, user_at, idle_seq, idle_at in db.execute(_INVENTORY_SQL):
                if (not isinstance(key, str) or not key or key in roots or not isinstance(title, str)
                        or type(created) is not int or type(updated) is not int):
                    return None
                roots[key] = RootHint(title, created, updated, _activity_hint(user_seq, user_at, idle_seq, idle_at))
            return BootstrapInventory(epoch, roots)
    except (sqlite3.Error, OSError, ValueError):
        return None
