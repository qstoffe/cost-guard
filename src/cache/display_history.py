"""Persistent, source-scoped Web history. Unlike cache v2 this is not disposable."""
from __future__ import annotations

from contextlib import closing, contextmanager
from dataclasses import dataclass
from decimal import Decimal
import sqlite3
from threading import Lock
import time

from .display_prompts import prompt_page, prompt_schema
from .display_account_usage import account_usage_slice
from .display_account_buckets import (
    account_buckets, account_chart, account_history_due, account_schema, cleanup_accounts, publish_account_run, stage_accounts,
)
from .display_requests import RequestRoster, countable_schema, publish_roster, request_schema
from .display_mix_groups import group_revision, inactive_run, mix_groups_schema, read_groups, remove_inactive_groups, stage_groups
from .display_mix_identity import mix_identity_schema, read_mix_identities, save_mix_identities
from .display_mix_order import MIX_GROUP_DEFAULT, MIX_GROUP_ORDER_VERSION
from .display_mix_totals import mix_refresh, mix_total_schema, publish_mix_totals, read_mix_total
from .display_models import benchmark_references, models_schema, read_models, write_models
from .display_usage_reader import read_usage_slice, retained_usage_version, usage_schema
from .display_watch import publish_watch, watch_schema, watch_snapshot
from .display_watch_quota import watch_quota_schema
from .display_session_seek import seek_keys
from .display_sort_keys import decimal_key
from .display_stats_evidence import stats_evidence_schema, stats_interval_page
from .display_stats_geometry_revision import geometry_schema
from .display_stats_reader import read_stats_geometry, read_stats_parents, read_stats_roots, read_stats_usage
from .display_stats_requests import read_stats_candidates, stats_request_schema
from .display_stats_revision import retained_stats_version, stats_revision_schema
from .display_stats_time import commit_time, read_time, stats_time_schema, time_due
from .display_stats_tokens import commit_tokens, read_tokens, stats_token_schema, tokens_due

FILENAME = "cost-guard-display-v1.sqlite3"
SCHEMA_VERSION = 1
APPLICATION_ID = 0x43474448  # CGDH
PAGE_LIMIT = 50
BATCH_LIMIT = 256
CHANGE_WINDOW = 64
RUNNING_FRESH_MS = 15_000
_RUNNING_METRICS = (("ccost", "TEXT"), ("context_tokens", "INTEGER"),
                    ("context_invalidated", "INTEGER NOT NULL DEFAULT 0"))
SORT_COLUMNS = {
    "activity": "activity_ms", "name": "title_key", "model": "model_key",
    "ccost": "cost_key", "prompts": "prompts", "duration": "duration_ms", "ctx": "context_tokens",
}
METRIC_FIELDS = ("activity_ms", "model", "ccost", "prompts", "duration_ms", "context_tokens", "latest_activity_ms",
                 "prompt_started_ms", "activity_origin", "catalog_activity_ms", "context_detail",
                 "model_help", "has_model_details")
SAVED_FIELDS = frozenset(METRIC_FIELDS)
ACQUIRED_SCALAR_FIELDS = SAVED_FIELDS - {"catalog_activity_ms"}
FINISH_FIELDS = frozenset({"activity_ms", "latest_activity_ms", "prompt_started_ms", "activity_origin"})
PERIOD_CLOCK = "period_clock_ms"
# Do not derive these bit positions from display order: they are disk format.
FIELD_EVIDENCE_BITS = {name: 1 << offset for offset, name in enumerate((
    "activity_ms", "model", "ccost", "prompts", "duration_ms", "context_tokens",
    "latest_activity_ms", "prompt_started_ms", "activity_origin", "catalog_activity_ms",
    None, "context_detail", "model_help", "has_model_details",
)) if name is not None}
EMPTY_HISTORY_EVIDENCE = 1 << 10


def field_evidence(observed_fields, *, empty_history=False):
    return sum(FIELD_EVIDENCE_BITS[field] for field in observed_fields) | (
        EMPTY_HISTORY_EVIDENCE if empty_history else 0)


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
    prompt_started_ms: int | None = None
    activity_origin: str | None = None
    catalog_activity_ms: int | None = None
    context_detail: str | None = None
    model_help: str | None = None
    has_model_details: bool | None = None


@dataclass(frozen=True, slots=True)
class SessionChange:
    fact: SessionFact
    # None is an insert guard, not a wildcard. The acquisition owner supplies
    # the last accepted revision before it reads and qualifies a new revision.
    previous_revision: str | None
    # Omitted fields carry forward as-of values; an explicitly observed None
    # can replace a field when a qualified correction says it is unknown.
    observed_fields: frozenset[str] = SAVED_FIELDS
    # A complete scalar projection for an exact dependency, not history coverage.
    dependency: str | None = None
    # Guard same-revision changes, including dependency-only updates and
    # observed gaps that leave the display row intact.
    previous_progress: int | None = None
    empty_history: bool = False
    request_roster: RequestRoster | None = None


@dataclass(frozen=True, slots=True)
class SessionCheckpoint:
    revision: str
    progress: int


@dataclass(frozen=True, slots=True)
class RunningSession:
    session_id: str
    title: str
    started_ms: int
    observed_ms: int
    prompt_id: str = ""
    ccost: Decimal | None = None
    context_tokens: int | None = None
    context_invalidated: bool = False


@dataclass(frozen=True, slots=True)
class FinishedSession:
    fact: SessionFact
    observed_ms: int
    fields: frozenset[str]


@dataclass(frozen=True, slots=True)
class LiveCommit:
    sessions_generation: int | None
    watch_generation: int | None


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
    prompt_started_ms: int | None
    activity_origin: str | None
    catalog_activity_ms: int | None
    running: bool = False
    field_evidence: int = 0
    context_detail: str | None = None
    model_help: str | None = None
    has_model_details: bool | None = None


@dataclass(frozen=True, slots=True)
class SessionPage:
    generation: int
    total: int
    rows: tuple[SessionSnapshot, ...]
    running_expires_ms: int | None = None
    coverage: SessionCoverage | None = None


