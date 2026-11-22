"""Pre-reconciliation input to Stats. A missing recipe is not an accepted candidate."""
from dataclasses import dataclass
from decimal import Decimal

from .display_stats_evidence import ResponseTiming
from .display_stats_revision import StatsVersion, retained_stats_version
from .display_usage_reader import USAGE_SLICE, UsageInput


@dataclass(frozen=True, slots=True)
class StatsRequestIdentity:
    message_key: bytes
    step_key: bytes | None
    sample_hash: bytes
    source_model_key: bytes
    effort: str


@dataclass(frozen=True, slots=True)
class StatsCandidate:
    usage: UsageInput
    identity: StatsRequestIdentity | None
    response: ResponseTiming | None
    fork: bytes | None
    tree: str | None
    ordinal: int


@dataclass(frozen=True, slots=True)
class StatsCandidateSlice:
    version: StatsVersion
    entries: tuple[StatsCandidate, ...]
    next_cursor: tuple[int, bytes] | None


def stats_request_schema():
    return """
        CREATE TABLE IF NOT EXISTS archive_stats_request_identity (
            source TEXT NOT NULL, request_key BLOB NOT NULL,
            message_key BLOB NOT NULL CHECK(length(message_key)=32),
            step_key BLOB CHECK(step_key IS NULL OR length(step_key)=32),
            sample_hash BLOB NOT NULL CHECK(length(sample_hash)=32),
            source_model_key BLOB NOT NULL CHECK(length(source_model_key)=32),
            effort TEXT NOT NULL, first_revision INTEGER NOT NULL,
            PRIMARY KEY(source,request_key),
            FOREIGN KEY(source,request_key) REFERENCES archive_requests(source,request_key) ON DELETE CASCADE
        ) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS archive_stats_request_ready (
            source TEXT NOT NULL, root_id TEXT NOT NULL, source_revision TEXT NOT NULL,
            PRIMARY KEY(source,root_id),
            FOREIGN KEY(source,root_id) REFERENCES archive_stats_roots(source,root_id) ON DELETE CASCADE
        ) WITHOUT ROWID;
        CREATE TRIGGER IF NOT EXISTS archive_stats_request_identity_stale AFTER UPDATE ON archive_requests
        WHEN (OLD.clock_ms,OLD.dedup_tree,OLD.provider,OLD.model,OLD.recorded_model,OLD.effort,OLD.request_ordinal)
          IS NOT (NEW.clock_ms,NEW.dedup_tree,NEW.provider,NEW.model,NEW.recorded_model,NEW.effort,NEW.request_ordinal)
        BEGIN
            DELETE FROM archive_stats_request_identity WHERE source=NEW.source AND request_key=NEW.request_key;
            DELETE FROM archive_stats_request_ready WHERE source=NEW.source
                AND root_id IN (OLD.dedup_tree,NEW.dedup_tree);
        END;
    """


def read_stats_candidates(db, source, *, expected=None, after=None):
    version = retained_stats_version(db, source, expected)
    if version is None:
        return None
    resume = "AND (r.first_revision,r.request_key)>(?,?)" if after is not None else ""
    rows = db.execute(f"""
        SELECT r.request_key,r.clock_ms,r.session_id,r.logical_prompt_id,r.provider,r.model,r.recorded_model,r.account_key,
               r.input_tokens,r.cache_read_tokens,r.cache_write_tokens,r.output_tokens,r.reasoning_tokens,r.known_fields,
               r.input_cost,r.cache_read_cost,r.cache_write_cost,r.output_cost,r.pricing,
               i.message_key,i.step_key,i.sample_hash,i.source_model_key,i.effort,
               t.start_ms,t.duration_ms,t.excluded,r.fork_key,r.dedup_tree,r.request_ordinal,r.first_revision
        FROM archive_requests AS r INDEXED BY archive_requests_revision
        LEFT JOIN archive_stats_request_identity AS i ON (i.source,i.request_key)=(r.source,r.request_key)
                                                        AND i.first_revision<=?
        LEFT JOIN archive_response_timing AS t ON (t.source,t.request_key)=(r.source,r.request_key)
                                                 AND t.completion_ms=r.clock_ms AND t.first_revision<=?
        WHERE r.source=? AND r.first_revision<=? {resume}
        ORDER BY r.first_revision,r.request_key LIMIT ?
    """, (version.evidence, version.evidence, source, version.usage.revision, *(after or ()), USAGE_SLICE + 1)).fetchall()
    cursor = (rows[USAGE_SLICE - 1][-1], rows[USAGE_SLICE - 1][0]) if len(rows) > USAGE_SLICE else None
    return StatsCandidateSlice(version, tuple(map(_candidate, rows[:USAGE_SLICE])), cursor)


def _candidate(row):
    costs = None if row[18] is None else tuple(map(Decimal, row[14:18]))
    usage = UsageInput(*row[:8], row[8:13], row[13], costs, row[18])
    identity = StatsRequestIdentity(*row[19:24]) if row[19] is not None else None
    response = ResponseTiming(row[24], row[25], bool(row[26])) if row[26] is not None else None
    return StatsCandidate(usage, identity, response, *row[27:30])
