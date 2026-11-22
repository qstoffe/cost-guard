"""Native V1 revision fields captured once; not an exact content identity."""
from dataclasses import dataclass, field
import hashlib

from .errors import SourceDataError
from .opencode_v1_revision import revision_row_bytes


REVISION_PAGE = 32
_MAX_SQLITE_INT = (1 << 63) - 1


@dataclass(slots=True)
class _Totals:
    count: int = 0
    updated_max: int | None = None
    updated_sum: int = 0
    created_max: int | None = None
    id_max: str = ""
    id_sort: bytes = b""

    def add(self, row):
        created, updated = row["time_created"], row["time_updated"]
        if type(created) is not int or type(updated) is not int:
            raise SourceDataError("V1 archive revision requires native integer clocks", phase="archive")
        self.count += 1
        self.updated_sum += updated
        if not -_MAX_SQLITE_INT - 1 <= self.updated_sum <= _MAX_SQLITE_INT:
            raise SourceDataError("V1 archive revision clock total exceeds SQLite integer range", phase="archive")
        self.updated_max = max(updated, self.updated_max) if self.updated_max is not None else updated
        self.created_max = max(created, self.created_max) if self.created_max is not None else created
        key = row["revision_id"]
        if key > self.id_sort:
            self.id_max, self.id_sort = row["id"], key

    def values(self):
        return (self.count, self.updated_max or 0, self.updated_sum, self.created_max or 0, self.id_max)


@dataclass(slots=True)
class MemberRevision:
    sort_key: bytes
    session: tuple
    messages: _Totals = field(default_factory=_Totals)
    parts: _Totals = field(default_factory=_Totals)

    @classmethod
    def from_row(cls, row):
        fields = ("id", "parent_id", "project_id", "time_updated", "time_archived")
        return cls(row["revision_id"], tuple(row[key] for key in fields))

    def bytes(self):
        return revision_row_bytes((*self.session, *self.messages.values(), *self.parts.values()))


class V1RevisionStamp:
    """Reduce one cursor's completed members in indexed, source-free turns."""
    def __init__(self, cursor, stage):
        if stage.in_transaction:
            raise ValueError("V1 revision staging requires its own transaction")
        self._cursor = cursor
        self._db = stage
        self._digest = hashlib.sha256()
        self._after = b""
        self._input_done = False
        self._invalid = False
        self._stamp = None
        stage.execute("""
            CREATE TEMP TABLE v1_revision_members(
                sort_key BLOB PRIMARY KEY, encoded BLOB NOT NULL
            ) WITHOUT ROWID
        """)

    def read_page(self):
        """Return the source page unchanged; callers can consume the same facts."""
        if self._input_done or self._invalid:
            raise SourceDataError("V1 revision capture cannot accept further input", phase="archive")
        try:
            page = self._cursor.read_page()
            if page.revision_member is not None:
                with self._db:
                    self._db.execute("INSERT INTO v1_revision_members VALUES(?,?)", page.revision_member)
        except BaseException:
            self._invalid = True
            raise
        self._input_done = page.eof
        return page

    def digest_turn(self):
        if not self._input_done:
            raise SourceDataError("V1 revision capture has not reached source EOF", phase="archive")
        if self._stamp is not None:
            return self._stamp
        rows = self._db.execute("""
            SELECT sort_key,encoded FROM v1_revision_members WHERE sort_key>?
            ORDER BY sort_key LIMIT ?
        """, (self._after, REVISION_PAGE)).fetchall()
        for key, encoded in rows:
            self._digest.update(encoded)
            self._after = key
        if len(rows) < REVISION_PAGE:
            self._stamp = "v1-tree:" + self._digest.hexdigest()
        return self._stamp
