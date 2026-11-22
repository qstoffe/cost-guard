"""Small indexed Session Detail facts; no transcripts, previews or tool payloads."""
from dataclasses import dataclass, fields
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class DisplayPrompt:
    event_id: str
    start_ms: int | None
    finish_ms: int | None
    duration_ms: int | None
    kind: str
    number: int | None
    model: str | None
    effort: str | None
    calls: int
    context_tokens: int | None
    observed_cost: Decimal | None
    cost_complete: bool
    incoming_cost: Decimal | None
    extra_cost: Decimal | None
    mix: str | None
    outcome: str

    def sql_values(self):
        values = (getattr(self, field.name) for field in fields(self))
        return tuple(str(value) if isinstance(value, Decimal) else value for value in values)


def prompt_schema():
    return """
        CREATE TABLE archive_prompt_history (
            source TEXT NOT NULL, root_id TEXT NOT NULL, event_id TEXT NOT NULL,
            start_ms INTEGER, finish_ms INTEGER, duration_ms INTEGER,
            kind TEXT NOT NULL, number INTEGER, model TEXT, effort TEXT, calls INTEGER NOT NULL,
            context_tokens INTEGER, observed_cost TEXT, cost_complete INTEGER NOT NULL,
            incoming_cost TEXT, extra_cost TEXT, mix TEXT, outcome TEXT NOT NULL,
            PRIMARY KEY(source, root_id, event_id),
            FOREIGN KEY(source, root_id) REFERENCES sessions(source, session_id) ON DELETE CASCADE
        ) WITHOUT ROWID;
        CREATE INDEX archive_prompt_order ON archive_prompt_history(source, root_id, start_ms DESC, event_id);
        CREATE TABLE archive_prompt_state (
            source TEXT NOT NULL, root_id TEXT NOT NULL, revision TEXT NOT NULL,
            PRIMARY KEY(source, root_id),
            FOREIGN KEY(source, root_id) REFERENCES sessions(source, session_id) ON DELETE CASCADE
        ) WITHOUT ROWID;
    """


def publish_prompts(db, source, root, revision, prompts):
    expected = db.execute("""
        SELECT revision FROM archive_prompt_state WHERE source=? AND root_id=?
    """, (source, root)).fetchone()
    changed = expected != (revision,)
    db.execute("""
        INSERT INTO archive_prompt_state VALUES(?, ?, ?)
        ON CONFLICT(source, root_id) DO UPDATE SET revision=excluded.revision
            WHERE archive_prompt_state.revision IS NOT excluded.revision
    """, (source, root, revision))
    updates = dict(
        start_ms="coalesce(excluded.start_ms, archive_prompt_history.start_ms)",
        finish_ms="coalesce(excluded.finish_ms, archive_prompt_history.finish_ms)",
        duration_ms="coalesce(excluded.duration_ms, archive_prompt_history.duration_ms)",
        kind="excluded.kind", number="excluded.number",
        model="coalesce(excluded.model, archive_prompt_history.model)",
        effort="coalesce(excluded.effort, archive_prompt_history.effort)", calls="excluded.calls",
        context_tokens="coalesce(excluded.context_tokens, archive_prompt_history.context_tokens)",
        observed_cost=("CASE WHEN archive_prompt_history.cost_complete AND NOT excluded.cost_complete "
                       "THEN archive_prompt_history.observed_cost ELSE excluded.observed_cost END"),
        cost_complete="max(excluded.cost_complete, archive_prompt_history.cost_complete)",
        incoming_cost="coalesce(excluded.incoming_cost, archive_prompt_history.incoming_cost)",
        extra_cost="coalesce(excluded.extra_cost, archive_prompt_history.extra_cost)",
        mix="coalesce(excluded.mix, archive_prompt_history.mix)",
        outcome="excluded.outcome",
    )
    columns = ", ".join(updates)
    values = ", ".join(updates.values())
    count = db.executemany(f"""
        INSERT INTO archive_prompt_history VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source, root_id, event_id) DO UPDATE SET ({columns})=({values})
            WHERE ({columns}) IS NOT ({values})
    """, ((source, root, *prompt.sql_values()) for prompt in prompts)).rowcount
    return changed or count > 0


def prompt_page(db, source, root, limit, offset):
    return tuple(DisplayPrompt(*row[:10], decimal(row[10]), bool(row[11]), decimal(row[12]), decimal(row[13]), *row[14:])
                 for row in db.execute("""
        SELECT event_id,start_ms,finish_ms,duration_ms,kind,number,model,effort,calls,context_tokens,
               observed_cost,cost_complete,incoming_cost,extra_cost,mix,outcome
        FROM archive_prompt_history WHERE source=? AND root_id=?
        ORDER BY start_ms DESC,event_id LIMIT ? OFFSET ?
    """, (source, root, limit, offset)))


def decimal(value):
    return None if value is None else Decimal(value)
