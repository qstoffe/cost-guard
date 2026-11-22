"""One root prompt's canonical physical request allocation, in bounded turns."""
from collections import deque

from src.analysis.billing import provider_matches
from src.analysis.child_links import OPEN_END
from src.sources.errors import SourceDataError

from .v1_child_walk import ChildScopeWalk
from .v1_scoped_calls import CALL_ROWS, ScopedCall, ScopedCalls, parent_call_page
from .v1_trace_facts import OTHER, PROMPT, SUBTASK, SYNTHETIC


_VISIBLE = f"kind IN ({PROMPT},{SUBTASK})"
_INVISIBLE = f"kind IN ({OTHER},{SYNTHETIC})"
_PROMPT_PAGE = f"""
    SELECT created,id FROM trace_messages INDEXED BY trace_visible
    WHERE session=? AND {_VISIBLE} AND {{seek}} ORDER BY created,id LIMIT ?
"""
PROMPT_ROWS = 32
SCHEMA = """
    CREATE TABLE trace_prompt_runs(id INTEGER PRIMARY KEY);
    CREATE TABLE trace_prompt_seen(
        run INTEGER NOT NULL, session TEXT NOT NULL, invoc TEXT NOT NULL,
        message TEXT NOT NULL, step TEXT NOT NULL,
        PRIMARY KEY(run,session,invoc,message,step)
    ) WITHOUT ROWID;
"""


def root_prompt_page(db, root, after):
    if after is None:
        return db.execute(_PROMPT_PAGE.format(seek="created>=0"), (root, PROMPT_ROWS)).fetchall()
    clock, prompt = after
    rows = db.execute(_PROMPT_PAGE.format(seek="created=? AND id>?"), (root, clock, prompt, PROMPT_ROWS)).fetchall()
    if len(rows) < PROMPT_ROWS:
        rows.extend(db.execute(_PROMPT_PAGE.format(seek="created>?"),
                               (root, clock, PROMPT_ROWS - len(rows))).fetchall())
    return rows


class RootPromptCalls:
    """Different causal prompts can own the same request; within one, emit once."""
    def __init__(self, db, launches, root, prompt, provider):
        launches.require_qualified()
        visible = db.execute(f"""
            SELECT created,kind FROM trace_messages WHERE session=? AND id=? AND {_VISIBLE}
        """, (root, prompt)).fetchone()
        if visible is None or visible[0] < 0:
            raise SourceDataError("V1 causal prompt does not have an eligible root window", phase="archive")
        self._db, self._launches, self._root = db, launches, root
        self._provider = provider
        self._start, self._kind = visible
        following = db.execute(f"""
            SELECT created FROM trace_messages INDEXED BY trace_visible
            WHERE session=? AND {_VISIBLE} AND created>? ORDER BY created LIMIT 1
        """, (root, self._start)).fetchone()
        self._end = following[0] if following else OPEN_END
        self._run = None
        self._after_event = None
        self._walk = None
        self._scopes = deque()
        self._child_calls = None
        self._done = False
        self._invalid = False
        self._start_event(prompt)

    def turn(self):
        if self._done:
            return None
        if self._invalid:
            raise SourceDataError("V1 prompt allocation is incomplete", phase="archive")
        try:
            if self._direct_pending:
                return self._direct()
            if self._walk is not None:
                return self._descendants()
            if self._event is None:
                return self._next_continuation()
            self._next_launcher()
            return ()
        except BaseException:
            self._invalid = True
            raise

    def _next_continuation(self):
        db, args = self._db, (self._root,)
        query = f"""
            SELECT created,id,kind FROM trace_messages INDEXED BY trace_invisible
            WHERE session=? AND role='user' AND {_INVISIBLE} AND {{seek}} ORDER BY created,id LIMIT 1
        """
        if self._after_event is None:
            row = db.execute(query.format(seek="created>? AND created<?"), (*args, self._start, self._end)).fetchone()
        else:
            clock, event = self._after_event
            row = db.execute(query.format(seek="created=? AND id>?"), (*args, clock, event)).fetchone()
            if row is None:
                row = db.execute(query.format(seek="created>? AND created<?"), (*args, clock, self._end)).fetchone()
        if row is None:
            self._done = True
            return None
        clock, event, kind = row
        self._after_event = clock, event
        if kind == OTHER or self._kind == SUBTASK:
            self._start_event(event)
        return ()

    def _start_event(self, event):
        self._event = event
        self._direct_pending = True
        self._call_after = None
        self._after_launcher = None

    def _next_launcher(self):
        message = self._launches.next_attempt(self._root, self._event, self._after_launcher)
        if message is None:
            self._event = None
            return
        self._after_launcher = message
        self._walk = ChildScopeWalk(self._db, self._launches, self._root, message)

    def _direct(self):
        rows = parent_call_page(self._db, self._root, self._event, self._call_after)
        if len(rows) < CALL_ROWS:
            self._direct_pending = False
        else:
            self._call_after = rows[-1][:2]
        # Root calls have a single captured initiating event and cannot also
        # be descendants of this root. Only overlapping child windows dedup.
        return tuple(ScopedCall(self._root, invocation, message, step)
                     for _, invocation, message, step in rows if self._tracked(message))

    def _tracked(self, message):
        if self._provider is None:
            return True
        provider, = self._db.execute("SELECT provider FROM trace_messages WHERE session=? AND id=?",
                                     (self._root, message)).fetchone()
        return provider_matches(provider, self._provider)

    def _descendants(self):
        if self._child_calls is not None:
            page = self._child_calls.turn()
            if page is None:
                self._child_calls = None
                return ()
            return self._unique(page)
        if self._scopes:
            scope = self._scopes.popleft()
            self._child_calls = ScopedCalls(self._db, scope, self._launches.membership(scope.direct), self._provider)
            return ()
        scopes = self._walk.turn()
        if scopes is None:
            self._walk = None
        else:
            self._scopes.extend(scopes)
        return ()

    def _unique(self, calls):
        if not calls:
            return ()
        with self._db:
            if self._run is None:
                self._run = self._db.execute("INSERT INTO trace_prompt_runs DEFAULT VALUES").lastrowid
            return tuple(call for call in calls if self._db.execute("""
                INSERT OR IGNORE INTO trace_prompt_seen VALUES(?,?,?,?,?)
            """, (self._run, call.session_id, call.invocation_id, call.message_id, call.step_part_id or "")).rowcount)
