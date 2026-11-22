"""Ordered reads over one prepared request slot, not live publication."""
from dataclasses import dataclass
from heapq import merge

from .display_requests import REQUEST_COLUMNS
from .display_usage_reader import USAGE_SLICE, UsageVersion, retained_usage_version, usage_version


_BASE_COLUMNS = ",".join(f"r.{column}" for column in REQUEST_COLUMNS)


@dataclass(frozen=True, slots=True)
class RequestSlot:
    attempt: str
    birth: int
    layout: int = 0  # Changes if a fold moves physical candidates between arms.


@dataclass(frozen=True, slots=True)
class ClockCursor:
    source: str
    start: int
    end: int
    version: UsageVersion
    slot: RequestSlot | None
    scanned_through: tuple[int, bytes]


@dataclass(frozen=True, slots=True)
class ClockSlice:
    rows: tuple[tuple, ...]  # REQUEST_COLUMNS, then first_revision
    next_cursor: ClockCursor | None


@dataclass(frozen=True, slots=True)
class BirthCursor:
    source: str
    through: int
    version: UsageVersion
    slot: RequestSlot | None
    scanned_through: tuple[int, bytes]


@dataclass(frozen=True, slots=True)
class BirthSlice:
    rows: tuple[tuple, ...]
    next_cursor: BirthCursor | None


def countable_request_rows(db, source, rows, *, slot=None):
    """Filter one effective page using global fork winners, never page counts."""
    _require_pinned(db, max(1, len(rows)))
    winners = {}
    accepted = []
    for row in rows:
        fork = row[2]
        if fork is None:
            accepted.append(row)
            continue
        tree = row[-3]
        if tree is None:
            continue
        if fork not in winners:
            winners[fork] = _winner(db, source, slot, fork)
        if tree == winners[fork]:
            accepted.append(row)
    return tuple(accepted)


def _winner(db, source, slot, fork):
    if slot is not None:
        row = db.execute("""
            SELECT winner FROM archive_prepare_winners WHERE attempt=? AND fork_key=? AND done
        """, (slot.attempt, fork)).fetchone()
        if row is not None:
            return row[0]
    row = db.execute("""
        SELECT dedup_tree FROM archive_fork_trees INDEXED BY archive_fork_rank
        WHERE source=? AND fork_key=?
        ORDER BY multiplicity DESC,first_ordinal,first_session,dedup_tree LIMIT 1
    """, (source, fork)).fetchone()
    return row[0] if row else None


def request_clock_slice(db, source, start, end, *, slot=None, cursor=None, limit=USAGE_SLICE):
    """Return one bounded half-open window slice, or None for a stale cursor.

    The caller supplies the committed slot read within this same transaction.
    A non-null cursor means more raw candidates, even when rows is empty.
    """
    _require_pinned(db, limit)
    if start >= end:
        raise ValueError("invalid_request_clock_slice")
    version = usage_version(db, source)
    after = cursor.scanned_through if cursor is not None else None
    if cursor is not None and cursor != ClockCursor(source, start, end, version, slot, after):
        return None

    base_query, base_args = _base_arm(source, slot, "archive_request_clock")
    base = _arm(db, base_query, base_args, "clock_ms", start, end - 1, after, limit + 1)
    overlay = _arm(db, f"""
            SELECT {_BASE_COLUMNS},coalesce(r.first_revision,?),0
            FROM archive_prepare_requests r INDEXED BY archive_prepare_clock WHERE r.source=?
        """, (slot.birth, slot.attempt), "clock_ms", start, end - 1, after, limit + 1) if slot else []
    rows, frontier = _merge_arms((base, overlay), _clock_position, limit)
    next_cursor = ClockCursor(source, start, end, version, slot, frontier) if frontier is not None else None
    return ClockSlice(rows, next_cursor)


