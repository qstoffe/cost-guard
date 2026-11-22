"""Bounded physical identities from a V1 descendant's effective window."""
from collections import deque
from dataclasses import dataclass

from src.analysis.billing import provider_matches
from src.sources.errors import SourceDataError


CALL_ROWS = 32
_FIRST_CLOCK = -(1 << 63)
_LAST_CLOCK = (1 << 63) - 1
_QUERY = """
    SELECT clock,id,message,step FROM trace_calls INDEXED BY {index}
    WHERE {owner} AND {time} ORDER BY clock,id LIMIT ?
"""


@dataclass(frozen=True, slots=True)
class ScopedCall:
    session_id: str
    invocation_id: str
    message_id: str
    step_part_id: str | None


def message_call_page(db, session, message, after):
    return _page(db, "trace_calls_message", "session=? AND message=?", (session, message),
                 _FIRST_CLOCK, _LAST_CLOCK, after)


def parent_call_page(db, session, parent, after):
    return _page(db, "trace_calls_parent", "session=? AND parent=?", (session, parent),
                 _FIRST_CLOCK, _LAST_CLOCK, after)


def _page(db, index, owner, keys, start, end, after):
    if after is None:
        return db.execute(_QUERY.format(index=index, owner=owner, time="clock>=? AND clock<=?"),
                          (*keys, start, end, CALL_ROWS)).fetchall()
    clock, invocation = after
    rows = db.execute(_QUERY.format(index=index, owner=owner, time="clock=? AND id>?"),
                      (*keys, clock, invocation, CALL_ROWS)).fetchall()
    if len(rows) < CALL_ROWS:
        rows.extend(db.execute(_QUERY.format(index=index, owner=owner, time="clock>? AND clock<=?"),
                               (*keys, clock, end, CALL_ROWS - len(rows))).fetchall())
    return rows


class ScopedCalls:
    """Union completion-window calls and earlier or later crossing calls.

    A call can qualify in multiple scopes. The eventual prompt allocation
    uses a physical-key/causal-prompt unique constraint across scopes.
    """
    def __init__(self, db, scope, membership, provider):
        self._db = db
        self._scope = scope
        self._session = scope.direct.session_id
        self._membership = membership
        self._provider = provider
        self._pending = deque()
        self._phase = "window"
        self._after = None

    def turn(self):
        if self._phase == "done":
            return None
        if self._phase == "invalid":
            raise SourceDataError("V1 descendant calls are incomplete", phase="archive")
        try:
            if self._phase == "window":
                return self._window()
            if self._pending:
                return self._crossing()
            rows = self._membership.turn()
            if rows is None:
                self._phase = "done"
                return None
            self._pending.extend(row.message_id for row in rows if row.continuing)
            return ()
        except BaseException:
            self._phase = "invalid"
            raise

    def _window(self):
        start, end = self._scope.direct.start_ms, self._scope.end_ms
        rows = _page(self._db, "trace_calls_session", "session=?", (self._session,), start, end, self._after)
        result = []
        for _, invocation, message, step in rows:
            created, provider = self._db.execute("""
                SELECT created,provider FROM trace_messages WHERE session=? AND id=?
            """, (self._session, message)).fetchone()
            if created >= start and provider_matches(provider, self._provider):
                result.append(ScopedCall(self._session, invocation, message, step))
        if len(rows) < CALL_ROWS:
            self._phase, self._after = "crossing", None
        else:
            self._after = rows[-1][:2]
        return tuple(result)

    def _crossing(self):
        message = self._pending[0]
        provider, = self._db.execute("SELECT provider FROM trace_messages WHERE session=? AND id=?",
                                     (self._session, message)).fetchone()
        if not provider_matches(provider, self._provider):
            self._pending.popleft()
            return ()
        rows = message_call_page(self._db, self._session, message, self._after)
        start, end = self._scope.direct.start_ms, self._scope.end_ms
        result = tuple(ScopedCall(self._session, invocation, message, step)
                       for clock, invocation, message, step in rows if not start <= clock <= end)
        if len(rows) < CALL_ROWS:
            self._pending.popleft()
            self._after = None
        else:
            self._after = rows[-1][:2]
        return result
