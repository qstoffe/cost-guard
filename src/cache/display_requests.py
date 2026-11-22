"""Typed physical usage retained inside the display archive, not a trace cache."""
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal

from .display_prompts import DisplayPrompt, publish_prompts
from .display_stats_evidence import ResponseTiming, StatsCapture, publish_stats_evidence
from .display_stats_requests import StatsRequestIdentity
from .display_usage_reader import advance_usage_revision, usage_version

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
    dedup_tree: str | None = None
    ordinal: int = 0
    response: ResponseTiming | None = None
    stats_identity: StatsRequestIdentity | None = None

    def values(self, pricing):
        amounts = tuple(str(value) for value in self.category_costs) if self.category_costs else (None,) * 4
        return (self.key, self.clock_ms, self.fork_key, self.session_id, self.logical_prompt_id,
                self.provider, self.model, self.recorded_model, self.account_key, *self.tokens, self.known,
                str(self.billed) if self.billed is not None else None, self.currency, self.disposition,
                *amounts, pricing if self.category_costs is not None else None, self.effort, self.summary,
                self.dedup_tree, self.ordinal)


@dataclass(frozen=True, slots=True)
class RequestRoster:
    """An exact complete acquisition; no roster is published for partial reads."""
    pricing: str
    requests: tuple[DisplayRequest, ...]
    attribution: tuple[tuple[bytes, str], ...]  # physical key → causal root prompt
    prompts: tuple[DisplayPrompt, ...] | None = None
    stats: StatsCapture | None = None