def request_birth_slice(db, source, through, *, slot=None, cursor=None, limit=USAGE_SLICE):
    """Scan by birth revision and key under the matching retained usage fence."""
    _require_pinned(db, limit)
    version = usage_version(db, source)
    if slot is None or version.revision == slot.birth:
        if retained_usage_version(db, source, UsageVersion(version.archive_epoch, through)) is None:
            return None
    elif through != slot.birth:
        # A fixture-only manifest without a published usage fence proves head only.
        return None
    after = cursor.scanned_through if cursor is not None else None
    if cursor is not None and cursor != BirthCursor(source, through, version, slot, after):
        return None

    base_query, base_args = _base_arm(source, slot, "archive_requests_revision")
    base = _arm(db, base_query, base_args, "first_revision", 0, through, after, limit + 1)
    corrected, inserted = [], []
    if slot is not None:
        corrected = _arm(db, f"""
            SELECT {_BASE_COLUMNS},r.first_revision,0 FROM archive_prepare_requests r INDEXED BY archive_prepare_birth
            WHERE r.source=? AND r.first_revision IS NOT NULL
        """, (slot.attempt,), "first_revision", 0, through, after, limit + 1)
        if slot.birth <= through and (after is None or after[0] <= slot.birth):
            tail = (after[1],) if after is not None and after[0] == slot.birth else ()
            seek = "AND r.request_key>?" if tail else ""
            inserted = db.execute(f"""
                SELECT {_BASE_COLUMNS},?,0 FROM archive_prepare_requests r INDEXED BY archive_prepare_birth
                WHERE r.source=? AND r.first_revision IS NULL {seek}
                ORDER BY r.request_key LIMIT ?
            """, (slot.birth, slot.attempt, *tail, limit + 1)).fetchall()
    rows, frontier = _merge_arms((base, corrected, inserted), _birth_position, limit)
    next_cursor = BirthCursor(source, through, version, slot, frontier) if frontier is not None else None
    return BirthSlice(rows, next_cursor)


def _require_pinned(db, limit):
    if not db.in_transaction:
        raise ValueError("request overlay reads require a pinned transaction")
    if not 1 <= limit <= USAGE_SLICE:
        raise ValueError("invalid_request_slice_limit")


def _base_arm(source, slot, index):
    seek = f"FROM archive_requests r INDEXED BY {index} WHERE r.source=?"
    if slot is None:
        return f"SELECT {_BASE_COLUMNS},r.first_revision,0 {seek}", (source,)
    return f"""
        SELECT {_BASE_COLUMNS},r.first_revision,EXISTS(
            SELECT 1 FROM archive_prepare_requests p WHERE p.source=? AND p.request_key=r.request_key)
        {seek}
    """, (slot.attempt, source)


def _merge_arms(arms, position, limit):
    # Advance no further than both arms have proven. An uncertain arm's last
    # scanned key bounds what can be emitted, independently of shadow density.
    frontier = min((position(arm[limit - 1]) for arm in arms if len(arm) > limit), default=None)
    rows = []
    for row in merge(*(arm[:limit] for arm in arms), key=position):
        if frontier is not None and position(row) > frontier:
            break
        if not row[-1]:
            if len(rows) == limit:
                frontier = position(rows[-1])
                break
            rows.append(row[:-1])
    return tuple(rows), frontier


def _clock_position(row):
    return row[1], row[0]


def _birth_position(row):
    return row[len(REQUEST_COLUMNS)], row[0]


def _arm(db, query, keys, column, start, end, after, count):
    order = f"ORDER BY r.{column},r.request_key LIMIT ?"
    if after is None:
        return db.execute(f"{query} AND r.{column}>=? AND r.{column}<=? {order}",
                          (*keys, start, end, count)).fetchall()
    lower, key = after
    rows = db.execute(f"{query} AND r.{column}=? AND r.request_key>? {order}",
                      (*keys, lower, key, count)).fetchall()
    if len(rows) < count:
        rows.extend(db.execute(f"{query} AND r.{column}>? AND r.{column}<=? {order}",
                               (*keys, lower, end, count - len(rows))).fetchall())
    return rows
