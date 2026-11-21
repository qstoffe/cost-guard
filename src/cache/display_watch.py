"""One replaceable typed Watch/Mini snapshot per authorized source."""
from dataclasses import dataclass, fields
from decimal import Decimal

from .display_watch_daily import WatchDaily, daily_schema, publish_daily, read_daily

WATCH_ROW_LIMIT = 512
WATCH_LIVE_MS = 15_000
_CARD_METRICS = (
    ("prompt_number", "INTEGER"), ("prompt_duration_ms", "INTEGER"), ("is_compaction", "INTEGER"),
    ("incoming_context_tokens", "INTEGER"), ("context_delta_tokens", "INTEGER"),
    ("mix_input", "INTEGER"), ("mix_read", "INTEGER"), ("mix_write", "INTEGER"), ("mix_output", "INTEGER"),
    ("abort_reason", "TEXT"), ("catalog_activity_ms", "INTEGER"),
)


@dataclass(frozen=True, slots=True)
class WatchFact:
    session_id: str
    event_id: str
    title: str
    group: str
    start_ms: int | None
    finish_ms: int | None
    outcome: str | None
    prompt_cost: Decimal | None
    prompt_cost_complete: bool
    session_cost: Decimal | None
    session_cost_complete: bool
    context_tokens: int | None
    model: str | None
    effort: str | None
    calls: int | None
    duration_ms: int | None
    qualified_ms: int | None
    prompt_number: int | None = None
    prompt_duration_ms: int | None = None
    is_compaction: bool | None = None
    incoming_context_tokens: int | None = None
    context_delta_tokens: int | None = None
    mix_input: int | None = None
    mix_read: int | None = None
    mix_write: int | None = None
    mix_output: int | None = None
    abort_reason: str | None = None
    catalog_activity_ms: int | None = None

    def values(self):
        values = (getattr(self, field.name) for field in fields(self))
        return tuple(str(value) if isinstance(value, Decimal) else value for value in values)


@dataclass(frozen=True, slots=True)
class WatchObservation:
    observed_ms: int
    projected_ms: int
    state: str | None
    truncated: bool
    facts: tuple[WatchFact, ...] | None
    daily: WatchDaily | None = None


def watch_schema(*, upgrade=False):
    metrics = ", ".join(f"{column} {kind}" for column, kind in _CARD_METRICS)
    if upgrade:
        return "\n".join(f"ALTER TABLE archive_watch_cards ADD COLUMN {column} {kind};"
                         for column, kind in _CARD_METRICS) + daily_schema()
    return f"""
        CREATE TABLE IF NOT EXISTS archive_watch_state (
            source TEXT PRIMARY KEY REFERENCES sources(source),
            binding TEXT NOT NULL, generation INTEGER NOT NULL,
            observed_ms INTEGER NOT NULL, projected_ms INTEGER NOT NULL,
            state TEXT, truncated INTEGER NOT NULL
        ) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS archive_watch_cards (
            source TEXT NOT NULL REFERENCES archive_watch_state(source) ON DELETE CASCADE,
            position INTEGER NOT NULL, session_id TEXT NOT NULL, event_id TEXT NOT NULL, title TEXT NOT NULL,
            card_group TEXT NOT NULL, start_ms INTEGER, finish_ms INTEGER, outcome TEXT,
            prompt_cost TEXT, prompt_cost_complete INTEGER NOT NULL,
            session_cost TEXT, session_cost_complete INTEGER NOT NULL,
            context_tokens INTEGER, model TEXT, effort TEXT, calls INTEGER, duration_ms INTEGER, qualified_ms INTEGER,
            {metrics}, PRIMARY KEY(source, position)
        ) WITHOUT ROWID;
    """ + daily_schema()


