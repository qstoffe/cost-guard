"""Whether V1 assistants carry a direct child launch past its return."""
from dataclasses import dataclass

from src.sources.errors import SourceDataError


_ROWS = 32
SCHEMA = """
    CREATE TABLE trace_crossing_parents(
        window INTEGER NOT NULL,parent TEXT NOT NULL,PRIMARY KEY(window,parent)
    ) WITHOUT ROWID;
"""


@dataclass(frozen=True, slots=True)
class ChildAssistant:
    message_id: str
    created_at_ms: int
    completed_at_ms: int | None
    continuing: bool


class ChildWindowMembership:
    """Visit one resolved launch without holding all messages or parents."""
    def __init__(self, db, window_id, window):
        self._db = db
        self._id = window_id
        self._window = window
        self._after = None
        self._phase = "crossings"

    def turn(self):
        """One bounded preparation or output turn. None is EOF."""
        if self._phase == "done":
            return None
        if self._phase == "invalid":
            raise SourceDataError("V1 child window is incomplete", phase="archive")
        try:
            if self._phase == "crossings":
                self._prepare()
                return ()
            return self._members()
        except BaseException:
            self._phase = "invalid"
            raise

    def _prepare(self):
        db, window = self._db, self._window
        with db:
            rows = self._page(window.end_ms)
            for _, _, parent, completed, finish in rows:
                if parent and (completed is None or completed > window.end_ms or finish == "tool-calls"):
                    self._crossing(parent)
            if len(rows) < _ROWS and window.owner_id:
                early_attempt = db.execute("""
                    SELECT 1 FROM trace_messages INDEXED BY trace_attempts
                    WHERE session=? AND parent=? AND created<? AND role='assistant' LIMIT 1
                """, (window.session_id, window.owner_id, window.end_ms)).fetchone()
                if early_attempt is None:
                    self._crossing(window.owner_id)
        if len(rows) < _ROWS:
            self._phase, self._after = "members", None
        else:
            self._after = rows[-1][1], rows[-1][0]

    def _crossing(self, parent):
        self._db.execute("INSERT OR IGNORE INTO trace_crossing_parents VALUES(?,?)", (self._id, parent))

    def _members(self):
        db, window = self._db, self._window
        rows = self._page(window.invocation_end_ms)
        members = []
        for message, created, parent, completed, _ in rows:
            continuing = parent is not None and db.execute("""
                SELECT 1 FROM trace_crossing_parents WHERE window=? AND parent=?
            """, (self._id, parent)).fetchone() is not None
            if continuing or (created < window.end_ms and (completed is None or completed <= window.end_ms)):
                members.append(ChildAssistant(message, created, completed, continuing))
        if len(rows) < _ROWS:
            self._phase = "done"
        else:
            self._after = rows[-1][1], rows[-1][0]
        return tuple(members) if members or rows else None

    def _page(self, end):
        db, window = self._db, self._window
        query = """
            SELECT id,created,parent,completed,finish FROM trace_messages INDEXED BY trace_assistants
            WHERE session=? AND role='assistant' AND {seek} ORDER BY created,id LIMIT ?
        """
        if self._after is None:
            return db.execute(query.format(seek="created>=? AND created<?"),
                              (window.session_id, window.start_ms, end, _ROWS)).fetchall()
        clock, message = self._after
        rows = db.execute(query.format(seek="created=? AND id>?"),
                          (window.session_id, clock, message, _ROWS)).fetchall()
        if len(rows) < _ROWS:
            rows.extend(db.execute(query.format(seek="created>? AND created<?"),
                                   (window.session_id, clock, end, _ROWS - len(rows))).fetchall())
        return rows
