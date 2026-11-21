"""Persistent, source-scoped Web history. Unlike cache v2 this is not disposable."""
from contextlib import closing, contextmanager
from dataclasses import dataclass
from decimal import Decimal
import sqlite3
from threading import Lock


FILENAME = "cost-guard-display.sqlite3"
SCHEMA_VERSION = 1
APPLICATION_ID = 0x43474448  # CGDH
PAGE_LIMIT = 50
BATCH_LIMIT = 256
SORT_COLUMNS = {
    "activity": "activity_ms", "name": "title_key", "model": "model_key",
    "ccost": "cost_key", "prompts": "prompts", "duration": "duration_ms", "ctx": "context_tokens",
}
SAVED_FIELDS = frozenset(("activity_ms", "model", "ccost", "prompts", "duration_ms", "context_tokens"))


def decimal_key(value: Decimal | None) -> bytes | None:
    """SQLite BLOB order is exact decimal order (no REAL rounding of close costs)."""
    if value is None:
        return None
    if not value.is_finite():
        raise ValueError("invalid_cost")
    if not value:
        return b"\x01"
    sign, digits, _ = value.as_tuple()
    end = len(digits)
    while digits[end - 1] == 0:
        end -= 1
    rank = (value.adjusted() + (1 << 63)).to_bytes(8, "big")
    magnitude = rank + bytes(digit + 1 for digit in digits[:end]) + b"\x00"
    if sign:
        return b"\x00" + bytes(255 - byte for byte in magnitude)
    return b"\x02" + magnitude


@dataclass(frozen=True, slots=True)
class SessionFact:
    session_id: str
    revision: str
    title: str
    activity_ms: int | None = None
    model: str | None = None
    ccost: Decimal | None = None
    prompts: int | None = None
    duration_ms: int | None = None
    context_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class SessionChange:
    fact: SessionFact
    # None is an insert guard, not a wildcard. The acquisition owner supplies
    # the last accepted revision before it reads and qualifies a new revision.
    previous_revision: str | None
    # Omitted fields carry forward as-of values; an explicitly observed None
    # can replace a field when a qualified correction says it is unknown.
    observed_fields: frozenset[str] = SAVED_FIELDS


@dataclass(frozen=True, slots=True)
class SessionSnapshot:
    session_id: str
    revision: str
    title: str
    activity_ms: int | None
    model: str | None
    ccost: str | None
    prompts: int | None
    duration_ms: int | None
    context_tokens: int | None
    source_present: bool


@dataclass(frozen=True, slots=True)
class SessionPage:
    generation: int
    total: int
    rows: tuple[SessionSnapshot, ...]


