"""Atomically committed cached Stats token subtotals, separate from time."""
from dataclasses import dataclass

from .display_stats_revision import StatsVersion, retained_stats_version
from .display_usage_reader import UsageVersion

_PERIODS = frozenset({"today", "7-days", "30-days", "month", "all"})


@dataclass(frozen=True, slots=True)
class StatsTokenStamp:
    version: StatsVersion
    zone: str
    as_of: int
    next_completion: int | None


@dataclass(frozen=True, slots=True)
class StatsTokenRow:
    period: str
    start_ms: int | None
    observed: int | None
    requests: int
    usage_gaps: bool
    population_gaps: bool


@dataclass(frozen=True, slots=True)
class StatsTokenPublication:
    stamp: StatsTokenStamp
    changed_periods: tuple[str, ...]


def stats_token_schema():
    return """
        CREATE TABLE IF NOT EXISTS archive_stats_token_state (
            source TEXT PRIMARY KEY REFERENCES sources(source), archive_epoch INTEGER NOT NULL,
            usage_revision INTEGER NOT NULL, evidence_revision INTEGER NOT NULL,
            zone TEXT NOT NULL, as_of INTEGER NOT NULL, next_completion INTEGER
        ) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS archive_stats_tokens (
            source TEXT NOT NULL REFERENCES archive_stats_token_state(source) ON DELETE CASCADE,
            period TEXT NOT NULL, start_ms INTEGER, observed TEXT, requests INTEGER NOT NULL,
            usage_gaps INTEGER NOT NULL, population_gaps INTEGER NOT NULL,
            PRIMARY KEY(source,period)
        ) WITHOUT ROWID;
    """


def _stamp(db, source):
    row = db.execute("""
        SELECT archive_epoch,usage_revision,evidence_revision,zone,as_of,next_completion
        FROM archive_stats_token_state WHERE source=?
    """, (source,)).fetchone()
    return StatsTokenStamp(StatsVersion(UsageVersion(*row[:2]), row[2]), *row[3:]) if row else None


def _decode(row):
    period, start, observed, calls, usage_gaps, population_gaps = row
    return StatsTokenRow(period, start, int(observed) if observed is not None else None, calls,
                         bool(usage_gaps), bool(population_gaps))


_ROWS = """SELECT period,start_ms,observed,requests,usage_gaps,population_gaps
           FROM archive_stats_tokens WHERE source=?"""


def commit_tokens(db, source, stamp, rows):
    if (not source or not stamp.zone or stamp.as_of <= 0
            or stamp.next_completion is not None and stamp.next_completion <= stamp.as_of
            or len(rows) != len(_PERIODS) or {row.period for row in rows} != _PERIODS):
        raise ValueError("invalid_stats_token_publication")
    for row in rows:
        if ((row.start_ms is None) != (row.period == "all")
                or row.start_ms is not None and row.start_ms > stamp.as_of or row.requests < 0
                or row.observed is not None and (row.requests <= 0 or row.observed < 0 or row.population_gaps)):
            raise ValueError("invalid_stats_token_row")

    if retained_stats_version(db, source, stamp.version) is None:
        return None
    previous = _stamp(db, source)
    prior = {}
    if previous and stamp.version.usage.archive_epoch == previous.version.usage.archive_epoch:
        if (stamp.as_of < previous.as_of or stamp.version.usage.revision < previous.version.usage.revision
                or stamp.version.evidence < previous.version.evidence):
            return None
        if stamp.zone == previous.zone:
            prior = {record[0]: _decode(record) for record in db.execute(_ROWS, (source,))}
    db.execute("INSERT OR IGNORE INTO sources(source) VALUES(?)", (source,))
    db.execute("""
        INSERT INTO archive_stats_token_state VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(source) DO UPDATE SET (archive_epoch,usage_revision,evidence_revision,zone,as_of,next_completion) =
            (excluded.archive_epoch,excluded.usage_revision,excluded.evidence_revision,excluded.zone,
             excluded.as_of,excluded.next_completion)
    """, (source, stamp.version.usage.archive_epoch, stamp.version.usage.revision, stamp.version.evidence,
          stamp.zone, stamp.as_of, stamp.next_completion))
    db.executemany("""
        INSERT INTO archive_stats_tokens VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(source,period) DO UPDATE SET (start_ms,observed,requests,usage_gaps,population_gaps) =
            (excluded.start_ms,excluded.observed,excluded.requests,excluded.usage_gaps,excluded.population_gaps)
        WHERE (start_ms,observed,requests,usage_gaps,population_gaps)
            IS NOT (excluded.start_ms,excluded.observed,excluded.requests,excluded.usage_gaps,excluded.population_gaps)
    """, ((source, row.period, row.start_ms, str(row.observed) if row.observed is not None else None,
           row.requests, row.usage_gaps, row.population_gaps) for row in rows))
    return StatsTokenPublication(stamp, tuple(row.period for row in rows if prior.get(row.period) != row))


def tokens_due(db, source, zone, scopes, now_ms):
    stamp = _stamp(db, source)
    if stamp is None:
        return db.execute("SELECT 1 FROM archive_requests WHERE source=? LIMIT 1", (source,)).fetchone() is not None
    if stamp.as_of > now_ms:
        return False
    if (stamp.zone != zone or stamp.version != retained_stats_version(db, source)
            or stamp.next_completion is not None and stamp.next_completion <= now_ms):
        return True
    saved = dict(db.execute("SELECT period,start_ms FROM archive_stats_tokens WHERE source=?", (source,)))
    return saved != dict(scopes)


def read_tokens(db, source, epoch, zone, period, start_ms, now_ms):
    if period not in _PERIODS:
        raise ValueError("invalid_stats_period")
    stamp = _stamp(db, source)
    if stamp is None or stamp.version.usage.archive_epoch != epoch or stamp.zone != zone or stamp.as_of > now_ms:
        return None
    row = db.execute(_ROWS + " AND period=? AND start_ms IS ?", (source, period, start_ms)).fetchone()
    return (_decode(row), stamp.as_of) if row else None
