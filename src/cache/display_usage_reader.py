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
    next_key: bytes | None
    unqualified_clocks: tuple[int | None, ...]


def usage_schema():
    return """
        CREATE TABLE IF NOT EXISTS archive_usage_revisions (
            source TEXT PRIMARY KEY REFERENCES sources(source),
            revision INTEGER NOT NULL
        ) WITHOUT ROWID;
    """


def advance_usage_revision(db, source):
    db.execute("""
        INSERT INTO archive_usage_revisions VALUES(?,1)
        ON CONFLICT(source) DO UPDATE SET revision=revision+1
    """, (source,))


def usage_version(db, source):
    row = db.execute("""
        SELECT archive_epoch,coalesce(revision,0) FROM sources
        LEFT JOIN archive_usage_revisions USING(source) WHERE source=?
    """, (source,)).fetchone()
    return UsageVersion(*row) if row else UsageVersion(0, 0)


def read_usage_slice(db, source, *, expected=None, after=None):
    """Read at most one indexed key-space slice; dedup precedes period admission.

    A missing next key means this exact version is exhausted. A null result
    withdraws a stale traversal; callers must not publish its partial reduction.
    """
    version = usage_version(db, source)
    if expected is not None and expected != version:
        return None
    bounds, args = ("", (source,)) if after is None else ("AND request_key>?", (source, after))
    rows = db.execute(f"""
        SELECT request_key,clock_ms,session_id,logical_prompt_id,provider,model,recorded_model,account_key,
               input_tokens,cache_read_tokens,cache_write_tokens,output_tokens,reasoning_tokens,known_fields,
               input_cost,cache_read_cost,cache_write_cost,output_cost,pricing,
               fork_key IS NOT NULL AND dedup_tree IS NULL AS unqualified
        FROM archive_requests
        WHERE source=? {bounds} ORDER BY request_key LIMIT ?
    """, (*args, USAGE_SLICE + 1)).fetchall()
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
        if row[-1]:
            unqualified.append(row[1])
        elif row[0] in accepted:
            amounts = None if row[18] is None else tuple(Decimal(amount) for amount in row[14:18])
            entries.append(UsageInput(*row[:8], row[8:13], row[13], amounts, row[18]))
    return UsageSlice(version, tuple(entries), keys[-1] if more else None, tuple(unqualified))
