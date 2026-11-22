"""Indexed slices of the shared physical archive for Accounts history."""
from dataclasses import dataclass
from decimal import Decimal

from .display_usage_reader import USAGE_SLICE, UsageVersion, retained_usage_version


@dataclass(frozen=True, slots=True)
class AccountUsage:
    clock_ms: int
    provider: str
    account_key: bytes | None
    disposition: str
    known: int
    pricing: str | None
    costs: tuple[Decimal, ...]


@dataclass(frozen=True, slots=True)
class AccountUsageSlice:
    version: UsageVersion
    rows: tuple[AccountUsage, ...]
    after: tuple[int, bytes] | None
    ambiguous_clocks: tuple[int, ...]


def account_usage_slice(db, source, start, end, *, version=None, after=None):
    """Pin candidates; apply global clone eligibility before account/window aggregation."""
    pinned = retained_usage_version(db, source, version)
    if pinned is None:
        return None
    cursor = "AND (clock_ms, request_key)>(?,?)" if after is not None else ""
    rows = db.execute(f"""
        SELECT request_key,clock_ms,provider,account_key,disposition,known_fields,pricing,
            input_cost,cache_read_cost,cache_write_cost,output_cost,
            fork_key IS NOT NULL AND dedup_tree IS NULL, first_revision
        FROM archive_requests
        WHERE source=? AND clock_ms>=? AND clock_ms<? {cursor}
        ORDER BY clock_ms,request_key LIMIT ?
    """, (source, start, end, *(after or ()), USAGE_SLICE + 1)).fetchall()
    more = len(rows) > USAGE_SLICE
    rows = rows[:USAGE_SLICE]
    keys = tuple(row[0] for row in rows)
    if not keys:
        return AccountUsageSlice(pinned, (), None, ())
    pinned_rows = tuple(row for row in rows if row[-1] <= pinned.revision)
    candidates = tuple(row[0] for row in pinned_rows if not row[-2])
    marks = ",".join("?" for _ in candidates)
    accepted = {key for key, in db.execute(f"""
        SELECT request_key FROM archive_countable_requests WHERE source=? AND request_key IN ({marks})
    """, (source, *candidates))} if candidates else set()
    scoped = tuple(AccountUsage(*row[1:7], tuple(Decimal(value) for value in row[7:11]) if row[6] else ())
                   for row in pinned_rows if row[0] in accepted)
    ambiguous = tuple(row[1] for row in pinned_rows if row[-2])
    tail = (rows[-1][1], keys[-1]) if more else None
    return AccountUsageSlice(pinned, scoped, tail, ambiguous)