@dataclass(frozen=True, slots=True)
class SessionCoverage:
    """An as-of proof for a fully enumerated supported source roster, not a row count."""
    observed_ms: int
    incomplete: bool
    unknown_clock: bool
    newest_gap_ms: int | None

    def covers(self, start_ms):
        if start_ms is None:
            return not self.incomplete
        return not self.unknown_clock and (self.newest_gap_ms is None or self.newest_gap_ms < start_ms)

    def with_gaps_from(self, previous):
        clocks = (value for value in (self.newest_gap_ms, previous.newest_gap_ms) if value is not None)
        return SessionCoverage(self.observed_ms, self.incomplete or previous.incomplete,
                               self.unknown_clock or previous.unknown_clock, max(clocks, default=None))


@dataclass(frozen=True, slots=True)
class HistoryState:
    generation: int = 0
    archive_epoch: int = 0


@dataclass(frozen=True, slots=True)
class SessionCommit:
    generation: int | None = None
    applied: int = 0
    detail_roots: frozenset[str] = frozenset()


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
    def _connect(self, *, read=False, initializing=False):
        target = self.path.as_uri() + "?mode=ro" if read else self.path
        with closing(sqlite3.connect(target, uri=read, timeout=0.15, isolation_level=None)) as db:
            if not initializing and self._identity(db) != (APPLICATION_ID, SCHEMA_VERSION):
                raise sqlite3.DatabaseError("unsupported_display_history_schema")
            db.execute("PRAGMA foreign_keys=ON")
            if read:
                db.execute("PRAGMA query_only=ON")
            yield db

    @staticmethod
    def _identity(db):
        return db.execute("PRAGMA application_id").fetchone()[0], db.execute("PRAGMA user_version").fetchone()[0]

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._write_lock, self._connect(initializing=True) as db:
            app_id, version = self._identity(db)
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
                    session_count INTEGER NOT NULL DEFAULT 0,
                    archive_epoch INTEGER NOT NULL DEFAULT 0
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
                    prompt_started_ms INTEGER, activity_origin TEXT, catalog_activity_ms INTEGER,
                    source_present INTEGER NOT NULL,
                    field_evidence INTEGER NOT NULL DEFAULT 0,
                    context_detail TEXT, model_help TEXT, has_model_details INTEGER,
                    PRIMARY KEY (source, session_id)
                ) WITHOUT ROWID;
                {self._sort_indexes()}
                {self._progress_schema()}
                {self._live_schema()}
                {self._coverage_schema()}
                {request_schema()}
                {prompt_schema()}
                {countable_schema()}
                {watch_schema()}
                {usage_schema()}
                {mix_total_schema()}
                {mix_groups_schema()}
                {mix_identity_schema()}
                {stats_evidence_schema()}
                {stats_request_schema()}
                {stats_revision_schema()}
                {geometry_schema()}
                {stats_time_schema()}
                {stats_token_schema()}
                {models_schema()}
                {account_schema()}
                {watch_quota_schema()}
                PRAGMA user_version={SCHEMA_VERSION};
                COMMIT;
            """)

    @staticmethod
    def _progress_schema():
        return """
            CREATE TABLE IF NOT EXISTS session_progress (
                source TEXT NOT NULL,
                session_id TEXT NOT NULL,
                revision TEXT NOT NULL,
                dependency TEXT,
                progress INTEGER NOT NULL,
                PRIMARY KEY (source, session_id),
                FOREIGN KEY (source, session_id) REFERENCES sessions(source, session_id) ON DELETE CASCADE
            ) WITHOUT ROWID;
        """

    @staticmethod
    def _live_schema():
        metrics = ", ".join(f"{name} {kind}" for name, kind in _RUNNING_METRICS)
        return f"""
            CREATE TABLE IF NOT EXISTS session_running (
                source TEXT NOT NULL REFERENCES sources(source),
                binding TEXT NOT NULL,
                session_id TEXT NOT NULL,
                title TEXT NOT NULL,
                started_ms INTEGER NOT NULL,
                observed_ms INTEGER NOT NULL,
                {metrics},
                PRIMARY KEY (source, session_id)
            ) WITHOUT ROWID;
        """

    @staticmethod
    def _coverage_schema():
        return """
            CREATE TABLE IF NOT EXISTS session_scope_coverage (
                source TEXT NOT NULL PRIMARY KEY REFERENCES sources(source),
                observed_ms INTEGER NOT NULL,
                incomplete INTEGER NOT NULL,
                unknown_clock INTEGER NOT NULL,
                newest_gap_ms INTEGER
            ) WITHOUT ROWID;
        """

    @staticmethod
    def _sort_indexes():
        return "\n".join(
            f"CREATE INDEX IF NOT EXISTS sessions_{sort}_{direction.lower()} "
            f"ON sessions(source, ({column} IS NULL), {column} {direction}, session_id, {PERIOD_CLOCK});"
            for sort, column in SORT_COLUMNS.items() if sort != "name" for direction in ("ASC", "DESC")
        ) + DisplayHistory._name_indexes() + f"\nCREATE INDEX IF NOT EXISTS sessions_period ON sessions(source, {PERIOD_CLOCK});"

    @staticmethod
    def _name_indexes():
        # title_key is NOT NULL; SQLite simplifies its null expression away,
        # so indexing that expression obstructs seeks and index-order scans.
        return "\n".join(
            f"CREATE INDEX IF NOT EXISTS sessions_name_{direction.lower()} "
            f"ON sessions(source, title_key {direction}, session_id, {PERIOD_CLOCK});"
            for direction in ("ASC", "DESC"))

    def commit_sessions(self, source, updates=(), *, missing=(), present=(), archive_epoch=0):
        """Apply qualified facts and membership changes, without deleting old values.

        `missing` entries are (session_id, expected_checkpoint) from a qualified
        source membership observation, not a failed source request. Return the
        durable generation only when visible data changed, and only after COMMIT.
        """
        return self.commit_session_batch(source, updates, missing=missing, present=present,
                                         archive_epoch=archive_epoch).generation

    def commit_summary(self, source, change, *, archive_epoch, eligible):
        """Distinguish a confirmed current summary from a lost compare-and-swap."""
        return self.commit_session_batch(source, (change,), archive_epoch=archive_epoch, eligible=eligible)

    def commit_session_batch(self, source, updates, *, missing=(), present=(), archive_epoch, eligible=None):
        if (not source or type(archive_epoch) is not int or archive_epoch < 0
                or len(updates) + len(missing) + len(present) > BATCH_LIMIT
                or sum(change.request_roster is not None for change in updates) > 1):
            raise ValueError("invalid_display_batch")
        if not updates and not missing and not present:
            return SessionCommit()
        with self._write_lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            state = self._state(db, source)
            if state.archive_epoch != archive_epoch or eligible is not None and not eligible():
                return SessionCommit()
            db.execute("INSERT OR IGNORE INTO sources(source) VALUES(?)", (source,))
            clocks = []
            detail_roots = set()
            inserted = 0
            applied = 0
            for change in updates:
                session_id = change.fact.session_id
                if change.dependency is not None and (not change.dependency or change.previous_progress is None
                                                      or not ACQUIRED_SCALAR_FIELDS <= change.observed_fields):
                    raise ValueError("invalid_session_progress")
                if change.request_roster is not None and change.previous_progress is None:
                    raise ValueError("unguarded_request_roster")
                before = db.execute(f"""
                    SELECT s.revision, s.{PERIOD_CLOCK}, coalesce(p.progress, 0)
                    FROM sessions AS s LEFT JOIN session_progress AS p USING (source, session_id)
                    WHERE s.source=? AND s.session_id=?
                """, (source, session_id)).fetchone()
                revision, clock, progress = before or (None, None, 0)
                if (change.previous_revision != revision or
                        change.previous_progress is not None and change.previous_progress != progress):
                    continue
                applied += 1
                visible = self._apply_session(db, source, change)
                if visible:
                    detail_roots.add(session_id)
                    inserted += int(before is None)
                    clocks.extend((clock, self._activity(db, source, session_id)))
                if change.previous_progress is not None or (visible and progress):
                    self._advance_progress(db, source, session_id, change.fact.revision, change.dependency)
                if change.request_roster is not None and publish_roster(
                        db, source, session_id, change.fact.revision, change.request_roster):
                    detail_roots.add(session_id)
            for membership, entries in ((0, missing), (1, present)):
                for session_id, checkpoint in entries:
                    if db.execute("""
                        UPDATE sessions SET source_present=?,
                            field_evidence=CASE WHEN ?=1 THEN 0 ELSE field_evidence END
                        WHERE source=? AND session_id=? AND revision=? AND source_present<>?
                            AND coalesce((SELECT progress FROM session_progress AS p
                                WHERE p.source=sessions.source AND p.session_id=sessions.session_id), 0)=?
                    """, (membership, membership, source, session_id, checkpoint.revision, membership,
                          checkpoint.progress)).rowcount:
                        detail_roots.add(session_id)
                        clocks.append(self._activity(db, source, session_id))
                        # Returning under the same revision must not revive a
                        # prior completion or accept an in-flight pre-gap read.
                        self._advance_progress(db, source, session_id, checkpoint.revision, None)
            generation = None
            if detail_roots:
                generation = state.generation + 1
                known = [clock for clock in clocks if clock is not None]
                self._append_change(db, source, generation, inserted, min(known, default=None), max(known, default=None))
            if eligible is not None and not eligible():
                db.rollback()
                return SessionCommit()
            db.commit()
        return SessionCommit(generation, applied, frozenset(detail_roots))

    @staticmethod
    def _append_change(db, source, generation, inserted, earliest, latest):
        db.execute("UPDATE sources SET generation=?, session_count=session_count+? WHERE source=?",
                   (generation, inserted, source))
        db.execute("INSERT INTO session_changes VALUES(?, ?, ?, ?)", (source, generation, earliest, latest))
        db.execute("DELETE FROM session_changes WHERE source=? AND generation<=?", (source, generation - CHANGE_WINDOW))

    def replace_running(self, source, binding, running, *, archive_epoch):
        outcome = self.replace_live(source, binding, running=running, archive_epoch=archive_epoch)
        return outcome.sessions_generation if outcome is not None else None

    def replace_watch(self, source, binding, observation, *, archive_epoch):
        outcome = self.replace_live(source, binding, watch=observation, archive_epoch=archive_epoch)
        return outcome.watch_generation if outcome is not None else None

    def replace_live(self, source, binding, *, running=None, watch=None, finishes=(),
                     archive_epoch, eligible=lambda: True, finishes_current=None):
        """Commit qualified Live facts without waiting for historical backfill."""
        if (not source or not binding or len(finishes) > BATCH_LIMIT or running is not None and
                (len(running) > BATCH_LIMIT or any(
                    not item.session_id or type(item.started_ms) is not int or type(item.observed_ms) is not int
                    or not 0 < item.started_ms <= item.observed_ms for item in running))):
            raise ValueError("invalid_live_observation")
        with self._write_lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            state = self._state(db, source)
            if state.archive_epoch != archive_epoch or not eligible():
                return None
            sessions_generation = watch_generation = None
            inserted, finish_clocks = 0, []
            if finishes and finishes_current is not None and finishes_current():
                db.execute("INSERT OR IGNORE INTO sources(source) VALUES(?)", (source,))
                inserted, finish_clocks = self._publish_finishes(db, source, finishes)
            clocks = list(finish_clocks)
            if running is not None:
                if self._replace_running(db, source, binding, running):
                    clocks.extend((0, (1 << 63) - 1))  # Running can cross period boundaries.
            if clocks:
                sessions_generation = state.generation + 1
                self._append_change(db, source, sessions_generation, inserted, min(clocks), max(clocks))
            if watch is not None:
                db.execute("INSERT OR IGNORE INTO sources(source) VALUES(?)", (source,))
                watch_generation = publish_watch(db, source, binding, watch)
            if not eligible() or finish_clocks and not finishes_current():
                db.rollback()
                return None
            db.commit()
            return LiveCommit(sessions_generation, watch_generation)

    def _replace_running(self, db, source, binding, running):
        previous = tuple(db.execute("""
            SELECT binding, session_id, title, started_ms, ccost, context_tokens, context_invalidated, observed_ms
            FROM session_running
            WHERE source=? ORDER BY session_id
        """, (source,)))
        replacement = tuple((binding, item.session_id, item.title, item.started_ms,
                             str(item.ccost) if item.ccost is not None else None,
                             item.context_tokens, int(item.context_invalidated), item.observed_ms)
                            for item in sorted(running, key=lambda row: row.session_id))
        if previous == replacement:
            return False
        db.execute("INSERT OR IGNORE INTO sources(source) VALUES(?)", (source,))
        db.execute("DELETE FROM session_running WHERE source=?", (source,))
        db.executemany("""
            INSERT INTO session_running
                (source, binding, session_id, title, started_ms, ccost, context_tokens, context_invalidated, observed_ms)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ((source, *row) for row in replacement))
        now = int(time.time() * 1000)
        return (tuple(row[:-1] for row in previous) != tuple(row[:-1] for row in replacement)
                or any(old[-1] + RUNNING_FRESH_MS <= now < new[-1] + RUNNING_FRESH_MS
                       for old, new in zip(previous, replacement)))

    def _publish_finishes(self, db, source, finishes):
        inserted, clocks = 0, []
        for item in finishes:
            fact, fields = item.fact, item.fields
            if (fact.activity_origin != "finish" or not FINISH_FIELDS <= fields
                    or any(type(clock) is not int for clock in
                           (fact.prompt_started_ms, fact.activity_ms, fact.latest_activity_ms, item.observed_ms))
                    or not 0 < fact.prompt_started_ms <= fact.activity_ms <= fact.latest_activity_ms):
                raise ValueError("invalid_session_finish")
            before = db.execute(f"""
                SELECT s.revision, s.{PERIOD_CLOCK}, s.field_evidence, p.dependency
                FROM sessions AS s LEFT JOIN session_progress AS p USING (source, session_id)
                WHERE s.source=? AND s.session_id=?
            """, (source, fact.session_id)).fetchone()
            previous, old_clock, evidence, dependency = before or (None, None, 0, None)
            same = previous == fact.revision
            if same and dependency is not None:
                continue  # Do not replace a completed canonical scalar/usage capture.
            change = SessionChange(fact, previous, fields)
            retained = evidence & ~EMPTY_HISTORY_EVIDENCE if same else 0
            if self._apply_session(db, source, change, retained_evidence=retained):
                self._advance_progress(db, source, fact.session_id, fact.revision, None)
                inserted += int(before is None)
                clocks.extend(value for value in (old_clock, self._activity(db, source, fact.session_id))
                              if value is not None)
        return inserted, clocks

    def watch(self, source, binding, now_ms, *, live_eligible, timezone_id="UTC"):
        with self._connect(read=True) as db:
            db.execute("BEGIN")
            value = watch_snapshot(db, source, binding, now_ms, live_eligible=live_eligible, timezone_id=timezone_id)
            return dict(**value, archive_epoch=self._state(db, source).archive_epoch)

    def usage_inputs(self, source, *, expected=None, after=None):
        with self._connect(read=True) as db:
            db.execute("BEGIN")
            return read_usage_slice(db, source, expected=expected, after=after)

    def stats_usage(self, source, *, expected=None, after=None):
        with self._connect(read=True) as db:
            db.execute("BEGIN")
            return read_stats_usage(db, source, expected=expected, after=after)

    def stats_candidates(self, source, *, expected=None, after=None):
        with self._connect(read=True) as db:
            db.execute("BEGIN")
            return read_stats_candidates(db, source, expected=expected, after=after)

    def stats_version(self, source, *, expected=None):
        with self._connect(read=True) as db:
            db.execute("BEGIN")
            return retained_stats_version(db, source, expected)

    def stats_geometry(self, source, *, expected=None, after=None):
        with self._connect(read=True) as db:
            db.execute("BEGIN")
            return read_stats_geometry(db, source, expected=expected, after=after)

    def stats_roots(self, source, *, expected=None, after=None):
        with self._connect(read=True) as db:
            db.execute("BEGIN")
            return read_stats_roots(db, source, expected=expected, after=after)

    def stats_intervals(self, source, root, *, expected, after=None):
        with self._connect(read=True) as db:
            db.execute("BEGIN")
            if retained_stats_version(db, source, expected) is not None:
                return stats_interval_page(db, source, root, after, through=expected.evidence)
            return None

    def stats_parents(self, source, root, *, expected, after=None):
        with self._connect(read=True) as db:
            db.execute("BEGIN")
            if retained_stats_version(db, source, expected) is not None:
                return read_stats_parents(db, source, root, expected.evidence, after)
            return None

    def publish_stats_time(self, source, stamp, rows, *, eligible):
        with self._write_lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if eligible():
                published = commit_time(db, source, stamp, rows)
                if published is not None and eligible():
                    db.commit()
                    return published
            db.rollback()
            return None

    def stats_time_due(self, source, zone, scopes, now_ms):
        with self._connect(read=True) as db:
            db.execute("BEGIN")
            return time_due(db, source, zone, scopes, now_ms)

    def stats_time(self, source, zone, period, start_ms, now_ms):
        return self.stats_time_view(source, zone, period, start_ms, now_ms)[0]

    def stats_time_view(self, source, zone, period, start_ms, now_ms):
        with self._connect(read=True) as db:
            db.execute("BEGIN")
            return read_time(db, source, zone, period, start_ms, now_ms), self._state(db, source).archive_epoch

    def stats_view(self, source, zone, period, start_ms, now_ms):
        with self._connect(read=True) as db:
            db.execute("BEGIN")
            epoch = self._state(db, source).archive_epoch
            return (read_time(db, source, zone, period, start_ms, now_ms),
                    read_tokens(db, source, epoch, zone, period, start_ms, now_ms), epoch)

    def stats_tokens_due(self, source, zone, scopes, now_ms):
        with self._connect(read=True) as db:
            db.execute("BEGIN")
            return tokens_due(db, source, zone, scopes, now_ms)

    def publish_stats_tokens(self, source, stamp, rows, *, eligible):
        with self._write_lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if eligible():
                published = commit_tokens(db, source, stamp, rows)
                if published is not None and eligible():
                    db.commit()
                    return published
            db.rollback()
            return None

    def replace_mix_totals(self, source, expected, timezone_id, rows, *, eligible=lambda: True,
                           group_run=None, group_marks=None, reference=None):
        with self._write_lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if eligible():
                published = publish_mix_totals(db, source, expected, timezone_id, rows,
                                                group_run=group_run, group_marks=group_marks, reference=reference)
                if published is not None and eligible():
                    db.commit()
                    return published
            db.rollback()
            return None

    def mix_identities(self, source, version, keys, *, candidates, observed_at, eligible):
        if not candidates:
            with self._connect(read=True) as db:
                db.execute("BEGIN")
                if eligible() and retained_usage_version(db, source, version) is not None:
                    return read_mix_identities(db, source, keys)
                return None
        with self._write_lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if not eligible() or retained_usage_version(db, source, version) is None:
                return None
            db.execute("INSERT OR IGNORE INTO sources(source) VALUES(?)", (source,))
            save_mix_identities(db, source, candidates, observed_at)
            found = read_mix_identities(db, source, keys)
            if not eligible():
                return None
            db.commit()
            return found

    def mix_refresh(self, source, timezone_id, now_ms):
        with self._connect(read=True) as db:
            db.execute("BEGIN")
            return mix_refresh(db, source, timezone_id, now_ms)

    def mix_total(self, source, timezone_id, period, start_ms, end_ms, *, group_orders=None):
        with self._connect(read=True) as db:
            db.execute("BEGIN")
            totals = read_mix_total(db, source, timezone_id, period, start_ms, end_ms)
            if totals is None or group_orders is None:
                return totals
            run, = db.execute("SELECT group_run FROM archive_mix_state WHERE source=?", (source,)).fetchone()
            revision = group_revision(db, source, period) if run else None
            indexed = revision and revision.startswith(MIX_GROUP_ORDER_VERSION)
            groups = {}
            if revision:
                for kind in ("model", "publisher"):
                    order = group_orders.get(kind, MIX_GROUP_DEFAULT) if indexed else None
                    groups[kind] = (*read_groups(db, source, run, period, kind, "", order), order)
            return *totals, revision, groups

    def stage_mix_groups(self, source, expected, run, rows, *, eligible):
        with self._write_lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if not eligible() or retained_usage_version(db, source, expected) is None:
                return False
            stage_groups(db, source, run, rows)
            if not eligible():
                return False
            db.commit()
            return True

    def reclaim_mix_groups(self, source):
        with self._connect(read=True) as db:
            db.execute("BEGIN")
            run = inactive_run(db, source)
        if run is None:
            return 0
        with self._write_lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            reclaimed = remove_inactive_groups(db, source, run)
            db.commit()
            return reclaimed

    def mix_group_page(self, source, timezone_id, period, start_ms, end_ms, kind, after="", *, known=None, order=None):
        with self._connect(read=True) as db:
            db.execute("BEGIN")
            state = db.execute("""
                SELECT group_run,state.end_ms FROM archive_mix_state AS state JOIN archive_mix_totals USING(source)
                WHERE source=? AND timezone_id=? AND period=? AND start_ms IS ? AND state.end_ms<=?
            """, (source, timezone_id, period, start_ms, end_ms)).fetchone()
            if state is None or state[0] is None:
                return None
            revision = group_revision(db, source, period)
            if not revision:
                return None
            if revision.startswith(MIX_GROUP_ORDER_VERSION):
                order = order or MIX_GROUP_DEFAULT
            else:
                order = None  # Upgraded v15 snapshots still page by identity.
            cursor = after if known == revision else ""
            return revision, state[1], order, *read_groups(db, source, state[0], period, kind, cursor, order)

    @staticmethod
    def _advance_progress(db, source, session_id, revision, dependency):
        db.execute("""
            INSERT INTO session_progress(source, session_id, revision, dependency, progress)
            VALUES (?, ?, ?, ?, 1)
            ON CONFLICT(source, session_id) DO UPDATE
            SET revision=excluded.revision, dependency=excluded.dependency, progress=progress+1
        """, (source, session_id, revision, dependency))

    def publish_model_catalog(self, source, catalog, *, archive_epoch, eligible):
        with self._write_lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if self._state(db, source).archive_epoch != archive_epoch or not eligible():
                return False
            if not write_models(db, source, catalog) or not eligible():
                return False
            db.commit()
            return True

    def models_page(self, source, request, now_ms, *, price_invalidated_ms):
        with self._connect(read=True) as db:
            db.execute("BEGIN")
            return read_models(db, source, request, now_ms, price_invalidated_ms), self._state(db, source).archive_epoch

    def account_usage(self, source, start, end, *, version=None, after=None):
        with self._connect(read=True) as db:
            db.execute("BEGIN")
            return account_usage_slice(db, source, start, end, version=version, after=after)

    def _write_account_buckets(self, action, eligible):
        with self._write_lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if not eligible() or not action(db) or not eligible():
                return False
            db.commit()
            return True

    def stage_account_buckets(self, source, version, run, rows, *, eligible):
        return self._write_account_buckets(lambda db: stage_accounts(db, source, version, run, rows), eligible)

    def publish_account_buckets(self, source, stamp, *, eligible):
        return self._write_account_buckets(lambda db: publish_account_run(db, source, stamp), eligible)

    def read_account_buckets(self, source, zone, roster, period, account, start, end):
        with self._connect(read=True) as db:
            db.execute("BEGIN")
            return account_buckets(db, source, zone, roster, period, account, start, end)

    def account_history_due(self, source, zone, roster, now_ms, earliest):
        with self._connect(read=True) as db:
            db.execute("BEGIN")
            return account_history_due(db, source, zone, roster, now_ms, earliest)

    def read_account_chart(self, source, zone, roster, period, now_ms):
        with self._connect(read=True) as db:
            db.execute("BEGIN")
            return account_chart(db, source, zone, roster, period, now_ms), self._state(db, source).archive_epoch

    def cleanup_account_buckets(self, source, protected_run=None):
        with self._write_lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            removed = cleanup_accounts(db, source, protected_run)
            db.commit()
            return removed

    def model_benchmark_references(self, source):
        with self._connect(read=True) as db:
            return benchmark_references(db, source)

    def clear_confirmed_sessions(self, source, expected_state):
        """Storage step after external confirmation and acquisition quiescence.

        Only the bound archive is changed. An obsolete snapshot is not consent
        to clear newly committed data. Pending producers must make a fresh
        observation in the new archive epoch before accepting any writes.
        """
        if not source or not isinstance(expected_state, HistoryState):
            raise ValueError("invalid_clear_state")
        with self._write_lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if self._state(db, source) != expected_state:
                return None
            db.execute("INSERT OR IGNORE INTO sources(source) VALUES(?)", (source,))
            db.execute("DELETE FROM sessions WHERE source=?", (source,))
            db.execute("DELETE FROM archive_requests WHERE source=?", (source,))
            db.execute("DELETE FROM archive_stats_revisions WHERE source=?", (source,))
            db.execute("DELETE FROM archive_stats_geometry_revisions WHERE source=?", (source,))
            db.execute("DELETE FROM archive_stats_time_state WHERE source=?", (source,))
            db.execute("DELETE FROM archive_stats_token_state WHERE source=?", (source,))
            db.execute("DELETE FROM archive_fork_trees WHERE source=?", (source,))
            db.execute("DELETE FROM archive_mix_state WHERE source=?", (source,))
            db.execute("DELETE FROM archive_mix_groups WHERE source=?", (source,))
            db.execute("DELETE FROM archive_mix_identities WHERE source=?", (source,))
            db.execute("DELETE FROM archive_watch_state WHERE source=?", (source,))
            db.execute("DELETE FROM display_model_state WHERE source=?", (source,))
            db.execute("DELETE FROM display_account_state WHERE source=?", (source,))
            db.execute("DELETE FROM display_account_buckets WHERE source=?", (source,))
            db.execute("DELETE FROM session_running WHERE source=?", (source,))
            db.execute("DELETE FROM session_scope_coverage WHERE source=?", (source,))
            db.execute("DELETE FROM session_changes WHERE source=?", (source,))
            db.execute("""
                UPDATE sources SET generation=generation+1, session_count=0, archive_epoch=archive_epoch+1
                WHERE source=?
            """, (source,))
            state = self._state(db, source)
            db.commit()
            return state

    @staticmethod
    def _apply_session(db, source, change, *, retained_evidence=0):
        fact = change.fact
        if (not change.observed_fields <= SAVED_FIELDS or not (fact.revision and fact.session_id)
                or fact.activity_origin not in (None, "finish", "start", "no-prompt")):
            raise ValueError("invalid_session_evidence")
        evidence = field_evidence(change.observed_fields, empty_history=change.empty_history) | retained_evidence
        if change.observed_fields != SAVED_FIELDS:
            previous = db.execute(f"""
                SELECT {", ".join(METRIC_FIELDS)}
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
                   fact.prompts, fact.duration_ms, fact.context_tokens, fact.latest_activity_ms,
                   fact.prompt_started_ms, fact.activity_origin, fact.catalog_activity_ms, evidence,
                   fact.context_detail, fact.model_help, fact.has_model_details)
        columns = ("revision, title, title_key, activity_ms, model, model_key, ccost, cost_key, "
                   "prompts, duration_ms, context_tokens, latest_activity_ms, prompt_started_ms, "
                   "activity_origin, catalog_activity_ms, field_evidence, context_detail, model_help, has_model_details")
        marks = ", ".join("?" for _ in values)
        if change.previous_revision is None:
            return db.execute(f"""
                INSERT INTO sessions(source, session_id, {columns}, source_present)
                VALUES(?, ?, {marks}, 1)
                ON CONFLICT(source, session_id) DO NOTHING
            """, (source, fact.session_id, *values)).rowcount
        return db.execute(f"""
            UPDATE sessions SET ({columns}, source_present)=({marks}, 1)
            WHERE source=? AND session_id=? AND revision=?
                AND ({columns}, source_present) IS NOT ({marks}, 1)
        """, (*values, source, fact.session_id, change.previous_revision, *values)).rowcount

    @staticmethod
    def _activity(db, source, session_id):
        row = db.execute(f"SELECT {PERIOD_CLOCK} FROM sessions WHERE source=? AND session_id=?",
                         (source, session_id)).fetchone()
        return row[0] if row else None

    @staticmethod
    def _state(db, source):
        row = db.execute("SELECT generation, archive_epoch FROM sources WHERE source=?", (source,)).fetchone()
        return HistoryState(*row) if row else HistoryState()

    def source_state(self, source):
        if not source:
            raise ValueError("invalid_source")
        with self._connect(read=True) as db:
            return self._state(db, source)

    def session_checkpoints(self, source, session_ids):
        """Read the revision and scalar write guard for a bounded publication."""
        if not source or len(session_ids) > BATCH_LIMIT:
            raise ValueError("invalid_revision_query")
        if not session_ids:
            return {}
        marks = ",".join("?" for _ in session_ids)
        with self._connect(read=True) as db:
            return {key: SessionCheckpoint(revision, progress) for key, revision, progress in db.execute(f"""
                SELECT s.session_id, s.revision, coalesce(p.progress, 0)
                FROM sessions AS s LEFT JOIN session_progress AS p USING (source, session_id)
                WHERE s.source=? AND s.session_id IN ({marks})
            """, (source, *session_ids))}

    def session_membership_slice(self, source, after):
        """Keyset walk for restart-safe reconciliation, independent of UI paging."""
        if not source or not isinstance(after, str):
            raise ValueError("invalid_membership_query")
        with self._connect(read=True) as db:
            rows = db.execute("""
                SELECT s.session_id, s.revision, coalesce(p.progress, 0), s.source_present
                FROM sessions AS s LEFT JOIN session_progress AS p USING (source, session_id)
                WHERE s.source=? AND s.session_id>?
                ORDER BY s.session_id LIMIT ?
            """, (source, after, BATCH_LIMIT))
            return tuple((key, SessionCheckpoint(revision, progress), present) for key, revision, progress, present in rows)

    def completed_sessions(self, source, revisions, dependency, *, with_history=False, with_stats_requests=False):
        """Match exact dependency evidence, never infer freshness from revision alone."""
        if not source or not dependency or len(revisions) > BATCH_LIMIT:
            raise ValueError("invalid_archive_progress_query")
        if not revisions:
            return frozenset()
        marks = ",".join("?" for _ in revisions)
        # Scalar-only capture can serve Sessions but is not evidence that
        # usage, prompt detail and Stats geometry for this revision exist.
        roster_check = """
            AND EXISTS(SELECT 1 FROM archive_stats_roots AS stats
                JOIN archive_prompt_state AS detail USING(source,root_id)
                WHERE stats.source=p.source AND stats.root_id=p.session_id
                    AND stats.source_revision=p.revision AND detail.revision=p.revision)
        """ if with_history else ""
        request_check = """
            AND EXISTS(SELECT 1 FROM archive_stats_request_ready AS stats
                WHERE stats.source=p.source AND stats.root_id=p.session_id AND stats.source_revision=p.revision)
        """ if with_stats_requests else ""
        with self._connect(read=True) as db:
            return frozenset(key for key, revision in db.execute(f"""
                SELECT p.session_id, p.revision FROM session_progress AS p
                JOIN sessions AS s USING (source, session_id, revision)
                WHERE p.source=? AND p.dependency=? AND p.session_id IN ({marks}) AND s.source_present=1
                {roster_check}
                {request_check}
            """, (source, dependency, *revisions)) if revisions[key] == revision)

    def session_coverage_slice(self, source, revisions):
        """One bounded join against the exact roster's current revisions."""
        if not source or len(revisions) > BATCH_LIMIT:
            raise ValueError("invalid_coverage_slice")
        if not revisions:
            return {}
        marks = ",".join("?" for _ in revisions)
        activity_bit = FIELD_EVIDENCE_BITS["latest_activity_ms"]
        with self._connect(read=True) as db:
            return {key: (dep if revision == revisions[key] and present else None,
                          revision == revisions[key] and present and bool(evidence & activity_bit), clock)
                    for key, revision, dep, evidence, clock, present in db.execute(f"""
                SELECT s.session_id,s.revision,p.dependency,s.field_evidence,s.{PERIOD_CLOCK},s.source_present
                FROM sessions AS s LEFT JOIN session_progress AS p USING (source,session_id,revision)
                WHERE s.source=? AND s.session_id IN ({marks})
            """, (source, *revisions))}

    @staticmethod
    def _session_coverage(db, source):
        value = db.execute("""
            SELECT observed_ms,incomplete,unknown_clock,newest_gap_ms
            FROM session_scope_coverage WHERE source=?
        """, (source,)).fetchone()
        return SessionCoverage(value[0], bool(value[1]), bool(value[2]), value[3]) if value is not None else None

    def publish_session_coverage(self, source, proof, *, archive_epoch, widen_only=False):
        with self._write_lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            state = self._state(db, source)
            if state.archive_epoch != archive_epoch:
                return None
            previous = self._session_coverage(db, source)
            if widen_only and previous is not None:
                proof = proof.with_gaps_from(previous)
            if previous is not None and (proof.observed_ms < previous.observed_ms or
                    (proof.incomplete, proof.unknown_clock, proof.newest_gap_ms) ==
                    (previous.incomplete, previous.unknown_clock, previous.newest_gap_ms)):
                return None
            db.execute("INSERT OR IGNORE INTO sources(source) VALUES(?)", (source,))
            db.execute("""
                INSERT INTO session_scope_coverage VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source) DO UPDATE SET observed_ms=excluded.observed_ms, incomplete=excluded.incomplete,
                    unknown_clock=excluded.unknown_clock, newest_gap_ms=excluded.newest_gap_ms
            """, (source, proof.observed_ms, proof.incomplete, proof.unknown_clock, proof.newest_gap_ms))
            generation = state.generation + 1
            self._append_change(db, source, generation, 0, 0, (1 << 63) - 1)
            db.commit()
            return generation

    def session_detail_page(self, source, root, *, limit, offset):
        with self._connect(read=True) as db:
            db.execute("BEGIN")
            state = self._state(db, source)
            header = db.execute("""
                SELECT s.title,s.ccost,s.prompts,s.context_tokens,s.context_detail,s.source_present,
                       p.revision IS NOT NULL,p.revision=s.revision
                FROM sessions AS s LEFT JOIN archive_prompt_state AS p
                    ON p.source=s.source AND p.root_id=s.session_id
                WHERE s.source=? AND s.session_id=?
            """, (source, root)).fetchone()
            if header is None:
                return state.generation, None, 0, ()
            count = db.execute("""
                SELECT count(*) FROM archive_prompt_history WHERE source=? AND root_id=?
            """, (source, root)).fetchone()[0]
            return state.generation, header, count, prompt_page(db, source, root, limit, offset)

    def has_present_session(self, source, root):
        with self._connect(read=True) as db:
            return db.execute("""
                SELECT 1 FROM sessions WHERE source=? AND session_id=? AND source_present=1
            """, (source, root)).fetchone() is not None

    def session_changes(self, source, previous):
        """Read compact committed hints, or signal a requery across a replay gap."""
        if not source or type(previous) is not int or previous < 0:
            raise ValueError("invalid_change_cursor")
        with self._connect(read=True) as db:
            db.execute("BEGIN")
            generation = self._state(db, source).generation
            if not 0 <= generation - previous <= CHANGE_WINDOW:
                return SessionChanges(generation, resync=True)
            count, oldest, latest = db.execute("""
                SELECT count(*), min(oldest_activity_ms), max(latest_activity_ms)
                FROM session_changes WHERE source=? AND generation>?
            """, (source, previous)).fetchone()
            if count != generation - previous:
                return SessionChanges(generation, resync=True)
        return SessionChanges(generation, oldest_activity_ms=oldest, latest_activity_ms=latest)

    def has_session_clock(self, source, start_ms, end_ms):
        """Indexed bound check when wall time advances without a cache write."""
        with self._connect(read=True) as db:
            return db.execute(f"""
                SELECT 1 FROM sessions WHERE source=? AND {PERIOD_CLOCK}>=? AND {PERIOD_CLOCK}<? LIMIT 1
            """, (source, start_ms, end_ms)).fetchone() is not None

    def has_running_snapshot(self, source, binding):
        with self._connect(read=True) as db:
            return db.execute(
                "SELECT 1 FROM session_running WHERE source=? AND binding=? LIMIT 1",
                (source, binding)).fetchone() is not None

    def session_page(self, source, *, sort="activity", direction=-1, start_ms=None, end_ms=None,
                     limit=25, offset=0, live_binding=None, now_ms=None, seek=None):
        if (not source or sort not in SORT_COLUMNS or type(direction) is not int or direction not in (-1, 1)
                or type(limit) is not int or not 1 <= limit <= PAGE_LIMIT
                or type(offset) is not int or not 0 <= offset <= 1_000_000):
            raise ValueError("invalid_display_query")
        column = SORT_COLUMNS[sort]
        order = "ASC" if direction == 1 else "DESC"
        index = f"sessions_{sort}_{order.lower()}"
        nullable = sort != "name"
        ordering = f"({column} IS NULL), {column} {order}" if nullable else f"{column} {order}"
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
            coverage = self._session_coverage(db, source)
            active, expires = self._running_page(db, source, live_binding, now_ms) if live_binding else ((), None)
            if seek is not None and not active and seek.generation == generation:
                same_end = seek.end_ms == end_ms
                passed_empty = (seek.end_ms is not None and end_ms is not None and seek.end_ms < end_ms and
                    db.execute(f"SELECT 1 FROM sessions WHERE source=? AND {PERIOD_CLOCK}>=? AND {PERIOD_CLOCK}<? LIMIT 1",
                               (source, seek.end_ms, end_ms)).fetchone() is None)
                if same_end or passed_empty:
                    keys = seek_keys(db, source, column=column, index=index, direction=direction, where=where,
                                     params=params, limit=limit, seek=seek, nullable=nullable)
                    if keys is not None and len(keys) == min(limit, seek.total - offset):
                        rows = self._seek_session_rows(db, source, keys)
                        return SessionPage(generation, seek.total, rows, coverage=coverage)
            if len(params) > 1:
                total = db.execute(f"SELECT count(*) FROM sessions WHERE {where}", params).fetchone()[0]
            if active:
                marks = ", ".join("?" for _ in active)
                ids = tuple(row.session_id for row in active)
                overlap = db.execute(f"SELECT count(*) FROM sessions WHERE {where} AND session_id IN ({marks})",
                                     (*params, *ids)).fetchone()[0]
                total += len(active) - overlap
                where += f" AND session_id NOT IN ({marks})"
                params.extend(ids)
            running_slice = active[offset:offset + limit]
            if len(running_slice) == limit:
                return SessionPage(generation, total, running_slice, expires, coverage)
            # Select ordered keys first with the covering index. CROSS JOIN
            # keeps the small selected set outermost; a reordered join can
            # scan every historical row just to return the first page.
            rows = db.execute(f"""
                WITH selected AS (
                    SELECT session_id FROM sessions INDEXED BY {index} WHERE {where}
                    ORDER BY {ordering}, session_id
                    LIMIT ? OFFSET ?
                )
                SELECT s.session_id, revision, title, activity_ms, model, ccost,
                    prompts, duration_ms, context_tokens, source_present, latest_activity_ms,
                    prompt_started_ms, activity_origin, catalog_activity_ms, field_evidence,
                    context_detail, model_help, has_model_details
                FROM selected CROSS JOIN sessions AS s
                WHERE s.source=? AND s.session_id=selected.session_id
                ORDER BY {ordering}, s.session_id
            """, (*params, limit - len(running_slice), max(0, offset - len(active)), source)).fetchall()
        return SessionPage(generation, total, running_slice + self._decode_session_rows(rows), expires, coverage)

    @classmethod
    def _seek_session_rows(cls, db, source, keys):
        if not keys:
            return ()
        marks = ",".join("?" for _ in keys)
        rows = cls._decode_session_rows(db.execute(f"""
            SELECT session_id, revision, title, activity_ms, model, ccost, prompts, duration_ms, context_tokens,
                source_present, latest_activity_ms, prompt_started_ms, activity_origin, catalog_activity_ms,
                field_evidence, context_detail, model_help, has_model_details
            FROM sessions WHERE source=? AND session_id IN ({marks})
        """, (source, *keys)))
        by_id = {row.session_id: row for row in rows}
        return tuple(by_id[key] for key in keys)

    @staticmethod
    def _decode_session_rows(rows):
        return tuple(SessionSnapshot(*row[:9], bool(row[9]), *row[10:14], field_evidence=row[14],
                                     context_detail=row[15], model_help=row[16], has_model_details=row[17])
                     for row in rows)

    @staticmethod
    def _running_page(db, source, binding, now_ms):
        if type(now_ms) is not int:
            raise ValueError("invalid_running_clock")
        rows = tuple(db.execute("""
            SELECT r.session_id, r.title, r.started_ms, r.observed_ms, s.revision, s.model,
                   coalesce(r.ccost, s.ccost), s.prompts, s.duration_ms,
                   CASE WHEN r.context_invalidated THEN NULL ELSE coalesce(r.context_tokens, s.context_tokens) END,
                   CASE WHEN NOT r.context_invalidated AND r.context_tokens IS NULL THEN s.context_detail END,
                   s.model_help, s.has_model_details
            FROM session_running AS r LEFT JOIN sessions AS s USING (source, session_id)
            WHERE r.source=? AND r.binding=? AND r.observed_ms>? AND r.observed_ms<=?
            ORDER BY r.started_ms DESC, r.session_id
        """, (source, binding, now_ms - RUNNING_FRESH_MS, now_ms)))
        expires = min((row[3] + RUNNING_FRESH_MS for row in rows), default=None)
        return (tuple(SessionSnapshot(key, revision or "", title, start, model, cost, prompts, duration, context,
                                      True, start, start, "running", None, running=True, context_detail=detail,
                                      model_help=help_text, has_model_details=has_details)
                      for key, title, start, _, revision, model, cost, prompts, duration, context,
                      detail, help_text, has_details in rows), expires)