class DisplayHistory:
    """Small committed view snapshots, concurrent readers, one writer per host.

    Source keys must come from a verified host binding, never from HTTP clients.
    The caller owns source/revision qualification and a stable acquisition epoch;
    this store only accepts bounded CAS commits and does not run acquisition.
    """

    def __init__(self, root):
        self.path = (root / "cache" / FILENAME).absolute()
        self._write_lock = Lock()

    @contextmanager
    def _connect(self, *, read=False):
        target = self.path.as_uri() + "?mode=ro" if read else self.path
        with closing(sqlite3.connect(target, uri=read, timeout=0.15, isolation_level=None)) as db:
            db.execute("PRAGMA foreign_keys=ON")
            if read:
                db.execute("PRAGMA query_only=ON")
            yield db

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._write_lock, self._connect() as db:
            app_id = db.execute("PRAGMA application_id").fetchone()[0]
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if (app_id, version) == (APPLICATION_ID, SCHEMA_VERSION):
                return
            if (app_id, version) != (0, 0) or db.execute("SELECT 1 FROM sqlite_schema LIMIT 1").fetchone():
                raise sqlite3.DatabaseError("unsupported_display_history_schema")
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(f"""
                BEGIN IMMEDIATE;
                PRAGMA application_id={APPLICATION_ID};
                CREATE TABLE IF NOT EXISTS sources (
                    source TEXT NOT NULL PRIMARY KEY,
                    generation INTEGER NOT NULL DEFAULT 0
                ) WITHOUT ROWID;
                CREATE TABLE IF NOT EXISTS sessions (
                    source TEXT NOT NULL REFERENCES sources(source),
                    session_id TEXT NOT NULL,
                    revision TEXT NOT NULL,
                    title TEXT NOT NULL, title_key TEXT NOT NULL,
                    activity_ms INTEGER,
                    model TEXT, model_key TEXT,
                    ccost TEXT, cost_key BLOB,
                    prompts INTEGER, duration_ms INTEGER, context_tokens INTEGER,
                    source_present INTEGER NOT NULL,
                    PRIMARY KEY (source, session_id)
                ) WITHOUT ROWID;
                {self._sort_indexes()}
                PRAGMA user_version={SCHEMA_VERSION};
                COMMIT;
            """)

    @staticmethod
    def _sort_indexes():
        return "\n".join(
            f"CREATE INDEX IF NOT EXISTS sessions_{sort}_{direction.lower()} "
            f"ON sessions(source, ({column} IS NULL), {column} {direction}, session_id);"
            for sort, column in SORT_COLUMNS.items() for direction in ("ASC", "DESC")
        ) + "\nCREATE INDEX IF NOT EXISTS sessions_period ON sessions(source, activity_ms);"

    def commit_sessions(self, source, updates=(), *, missing=()):
        """Apply qualified facts and membership changes, without deleting old values.

        `missing` entries are (session_id, expected_revision) from a qualified
        source membership observation, not a failed source request. Return the
        durable generation only when visible data changed, and only after COMMIT.
        """
        if not source or len(updates) + len(missing) > BATCH_LIMIT:
            raise ValueError("invalid_display_batch")
        if not updates and not missing:
            return None
        with self._write_lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT OR IGNORE INTO sources(source) VALUES(?)", (source,))
            changed = sum(self._apply_session(db, source, change) for change in updates)
            for session_id, revision in missing:
                changed += db.execute("""
                    UPDATE sessions SET source_present=0
                    WHERE source=? AND session_id=? AND revision=? AND source_present=1
                """, (source, session_id, revision)).rowcount
            generation = None
            if changed:
                db.execute("UPDATE sources SET generation=generation+1 WHERE source=?", (source,))
                generation = self._generation(db, source)
            db.commit()
            return generation

    @staticmethod
    def _apply_session(db, source, change):
        fact = change.fact
        if not change.observed_fields <= SAVED_FIELDS or not (fact.revision and fact.session_id):
            raise ValueError("invalid_session_evidence")
        if change.observed_fields != SAVED_FIELDS:
            previous = db.execute("""
                SELECT activity_ms, model, ccost, prompts, duration_ms, context_tokens
                FROM sessions WHERE source=? AND session_id=? AND revision=?
            """, (source, fact.session_id, change.previous_revision)).fetchone()
            names = ("activity_ms", "model", "ccost", "prompts", "duration_ms", "context_tokens")
            retained = dict(zip(names, previous)) if previous is not None else {}
            metrics = {name: getattr(fact, name) if name in change.observed_fields else retained.get(name)
                       for name in names}
            if isinstance(metrics["ccost"], str):
                metrics["ccost"] = Decimal(metrics["ccost"])
            fact = SessionFact(fact.session_id, fact.revision, fact.title, **metrics)
        values = (fact.revision, fact.title, fact.title.casefold(), fact.activity_ms,
                  fact.model, fact.model.casefold() if fact.model is not None else None,
                  str(fact.ccost) if fact.ccost is not None else None, decimal_key(fact.ccost),
                  fact.prompts, fact.duration_ms, fact.context_tokens)
        if change.previous_revision is None:
            return db.execute("""
                INSERT INTO sessions(source, session_id, revision, title, title_key, activity_ms,
                    model, model_key, ccost, cost_key, prompts, duration_ms, context_tokens, source_present)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(source, session_id) DO NOTHING
            """, (source, fact.session_id, *values)).rowcount
        return db.execute("""
            UPDATE sessions SET revision=?, title=?, title_key=?, activity_ms=?, model=?, model_key=?,
                ccost=?, cost_key=?, prompts=?, duration_ms=?, context_tokens=?, source_present=1
            WHERE source=? AND session_id=? AND revision=?
                AND (revision, title, title_key, activity_ms, model, model_key, ccost, cost_key,
                     prompts, duration_ms, context_tokens, source_present)
                    IS NOT (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (*values, source, fact.session_id, change.previous_revision, *values)).rowcount

    @staticmethod
    def _generation(db, source):
        row = db.execute("SELECT generation FROM sources WHERE source=?", (source,)).fetchone()
        return row[0] if row else 0

    def session_page(self, source, *, sort="activity", direction=-1, start_ms=None, end_ms=None,
                     limit=25, offset=0):
        if (not source or sort not in SORT_COLUMNS or type(direction) is not int or direction not in (-1, 1)
                or type(limit) is not int or not 1 <= limit <= PAGE_LIMIT
                or type(offset) is not int or not 0 <= offset <= 1_000_000):
            raise ValueError("invalid_display_query")
        column = SORT_COLUMNS[sort]
        order = "ASC" if direction == 1 else "DESC"
        conditions, params = ["source=?"], [source]
        if start_ms is not None:
            conditions.append("activity_ms>=?")
            params.append(start_ms)
        if end_ms is not None:
            conditions.append("activity_ms<?")
            params.append(end_ms)
        where = " AND ".join(conditions)
        with self._connect(read=True) as db:
            db.execute("BEGIN")
            generation = self._generation(db, source)
            total = db.execute(f"SELECT count(*) FROM sessions WHERE {where}", params).fetchone()[0]
            rows = db.execute(f"""
                SELECT session_id, revision, title, activity_ms, model, ccost,
                    prompts, duration_ms, context_tokens, source_present
                FROM sessions WHERE {where}
                ORDER BY ({column} IS NULL), {column} {order}, session_id
                LIMIT ? OFFSET ?
            """, (*params, limit, offset)).fetchall()
        return SessionPage(generation, total, tuple(SessionSnapshot(*row[:-1], bool(row[-1])) for row in rows))
