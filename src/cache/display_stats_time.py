"""Committed AI Stats measured working time; no estimated or live geometry."""
from dataclasses import dataclass

from .display_stats_revision import StatsVersion, retained_stats_version
from .display_usage_reader import UsageVersion

_PERIODS = frozenset({"today", "7-days", "30-days", "month", "all"})


@dataclass(frozen=True, slots=True)
class StatsTimeRow:
    period: str
    start_ms: int | None
    working_ms: int | None


@dataclass(frozen=True, slots=True)
class StatsTimeStamp:
    version: StatsVersion
    zone: str
    as_of: int
    next_end: int | None


@dataclass(frozen=True, slots=True)
class StatsTimePublication:
    stamp: StatsTimeStamp
    changed_periods: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StatsTimeSnapshot:
    row: StatsTimeRow
    stamp: StatsTimeStamp
    current: bool  # Current against the archive, not proof of historical coverage.


def stats_time_schema():
    return """
        CREATE TABLE IF NOT EXISTS archive_stats_time_state (
            source TEXT PRIMARY KEY REFERENCES sources(source),
            archive_epoch INTEGER NOT NULL, usage_revision INTEGER NOT NULL, evidence_revision INTEGER NOT NULL,
            timezone_id TEXT NOT NULL, end_ms INTEGER NOT NULL, next_end INTEGER
        ) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS archive_stats_time (
            source TEXT NOT NULL REFERENCES archive_stats_time_state(source) ON DELETE CASCADE,
            period TEXT NOT NULL, start_ms INTEGER, working_ms INTEGER,
            PRIMARY KEY(source,period)
        ) WITHOUT ROWID;
    """


def time_stamp(db, source):
    row = db.execute("SELECT archive_epoch,usage_revision,evidence_revision,timezone_id,end_ms,next_end "
                     "FROM archive_stats_time_state WHERE source=?", (source,)).fetchone()
    return StatsTimeStamp(StatsVersion(UsageVersion(*row[:2]), row[2]), *row[3:]) if row else None


def commit_time(db, source, stamp, rows):
    if (not source or not stamp.zone or stamp.as_of <= 0
            or (stamp.next_end is not None and stamp.next_end <= stamp.as_of)
            or len(rows) != len(_PERIODS) or {row.period for row in rows} != _PERIODS):
        raise ValueError("invalid_stats_time")
    for row in rows:
        if ((row.start_ms is None) != (row.period == "all")
                or (row.start_ms is not None and row.start_ms > stamp.as_of)
                or (row.working_ms is not None and not 0 < row.working_ms <= stamp.as_of - max(0, row.start_ms or 0))):
            raise ValueError("invalid_stats_time_row")
    if retained_stats_version(db, source, stamp.version) is None:
        return None
    old = time_stamp(db, source)
    prior = {}
    if old and stamp.version.usage.archive_epoch == old.version.usage.archive_epoch:
        if (stamp.as_of < old.as_of or stamp.version.evidence < old.version.evidence
                or stamp.version.usage.revision < old.version.usage.revision):
            return None
        if old.zone == stamp.zone:
            prior = {period: (start, duration) for period, start, duration in db.execute("""
                SELECT period,start_ms,working_ms FROM archive_stats_time WHERE source=?
            """, (source,))}
    db.execute("INSERT OR IGNORE INTO sources(source) VALUES(?)", (source,))
    db.execute("""
        INSERT INTO archive_stats_time_state VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(source) DO UPDATE SET (archive_epoch,usage_revision,evidence_revision,timezone_id,end_ms,next_end)=
            (excluded.archive_epoch,excluded.usage_revision,excluded.evidence_revision,
             excluded.timezone_id,excluded.end_ms,excluded.next_end)
    """, (source, stamp.version.usage.archive_epoch, stamp.version.usage.revision,
          stamp.version.evidence, stamp.zone, stamp.as_of, stamp.next_end))
    db.executemany("""
        INSERT INTO archive_stats_time VALUES(?,?,?,?)
        ON CONFLICT(source,period) DO UPDATE SET (start_ms,working_ms)=(excluded.start_ms,excluded.working_ms)
        WHERE (start_ms,working_ms) IS NOT (excluded.start_ms,excluded.working_ms)
    """, ((source, row.period, row.start_ms, row.working_ms) for row in rows))
    changed = tuple(row.period for row in rows if prior.get(row.period) != (row.start_ms, row.working_ms))
    return StatsTimePublication(stamp, changed)


def time_due(db, source, zone, scopes, now_ms):
    stamp = time_stamp(db, source)
    if stamp is None:
        return True
    if stamp.as_of > now_ms:
        return False  # Do not overwrite a newer observation on UTC clock reversal.
    if stamp.zone != zone or not _current(db, source, stamp, now_ms):
        return True
    saved = dict(db.execute("SELECT period,start_ms FROM archive_stats_time WHERE source=?", (source,)))
    return saved != dict(scopes)


def read_time(db, source, zone, period, start_ms, now_ms):
    if period not in _PERIODS:
        raise ValueError("invalid_stats_period")
    stamp = time_stamp(db, source)
    if stamp is None or stamp.zone != zone or stamp.as_of > now_ms:
        return None
    version = retained_stats_version(db, source)
    if stamp.version.usage.archive_epoch != version.usage.archive_epoch:
        return None
    row = db.execute("""
        SELECT working_ms FROM archive_stats_time WHERE source=? AND period=? AND start_ms IS ?
    """, (source, period, start_ms)).fetchone()
    if row is None:
        return None
    return StatsTimeSnapshot(StatsTimeRow(period, start_ms, row[0]), stamp,
                             version == stamp.version and _unexpired(stamp, now_ms))


def _current(db, source, stamp, now_ms):
    return _unexpired(stamp, now_ms) and retained_stats_version(db, source) == stamp.version


def _unexpired(stamp, now_ms):
    return stamp.next_end is None or now_ms < stamp.next_end
