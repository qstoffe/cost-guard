"""Allowlisted working facts for paged V1 usage; no message/part payloads."""
from decimal import Decimal

from src.domain import CostKind, CostObservation, MessageRole, ModelInvocation, ModelRef, NormalizedMessage, TokenUsage


OTHER, SYNTHETIC, PROMPT, SUBTASK, COMPACTION = range(5)
TOKENS = "input_tokens,cache_read,cache_write,output_tokens,reasoning,known"
HEAD = f"role,created,completed,parent,provider,model,variant,summary,finish,error,cost,{TOKENS}"

SCHEMA = f"""
    CREATE TABLE trace_members(id TEXT PRIMARY KEY,parent TEXT) WITHOUT ROWID;
    CREATE TABLE trace_messages(
        session TEXT NOT NULL,id TEXT NOT NULL,role TEXT NOT NULL,created INTEGER NOT NULL,completed INTEGER,
        parent TEXT,provider TEXT,model TEXT,variant TEXT,summary INTEGER NOT NULL,finish TEXT,error TEXT,cost TEXT,
        input_tokens INTEGER,cache_read INTEGER,cache_write INTEGER,output_tokens INTEGER,reasoning INTEGER,known TEXT,
        kind INTEGER NOT NULL DEFAULT {OTHER},response INTEGER NOT NULL DEFAULT 0,step INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(session,id)
    ) WITHOUT ROWID;
    CREATE INDEX trace_visible ON trace_messages(session,created,id) WHERE kind IN ({PROMPT},{SUBTASK});
    CREATE INDEX trace_subtasks ON trace_messages(session,created,id) WHERE kind={SUBTASK};
    CREATE TABLE trace_choices(
        session TEXT NOT NULL,message TEXT NOT NULL,field TEXT NOT NULL,clock INTEGER NOT NULL,part TEXT NOT NULL,
        value TEXT NOT NULL,PRIMARY KEY(session,message,field)
    ) WITHOUT ROWID;
    CREATE TABLE trace_calls(
        clock INTEGER NOT NULL,id TEXT NOT NULL,session TEXT NOT NULL,message TEXT NOT NULL,step TEXT,cost TEXT,
        input_tokens INTEGER NOT NULL,cache_read INTEGER NOT NULL,cache_write INTEGER NOT NULL,
        output_tokens INTEGER NOT NULL,reasoning INTEGER NOT NULL,known TEXT NOT NULL,
        PRIMARY KEY(clock,id)
    ) WITHOUT ROWID;
"""


def _token_values(tokens):
    return ((tokens.input, tokens.cache_read, tokens.cache_write, tokens.output, tokens.reasoning,
             ",".join(tokens.known_fields)) if tokens is not None else (None,) * 6)


def _tokens(values):
    return TokenUsage(*values[:-1], known_fields=tuple(filter(None, values[-1].split(",")))) if values[-1] is not None else None


def _cost(value):
    return CostObservation(Decimal(value), "USD", CostKind.PROVIDER_REPORTED) if value is not None else None


def save_header(db, message):
    model = message.model
    db.execute(f"""
        INSERT INTO trace_messages(session,id,{HEAD}) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (message.session_id, message.message_id, message.role.value, message.created_at_ms, message.completed_at_ms,
          message.parent_message_id, model.provider if model else None, model.model if model else None, message.variant,
          message.summary, message.finish_reason, message.error_name,
          str(message.cost.amount) if message.cost else None, *_token_values(message.tokens)))


def load_header(row, source, session, message):
    role, created, completed, parent, provider, model, variant, summary, finish, error, cost = row[:11]
    return NormalizedMessage(
        message, session, MessageRole(role), created, source._event_provenance(session, message),
        completed_at_ms=completed, parent_message_id=parent,
        model=ModelRef(provider, model) if model is not None else None,
        variant=variant, summary=bool(summary), finish_reason=finish, error_name=error,
        cost=_cost(cost), tokens=_tokens(row[11:]),
    )


def save_call(db, invocation):
    completion = invocation.completed_at_ms
    clock = invocation.created_at_ms if completion is None else completion
    db.execute("""
        INSERT INTO trace_calls VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
    """, (clock, invocation.invocation_id, invocation.session_id, invocation.message_id, invocation.step_part_id,
          str(invocation.cost.amount) if invocation.cost else None, *_token_values(invocation.tokens)))


def load_call(row, source, header):
    _, invocation, session, message, step, cost, *tokens = row
    return ModelInvocation(
        invocation, session, header.created_at_ms, header.model, _tokens(tokens),
        source._event_provenance(session, step if step is not None else message),
        completed_at_ms=header.completed_at_ms, cost=_cost(cost), initiating_event_id=header.parent_message_id,
        message_id=message, step_part_id=step, variant=header.variant, summary=header.summary,
        finish_reason=header.finish_reason, error_name=header.error_name,
    )


def own_event(db, session, event):
    if event is None:
        return None, {}
    row = db.execute("""
        SELECT kind,created,provider,model,variant FROM trace_messages
        WHERE session=? AND id=? AND role='user'
    """, (session, event)).fetchone()
    if row is None:
        return None, {}
    kind, clock, provider, model, variant = row
    selection = {key: value for key, value in zip(
        ("provider_id", "model_id", "variant"), (provider, model, variant), strict=True) if value}
    selection.update(db.execute("""
        SELECT field,value FROM trace_choices WHERE session=? AND message=?
    """, (session, event)))
    if kind in (PROMPT, SUBTASK):
        return event, selection
    if kind not in (OTHER, SYNTHETIC):
        return None, selection
    bucket = db.execute(f"""
        SELECT created FROM trace_messages INDEXED BY trace_visible
        WHERE session=? AND created<=? AND kind IN ({PROMPT},{SUBTASK}) ORDER BY created DESC LIMIT 1
    """, (session, clock)).fetchone()
    if bucket is None or bucket[0] == clock:
        return None, selection
    predicate = f"kind={SUBTASK}" if kind == SYNTHETIC else f"kind IN ({PROMPT},{SUBTASK})"
    index = "trace_subtasks" if kind == SYNTHETIC else "trace_visible"
    owners = db.execute(f"""
        SELECT id FROM trace_messages INDEXED BY {index}
        WHERE session=? AND created=? AND {predicate} ORDER BY id LIMIT 2
    """, (session, bucket[0])).fetchall()
    return (owners[0][0] if len(owners) == 1 else None), selection
