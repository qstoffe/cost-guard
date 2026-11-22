"""Replaceable typed native quota rows; never historical account attribution."""
from dataclasses import dataclass, fields


WATCH_ACCOUNT_LIMIT = 32


@dataclass(frozen=True, slots=True)
class WatchQuotaFact:
    account_id: str
    provider_id: str
    label: str
    observed_ms: int
    stale: bool
    quota_label: str
    period: str
    used: str | None
    capacity: str | None
    remaining: str | None
    remaining_fraction: str | None
    unit: str | None
    reset_ms: int | None
    duration_seconds: int | None
    status: str
    unlimited: bool
    remaining_money: str | None
    limit_money: str | None
    window_active: bool | None


@dataclass(frozen=True, slots=True)
class WatchQuotaBatch:
    revision: int
    facts: tuple[WatchQuotaFact, ...]


def watch_quota_schema():
    return """
        CREATE TABLE IF NOT EXISTS archive_watch_quota_state (
            source TEXT PRIMARY KEY REFERENCES archive_watch_state(source) ON DELETE CASCADE,
            binding TEXT NOT NULL, revision INTEGER NOT NULL
        ) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS archive_watch_quotas (
            source TEXT NOT NULL REFERENCES archive_watch_quota_state(source) ON DELETE CASCADE,
            position INTEGER NOT NULL,
            account_id TEXT NOT NULL, provider_id TEXT NOT NULL, label TEXT NOT NULL,
            observed_ms INTEGER NOT NULL, stale INTEGER NOT NULL, quota_label TEXT NOT NULL,
            period TEXT NOT NULL, used TEXT, capacity TEXT, remaining TEXT, remaining_fraction TEXT,
            unit TEXT, reset_ms INTEGER, duration_seconds INTEGER, status TEXT NOT NULL, unlimited INTEGER NOT NULL,
            remaining_money TEXT, limit_money TEXT, window_active INTEGER,
            PRIMARY KEY(source, position)
        ) WITHOUT ROWID;
    """


def publish_watch_quotas(db, source, binding, value):
    if value is None:
        return False
    if not 0 < value.revision or len(value.facts) > WATCH_ACCOUNT_LIMIT:
        raise ValueError("invalid_watch_quota")
    changed = db.execute("""
        INSERT INTO archive_watch_quota_state VALUES(?,?,?)
        ON CONFLICT(source) DO UPDATE SET binding=excluded.binding, revision=excluded.revision
        WHERE binding != excluded.binding OR revision < excluded.revision
    """, (source, binding, value.revision)).rowcount
    if not changed:
        return False
    db.execute("DELETE FROM archive_watch_quotas WHERE source=?", (source,))
    names = tuple(field.name for field in fields(WatchQuotaFact))
    marks = ",".join("?" for _ in range(2 + len(names)))
    db.executemany(f"INSERT INTO archive_watch_quotas VALUES({marks})",
                   ((source, index, *(getattr(fact, name) for name in names)) for index, fact in enumerate(value.facts)))
    return True


def read_watch_quotas(db, source, binding):
    state = db.execute("SELECT revision FROM archive_watch_quota_state WHERE source=? AND binding=?",
                       (source, binding)).fetchone()
    if state is None:
        return None
    names = ", ".join(field.name for field in fields(WatchQuotaFact))
    return WatchQuotaBatch(state[0], tuple(WatchQuotaFact(*values) for values in db.execute(
        f"SELECT {names} FROM archive_watch_quotas WHERE source=? ORDER BY position LIMIT ?",
        (source, WATCH_ACCOUNT_LIMIT))))
