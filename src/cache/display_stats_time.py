"""Committed AI Stats measured working time; no estimated or live geometry."""
from dataclasses import astuple, dataclass

from .display_stats_geometry_revision import StatsGeometryVersion, retained_geometry_version

_PERIODS = frozenset({"today", "7-days", "30-days", "month", "all"})


@dataclass(frozen=True, slots=True)
class StatsCalendar:
    busiest_local_day: int  # Gregorian date ordinal, not a UTC timestamp.
    busiest_ms: int
    night_ms: int
    streak_days: int


@dataclass(frozen=True, slots=True)
class StatsRootTime:
    longest_root: str
    longest_ms: int
    peak_roots: int


@dataclass(frozen=True, slots=True)
class StatsTimeRow:
    period: str
    start_ms: int | None
    working_ms: int | None
    calendar: StatsCalendar | None = None
    roots: StatsRootTime | None = None


@dataclass(frozen=True, slots=True)
class StatsTimeStamp:
    version: StatsGeometryVersion
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
    longest_title: str | None
    sessions_generation: int


def stats_time_schema(*, upgrade=False):
    migration = """
        ALTER TABLE archive_stats_time_state DROP COLUMN usage_revision;
        ALTER TABLE archive_stats_time_state RENAME COLUMN evidence_revision TO geometry_revision;
        UPDATE archive_stats_time_state SET geometry_revision=-1;
    """ if upgrade else ""
    return migration + """
        CREATE TABLE IF NOT EXISTS archive_stats_time_state (
            source TEXT PRIMARY KEY REFERENCES sources(source),
            archive_epoch INTEGER NOT NULL, geometry_revision INTEGER NOT NULL,
            timezone_id TEXT NOT NULL, end_ms INTEGER NOT NULL, next_end INTEGER
        ) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS archive_stats_time (
            source TEXT NOT NULL REFERENCES archive_stats_time_state(source) ON DELETE CASCADE,
            period TEXT NOT NULL, start_ms INTEGER, working_ms INTEGER,
            PRIMARY KEY(source,period)
        ) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS archive_stats_calendar (
            source TEXT NOT NULL, period TEXT NOT NULL,
            busiest_local_day INTEGER, busiest_ms INTEGER, night_ms INTEGER, streak_days INTEGER,
            PRIMARY KEY(source,period),
            FOREIGN KEY(source,period) REFERENCES archive_stats_time(source,period) ON DELETE CASCADE
        ) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS archive_stats_root_time (
            source TEXT NOT NULL, period TEXT NOT NULL,
            longest_root TEXT, longest_ms INTEGER, peak_roots INTEGER,
            PRIMARY KEY(source,period),
            FOREIGN KEY(source,period) REFERENCES archive_stats_time(source,period) ON DELETE CASCADE
        ) WITHOUT ROWID;
    """


_COLUMNS = """period,start_ms,working_ms,busiest_local_day,busiest_ms,night_ms,streak_days,
              longest_root,longest_ms,peak_roots"""
_FROM = """
    FROM archive_stats_time LEFT JOIN archive_stats_calendar USING(source,period)
         LEFT JOIN archive_stats_root_time USING(source,period)
"""
_ROWS = f"SELECT {_COLUMNS} {_FROM} WHERE source=?"


