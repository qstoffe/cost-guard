"""Atomically committed cached request subtotals, separate from time."""
from dataclasses import dataclass
from decimal import Decimal

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
    reference_ccost: Decimal | None = None
    priced: int = 0
    mixed_prices: bool = False
    subagent_reference_ccost: Decimal | None = None


@dataclass(frozen=True, slots=True)
class StatsTokenPublication:
    stamp: StatsTokenStamp
    changed_periods: tuple[str, ...]


def stats_token_schema(*, upgrade=False, add_subagent_cost=False):
    subagent_upgrade = """
        ALTER TABLE archive_stats_tokens ADD COLUMN subagent_reference_ccost TEXT;
        UPDATE archive_stats_token_state SET evidence_revision=-1;
    """ if add_subagent_cost else ""
    if upgrade:
        return subagent_upgrade + """
            ALTER TABLE archive_stats_tokens ADD COLUMN reference_ccost TEXT;
            ALTER TABLE archive_stats_tokens ADD COLUMN priced INTEGER NOT NULL DEFAULT 0;
            ALTER TABLE archive_stats_tokens ADD COLUMN mixed_prices INTEGER NOT NULL DEFAULT 0;
            UPDATE archive_stats_token_state SET evidence_revision=-1;
        """
    return subagent_upgrade + """
        CREATE TABLE IF NOT EXISTS archive_stats_token_state (
            source TEXT PRIMARY KEY REFERENCES sources(source), archive_epoch INTEGER NOT NULL,
            usage_revision INTEGER NOT NULL, evidence_revision INTEGER NOT NULL,
            zone TEXT NOT NULL, as_of INTEGER NOT NULL, next_completion INTEGER
        ) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS archive_stats_tokens (
            source TEXT NOT NULL REFERENCES archive_stats_token_state(source) ON DELETE CASCADE,
            period TEXT NOT NULL, start_ms INTEGER, observed TEXT, requests INTEGER NOT NULL,
            usage_gaps INTEGER NOT NULL, population_gaps INTEGER NOT NULL,
            reference_ccost TEXT, priced INTEGER NOT NULL, mixed_prices INTEGER NOT NULL,
            subagent_reference_ccost TEXT,
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
    period, start, observed, calls, usage_gaps, population_gaps, cost, priced, mixed_prices, subagent_cost = row
    return StatsTokenRow(period, start, int(observed) if observed is not None else None, calls,
                         bool(usage_gaps), bool(population_gaps), Decimal(cost) if cost is not None else None,
                         priced, bool(mixed_prices), Decimal(subagent_cost) if subagent_cost is not None else None)


_ROWS = """SELECT period,start_ms,observed,requests,usage_gaps,population_gaps,reference_ccost,priced,mixed_prices,
                 subagent_reference_ccost
           FROM archive_stats_tokens WHERE source=?"""


def commit_tokens(db, source, stamp, rows):
    if (not source or not stamp.zone or stamp.as_of <= 0
            or stamp.next_completion is not None and stamp.next_completion <= stamp.as_of
            or len(rows) != len(_PERIODS) or {row.period for row in rows} != _PERIODS):
        raise ValueError("invalid_stats_token_publication")
    for row in rows:
        subagent = row.subagent_reference_ccost
        if ((row.start_ms is None) != (row.period == "all")
                or row.start_ms is not None and row.start_ms > stamp.as_of or row.requests < 0
                or row.observed is not None and (row.requests <= 0 or row.observed < 0 or row.population_gaps)
                or not 0 <= row.priced <= row.requests
                or row.reference_ccost is not None and (row.population_gaps or row.mixed_prices or not row.priced
                        or not row.reference_ccost.is_finite() or row.reference_ccost < 0)
                or subagent is not None and (row.population_gaps or not row.priced
                                             or not subagent.is_finite() or subagent < 0)):
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
        INSERT INTO archive_stats_tokens
            (source,period,start_ms,observed,requests,usage_gaps,population_gaps,reference_ccost,priced,mixed_prices,
             subagent_reference_ccost) VALUES(?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(source,period) DO UPDATE SET
            start_ms=excluded.start_ms,observed=excluded.observed,requests=excluded.requests,
            usage_gaps=excluded.usage_gaps,population_gaps=excluded.population_gaps,
            reference_ccost=excluded.reference_ccost,priced=excluded.priced,mixed_prices=excluded.mixed_prices,
            subagent_reference_ccost=excluded.subagent_reference_ccost
        WHERE (start_ms,observed,requests,usage_gaps,population_gaps,reference_ccost,priced,mixed_prices,
               subagent_reference_ccost)
             IS NOT (excluded.start_ms,excluded.observed,excluded.requests,excluded.usage_gaps,excluded.population_gaps,
                     excluded.reference_ccost,excluded.priced,excluded.mixed_prices,excluded.subagent_reference_ccost)
    """, ((source, row.period, row.start_ms, str(row.observed) if row.observed is not None else None,
           row.requests, row.usage_gaps, row.population_gaps,
            str(row.reference_ccost) if row.reference_ccost is not None else None, row.priced, row.mixed_prices,
            str(row.subagent_reference_ccost) if row.subagent_reference_ccost is not None else None)
          for row in rows))
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
