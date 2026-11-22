"""Typed, source- and account-bound snapshots of observed reference costs."""
from dataclasses import dataclass
from decimal import Decimal

from .display_usage_reader import UsageVersion, retained_usage_version, usage_version


ACCOUNT_BATCH = 32
ACCOUNT_LIMIT = 32
ACCOUNT_MAX_BUCKETS = 32  # Max local dates or transition-split Today slots.
ACCOUNT_PERIODS = frozenset({"today", "7-days", "30-days", "month"})
ACCOUNT_MAX_ROWS = ACCOUNT_LIMIT * ACCOUNT_MAX_BUCKETS * len(ACCOUNT_PERIODS)


@dataclass(frozen=True, slots=True)
class AccountBucket:
    period: str
    account: bytes
    start: int
    end: int
    subtotal: Decimal | None
    matched: int
    priced: int
    pricing: str | None


@dataclass(frozen=True, slots=True)
class AccountRun:
    run: str
    version: UsageVersion
    zone: str
    roster: str
    end: int
    count: int


def account_schema():
    return """
        CREATE TABLE IF NOT EXISTS display_account_state (
            source TEXT NOT NULL PRIMARY KEY REFERENCES sources(source),
            run TEXT NOT NULL, archive_epoch INTEGER NOT NULL, usage_revision INTEGER NOT NULL,
            zone TEXT NOT NULL, roster TEXT NOT NULL, end_ms INTEGER NOT NULL
        ) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS display_account_buckets (
            source TEXT NOT NULL REFERENCES sources(source),
            run TEXT NOT NULL, period TEXT NOT NULL, account BLOB NOT NULL,
            start_ms INTEGER NOT NULL, end_ms INTEGER NOT NULL,
            subtotal TEXT, matched INTEGER NOT NULL, priced INTEGER NOT NULL, pricing TEXT,
            PRIMARY KEY(source,run,period,account,start_ms)
        ) WITHOUT ROWID;
    """


def stage_accounts(db, source, version, run, rows):
    if not 0 < len(rows) <= ACCOUNT_BATCH:
        raise ValueError("invalid_account_batch")
    if retained_usage_version(db, source, version) is None or db.execute(
            "SELECT 1 FROM display_account_state WHERE source=? AND run=?", (source, run)).fetchone():
        return False
    db.execute("INSERT OR IGNORE INTO sources(source) VALUES(?)", (source,))
    db.executemany("INSERT INTO display_account_buckets VALUES(?,?,?,?,?,?,?,?,?,?)",
        ((source, run, row.period, row.account, row.start, row.end,
          str(row.subtotal) if row.subtotal is not None else None, row.matched, row.priced, row.pricing)
         for row in rows))
    return True


def publish_account_run(db, source, stamp):
    if not 0 <= stamp.count <= ACCOUNT_MAX_ROWS:
        raise ValueError("invalid_account_row_count")
    if retained_usage_version(db, source, stamp.version) is None:
        return False
    previous = db.execute("SELECT end_ms,usage_revision FROM display_account_state WHERE source=?",
                          (source,)).fetchone()
    if previous and (previous[0] > stamp.end or previous[1] > stamp.version.revision):
        return False
    count = db.execute("SELECT count(*) FROM display_account_buckets WHERE source=? AND run=?",
                       (source, stamp.run)).fetchone()[0]
    if count != stamp.count:
        return False
    db.execute("INSERT OR IGNORE INTO sources(source) VALUES(?)", (source,))
    db.execute("""
        INSERT INTO display_account_state VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(source) DO UPDATE SET (run,archive_epoch,usage_revision,zone,roster,end_ms)=
            (excluded.run,excluded.archive_epoch,excluded.usage_revision,excluded.zone,excluded.roster,excluded.end_ms)
    """, (source, stamp.run, stamp.version.archive_epoch, stamp.version.revision, stamp.zone, stamp.roster, stamp.end))
    return True


def account_buckets(db, source, zone, roster, period, account, start, end):
    if period not in ACCOUNT_PERIODS or type(account) is not bytes or len(account) != 32:
        raise ValueError("invalid_account_query")
    state = db.execute("""
        SELECT run,archive_epoch,usage_revision,end_ms FROM display_account_state
        WHERE source=? AND zone=? AND roster=? AND end_ms<=?
    """, (source, zone, roster, end)).fetchone()
    if state is None:
        return None
    run, epoch, revision, as_of = state
    # Forwards window shifts cannot pick up prior out-of-window evidence.
    # A rolling cut through a saved bucket is withheld, not prorated.
    rows = tuple(AccountBucket(period, account, left, right, Decimal(value) if value is not None else None,
                               matched, priced, pricing)
                 for left, right, value, matched, priced, pricing in db.execute("""
        SELECT start_ms,end_ms,subtotal,matched,priced,pricing FROM display_account_buckets
        WHERE source=? AND run=? AND period=? AND account=? AND start_ms>=?
        ORDER BY start_ms LIMIT ?
    """, (source, run, period, account, start, ACCOUNT_MAX_BUCKETS)))
    return UsageVersion(epoch, revision), as_of, rows


def account_history_due(db, source, zone, roster, now_ms, earliest):
    state = db.execute("""
        SELECT archive_epoch,usage_revision,zone,roster,end_ms FROM display_account_state WHERE source=?
    """, (source,)).fetchone()
    if state is None:
        return True
    epoch, revision, saved_zone, saved_roster, published = state
    if not 0 <= published <= now_ms or zone != saved_zone or roster != saved_roster:
        return True
    if UsageVersion(epoch, revision) != usage_version(db, source):
        return True
    if published < earliest:
        return True
    return db.execute("""
        SELECT 1 FROM archive_requests WHERE source=? AND clock_ms>=? AND clock_ms<? LIMIT 1
    """, (source, published, now_ms)).fetchone() is not None


def cleanup_accounts(db, source, protected_run=None):
    active = db.execute("SELECT run FROM display_account_state WHERE source=?", (source,)).fetchone()
    excluded = (active[0] if active else "", protected_run or "")
    obsolete = db.execute("""
        SELECT run FROM display_account_buckets WHERE source=? AND run NOT IN (?,?) ORDER BY run LIMIT 1
    """, (source, *excluded)).fetchone()
    if obsolete is None:
        return 0
    return db.execute("""
        DELETE FROM display_account_buckets WHERE (source,run,period,account,start_ms) IN (
            SELECT source,run,period,account,start_ms FROM display_account_buckets
            WHERE source=? AND run=? LIMIT ?
        )
    """, (source, obsolete[0], ACCOUNT_BATCH)).rowcount
