"""Typed Stats-only geometry, separate from usage, prompt display and billing."""
from dataclasses import dataclass

from .display_usage_reader import USAGE_SLICE


@dataclass(frozen=True, slots=True)
class ResponseTiming:
    """Completed stream geometry or explicit exclusion; None means no proof."""
    start_ms: int | None = None
    duration_ms: int | None = None
    excluded: bool = False


@dataclass(frozen=True, slots=True)
class StatsInterval:
    session: str
    event: str
    kind: str
    start_ms: int | None
    duration_ms: int | None
    provisional: bool


@dataclass(frozen=True, slots=True)
class StatsMatch:
    event: str
    fingerprint: bytes
    start_ms: int
    duration_ms: int | None
    status: str


@dataclass(frozen=True, slots=True)
class StatsCapture:
    intervals: tuple[StatsInterval, ...]
    usage_pending: bool
    first_input: StatsMatch | None
    parents: tuple[tuple[str, str | None], ...]


@dataclass(frozen=True, slots=True)
class StatsIntervalPage:
    intervals: tuple[StatsInterval, ...]
    next_cursor: tuple[str, str, str] | None


def stats_evidence_schema():
    return """
        CREATE TABLE IF NOT EXISTS archive_stats_revisions (
            source TEXT PRIMARY KEY REFERENCES sources(source),
            revision INTEGER NOT NULL
        ) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS archive_stats_roots (
            source TEXT NOT NULL, root_id TEXT NOT NULL,
            source_revision TEXT NOT NULL, usage_pending INTEGER NOT NULL,
            PRIMARY KEY(source,root_id),
            FOREIGN KEY(source,root_id) REFERENCES archive_request_rosters(source,root_id) ON DELETE CASCADE
        ) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS archive_stats_intervals (
            source TEXT NOT NULL, root_id TEXT NOT NULL, session_id TEXT NOT NULL, event_id TEXT NOT NULL,
            kind TEXT NOT NULL, start_ms INTEGER, duration_ms INTEGER,
            provisional INTEGER NOT NULL CHECK(provisional IN (0,1)),
            PRIMARY KEY(source,root_id,session_id,event_id,kind),
            FOREIGN KEY(source,root_id) REFERENCES archive_stats_roots(source,root_id) ON DELETE CASCADE
        ) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS archive_stats_parents (
            source TEXT NOT NULL, root_id TEXT NOT NULL, session_id TEXT NOT NULL, parent_id TEXT,
            PRIMARY KEY(source,root_id,session_id),
            FOREIGN KEY(source,root_id) REFERENCES archive_stats_roots(source,root_id) ON DELETE CASCADE
        ) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS archive_stats_first_inputs (
            source TEXT NOT NULL, root_id TEXT NOT NULL, event_id TEXT NOT NULL,
            fingerprint BLOB NOT NULL CHECK(length(fingerprint)=32), start_ms INTEGER NOT NULL CHECK(start_ms>0),
            duration_ms INTEGER, status TEXT NOT NULL CHECK(status IN ('complete','failed','aborted','unverified','unknown')),
            PRIMARY KEY(source,root_id),
            FOREIGN KEY(source,root_id) REFERENCES archive_stats_roots(source,root_id) ON DELETE CASCADE
        ) WITHOUT ROWID;
        CREATE INDEX IF NOT EXISTS archive_stats_match_clock ON archive_stats_first_inputs(source,start_ms,fingerprint);
        CREATE TABLE IF NOT EXISTS archive_response_timing (
            source TEXT NOT NULL, request_key BLOB NOT NULL, completion_ms INTEGER NOT NULL,
            start_ms INTEGER, duration_ms INTEGER, excluded INTEGER NOT NULL,
            PRIMARY KEY(source,request_key),
            FOREIGN KEY(source,request_key) REFERENCES archive_requests(source,request_key) ON DELETE CASCADE,
            CHECK((excluded=1 AND start_ms IS NULL AND duration_ms IS NULL)
                  OR (excluded=0 AND start_ms IS NOT NULL AND duration_ms IS NOT NULL
                      AND start_ms>0 AND duration_ms>0 AND start_ms+duration_ms<=completion_ms))
        ) WITHOUT ROWID;
    """


