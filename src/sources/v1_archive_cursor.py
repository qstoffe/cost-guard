"""Tentative, keyset-paged V1 facts from one owned SQLite read snapshot."""
from dataclasses import dataclass
import sqlite3
from time import monotonic

from src.domain import NormalizedMessage, NormalizedPart, NormalizedSession

from .errors import SourceConcurrentChangeError, SourceDataError, SourceSchemaError
from .v1_archive_revision import MemberRevision


PAGE_ROWS = 128
PAGE_BYTES = 1024 * 1024
PIN_SECONDS = 30
MAX_DEPTH = 128
_REVISION_ID = "CAST(id AS BLOB) AS revision_id"  # Match BINARY order in the source database encoding.
_TABLES = (
    ("session", "parent_id", f"id,parent_id,project_id,title,time_created,time_updated,time_archived,{_REVISION_ID}"),
    ("message", "session_id", f"id,session_id,time_created,time_updated,{_REVISION_ID}"),
    ("part", "session_id", f"id,message_id,session_id,time_created,time_updated,{_REVISION_ID}"),
)
_KEYS = (("id",), ("time_created", "id"), ("rowid",))
_DATA_COLUMNS = ("rowid", "typeof(data)")


@dataclass(frozen=True, slots=True)
class V1ArchivePage:
    sessions: tuple[NormalizedSession, ...] = ()
    messages: tuple[NormalizedMessage, ...] = ()  # Parts arrive separately, keyed by message ID.
    parts: tuple[NormalizedPart, ...] = ()
    eof: bool = False
    revision_member: tuple[bytes, bytes] | None = None
    # Canonical tie-break for equal-ranked tool observations, independent of
    # this cursor's seek order and the staging database's encoding.
    message_order: tuple[tuple[int, bytes], ...] = ()
    part_order: tuple[bytes, ...] = ()


def _identifier(value):
    return '"' + value.replace('"', '""') + '"'


def _indexes(db, table):
    for row in db.execute(f"PRAGMA index_list({table})"):
        if not row["partial"]:
            name = _identifier(row["name"])
            yield name, row["unique"], tuple(db.execute(f"PRAGMA index_xinfo({name})"))


def _unique_id_index(db, indexes, table):
    for name, unique, columns in indexes:
        key = [(col["name"], col["coll"]) for col in columns if col["key"]]
        if unique and key == [("id", "BINARY")]:
            plan = tuple(row["detail"] for row in db.execute(
                f"EXPLAIN QUERY PLAN SELECT id FROM {table} INDEXED BY {name} ORDER BY id LIMIT 1"))
            if len(plan) == 1 and plan[0].startswith("SCAN "):
                # ORDER BY id must use the same BINARY ordering as the index;
                # otherwise the legacy MAX(id) need not match our captured max.
                return name
    raise SourceSchemaError(f"OpenCode V1 lacks a unique archive identity for {table}", phase="archive")


@dataclass(frozen=True, slots=True)
class _Seek:
    first: str
    resume: str
    keys: tuple[str, ...]

    @classmethod
    def find(cls, db, indexes, table, owner, fields, limit):
        # Only indexes with a native seek and native ordering qualify. Names
        # vary by OpenCode build; neither creating an index nor scanning is OK.
        for name, _, columns in indexes:
            for keys in _KEYS:
                prefix = columns[:len(keys) + 1]
                names = tuple("rowid" if item["cid"] == -1 else item["name"] for item in prefix)
                if names != (owner, *keys) or any(item["desc"] or item["coll"] != "BINARY" for item in prefix):
                    continue
                plan = cls._for_index(name, table, owner, fields, keys)
                if plan._qualifies(db, owner, limit):
                    return plan
        raise SourceSchemaError(f"OpenCode V1 lacks a bounded archive seek for {table}", phase="archive")

    @classmethod
    def _for_index(cls, index, table, owner, fields, keys):
        order = ",".join(keys)
        selected = f"{fields},{order}"  # Duplicate keys by position, not by name.
        if table != "session":
            selected += "," + ",".join(_DATA_COLUMNS)
        base = f"SELECT {selected} FROM {table} INDEXED BY {index} WHERE {owner}=?"
        tail = f" ORDER BY {order} LIMIT ?"
        seek = f"({order})>({','.join('?' for _ in keys)})"
        return cls(base + tail, base + " AND " + seek + tail, keys)

    def _qualifies(self, db, owner, limit):
        resume = tuple("seek" if key == "id" else 1 for key in self.keys)
        # An index that merely filters the owner can still rescan its entire
        # prefix on every resume. Explicitly require the lower bound too.
        for sql, params, bound in ((self.first, ("owner", limit), ""),
                                    (self.resume, ("owner", *resume, limit), ">")):
            plan = tuple(row["detail"] for row in db.execute("EXPLAIN QUERY PLAN " + sql, params))
            if (len(plan) != 1 or not plan[0].startswith("SEARCH ")
                    or f"{owner}=?" not in plan[0] or bound not in plan[0]):
                return False
        return True

    def rows(self, db, owner, after, limit):
        if after is None:
            return db.execute(self.first, (owner, limit)).fetchall()
        return db.execute(self.resume, (owner, *after, limit)).fetchall()

    def key(self, row, *, trailing_columns=0):
        offset = len(row) - len(self.keys) - trailing_columns
        values = tuple(row[offset:offset + len(self.keys)])
        if not all(type(value) is (str if key == "id" else int) for key, value in zip(self.keys, values, strict=True)):
            raise SourceDataError("OpenCode V1 archive seek has invalid key types", phase="archive")
        return values


