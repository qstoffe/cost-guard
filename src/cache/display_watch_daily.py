"""Independent local-day summary from the Watch observer, not a second ledger."""
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class WatchDaily:
    timezone_id: str
    day_start_ms: int
    day_end_ms: int
    observed_at_ms: int
    known_ccost: Decimal | None
    cost_complete: bool
    prompt_count: int
    prompt_count_complete: bool


def daily_schema():
    return """
        CREATE TABLE IF NOT EXISTS archive_watch_daily (
            source TEXT PRIMARY KEY REFERENCES archive_watch_state(source) ON DELETE CASCADE,
            timezone_id TEXT NOT NULL, day_start_ms INTEGER NOT NULL, day_end_ms INTEGER NOT NULL,
            observed_at_ms INTEGER NOT NULL, known_ccost TEXT, cost_complete INTEGER NOT NULL,
            prompt_count INTEGER NOT NULL, prompt_count_complete INTEGER NOT NULL
        ) WITHOUT ROWID;
    """


def publish_daily(db, source, daily):
    if daily is None:
        return False
    cost = str(daily.known_ccost) if daily.known_ccost is not None else None
    value = (daily.timezone_id, daily.day_start_ms, daily.day_end_ms, daily.observed_at_ms,
             cost, daily.cost_complete, daily.prompt_count, daily.prompt_count_complete)
    return db.execute("""
        INSERT INTO archive_watch_daily VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source) DO UPDATE SET
            (timezone_id,day_start_ms,day_end_ms,observed_at_ms,known_ccost,cost_complete,prompt_count,prompt_count_complete) =
            (excluded.timezone_id,excluded.day_start_ms,excluded.day_end_ms,excluded.observed_at_ms,
             excluded.known_ccost,excluded.cost_complete,excluded.prompt_count,excluded.prompt_count_complete)
        WHERE excluded.observed_at_ms>archive_watch_daily.observed_at_ms OR
              (excluded.observed_at_ms=archive_watch_daily.observed_at_ms
               AND excluded.timezone_id!=archive_watch_daily.timezone_id)
    """, (source, *value)).rowcount > 0


def read_daily(db, source, now_ms, timezone_id):
    row = db.execute("""
        SELECT day_start_ms,day_end_ms,observed_at_ms,known_ccost,cost_complete,prompt_count,prompt_count_complete
        FROM archive_watch_daily
        WHERE source=? AND timezone_id=? AND day_start_ms<=? AND day_end_ms>? AND observed_at_ms<=?
    """, (source, timezone_id, now_ms, now_ms, now_ms)).fetchone()
    if row is None:
        return None
    start, end, observed, cost, priced, prompts, complete = row
    return dict(day_start_ms=start, day_end_ms=end, observed_at_ms=observed, known_ccost=cost,
                cost_complete=bool(priced), prompt_count=prompts, prompt_count_complete=bool(complete))
