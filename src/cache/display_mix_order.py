"""Bounded seeks over staged group orderings, never a request-time sort."""
import re

from src.domain.model_identity import UNKNOWN_MODEL, UNKNOWN_PUBLISHER
from src.numbers import exact_decimal_sum

from .display_sort_keys import decimal_key, fraction_key, whole_key


MIX_GROUP_ORDER_VERSION = "v16:"
MIX_GROUP_DEFAULT = ("ccost", "desc")
MIX_GROUP_SORTS = ("publisher", "model", "prompts", "calls", "tokens", "input", "cache", "write", "output", "ccost")
_REVISION = re.compile(rf"(?:{re.escape(MIX_GROUP_ORDER_VERSION)})?[a-f0-9]{{64}}")
_PARTITION = "source,run,period,kind"
_KEY = _PARTITION + ",identity"
_TABLE = "archive_mix_group_order"


def valid_group_revision(value):
    return isinstance(value, str) and _REVISION.fullmatch(value) is not None


def group_order_schema():
    columns = ", ".join(f"{field} {kind}" for field, kind in zip(
        MIX_GROUP_SORTS, ("TEXT", "TEXT", "INTEGER", "INTEGER", "BLOB", "BLOB", "BLOB", "BLOB", "BLOB", "BLOB")))
    indexes = "\n".join(
        f"CREATE INDEX IF NOT EXISTS mix_group_order_{field} ON {_TABLE}({_PARTITION},{field},identity);"
        for field in MIX_GROUP_SORTS
    )
    return f"""
        CREATE TABLE IF NOT EXISTS {_TABLE} (
            source TEXT NOT NULL, run TEXT NOT NULL, period TEXT NOT NULL,
            kind TEXT NOT NULL, identity TEXT NOT NULL, {columns},
            PRIMARY KEY({_KEY}),
            FOREIGN KEY({_KEY}) REFERENCES archive_mix_groups({_KEY}) ON DELETE CASCADE
        ) WITHOUT ROWID;
        {indexes}
    """


def stage_group_order(db, source, run, rows):
    def values(row):
        total = sum(row.totals) if all(value is not None for value in row.totals) else 0
        shares = tuple(fraction_key(value, total) for value in row.totals) if total else (None,) * 4
        publisher = None if row.publisher == UNKNOWN_PUBLISHER else row.publisher.casefold()
        model = None if row.label == UNKNOWN_MODEL else row.label.casefold()
        return (source, run, row.period, row.kind, row.identity, publisher, model,
                row.prompts, row.calls, None if row.known_volume is None else whole_key(row.known_volume),
                *shares, None if row.costs is None else decimal_key(exact_decimal_sum(row.costs)))

    parameters = ",".join("?" for _ in range(5 + len(MIX_GROUP_SORTS)))
    db.executemany(f"INSERT INTO {_TABLE} VALUES({parameters})", map(values, rows))


def group_order_keys(db, partition, sort, direction, after, limit):
    # HTTP and internal callers use the same allowlist; no value enters SQL as
    # an identifier other than these fixed column and direction choices.
    if sort not in MIX_GROUP_SORTS or direction not in ("asc", "desc"):
        raise ValueError("invalid_mix_group_order")
    op = ">" if direction == "asc" else "<"
    where = "(source,run,period,kind)=(?,?,?,?)"
    anchor = db.execute(f"SELECT {sort} FROM {_TABLE} WHERE {where} AND identity=?",
                        (*partition, after)).fetchone() if after else None

    def seek(condition, order, args, remaining):
        return db.execute(f"""
            SELECT identity FROM {_TABLE} INDEXED BY mix_group_order_{sort}
            WHERE {where} AND {condition} ORDER BY {order} LIMIT ?
        """, (*partition, *args, remaining)).fetchall()

    keys = []
    if anchor is None or anchor[0] is not None:
        condition, args = (f"({sort},identity){op}(?,?)", (anchor[0], after)) if anchor else ("1", ())
        keys = seek(f"{sort} IS NOT NULL AND {condition}", f"{sort} {direction}, identity {direction}", args, limit)
    if len(keys) < limit:
        # Split NULLs into their own indexed suffix in both directions.
        condition, args = (f" AND identity{op}?", (after,)) if anchor == (None,) else ("", ())
        keys.extend(seek(f"{sort} IS NULL{condition}", f"identity {direction}", args, limit - len(keys)))
    return tuple(key for (key,) in keys)