def time_stamp(db, source):
    row = db.execute("SELECT archive_epoch,geometry_revision,timezone_id,end_ms,next_end "
                     "FROM archive_stats_time_state WHERE source=?", (source,)).fetchone()
    return StatsTimeStamp(StatsGeometryVersion(*row[:2]), *row[2:]) if row else None


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
        calendar = row.calendar
        if calendar and (row.working_ms is None or not 0 < calendar.busiest_ms <= row.working_ms
                         or not 0 <= calendar.night_ms <= row.working_ms
                         or calendar.busiest_local_day <= 0 or calendar.streak_days <= 0):
            raise ValueError("invalid_stats_calendar_row")
        roots = row.roots
        if roots and (row.working_ms is None or not 0 < roots.longest_ms <= row.working_ms or roots.peak_roots <= 0
                      or not roots.longest_root):
            raise ValueError("invalid_stats_root_time_row")
    if retained_geometry_version(db, source, stamp.version) is None:
        return None
    old = time_stamp(db, source)
    prior = {}
    if old and stamp.version.archive_epoch == old.version.archive_epoch:
        if stamp.as_of < old.as_of or stamp.version.revision < old.version.revision:
            return None
        if old.zone == stamp.zone:
            prior = {row[0]: _decode(row) for row in db.execute(_ROWS, (source,))}
    db.execute("INSERT OR IGNORE INTO sources(source) VALUES(?)", (source,))
    db.execute("""
        INSERT INTO archive_stats_time_state(source,archive_epoch,geometry_revision,timezone_id,end_ms,next_end)
        VALUES(?,?,?,?,?,?)
        ON CONFLICT(source) DO UPDATE SET (archive_epoch,geometry_revision,timezone_id,end_ms,next_end)=
            (excluded.archive_epoch,excluded.geometry_revision,excluded.timezone_id,excluded.end_ms,excluded.next_end)
    """, (source, stamp.version.archive_epoch, stamp.version.revision, stamp.zone, stamp.as_of, stamp.next_end))
    db.executemany("""
        INSERT INTO archive_stats_time VALUES(?,?,?,?)
        ON CONFLICT(source,period) DO UPDATE SET (start_ms,working_ms)=(excluded.start_ms,excluded.working_ms)
        WHERE (start_ms,working_ms) IS NOT (excluded.start_ms,excluded.working_ms)
    """, ((source, row.period, row.start_ms, row.working_ms) for row in rows))
    db.executemany("""
        INSERT INTO archive_stats_calendar VALUES(?,?,?,?,?,?)
        ON CONFLICT(source,period) DO UPDATE SET (busiest_local_day,busiest_ms,night_ms,streak_days)=
            (excluded.busiest_local_day,excluded.busiest_ms,excluded.night_ms,excluded.streak_days)
        WHERE (busiest_local_day,busiest_ms,night_ms,streak_days) IS NOT
            (excluded.busiest_local_day,excluded.busiest_ms,excluded.night_ms,excluded.streak_days)
    """, ((source, row.period, *_values(row.calendar, 4)) for row in rows))
    db.executemany("""
        INSERT INTO archive_stats_root_time VALUES(?,?,?,?,?)
        ON CONFLICT(source,period) DO UPDATE SET (longest_root,longest_ms,peak_roots)=
            (excluded.longest_root,excluded.longest_ms,excluded.peak_roots)
        WHERE (longest_root,longest_ms,peak_roots) IS NOT (excluded.longest_root,excluded.longest_ms,excluded.peak_roots)
    """, ((source, row.period, *_values(row.roots, 3)) for row in rows))
    changed = tuple(row.period for row in rows if prior.get(row.period) != row)
    return StatsTimePublication(stamp, changed)


def time_due(db, source, zone, scopes, now_ms):
    stamp = time_stamp(db, source)
    if stamp is None:
        return True
    if stamp.as_of > now_ms:
        return False  # Do not overwrite a newer observation on UTC clock reversal.
    if stamp.zone != zone or not _current(db, source, stamp, now_ms):
        return True
    saved = dict(db.execute("""
        SELECT period,start_ms FROM archive_stats_time JOIN archive_stats_calendar USING(source,period)
             JOIN archive_stats_root_time USING(source,period) WHERE source=?
    """, (source,)))
    return saved != dict(scopes)


def read_time(db, source, zone, period, start_ms, now_ms):
    if period not in _PERIODS:
        raise ValueError("invalid_stats_period")
    stamp = time_stamp(db, source)
    if stamp is None or stamp.zone != zone or stamp.as_of > now_ms:
        return None
    version = retained_geometry_version(db, source)
    if stamp.version.archive_epoch != version.archive_epoch:
        return None
    # Look up at most one retained title using the measured leader and the
    # existing source/session primary key; no geometry replay on a rename.
    row = db.execute(f"""
        SELECT {_COLUMNS},sessions.title,sources.generation {_FROM}
        JOIN sources USING(source)
        LEFT JOIN sessions ON (sessions.source,sessions.session_id)=(sources.source,longest_root)
        WHERE sources.source=? AND period=? AND start_ms IS ?
    """, (source, period, start_ms)).fetchone()
    if row is None:
        return None
    return StatsTimeSnapshot(_decode(row[:10]), stamp,
                             version == stamp.version and _unexpired(stamp, now_ms), *row[10:])


def _decode(row):
    return StatsTimeRow(*row[:3], StatsCalendar(*row[3:7]) if row[3] is not None else None,
                        StatsRootTime(*row[7:]) if row[7] is not None else None)


def _values(value, count):
    return (None,) * count if value is None else astuple(value)


def _current(db, source, stamp, now_ms):
    return _unexpired(stamp, now_ms) and retained_geometry_version(db, source) == stamp.version


def _unexpired(stamp, now_ms):
    return stamp.next_end is None or now_ms < stamp.next_end
