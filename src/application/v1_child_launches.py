"""Bounded direct child launch windows; not descendant attribution."""
from dataclasses import dataclass

from src.analysis.child_links import OPEN_END, tool_call_key, tool_launch

from .v1_trace_facts import COMPACTION, PROMPT, SUBTASK


_WINDOW_ROWS = 32
_TURNS = f"kind IN ({PROMPT},{SUBTASK},{COMPACTION})"
SCHEMA = """
    CREATE TABLE trace_tool_winners(
        ordinal INTEGER PRIMARY KEY, session TEXT NOT NULL, kind TEXT NOT NULL, id TEXT NOT NULL,
        message TEXT NOT NULL, updated INTEGER NOT NULL, created INTEGER NOT NULL,
        native_clock INTEGER NOT NULL, native_message BLOB NOT NULL, part_clock INTEGER NOT NULL, native_part BLOB NOT NULL,
        target TEXT, start INTEGER, finish INTEGER, background INTEGER,
        UNIQUE(session,kind,id)
    );
    CREATE TABLE trace_launches(
        ordinal INTEGER PRIMARY KEY, session TEXT NOT NULL, message TEXT NOT NULL,
        target TEXT NOT NULL, start INTEGER NOT NULL, finish INTEGER NOT NULL, background INTEGER NOT NULL
    );
    CREATE INDEX trace_child_launch ON trace_launches(target,start);
"""


@dataclass(frozen=True, slots=True)
class DirectChildWindow:
    parent_session_id: str
    message_id: str
    session_id: str
    start_ms: int
    end_ms: int
    invocation_end_ms: int
    owner_id: str
    background: bool


class ChildLaunches:
    def __init__(self, db):
        self._db = db
        self._qualified_after = 0
        self._window_after = 0
        self._qualified = False
        self._done = False
        db.executescript(SCHEMA)

    def accept(self, part, message, native_message, native_part):
        key = tool_call_key(part, message)
        if key is None:
            return
        launch = tool_launch(part, message)
        self._db.execute("""
            INSERT INTO trace_tool_winners(
                session,kind,id,message,updated,created,native_clock,native_message,part_clock,native_part,
                target,start,finish,background
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(session,kind,id) DO UPDATE SET
                (message,updated,created,native_clock,native_message,part_clock,native_part,
                 target,start,finish,background) =
                (excluded.message,excluded.updated,excluded.created,excluded.native_clock,
                 excluded.native_message,excluded.part_clock,excluded.native_part,
                 excluded.target,excluded.start,excluded.finish,excluded.background)
            WHERE excluded.updated > updated OR (excluded.updated = updated AND
                (excluded.created,excluded.native_clock,excluded.native_message,excluded.part_clock,excluded.native_part)
                < (created,native_clock,native_message,part_clock,native_part))
        """, (message.session_id, *key, message.message_id, part.updated_at_ms, message.created_at_ms,
              *native_message, part.created_at_ms, native_part, *(launch or (None,) * 4)))

    def turn(self):
        """Visit at most one page of winners or direct windows. None is EOF."""
        if self._done:
            return None
        if not self._qualified:
            self._qualify_turn()
            return ()
        rows = self._db.execute("""
            SELECT * FROM trace_launches WHERE ordinal>? ORDER BY ordinal LIMIT ?
        """, (self._window_after, _WINDOW_ROWS)).fetchall()
        result = tuple(self._window(*row[1:]) for row in rows)
        if len(rows) < _WINDOW_ROWS:
            self._done = True
        else:
            self._window_after = rows[-1][0]
        return result or None

    def _qualify_turn(self):
        db = self._db
        with db:
            # Visit losers as well: a sparse join must not seek through an
            # unbounded number of unqualified tool calls in one turn.
            rows = db.execute("""
                SELECT ordinal,session,message,target,start,finish,background
                FROM trace_tool_winners WHERE ordinal>? ORDER BY ordinal LIMIT ?
            """, (self._qualified_after, _WINDOW_ROWS)).fetchall()
            for row in rows:
                ordinal, session, message, target, start, finish, background = row
                if target is None:
                    continue
                child = db.execute("SELECT parent,created FROM trace_members WHERE id=?", (target,)).fetchone()
                if child is None or child[0] != session or (finish and child[1] > finish):
                    continue
                db.execute("INSERT INTO trace_launches VALUES(?,?,?,?,?,?,?)",
                           (ordinal, session, message, target, start, OPEN_END if background or not finish else finish,
                            background))
        if len(rows) < _WINDOW_ROWS:
            self._qualified = True
        else:
            self._qualified_after = rows[-1][0]

    def _window(self, session, message, target, start, finish, background):
        db = self._db
        next_launch = db.execute("""
            SELECT start FROM trace_launches INDEXED BY trace_child_launch
            WHERE target=? AND start>? ORDER BY start LIMIT 1
        """, (target, start)).fetchone()
        upper = next_launch[0] if next_launch else OPEN_END
        owner = self._first_turn(target, start, min(upper, finish))
        if owner is None:
            created, = db.execute("SELECT created FROM trace_members WHERE id=?", (target,)).fetchone()
            if start <= created < finish:
                owner = self._first_turn(target, start, upper)
        if owner is not None:
            following = db.execute(f"""
                SELECT created FROM trace_messages INDEXED BY trace_turns
                WHERE session=? AND {_TURNS} AND created>=? ORDER BY created LIMIT 1
            """, (target, max(finish, owner[0] + 1))).fetchone() if finish < OPEN_END else None
            if following is not None:
                upper = min(upper, following[0])
        return DirectChildWindow(session, message, target, start, min(upper, finish), upper,
                                 owner[1] if owner is not None else "", bool(background))

    def _first_turn(self, target, start, end):
        return self._db.execute(f"""
            SELECT created,id FROM trace_messages INDEXED BY trace_turns
            WHERE session=? AND {_TURNS} AND created>=? AND created<? ORDER BY created,id LIMIT 1
        """, (target, start, end)).fetchone()
