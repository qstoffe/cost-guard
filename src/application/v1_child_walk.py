"""Bounded V1 descendant scope traversal starting from a root assistant."""
from collections import deque
from dataclasses import dataclass

from src.analysis.child_links import OPEN_END
from src.sources.errors import SourceDataError

from .v1_child_launches import DirectChildWindow


SCHEMA = """
    CREATE TABLE trace_walks(id INTEGER PRIMARY KEY);
    CREATE TABLE trace_walk_messages(
        ordinal INTEGER PRIMARY KEY, walk INTEGER NOT NULL, session TEXT NOT NULL, message TEXT NOT NULL,
        lower INTEGER NOT NULL, upper INTEGER NOT NULL, UNIQUE(walk,session,message,lower,upper)
    );
    CREATE INDEX trace_walk_pending ON trace_walk_messages(walk,ordinal);
    CREATE TABLE trace_walk_scopes(
        walk INTEGER NOT NULL, target TEXT NOT NULL, start INTEGER NOT NULL, raw_end INTEGER NOT NULL,
        clipped_end INTEGER NOT NULL, invocation_end INTEGER NOT NULL, owner TEXT NOT NULL, background INTEGER NOT NULL,
        PRIMARY KEY(walk,target,start,raw_end,clipped_end,invocation_end,owner,background)
    ) WITHOUT ROWID;
"""


@dataclass(frozen=True, slots=True)
class ScopedChildWindow:
    direct: DirectChildWindow
    end_ms: int

    def assistant_upper(self, assistant):
        if assistant.continuing:
            return self.direct.invocation_end_ms
        return self.end_ms if (assistant.created_at_ms < self.end_ms and
                               (assistant.completed_at_ms is None or assistant.completed_at_ms <= self.end_ms)) else None


class ChildScopeWalk:
    """Each turn visits one page of links or one page of child assistants.

    Raw boundaries are retained alongside effective foreground clipping because
    continuing attempts must be resolved against the original launch window.
    """
    def __init__(self, db, launches, root, message):
        launches.require_qualified()
        self._db = db
        self._launches = launches
        self._visited = 0
        self._pending = None
        self._after_link = 0
        self._memberships = deque()  # At most one page of newly accepted links.
        self._done = False
        self._invalid = False
        with db:
            self._id = db.execute("INSERT INTO trace_walks DEFAULT VALUES").lastrowid
            self._enqueue(root, message, 0, OPEN_END)

    def turn(self):
        if self._done:
            return None
        if self._invalid:
            raise SourceDataError("V1 descendant scope walk is incomplete", phase="archive")
        try:
            if self._memberships:
                self._walk_assistants()
                return ()
            if self._pending is None:
                self._pending = self._db.execute("""
                    SELECT ordinal,session,message,lower,upper FROM trace_walk_messages INDEXED BY trace_walk_pending
                    WHERE walk=? AND ordinal>? ORDER BY ordinal LIMIT 1
                """, (self._id, self._visited)).fetchone()
                if self._pending is None:
                    self._done = True
                    return None
                self._after_link = 0
            return self._walk_links()
        except BaseException:
            self._invalid = True
            raise

    def _walk_links(self):
        ordinal, session, message, lower, upper = self._pending
        links = self._launches.links_for_message(session, message, self._after_link)
        if not links:
            self._visited, self._pending = ordinal, None
            return ()
        accepted = []
        with self._db:
            for _, link in links:
                if not lower <= link.start_ms < upper:
                    continue
                end = link.end_ms if link.background else min(link.end_ms, upper)
                if end <= link.start_ms:
                    continue
                inserted = self._db.execute("""
                    INSERT OR IGNORE INTO trace_walk_scopes VALUES(?,?,?,?,?,?,?,?)
                """, (self._id, link.session_id, link.start_ms, link.end_ms, end, link.invocation_end_ms,
                      link.owner_id, link.background))
                if inserted.rowcount:
                    scope = ScopedChildWindow(link, end)
                    accepted.append(scope)
                    self._memberships.append((scope, self._launches.membership(link)))
        self._after_link = links[-1][0]
        return tuple(accepted)

    def _walk_assistants(self):
        scope, membership = self._memberships[0]
        rows = membership.turn()
        if rows is None:
            self._memberships.popleft()
            return
        with self._db:
            for row in rows:
                upper = scope.assistant_upper(row)
                if upper is not None:
                    self._enqueue(scope.direct.session_id, row.message_id, scope.direct.start_ms, upper)

    def _enqueue(self, session, message, lower, upper):
        self._db.execute("""
            INSERT OR IGNORE INTO trace_walk_messages(walk,session,message,lower,upper) VALUES(?,?,?,?,?)
        """, (self._id, session, message, lower, upper))
