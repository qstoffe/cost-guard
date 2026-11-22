"""Small durable Token Mix totals; scope reads never traverse source facts."""
from dataclasses import dataclass
from decimal import Decimal

from .display_mix_groups import record_group_marks
from .display_mix_identity import MixReferenceStamp, read_mix_reference, save_mix_reference
from .display_mix_order import MIX_GROUP_ORDER_VERSION
from .display_usage_reader import UsageVersion, retained_usage_version, usage_version


MIX_PERIODS = frozenset({"today", "7-days", "30-days", "month", "all"})
_CATEGORIES = ("input", "cache_read", "cache_write", "output")
_KINDS = (("known", "TEXT"), ("observed", "TEXT"), ("cost", "TEXT"))
_METRICS = tuple((category + "_" + name, kind) for name, kind in _KINDS for category in _CATEGORIES)


@dataclass(frozen=True, slots=True)
class MixTotalRow:
    period: str
    start_ms: int | None
    end_ms: int
    totals: tuple[int | None, ...]
    observed: tuple[int, ...]
    costs: tuple[Decimal, ...] | None
    known_volume: int | None
    prompts: int
    calls: int
    priced: int
    unqualified_forks: int
    undated_calls: int
    stale_prices: int

    def values(self):
        metrics = (*self.totals, *self.observed, *(self.costs if self.costs is not None else (None,) * 4))
        return (self.period, self.start_ms, self.end_ms, self.prompts, self.calls, self.priced,
                None if self.known_volume is None else str(self.known_volume),
                self.unqualified_forks, self.undated_calls, self.stale_prices,
                *(None if value is None else str(value) for value in metrics))


@dataclass(frozen=True, slots=True)
class MixRefresh:
    end_ms: int
    changed: bool
    grouped: bool
    reference: MixReferenceStamp | None


@dataclass(frozen=True, slots=True)
class MixPublication:
    version: UsageVersion
    end_ms: int
    changed_periods: tuple[str, ...]
    group_marks: dict[str, str]


def mix_total_schema():
    metrics = ", ".join(f"{name} {kind}" for name, kind in _METRICS)
    return f"""
        CREATE TABLE IF NOT EXISTS archive_mix_state (
            source TEXT PRIMARY KEY REFERENCES sources(source),
            archive_epoch INTEGER NOT NULL, usage_revision INTEGER NOT NULL, timezone_id TEXT NOT NULL,
            end_ms INTEGER NOT NULL, group_run TEXT
        ) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS archive_mix_totals (
            source TEXT NOT NULL REFERENCES archive_mix_state(source) ON DELETE CASCADE,
            period TEXT NOT NULL, start_ms INTEGER, end_ms INTEGER NOT NULL,
            prompts INTEGER NOT NULL, calls INTEGER NOT NULL, priced INTEGER NOT NULL,
            known_volume TEXT, unqualified_forks INTEGER NOT NULL, undated_calls INTEGER NOT NULL,
            stale_prices INTEGER NOT NULL, {metrics}, PRIMARY KEY(source,period)
        ) WITHOUT ROWID;
    """


def publish_mix_totals(db, source, expected: UsageVersion, timezone_id, rows, *, group_run=None, group_marks=None,
                       reference=None):
    if (not source or not timezone_id or len(rows) != len(MIX_PERIODS)
            or {row.period for row in rows} != MIX_PERIODS or len({row.end_ms for row in rows}) != 1):
        raise ValueError("invalid_mix_totals")
    if retained_usage_version(db, source, expected) is None:
        return None
    end_ms = rows[0].end_ms
    previous = db.execute("SELECT end_ms,timezone_id,usage_revision FROM archive_mix_state WHERE source=?",
                          (source,)).fetchone()
    if previous is not None and (previous[0] > end_ms or previous[2] > expected.revision):
        return None
    prior = {row[1]: (row[2], *row[4:]) for row in db.execute(
        "SELECT * FROM archive_mix_totals WHERE source=?", (source,))} if previous and previous[1] == timezone_id else {}
    values = tuple(row.values() for row in rows)
    # As-of clock alone is not a content change. A changed start, qualification
    # gap, prompt count or any contribution belongs to the affected period.
    changed = {row[0] for row in values if prior.get(row[0]) != (row[1], *row[3:])}
    db.execute("INSERT OR IGNORE INTO sources(source) VALUES(?)", (source,))
    db.execute("""
        INSERT INTO archive_mix_state VALUES(?,?,?,?,?,?)
        ON CONFLICT(source) DO UPDATE SET (archive_epoch,usage_revision,timezone_id,end_ms,group_run)=
            (excluded.archive_epoch,excluded.usage_revision,excluded.timezone_id,excluded.end_ms,excluded.group_run)
    """, (source, expected.archive_epoch, expected.revision, timezone_id, end_ms, group_run))
    db.execute("DELETE FROM archive_mix_totals WHERE source=?", (source,))
    marks = ",".join("?" for _ in range(11 + len(_METRICS)))
    db.executemany(f"INSERT INTO archive_mix_totals VALUES({marks})", ((source, *row) for row in values))
    if reference:
        save_mix_reference(db, source, reference)
    group_marks = group_marks or {}
    changed.update(record_group_marks(db, source, group_marks))
    return MixPublication(expected, end_ms, tuple(row[0] for row in values if row[0] in changed), group_marks)


def mix_refresh(db, source, timezone_id, now_ms):
    row = db.execute("""
        SELECT archive_epoch,usage_revision,timezone_id,end_ms,
               (SELECT digest FROM archive_mix_group_marks WHERE source=state.source AND period='all')
        FROM archive_mix_state AS state WHERE source=?
    """, (source,)).fetchone()
    if row is None:
        return None
    epoch, revision, zone, end_ms, groups = row
    changed = zone != timezone_id or UsageVersion(epoch, revision) != usage_version(db, source)
    if not changed and end_ms < now_ms:
        changed = db.execute("""
            SELECT 1 FROM archive_requests WHERE source=? AND clock_ms>? AND clock_ms<=? LIMIT 1
        """, (source, end_ms, now_ms)).fetchone() is not None
    return MixRefresh(end_ms, changed, groups is not None and groups.startswith(MIX_GROUP_ORDER_VERSION),
                      read_mix_reference(db, source))


def read_mix_total(db, source, timezone_id, period, start_ms, end_ms):
    if period not in MIX_PERIODS:
        raise ValueError("invalid_mix_period")
    row = db.execute("""
        SELECT totals.*,state.archive_epoch,state.usage_revision
        FROM archive_mix_totals AS totals JOIN archive_mix_state AS state USING(source)
        WHERE source=? AND timezone_id=? AND period=? AND start_ms IS ? AND totals.end_ms<=?
    """, (source, timezone_id, period, start_ms, end_ms)).fetchone()
    if row is None:
        return None
    _, period, start, end, prompts, calls, priced, known, forks, undated, stale = row[:11]
    totals = tuple(None if value is None else int(value) for value in row[11:15])
    observed = tuple(map(int, row[15:19]))
    costs = tuple(map(Decimal, row[19:23])) if priced else None
    result = MixTotalRow(period, start, end, totals, observed, costs, None if known is None else int(known),
                         prompts, calls, priced, forks, undated, stale)
    version = UsageVersion(*row[-2:])
    return result, version == usage_version(db, source)