REQUEST_COLUMNS = (
    "request_key", "clock_ms", "fork_key", "session_id", "logical_prompt_id", "provider", "model", "recorded_model",
    "account_key", "input_tokens", "cache_read_tokens", "cache_write_tokens", "output_tokens", "reasoning_tokens",
    "known_fields", "billed", "currency", "disposition", "input_cost", "cache_read_cost", "cache_write_cost",
    "output_cost", "pricing", "effort", "summary", "dedup_tree", "request_ordinal",
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
            effort TEXT, summary INTEGER NOT NULL, dedup_tree TEXT, request_ordinal INTEGER NOT NULL DEFAULT 0,
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


def countable_schema(*, upgrade=False):
    columns = """
        ALTER TABLE archive_requests ADD COLUMN dedup_tree TEXT;
        ALTER TABLE archive_requests ADD COLUMN request_ordinal INTEGER NOT NULL DEFAULT 0;
    """ if upgrade else ""
    return columns + """
        CREATE INDEX archive_fork_candidates ON archive_requests(source, fork_key, dedup_tree, request_ordinal, session_id)
            WHERE fork_key IS NOT NULL AND dedup_tree IS NOT NULL;
        CREATE INDEX archive_unqualified_forks ON archive_requests(source, clock_ms)
            WHERE fork_key IS NOT NULL AND dedup_tree IS NULL;
        CREATE TABLE archive_fork_trees (
            source TEXT NOT NULL REFERENCES sources(source), fork_key BLOB NOT NULL, dedup_tree TEXT NOT NULL,
            multiplicity INTEGER NOT NULL CHECK(multiplicity > 0),
            first_ordinal INTEGER NOT NULL, first_session TEXT NOT NULL,
            PRIMARY KEY(source, fork_key, dedup_tree)
        ) WITHOUT ROWID;
        CREATE INDEX archive_fork_rank ON archive_fork_trees(
            source, fork_key, multiplicity DESC, first_ordinal, first_session, dedup_tree);
        CREATE VIEW archive_countable_requests AS
            SELECT source,request_key,fork_key,clock_ms FROM archive_requests AS request
            WHERE fork_key IS NULL OR dedup_tree=(
                SELECT dedup_tree FROM archive_fork_trees
                WHERE source=request.source AND fork_key=request.fork_key
                ORDER BY multiplicity DESC,first_ordinal,first_session,dedup_tree LIMIT 1
            );
    """


def unqualified_forks(db, source, start_ms=None, end_ms=None):
    """True if the window contains preserved facts without proven fork membership."""
    bounds, args = [], [source]
    if start_ms is not None:
        bounds.append("clock_ms>=?")
        args.append(start_ms)
    if end_ms is not None:
        bounds.append("clock_ms<=?")
        args.append(end_ms)
    where = "".join(f" AND {bound}" for bound in bounds)
    return db.execute(f"""
        SELECT 1 FROM archive_requests
        WHERE source=? AND fork_key IS NOT NULL AND dedup_tree IS NULL{where}
        LIMIT 1
    """, args).fetchone() is not None


def _fork_candidates(db, source, keys):
    candidates = set()
    for offset in range(0, len(keys), 256):
        batch = keys[offset:offset + 256]
        parameters = ",".join("?" for _ in batch)
        candidates.update(db.execute(f"""
            SELECT request_key,fork_key,dedup_tree,request_ordinal,session_id FROM archive_requests
            WHERE source=? AND request_key IN ({parameters}) AND fork_key IS NOT NULL AND dedup_tree IS NOT NULL
        """, (source, *batch)))
    return candidates


def _update_fork_trees(db, source, before, after):
    # Visit only changed trees. A correction doesn't scan or rewrite the other
    # members of a large fork family, even when it changes the winning tree.
    delta = Counter((fork, tree) for _, fork, tree, _, _ in after - before)
    delta.subtract((fork, tree) for _, fork, tree, _, _ in before - after)
    forks = {fork for fork, _ in delta}

    def winner(fork):
        return db.execute("""
            SELECT dedup_tree FROM archive_fork_trees WHERE source=? AND fork_key=?
            ORDER BY multiplicity DESC,first_ordinal,first_session,dedup_tree LIMIT 1
        """, (source, fork)).fetchone()

    previous_winners = {fork: winner(fork) for fork in forks}
    for (fork, tree), change in delta.items():
        key = (source, fork, tree)
        previous = db.execute("""
            SELECT multiplicity FROM archive_fork_trees WHERE source=? AND fork_key=? AND dedup_tree=?
        """, key).fetchone()
        multiplicity = (previous[0] if previous else 0) + change
        if not multiplicity:
            db.execute("DELETE FROM archive_fork_trees WHERE source=? AND fork_key=? AND dedup_tree=?", key)
            continue
        first = db.execute("""
            SELECT request_ordinal,session_id FROM archive_requests
            WHERE source=? AND fork_key=? AND dedup_tree=?
            ORDER BY request_ordinal,session_id LIMIT 1
        """, key).fetchone()
        db.execute("""
            INSERT INTO archive_fork_trees VALUES(?, ?, ?, ?, ?, ?)
            ON CONFLICT(source, fork_key, dedup_tree) DO UPDATE SET
                (multiplicity, first_ordinal, first_session) =
                (excluded.multiplicity, excluded.first_ordinal, excluded.first_session)
        """, (*key, multiplicity, *first))
    # A newly added replica can displace older requests even if no existing
    # physical fact was updated. Unlike a plain insertion it invalidates
    # an in-flight old population.
    return any(prior is not None and prior != winner(fork) for fork, prior in previous_winners.items())


def publish_roster(db, source, root_id, revision, roster):
    """Record new positive evidence in the same transaction as the session CAS."""
    requests = {request.key: request for request in roster.requests}
    if (len(requests) != len(roster.requests)
            or len(requests) + len(roster.attribution) + len(roster.prompts or ()) > ROOT_WRITE_LIMIT
            or roster.stats is not None and len(roster.stats.intervals) + len(roster.stats.parents) > ROOT_WRITE_LIMIT
            or any(request.dedup_tree not in {None, root_id} for request in roster.requests)
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
    keys = tuple(requests)
    before = _fork_candidates(db, source, keys)
    values = {column: f"excluded.{column}" for column in REQUEST_COLUMNS[1:]}
    for column in prices:
        values[column] = f"CASE WHEN {keep_previous} THEN archive_requests.{column} ELSE excluded.{column} END"
    values["logical_prompt_id"] = """
        CASE WHEN excluded.summary THEN NULL ELSE coalesce(excluded.logical_prompt_id,
                                                            archive_requests.logical_prompt_id) END
    """
    updates = ", ".join(f"{column}={value}" for column, value in values.items())
    compared = ", ".join(f"archive_requests.{column}" for column in values)
    proposed = ", ".join(values.values())
    first_revision = usage_version(db, source).revision + 1
    written = db.executemany(f"""
        INSERT INTO archive_requests(source,first_revision, {fields}) VALUES(?, ?, {marks})
        ON CONFLICT(source, request_key) DO UPDATE SET {updates}
        WHERE (excluded.known_fields & archive_requests.known_fields) = archive_requests.known_fields
          AND (excluded.dedup_tree IS NOT NULL OR archive_requests.dedup_tree IS NULL)
          AND ({compared}) IS NOT ({proposed})
    """, ((source, first_revision, *request.values(roster.pricing)) for request in roster.requests))
    if written.rowcount:
        changed_winner = _update_fork_trees(db, source, before, _fork_candidates(db, source, keys))
        advance_usage_revision(db, source, changed_winner=changed_winner)
    # Missing requests/children may have been deleted from OpenCode, even when
    # the root still exists. A roster observes availability, not retraction.
    db.executemany("INSERT OR IGNORE INTO archive_request_membership VALUES(?, ?, ?)",
                   ((source, root_id, key) for key in requests))
    db.executemany("INSERT OR IGNORE INTO archive_prompt_attribution VALUES(?, ?, ?, ?)",
                    ((source, root_id, key, prompt) for key, prompt in roster.attribution))
    if roster.stats is not None:
        publish_stats_evidence(db, source, root_id, revision, roster.stats, roster.requests)
    return roster.prompts is not None and publish_prompts(db, source, root_id, revision, roster.prompts)