@dataclass(slots=True)
class _Member:
    session_id: str
    revision: MemberRevision
    phase: int = 1  # Message and part streams, then children.
    after: tuple | None = None


class V1ArchiveCursor:
    """Storage order, not causal order; nothing is authoritative before EOF.

    Seek positions are intentionally private to this transaction. Closing,
    expiry, decoding failure or a lost read transaction requires a fresh
    cursor, not a restart from a previously returned position.
    """
    def __init__(self, source, db, root_id):
        self._source, self._db = source, db
        self._deadline = monotonic() + PIN_SECONDS
        seeks = []
        for table, owner, fields in _TABLES:
            if any(row["name"].casefold() == "rowid" for row in db.execute(f"PRAGMA table_xinfo({table})")):
                raise SourceSchemaError("OpenCode V1 archive row identity is shadowed", phase="archive")
            indexes = tuple(_indexes(db, table))
            identity_index = _unique_id_index(db, indexes, table)
            if table == "session":
                root_sql = f"SELECT {fields} FROM session INDEXED BY {identity_index} WHERE id COLLATE BINARY=?"
            limit = 1 if table == "session" else PAGE_ROWS
            seeks.append(_Seek.find(db, indexes, table, owner, fields, limit))
        self._seeks = tuple(seeks)
        self._encoding = db.execute("PRAGMA encoding").fetchone()[0]
        root = db.execute(root_sql, (root_id,)).fetchone()
        if root is None or root["parent_id"] not in (None, ""):
            raise SourceDataError("OpenCode V1 archive root is not a top-level session", phase="archive")
        _require_ids(root, "id")
        self._root = self._source._normalize_session(root)
        self._stack = [_Member(self._root.session_id, MemberRevision.from_row(root))]

    def close(self):
        db, self._db = self._db, None
        self._root = None
        self._stack.clear()
        if db is not None:
            try:
                db.rollback()
            except sqlite3.ProgrammingError:
                # The owning context may already have closed the connection.
                pass

    def read_page(self):
        db = self._db
        try:
            if db is None or not db.in_transaction or monotonic() >= self._deadline:
                raise _unusable_pin()
            page = self._read_page(db)
            if monotonic() >= self._deadline:
                raise _unusable_pin()
            if page.eof:
                self.close()
            return page
        except sqlite3.ProgrammingError as error:
            self.close()
            raise _unusable_pin() from error
        except sqlite3.Error as error:
            self.close()
            raise SourceDataError("OpenCode V1 archive page could not be read", phase="archive") from error
        except BaseException:
            self.close()
            raise

    def _read_page(self, db):
        if self._root is not None:
            result = V1ArchivePage(sessions=(self._root,))
            self._root = None
            return result
        if not self._stack:
            return V1ArchivePage(eof=True)
        member = self._stack[-1]
        seek = self._seeks[member.phase]
        if member.phase == 0:
            return self._child_page(db, member, seek)
        table = _TABLES[member.phase][0]
        normalize = self._source._normalize_message if member.phase == 1 else self._source._normalize_part
        values, native_order = [], []
        remaining = PAGE_BYTES
        for row in seek.rows(db, member.session_id, member.after, PAGE_ROWS):
            _require_ids(row, "id", "session_id")
            if table == "part":
                _require_ids(row, "message_id")
            rowid, storage_type = row[-len(_DATA_COLUMNS):]
            if storage_type != "text":
                raise SourceDataError("OpenCode V1 archive payload is not JSON text", phase="archive")
            with db.blobopen(table, "data", rowid, readonly=True) as payload:
                if len(payload) > PAGE_BYTES:
                    raise SourceDataError("OpenCode V1 archive row exceeds the decode budget", phase="archive")
                if len(payload) > remaining:
                    break
                remaining -= len(payload)
                record = dict(row)
                try:
                    record["data"] = payload.read().decode(self._encoding)
                except UnicodeError as error:
                    raise SourceDataError("OpenCode V1 archive payload has invalid text", phase="archive") from error
                values.append(normalize(record, ()) if member.phase == 1 else normalize(record))
                if table == "message":
                    native_order.append((row["time_created"], row["revision_id"]))
                else:
                    native_order.append(row["revision_id"])
            totals = member.revision.messages if member.phase == 1 else member.revision.parts
            totals.add(row)
            member.after = seek.key(row, trailing_columns=len(_DATA_COLUMNS))
        else:
            if len(values) < PAGE_ROWS:
                member.phase = 2 if member.phase == 1 else 0
                member.after = None
        if table == "message":
            return V1ArchivePage(messages=tuple(values), message_order=tuple(native_order))
        return V1ArchivePage(parts=tuple(values), part_order=tuple(native_order))

    def _child_page(self, db, member, seek):
        rows = seek.rows(db, member.session_id, member.after, 1)
        if not rows:
            self._stack.pop()
            return V1ArchivePage(revision_member=(member.revision.sort_key, member.revision.bytes()))
        if len(self._stack) >= MAX_DEPTH:
            raise SourceDataError("OpenCode V1 archive tree exceeds the traversal depth budget", phase="archive")
        _require_ids(rows[0], "id", "parent_id")
        child = self._source._normalize_session(rows[0])
        member.after = seek.key(rows[0])
        self._stack.append(_Member(child.session_id, MemberRevision.from_row(rows[0])))
        return V1ArchivePage(sessions=(child,))


def _require_ids(row, *columns):
    if any(not isinstance(row[col], str) or not row[col] for col in columns):
        raise SourceDataError("OpenCode V1 archive row has an invalid identity", phase="archive")


def _unusable_pin():
    return SourceConcurrentChangeError("OpenCode V1 archive read pin is no longer usable", phase="archive")