def publish_watch(db, source, binding, observation):
    if (not source or not binding or not 0 < observation.observed_ms <= observation.projected_ms
            or len(observation.facts or ()) > WATCH_ROW_LIMIT):
        raise ValueError("invalid_watch_observation")
    old = db.execute("""
        SELECT binding,generation,observed_ms,projected_ms FROM archive_watch_state WHERE source=?
    """, (source,)).fetchone()
    newer_cards = observation.facts is not None and (old is None or old[0] != binding
        or (observation.observed_ms, observation.projected_ms) > old[2:])
    generation = old[1] + 1 if old else 1
    if newer_cards:
        db.execute("""
            INSERT INTO archive_watch_state VALUES(?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source) DO UPDATE SET (binding,generation,observed_ms,projected_ms,state,truncated)=
                (excluded.binding,excluded.generation,excluded.observed_ms,excluded.projected_ms,excluded.state,
                 excluded.truncated)
        """, (source, binding, generation, observation.observed_ms, observation.projected_ms,
              observation.state, observation.truncated))
        db.execute("DELETE FROM archive_watch_cards WHERE source=?", (source,))
        marks = ", ".join("?" for _ in range(2 + len(fields(WatchFact))))
        db.executemany(f"INSERT INTO archive_watch_cards VALUES({marks})",
                       ((source, offset, *fact.values()) for offset, fact in enumerate(observation.facts)))
    elif old is None:
        if observation.daily is None:
            return None
        db.execute("INSERT INTO archive_watch_state VALUES(?,?,?,0,0,NULL,0)", (source, binding, generation))
    newer_daily = publish_daily(db, source, observation.daily)
    if not newer_cards:
        if not newer_daily:
            return None
        db.execute("UPDATE archive_watch_state SET generation=? WHERE source=?", (generation, source))
    return generation


def watch_snapshot(db, source, binding, now_ms, *, live_eligible, timezone_id):
    state = db.execute("""
        SELECT binding,generation,observed_ms,projected_ms,state,truncated FROM archive_watch_state WHERE source=?
    """, (source,)).fetchone()
    if state is None:
        return dict(generation=0, freshness="empty", observed_ms=None, projected_ms=None, expires_ms=None,
                    state=None, truncated=False, cards=[], daily=None)
    issued, generation, observed, projected, card_state, truncated = state
    current = bool(observed and live_eligible and issued == binding and 0 <= now_ms - observed < WATCH_LIVE_MS)
    expires_ms = observed + WATCH_LIVE_MS if current else None
    cards = []
    keys = tuple(field.name for field in fields(WatchFact))
    metrics = ", ".join(column for column, _ in _CARD_METRICS)
    for values in db.execute(f"""
        SELECT session_id,event_id,title,card_group,start_ms,finish_ms,outcome,prompt_cost,prompt_cost_complete,
               session_cost,session_cost_complete,context_tokens,model,effort,calls,duration_ms,qualified_ms,{metrics}
        FROM archive_watch_cards WHERE source=? ORDER BY position LIMIT ?
    """, (source, WATCH_ROW_LIMIT)):
        facts = dict(zip(keys, values))
        for name in ("prompt_cost_complete", "session_cost_complete"):
            facts[name] = bool(facts[name])
        if facts["is_compaction"] is not None:
            facts["is_compaction"] = bool(facts["is_compaction"])
        proof = facts.pop("qualified_ms")
        if facts["outcome"] == "running":
            if current and proof is not None and 0 <= now_ms - proof < WATCH_LIVE_MS:
                expires_ms = min(expires_ms, proof + WATCH_LIVE_MS)
            else:
                _withdraw_running(facts)
        cards.append(facts)
    return dict(generation=generation, freshness="current" if current else "as-of" if observed else "empty",
                observed_ms=observed or None, projected_ms=projected or None,
                state=card_state if current else "retained" if observed else None,
                expires_ms=expires_ms, truncated=bool(truncated), cards=cards,
                daily=read_daily(db, source, now_ms, timezone_id))


def withdraw_watch_liveness(value):
    """Downgrade this same read when qualification is lost while serving it."""
    value.update(freshness="as-of", state="retained", expires_ms=None)
    for fact in value["cards"]:
        if fact["outcome"] == "running":
            _withdraw_running(fact)


def _withdraw_running(fact):
    fact.update(outcome="unverified", context_delta_tokens=None, prompt_duration_ms=None)