def publish_stats_evidence(db, source, root, revision, capture, requests):
    """Independent corrections are atomic with their qualified source capture."""
    count = db.execute("""
        INSERT INTO archive_stats_roots VALUES(?,?,?,?)
        ON CONFLICT(source,root_id) DO UPDATE SET
            (source_revision,usage_pending)=(excluded.source_revision,excluded.usage_pending)
        WHERE (source_revision,usage_pending) IS NOT (excluded.source_revision,excluded.usage_pending)
    """, (source, root, revision, capture.usage_pending)).rowcount
    # Missing or provisional facts cannot erase measured historical geometry.
    # New measured facts on a currently observed event can correct it.
    count += db.executemany("""
        INSERT INTO archive_stats_intervals VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(source,root_id,session_id,event_id,kind) DO UPDATE SET
            (start_ms,duration_ms,provisional)=(excluded.start_ms,excluded.duration_ms,excluded.provisional)
        WHERE (start_ms IS NULL OR excluded.start_ms IS NOT NULL)
          AND (duration_ms IS NULL OR excluded.duration_ms IS NOT NULL)
          AND (provisional OR NOT excluded.provisional)
          AND (start_ms,duration_ms,provisional) IS NOT (excluded.start_ms,excluded.duration_ms,excluded.provisional)
    """, ((source, root, value.session, value.event, value.kind, value.start_ms, value.duration_ms, value.provisional)
          for value in capture.intervals)).rowcount
    count += db.executemany("""
        INSERT INTO archive_response_timing
        SELECT source,request_key,clock_ms,?,?,? FROM archive_requests
        WHERE source=? AND request_key=? AND clock_ms=? AND dedup_tree IS ?
        ON CONFLICT(source,request_key) DO UPDATE SET
            (completion_ms,start_ms,duration_ms,excluded) =
                (excluded.completion_ms,excluded.start_ms,excluded.duration_ms,excluded.excluded)
        WHERE (completion_ms,start_ms,duration_ms,archive_response_timing.excluded) IS NOT
              (excluded.completion_ms,excluded.start_ms,excluded.duration_ms,excluded.excluded)
    """, ((value.response.start_ms, value.response.duration_ms, value.response.excluded,
           source, value.key, value.clock_ms, value.dedup_tree) for value in requests
          if value.response is not None)).rowcount
    count += _publish_match_and_parents(db, source, root, capture)
    if count:
        db.execute("""
            INSERT INTO archive_stats_revisions VALUES(?,1)
            ON CONFLICT(source) DO UPDATE SET revision=revision+1
        """, (source,))


def _publish_match_and_parents(db, source, root, capture):
    count = db.executemany("""
        INSERT INTO archive_stats_parents VALUES(?,?,?,?)
        ON CONFLICT(source,root_id,session_id) DO UPDATE SET parent_id=excluded.parent_id
        WHERE parent_id IS NOT excluded.parent_id
    """, ((source, root, session, parent) for session, parent in capture.parents)).rowcount
    value = capture.first_input
    if value is not None:
        count += db.execute("""
            INSERT INTO archive_stats_first_inputs VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(source,root_id) DO UPDATE SET
                (event_id,fingerprint,start_ms,duration_ms,status)=
                    (excluded.event_id,excluded.fingerprint,excluded.start_ms,excluded.duration_ms,excluded.status)
            WHERE (event_id,fingerprint,start_ms,duration_ms,status) IS NOT
                (excluded.event_id,excluded.fingerprint,excluded.start_ms,excluded.duration_ms,excluded.status)
              AND (event_id=excluded.event_id OR (excluded.start_ms,excluded.event_id)<(start_ms,event_id))
              AND (status NOT IN ('complete','failed','aborted')
                   OR (event_id,fingerprint,start_ms) IS NOT (excluded.event_id,excluded.fingerprint,excluded.start_ms)
                   OR excluded.status IN ('complete','failed','aborted'))
        """, (source, root, value.event, value.fingerprint, value.start_ms, value.duration_ms, value.status)).rowcount
    return count


def stats_revision(db, source):
    row = db.execute("SELECT revision FROM archive_stats_revisions WHERE source=?", (source,)).fetchone()
    return row[0] if row else 0


def stats_interval_page(db, source, root, after=None):
    resume = "AND (session_id,event_id,kind)>(?,?,?)" if after is not None else ""
    rows = db.execute(f"""
        SELECT session_id,event_id,kind,start_ms,duration_ms,provisional
        FROM archive_stats_intervals WHERE source=? AND root_id=? {resume}
        ORDER BY session_id,event_id,kind LIMIT ?
    """, (source, root, *(after or ()), USAGE_SLICE + 1)).fetchall()
    return StatsIntervalPage(tuple(StatsInterval(*row[:-1], bool(row[-1])) for row in rows[:USAGE_SLICE]),
                             rows[USAGE_SLICE - 1][:3] if len(rows) > USAGE_SLICE else None)


def response_timings(db, source, request_keys):
    if not request_keys:
        return {}
    if len(request_keys) > USAGE_SLICE:
        raise ValueError("invalid_response_timing_slice")
    marks = ",".join("?" for _ in request_keys)
    return {key: ResponseTiming(start, duration, bool(excluded)) for key, start, duration, excluded in db.execute(f"""
        SELECT timing.request_key,start_ms,duration_ms,excluded
        FROM archive_response_timing AS timing JOIN archive_requests AS request USING(source,request_key)
        WHERE source=? AND request_key IN ({marks}) AND request.clock_ms=timing.completion_ms
    """, (source, *request_keys))}
