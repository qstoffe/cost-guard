"""Typed physical usage retained inside the display archive, not a trace cache."""
from dataclasses import dataclass
from decimal import Decimal


TOKEN_FIELDS = ("input", "cache_read", "cache_write", "output", "reasoning")
ROOT_WRITE_LIMIT = 4096


@dataclass(frozen=True, slots=True)
class DisplayRequest:
    key: bytes
    clock_ms: int | None
    fork_key: bytes | None
    session_id: str
    logical_prompt_id: str | None
    provider: str
    model: str
    recorded_model: str
    account_key: bytes | None
    tokens: tuple[int, int, int, int, int]
    known: int
    billed: Decimal | None
    currency: str | None
    disposition: str
    category_costs: tuple[Decimal, Decimal, Decimal, Decimal] | None
    effort: str | None
    summary: bool

    def values(self, pricing):
        amounts = tuple(str(value) for value in self.category_costs) if self.category_costs else (None,) * 4
        return (self.key, self.clock_ms, self.fork_key, self.session_id, self.logical_prompt_id,
                self.provider, self.model, self.recorded_model, self.account_key, *self.tokens, self.known,
                str(self.billed) if self.billed is not None else None, self.currency, self.disposition,
                *amounts, pricing if self.category_costs is not None else None, self.effort, self.summary)


@dataclass(frozen=True, slots=True)
class RequestRoster:
    """An exact complete acquisition; no roster is published for partial reads."""
    pricing: str
    requests: tuple[DisplayRequest, ...]
    attribution: tuple[tuple[bytes, str], ...]  # physical key → causal root prompt


REQUEST_COLUMNS = (
    "request_key", "clock_ms", "fork_key", "session_id", "logical_prompt_id", "provider", "model", "recorded_model",
    "account_key", "input_tokens", "cache_read_tokens", "cache_write_tokens", "output_tokens", "reasoning_tokens",
    "known_fields", "billed", "currency", "disposition", "input_cost", "cache_read_cost", "cache_write_cost",
    "output_cost", "pricing", "effort", "summary",
)


def request_schema():
    return """
        CREATE TABLE archive_requests (
            source TEXT NOT NULL REFERENCES sources(source),
            request_key BLOB NOT NULL,
            clock_ms INTEGER, fork_key BLOB,
            session_id TEXT NOT NULL, logical_prompt_id TEXT,
            provider TEXT NOT NULL, model TEXT NOT NULL, recorded_model TEXT NOT NULL, account_key BLOB,
            input_tokens INTEGER NOT NULL, cache_read_tokens INTEGER NOT NULL, cache_write_tokens INTEGER NOT NULL,
            output_tokens INTEGER NOT NULL, reasoning_tokens INTEGER NOT NULL, known_fields INTEGER NOT NULL,
            billed TEXT, currency TEXT, disposition TEXT NOT NULL,
            input_cost TEXT, cache_read_cost TEXT, cache_write_cost TEXT, output_cost TEXT, pricing TEXT,
            effort TEXT, summary INTEGER NOT NULL,
            PRIMARY KEY(source, request_key)
        ) WITHOUT ROWID;
        CREATE INDEX archive_request_clock ON archive_requests(source, clock_ms, request_key);
        CREATE TABLE archive_request_rosters (
            source TEXT NOT NULL, root_id TEXT NOT NULL, revision TEXT NOT NULL, pricing TEXT NOT NULL,
            PRIMARY KEY(source, root_id),
            FOREIGN KEY(source, root_id) REFERENCES sessions(source, session_id) ON DELETE CASCADE
        ) WITHOUT ROWID;
        CREATE TABLE archive_request_membership (
            source TEXT NOT NULL, root_id TEXT NOT NULL, request_key BLOB NOT NULL,
            PRIMARY KEY(source, root_id, request_key),
            FOREIGN KEY(source, root_id) REFERENCES archive_request_rosters(source, root_id) ON DELETE CASCADE,
            FOREIGN KEY(source, request_key) REFERENCES archive_requests(source, request_key)
        ) WITHOUT ROWID;
        CREATE INDEX archive_request_owners ON archive_request_membership(source, request_key);
        CREATE TABLE archive_prompt_attribution (
            source TEXT NOT NULL, root_id TEXT NOT NULL, request_key BLOB NOT NULL, prompt_id TEXT NOT NULL,
            PRIMARY KEY(source, root_id, request_key, prompt_id),
            FOREIGN KEY(source, root_id, request_key)
                REFERENCES archive_request_membership(source, root_id, request_key) ON DELETE CASCADE
        ) WITHOUT ROWID;
    """


def publish_roster(db, source, root_id, revision, roster):
    """Record new positive evidence in the same transaction as the session CAS."""
    requests = {request.key: request for request in roster.requests}
    if (len(requests) != len(roster.requests) or len(requests) + len(roster.attribution) > ROOT_WRITE_LIMIT
            or not roster.pricing or any(key not in requests or not prompt for key, prompt in roster.attribution)):
        raise ValueError("invalid_request_roster")
    db.execute("""
        INSERT INTO archive_request_rosters VALUES(?, ?, ?, ?)
        ON CONFLICT(source, root_id) DO UPDATE SET revision=excluded.revision, pricing=excluded.pricing
    """, (source, root_id, revision, roster.pricing))
    fields = ", ".join(REQUEST_COLUMNS)
    marks = ", ".join("?" for _ in REQUEST_COLUMNS)
    # A new price failure on unchanged inputs is not evidence against the
    # prior valuation. Never attach old valuation to a changed token vector.
    valuation_columns = ("provider", "model", "recorded_model", *(
        f"{field}_tokens" for field in TOKEN_FIELDS), "known_fields")
    left = ",".join(f"excluded.{column}" for column in valuation_columns)
    right = ",".join(f"archive_requests.{column}" for column in valuation_columns)
    keep_previous = f"excluded.pricing IS NULL AND ({left}) IS ({right})"
    prices = {"input_cost", "cache_read_cost", "cache_write_cost", "output_cost", "pricing"}
    updates = ", ".join(f"{column}=CASE WHEN {keep_previous} THEN archive_requests.{column} "
                       f"ELSE excluded.{column} END" if column in prices else f"{column}=excluded.{column}"
                       for column in REQUEST_COLUMNS[1:])
    db.executemany(f"""
        INSERT INTO archive_requests(source, {fields}) VALUES(?, {marks})
        ON CONFLICT(source, request_key) DO UPDATE SET {updates}
        WHERE (excluded.known_fields & archive_requests.known_fields) = archive_requests.known_fields
    """, ((source, *request.values(roster.pricing)) for request in roster.requests))
    # Missing requests/children may have been deleted from OpenCode, even when
    # the root still exists. A roster observes availability, not retraction.
    db.executemany("INSERT OR IGNORE INTO archive_request_membership VALUES(?, ?, ?)",
                   ((source, root_id, key) for key in requests))
    db.executemany("INSERT OR IGNORE INTO archive_prompt_attribution VALUES(?, ?, ?, ?)",
                   ((source, root_id, key, prompt) for key, prompt in roster.attribution))
