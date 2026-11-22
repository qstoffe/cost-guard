"""Bounded, revision-fenced reads for background historical reductions."""
from dataclasses import dataclass
from decimal import Decimal


USAGE_SLICE = 128


@dataclass(frozen=True, slots=True)
class UsageVersion:
    archive_epoch: int
    revision: int


@dataclass(frozen=True, slots=True)
class UsageInput:
    request_key: bytes
    clock_ms: int | None
    session_id: str
    logical_prompt_id: str | None
    provider: str
    model: str
    recorded_model: str
    account_key: bytes | None
    tokens: tuple[int, int, int, int, int]
    known: int
    category_costs: tuple[Decimal, Decimal, Decimal, Decimal] | None
    pricing: str | None


@dataclass(frozen=True, slots=True)
class UsageSlice:
    version: UsageVersion
    entries: tuple[UsageInput, ...]
    next_cursor: tuple[int, bytes] | None
    unqualified_clocks: tuple[int | None, ...]


def usage_schema():
    return """
        CREATE TABLE IF NOT EXISTS archive_usage_revisions (
            source TEXT PRIMARY KEY REFERENCES sources(source),
            revision INTEGER NOT NULL,
            invalidated_through INTEGER NOT NULL DEFAULT 0
        ) WITHOUT ROWID;
        CREATE INDEX archive_requests_revision ON archive_requests(source,first_revision,request_key);
        CREATE TRIGGER archive_usage_correction AFTER UPDATE ON archive_requests BEGIN
            INSERT INTO archive_usage_revisions(source,revision,invalidated_through) VALUES(NEW.source,0,1)
            ON CONFLICT(source) DO UPDATE SET invalidated_through=revision+1;
        END;
    """


def advance_usage_revision(db, source, *, changed_winner):
    db.execute("""
        INSERT INTO archive_usage_revisions VALUES(?,1,?)
        ON CONFLICT(source) DO UPDATE SET revision=revision+1,
            invalidated_through=CASE WHEN ? THEN revision+1 ELSE invalidated_through END
    """, (source, int(changed_winner), changed_winner))


def _usage_state(db, source):
    row = db.execute("""
        SELECT archive_epoch,coalesce(revision,0),coalesce(invalidated_through,0) FROM sources
        LEFT JOIN archive_usage_revisions USING(source) WHERE source=?
    """, (source,)).fetchone()
    return row if row else (0, 0, 0)


def usage_version(db, source):
    return UsageVersion(*_usage_state(db, source)[:2])


def retained_usage_version(db, source, expected=None):
    epoch, revision, floor = _usage_state(db, source)
    if expected is None:
        return UsageVersion(epoch, revision)
    return expected if expected.archive_epoch == epoch and floor <= expected.revision <= revision else None


def read_usage_slice(db, source, *, expected=None, after=None):
    """Read at most one indexed key-space slice; dedup precedes period admission.

    A missing cursor means this exact version is exhausted. Appends do not change
    the pinned population. Corrections, winner changes and purge invalidate it.
    """
    version = retained_usage_version(db, source, expected)
    if version is None:
        return None
    bounds = "" if after is None else "AND (first_revision,request_key)>(?,?)"
    rows = db.execute(f"""
        SELECT request_key,clock_ms,session_id,logical_prompt_id,provider,model,recorded_model,account_key,
               input_tokens,cache_read_tokens,cache_write_tokens,output_tokens,reasoning_tokens,known_fields,
               input_cost,cache_read_cost,cache_write_cost,output_cost,pricing,
               fork_key IS NOT NULL AND dedup_tree IS NULL AS unqualified,first_revision
        FROM archive_requests
        WHERE source=? AND first_revision<=? {bounds} ORDER BY first_revision,request_key LIMIT ?
    """, (source, version.revision, *(after or ()), USAGE_SLICE + 1)).fetchall()
    more = len(rows) > USAGE_SLICE
    rows = rows[:USAGE_SLICE]
    keys = tuple(row[0] for row in rows)
    if not keys:
        return UsageSlice(version, (), None, ())
    marks = ",".join("?" for _ in keys)
    accepted = {key for key, in db.execute(f"""
        SELECT request_key FROM archive_countable_requests WHERE source=? AND request_key IN ({marks})
    """, (source, *keys))}
    entries, unqualified = [], []
    for row in rows:
        if row[-2]:
            unqualified.append(row[1])
        elif row[0] in accepted:
            amounts = None if row[18] is None else tuple(Decimal(amount) for amount in row[14:18])
            entries.append(UsageInput(*row[:8], row[8:13], row[13], amounts, row[18]))
    return UsageSlice(version, tuple(entries), (rows[-1][-1], keys[-1]) if more else None, tuple(unqualified))
