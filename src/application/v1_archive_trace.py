"""Off-dispatch proof of bounded V1 trace production from one pinned cursor."""
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

from src.analysis.billing import provider_matches
from src.analysis.causal import TRACKED_PROVIDER_DEFAULT, trace_entry
from src.analysis.models import TraceEntry
from src.domain import EventKind, MessageRole, TokenUsage
from src.sources.errors import SourceDataError
from src.sources.opencode_requests import observed_response
from src.sources.opencode_v1 import _event_kind, _subtask_selection

from . import v1_child_walk, v1_trace_facts as facts
from .v1_child_launches import ChildLaunches
from .v1_scoped_calls import ScopedCalls


TRACE_ROWS = 32
_KINDS = {
    EventKind.OTHER: facts.OTHER, EventKind.SYNTHETIC_CONTINUATION: facts.SYNTHETIC,
    EventKind.USER_PROMPT: facts.PROMPT, EventKind.SUBTASK: facts.SUBTASK, EventKind.COMPACTION: facts.COMPACTION,
}


@dataclass(frozen=True, slots=True)
class V1TraceRow:
    entry: TraceEntry
    executing_prompt_id: str | None


class V1ArchiveTrace:
    """The caller owns the cursor and a separate, disposable staging database.

    All facts are tentative until the source pin reaches EOF. This is only
    usage trace and executing-prompt identity; it has no descendant causal
    attribution, coverage or display authority.
    """
    def __init__(self, source, cursor, stage, *, subscription_providers=frozenset(),
                 tracked_provider=TRACKED_PROVIDER_DEFAULT):
        files = tuple(stage.execute("PRAGMA database_list"))
        if (stage.in_transaction or stage.isolation_level is None or len(files) != 1
                or files[0][2] and Path(files[0][2]).resolve() == source.database_path
                or stage.execute("SELECT 1 FROM sqlite_schema LIMIT 1").fetchone()):
            raise ValueError("V1 trace requires an empty private staging database")
        self._db = stage
        self._source = source
        self._cursor = cursor
        self._subscriptions = subscription_providers
        self._tracked_provider = tracked_provider
        self._root = None
        self._phase = "input"
        self._fallback_after = None
        self._trace_after = None
        self._ordinal = 0
        stage.executescript(facts.SCHEMA + v1_child_walk.SCHEMA)
        self._launches = ChildLaunches(stage)

    def capture_turn(self):
        self._require("input")
        try:
            page = self._cursor.read_page()
            if page.eof and self._root is None:
                raise SourceDataError("V1 trace captured no root", phase="archive")
            with self._db:
                for session in page.sessions:
                    if session.provenance.source_instance != self._source.source_instance:
                        raise SourceDataError("V1 trace cursor has a different source binding", phase="archive")
                    self._db.execute("INSERT INTO trace_members VALUES(?,?,?)",
                                     (session.session_id, session.parent_session_id, session.created_at_ms))
                    if self._root is None:
                        self._root = session.session_id
                for message, order in zip(page.messages, page.message_order, strict=True):
                    facts.save_header(self._db, message, order)
                for part, order in zip(page.parts, page.part_order, strict=True):
                    self._accept_part(part, order)
        except BaseException:
            self._phase = "invalid"
            raise
        if page.eof:
            self._phase = "fallback"
        return page.eof

    def _require(self, phase):
        if self._phase != phase:
            raise SourceDataError("V1 trace stage is not ready for this phase", phase="archive")

    def _accept_part(self, part, native_order):
        db = self._db
        key = part.session_id, part.message_id
        columns = facts.HEAD + ",native_clock,native_id" if part.kind == "tool" else facts.HEAD
        row = db.execute(f"SELECT {columns} FROM trace_messages WHERE session=? AND id=?", key).fetchone()
        if row is None:
            raise SourceDataError("V1 trace part has no observed message in its session", phase="archive")
        role = MessageRole(row[0])
        if role is MessageRole.USER:
            kind = _KINDS[_event_kind((part,))]
            db.execute("UPDATE trace_messages SET kind=max(kind,?) WHERE session=? AND id=?", (kind, *key))
            if part.kind == "subtask":
                db.executemany("""
                    INSERT INTO trace_choices VALUES(?,?,?,?,?,?)
                    ON CONFLICT(session,message,field) DO UPDATE SET (clock,part,value)=
                        (excluded.clock,excluded.part,excluded.value)
                    WHERE (clock,part)<(excluded.clock,excluded.part)
                """, ((*key, field, part.created_at_ms, part.part_id, value)
                      for field, value in _subtask_selection(part).items()))
            return
        if role is not MessageRole.ASSISTANT:
            return
        if part.kind == "tool":
            header = facts.load_header(row[:-2], self._source, *key)
            self._launches.accept(part, header, row[-2:], native_order)
        if observed_response(part):
            db.execute("UPDATE trace_messages SET response=1 WHERE session=? AND id=? AND NOT response", key)
        if part.kind == "step-finish" and isinstance(part.data.get("tokens"), Mapping):
            message = facts.load_header(row, self._source, *key)
            for call in self._source._normalize_invocations(replace(message, parts=(part,))):
                facts.save_call(db, call)
                db.execute("UPDATE trace_messages SET step=1 WHERE session=? AND id=? AND NOT step", key)

    def child_launch_turn(self):
        """Visit direct launches after source EOF, independently of trace replay."""
        if self._phase in ("input", "invalid"):
            raise SourceDataError("V1 child launch stage is not ready", phase="archive")
        try:
            return self._launches.turn()
        except BaseException:
            self._phase = "invalid"
            raise

    def child_window_membership(self, window):
        """Prepare and read assistants for one returned direct window."""
        if self._phase in ("input", "invalid"):
            raise SourceDataError("V1 child launch stage is not ready", phase="archive")
        return self._launches.membership(window)

    def child_scope_walk(self, root_assistant_id):
        if self._phase in ("input", "invalid"):
            raise SourceDataError("V1 child launch stage is not ready", phase="archive")
        return v1_child_walk.ChildScopeWalk(self._db, self._launches, self._root, root_assistant_id)

    def scoped_calls(self, scope):
        if self._phase not in ("trace", "done"):
            raise SourceDataError("V1 descendant calls require prepared trace", phase="archive")
        return ScopedCalls(self._db, scope, self._launches.membership(scope.direct), self._tracked_provider)

    def prepare_turn(self):
        """Decide fallback only after all steps are known; visit even noncalls."""
        self._require("fallback")
        db = self._db
        try:
            with db:
                rows = _keyset(db, "trace_messages", "session,id", f"session,id,{facts.HEAD},step,response",
                               self._fallback_after)
                for session, message, *fields in rows:
                    step, observed = fields[-2:]
                    if step or fields[0] != MessageRole.ASSISTANT.value:
                        continue
                    header = facts.load_header(fields[:-2], self._source, session, message)
                    if header.tokens is None and observed:
                        header = replace(header, tokens=TokenUsage(known_fields=()))
                    for call in self._source._normalize_invocations(header):
                        facts.save_call(db, call)
        except BaseException:
            self._phase = "invalid"
            raise
        if len(rows) < TRACE_ROWS:
            self._phase = "trace"
            return True
        self._fallback_after = rows[-1][:2]
        return False

    def trace_turn(self):
        """Return an ordered page of trace and executing-prompt facts, or None for EOF."""
        if self._phase == "done":
            return None
        self._require("trace")
        db = self._db
        result = []
        try:
            rows = _keyset(db, "trace_calls", "clock,id", "*", self._trace_after)
            for call_values in rows:
                session, message = call_values[2:4]
                row = db.execute(f"""
                    SELECT {facts.HEAD} FROM trace_messages WHERE session=? AND id=?
                """, (session, message)).fetchone()
                header = facts.load_header(row, self._source, session, message)
                call = facts.load_call(call_values, self._source, header)
                parent, = db.execute("SELECT parent FROM trace_members WHERE id=?", (session,)).fetchone()
                owner, first_window, selection = facts.own_event(db, session, call.initiating_event_id)
                entry = trace_entry(call, self._ordinal, root=self._root, parent=parent, owner=owner,
                                    selection=selection, subscription_providers=self._subscriptions)
                prompt = None if entry.summary else owner
                if (prompt is None and not entry.summary and session == self._root
                        and provider_matches(entry.model.provider, self._tracked_provider)):
                    # Root records are ordered by prompt clock then ID. This
                    # very call makes every enclosing window a nonempty record.
                    # Child causal attribution cannot supply this fallback.
                    prompt = first_window
                result.append(V1TraceRow(entry, prompt))
                self._ordinal += 1
        except BaseException:
            self._phase = "invalid"
            raise
        if len(rows) < TRACE_ROWS:
            self._phase = "done"
        elif rows:
            self._trace_after = rows[-1][:2]
        return tuple(result) if rows else None


def _keyset(db, table, ordering, selected, after):
    lead, tie = ordering.split(",")
    base = f"SELECT {selected} FROM {table} {{bounds}} ORDER BY {ordering} LIMIT ?"
    if after is None:
        return db.execute(base.format(bounds=""), (TRACE_ROWS,)).fetchall()
    rows = db.execute(base.format(bounds=f"WHERE {lead}=? AND {tie}>?"), (*after, TRACE_ROWS)).fetchall()
    if len(rows) < TRACE_ROWS:
        rows.extend(db.execute(base.format(bounds=f"WHERE {lead}>?"), (after[0], TRACE_ROWS - len(rows))).fetchall())
    return rows
