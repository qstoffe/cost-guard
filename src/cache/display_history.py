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
CHANGE_WINDOW = 64
SORT_COLUMNS = {
    "activity": "activity_ms", "name": "title_key", "model": "model_key",
    "ccost": "cost_key", "prompts": "prompts", "duration": "duration_ms", "ctx": "context_tokens",
}
METRIC_FIELDS = ("activity_ms", "model", "ccost", "prompts", "duration_ms", "context_tokens", "latest_activity_ms")
SAVED_FIELDS = frozenset(METRIC_FIELDS)
PERIOD_CLOCK = "period_clock_ms"


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
    # Membership and the displayed finish/start clock are distinct. The
    # canonical source summary can observe later linked work with the same
    # displayed activity. Fall back only when this clock was not supplied.
    latest_activity_ms: int | None = None


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
    latest_activity_ms: int | None


@dataclass(frozen=True, slots=True)
class SessionPage:
    generation: int
    total: int
    rows: tuple[SessionSnapshot, ...]


@dataclass(frozen=True, slots=True)
class SessionChanges:
    generation: int
    resync: bool = False
    oldest_activity_ms: int | None = None
    latest_activity_ms: int | None = None

    def affects(self, previous, *, start_ms=None, end_ms=None):
        if self.resync:
            return True
        if previous == self.generation:
            return False
        if start_ms is None and end_ms is None:
            return True  # All time includes rows with no known activity clock.
        return (self.oldest_activity_ms is not None
                and (start_ms is None or self.latest_activity_ms >= start_ms)
                and (end_ms is None or self.oldest_activity_ms < end_ms))


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
                    generation INTEGER NOT NULL DEFAULT 0,
                    session_count INTEGER NOT NULL DEFAULT 0
                ) WITHOUT ROWID;
                CREATE TABLE IF NOT EXISTS session_changes (
                    source TEXT NOT NULL REFERENCES sources(source),
                    generation INTEGER NOT NULL,
                    oldest_activity_ms INTEGER,
                    latest_activity_ms INTEGER,
                    PRIMARY KEY (source, generation)
                ) WITHOUT ROWID;
                CREATE TABLE IF NOT EXISTS sessions (
                    source TEXT NOT NULL REFERENCES sources(source),
                    session_id TEXT NOT NULL,
                    revision TEXT NOT NULL,
                    title TEXT NOT NULL, title_key TEXT NOT NULL,
                    activity_ms INTEGER, latest_activity_ms INTEGER,
                    period_clock_ms INTEGER GENERATED ALWAYS AS (coalesce(latest_activity_ms, activity_ms)) VIRTUAL,
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
            f"ON sessions(source, ({column} IS NULL), {column} {direction}, session_id, {PERIOD_CLOCK});"
            for sort, column in SORT_COLUMNS.items() for direction in ("ASC", "DESC")
        ) + f"\nCREATE INDEX IF NOT EXISTS sessions_period ON sessions(source, {PERIOD_CLOCK});"

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
            clocks = []
            changed = False
            inserted = 0
            for change in updates:
                session_id = change.fact.session_id
                previous = self._activity(db, source, session_id)
                if self._apply_session(db, source, change):
                    changed = True
                    inserted += int(change.previous_revision is None)
                    clocks.extend((previous, self._activity(db, source, session_id)))
            for session_id, revision in missing:
                previous = self._activity(db, source, session_id)
                if db.execute("""
                    UPDATE sessions SET source_present=0
                    WHERE source=? AND session_id=? AND revision=? AND source_present=1
                """, (source, session_id, revision)).rowcount:
                    changed = True
                    clocks.append(previous)
            generation = None
            if changed:
                db.execute("UPDATE sources SET generation=generation+1, session_count=session_count+? WHERE source=?",
                           (inserted, source))
                generation = self._generation(db, source)
                known = [clock for clock in clocks if clock is not None]
                db.execute("INSERT INTO session_changes VALUES(?, ?, ?, ?)",
                           (source, generation, min(known, default=None), max(known, default=None)))
                db.execute("DELETE FROM session_changes WHERE source=? AND generation<=?",
                           (source, generation - CHANGE_WINDOW))
            db.commit()
            return generation

    @staticmethod
    def _apply_session(db, source, change):
        fact = change.fact
        if not change.observed_fields <= SAVED_FIELDS or not (fact.revision and fact.session_id):
            raise ValueError("invalid_session_evidence")
        if change.observed_fields != SAVED_FIELDS:
            previous = db.execute("""
                SELECT activity_ms, model, ccost, prompts, duration_ms, context_tokens, latest_activity_ms
                FROM sessions WHERE source=? AND session_id=? AND revision=?
            """, (source, fact.session_id, change.previous_revision)).fetchone()
            retained = dict(zip(METRIC_FIELDS, previous)) if previous is not None else {}
            metrics = {name: getattr(fact, name) if name in change.observed_fields else retained.get(name)
                       for name in METRIC_FIELDS}
            if isinstance(metrics["ccost"], str):
                metrics["ccost"] = Decimal(metrics["ccost"])
            fact = SessionFact(fact.session_id, fact.revision, fact.title, **metrics)
        values = (fact.revision, fact.title, fact.title.casefold(), fact.activity_ms,
                  fact.model, fact.model.casefold() if fact.model is not None else None,
                  str(fact.ccost) if fact.ccost is not None else None, decimal_key(fact.ccost),
                  fact.prompts, fact.duration_ms, fact.context_tokens, fact.latest_activity_ms)
        if change.previous_revision is None:
            return db.execute("""
                INSERT INTO sessions(source, session_id, revision, title, title_key, activity_ms,
                    model, model_key, ccost, cost_key, prompts, duration_ms, context_tokens,
                    latest_activity_ms, source_present)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(source, session_id) DO NOTHING
            """, (source, fact.session_id, *values)).rowcount
        return db.execute("""
            UPDATE sessions SET revision=?, title=?, title_key=?, activity_ms=?, model=?, model_key=?,
                ccost=?, cost_key=?, prompts=?, duration_ms=?, context_tokens=?, latest_activity_ms=?, source_present=1
            WHERE source=? AND session_id=? AND revision=?
                AND (revision, title, title_key, activity_ms, model, model_key, ccost, cost_key,
                     prompts, duration_ms, context_tokens, latest_activity_ms, source_present)
                    IS NOT (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (*values, source, fact.session_id, change.previous_revision, *values)).rowcount

    @staticmethod
    def _activity(db, source, session_id):
        row = db.execute(f"SELECT {PERIOD_CLOCK} FROM sessions WHERE source=? AND session_id=?",
                         (source, session_id)).fetchone()
        return row[0] if row else None

    @staticmethod
    def _generation(db, source):
        row = db.execute("SELECT generation FROM sources WHERE source=?", (source,)).fetchone()
        return row[0] if row else 0

    def session_changes(self, source, previous):
        """Read compact committed hints, or signal a requery across a replay gap."""
        if not source or type(previous) is not int or previous < 0:
            raise ValueError("invalid_change_cursor")
        with self._connect(read=True) as db:
            db.execute("BEGIN")
            generation = self._generation(db, source)
            if not 0 <= generation - previous <= CHANGE_WINDOW:
                return SessionChanges(generation, resync=True)
            count, oldest, latest = db.execute("""
                SELECT count(*), min(oldest_activity_ms), max(latest_activity_ms)
                FROM session_changes WHERE source=? AND generation>?
            """, (source, previous)).fetchone()
            if count != generation - previous:
                return SessionChanges(generation, resync=True)
        return SessionChanges(generation, oldest_activity_ms=oldest, latest_activity_ms=latest)

    def session_page(self, source, *, sort="activity", direction=-1, start_ms=None, end_ms=None,
                     limit=25, offset=0):
        if (not source or sort not in SORT_COLUMNS or type(direction) is not int or direction not in (-1, 1)
                or type(limit) is not int or not 1 <= limit <= PAGE_LIMIT
                or type(offset) is not int or not 0 <= offset <= 1_000_000):
            raise ValueError("invalid_display_query")
        column = SORT_COLUMNS[sort]
        order = "ASC" if direction == 1 else "DESC"
        index = f"sessions_{sort}_{order.lower()}"
        conditions, params = ["source=?"], [source]
        if start_ms is not None:
            conditions.append(f"{PERIOD_CLOCK}>=?")
            params.append(start_ms)
        if end_ms is not None:
            conditions.append(f"{PERIOD_CLOCK}<?")
            params.append(end_ms)
        where = " AND ".join(conditions)
        with self._connect(read=True) as db:
            db.execute("BEGIN")
            state = db.execute("SELECT generation, session_count FROM sources WHERE source=?", (source,)).fetchone()
            if state is None:
                return SessionPage(0, 0, ())
            generation, total = state
            if len(params) > 1:
                total = db.execute(f"SELECT count(*) FROM sessions WHERE {where}", params).fetchone()[0]
            # Select ordered keys first with the covering index. CROSS JOIN
            # keeps the small selected set outermost; a reordered join can
            # scan every historical row just to return the first page.
            rows = db.execute(f"""
                WITH selected AS (
                    SELECT session_id FROM sessions INDEXED BY {index} WHERE {where}
                    ORDER BY ({column} IS NULL), {column} {order}, session_id
                    LIMIT ? OFFSET ?
                )
                SELECT s.session_id, revision, title, activity_ms, model, ccost,
                    prompts, duration_ms, context_tokens, latest_activity_ms, source_present
                FROM selected CROSS JOIN sessions AS s
                WHERE s.source=? AND s.session_id=selected.session_id
                ORDER BY ({column} IS NULL), {column} {order}, s.session_id
            """, (*params, limit, offset, source)).fetchall()
        return SessionPage(generation, total, tuple(SessionSnapshot(*row[:-2], bool(row[-1]), row[-2]) for row in rows))
