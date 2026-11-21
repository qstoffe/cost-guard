"""Typed model/publisher groups, invisible until a compatible build commits."""
from dataclasses import dataclass
from decimal import Decimal


GROUP_BATCH = 32
GROUP_PAGE = 25
_CATEGORIES = ("input", "cache", "write", "output")
_METRICS = tuple(f"{prefix}_{name}" for prefix in ("tokens", "cost") for name in _CATEGORIES)


@dataclass(frozen=True, slots=True)
class MixGroupRow:
    period: str
    kind: str
    identity: str
    label: str
    publisher: str
    prompts: int
    calls: int
    priced: int
    known_volume: int | None
    totals: tuple[int | None, ...]
    costs: tuple[Decimal, ...] | None

    def values(self):
        scalars = (self.period, self.kind, self.identity, self.label, self.publisher, self.prompts, self.calls,
                   self.priced, None if self.known_volume is None else str(self.known_volume))
        values = (*self.totals, *(self.costs if self.costs is not None else (None,) * 4))
        return (*scalars, *(None if value is None else str(value) for value in values))


def mix_groups_schema(*, add_run=False):
    metrics = ", ".join(f"{column} TEXT" for column in _METRICS)
    column = "ALTER TABLE archive_mix_state ADD COLUMN group_run TEXT;" if add_run else ""
    return f"""
        {column}
        CREATE TABLE IF NOT EXISTS archive_mix_groups (
            source TEXT NOT NULL REFERENCES sources(source), run TEXT NOT NULL,
            period TEXT NOT NULL, kind TEXT NOT NULL, identity TEXT NOT NULL,
            label TEXT NOT NULL, publisher TEXT NOT NULL, prompts INTEGER NOT NULL, calls INTEGER NOT NULL,
            priced INTEGER NOT NULL, known_volume TEXT, {metrics},
            PRIMARY KEY(source,run,period,kind,identity)
        ) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS archive_mix_group_marks (
            source TEXT NOT NULL REFERENCES archive_mix_state(source) ON DELETE CASCADE,
            period TEXT NOT NULL, digest TEXT NOT NULL, PRIMARY KEY(source,period)
        ) WITHOUT ROWID;
    """


def stage_groups(db, source, run, rows):
    if not source or not run or not 0 < len(rows) <= GROUP_BATCH:
        raise ValueError("invalid_archive_mix_group_batch")
    db.execute("INSERT OR IGNORE INTO sources(source) VALUES(?)", (source,))
    marks = ",".join("?" for _ in range(11 + len(_METRICS)))
    db.executemany(f"INSERT INTO archive_mix_groups VALUES({marks})", ((source, run, *row.values()) for row in rows))


def inactive_run(db, source):
    active = db.execute("SELECT group_run FROM archive_mix_state WHERE source=?", (source,)).fetchone()
    active = active[0] if active else None
    def edge(direction):
        return db.execute(f"SELECT run FROM archive_mix_groups WHERE source=? ORDER BY run {direction} LIMIT 1",
                          (source,)).fetchone()
    first = edge("ASC")
    if first is not None and first[0] != active:
        return first[0]
    last = edge("DESC") if first else None
    return last[0] if last is not None and last[0] != active else None


def remove_inactive_groups(db, source, run):
    """Maintenance never visits current or in-flight group rows."""
    return db.execute("""
        DELETE FROM archive_mix_groups WHERE (source,run,period,kind,identity) IN (
            SELECT source,run,period,kind,identity FROM archive_mix_groups AS groups
            WHERE source=? AND run=? AND run IS NOT
              (SELECT group_run FROM archive_mix_state WHERE source=groups.source)
            LIMIT ?
        )
    """, (source, run, GROUP_BATCH)).rowcount


def record_group_marks(db, source, marks):
    previous = dict(db.execute("SELECT period,digest FROM archive_mix_group_marks WHERE source=?", (source,)))
    db.execute("DELETE FROM archive_mix_group_marks WHERE source=?", (source,))
    db.executemany("INSERT INTO archive_mix_group_marks VALUES(?,?,?)",
                   ((source, period, stamp) for period, stamp in marks.items()))
    return {period for period in previous.keys() | marks.keys() if previous.get(period) != marks.get(period)}


def read_groups(db, source, run, period, kind, after):
    rows = db.execute("""
        SELECT period,kind,identity,label,publisher,prompts,calls,priced,known_volume,
               """ + ",".join(_METRICS) + """
        FROM archive_mix_groups WHERE source=? AND run=? AND period=? AND kind=? AND identity>?
        ORDER BY identity LIMIT ?
    """, (source, run, period, kind, after, GROUP_PAGE + 1)).fetchall()
    values = tuple(MixGroupRow(*row[:8], None if row[8] is None else int(row[8]),
                   tuple(None if value is None else int(value) for value in row[9:13]),
                   tuple(map(Decimal, row[13:17])) if row[7] else None) for row in rows[:GROUP_PAGE])
    return values, values[-1].identity if len(rows) > GROUP_PAGE else None
