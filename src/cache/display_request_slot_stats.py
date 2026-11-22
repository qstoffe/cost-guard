"""Stats request candidates for a pinned private usage slot, not live readiness."""
from dataclasses import dataclass
from decimal import Decimal

from .display_request_overlay import BirthCursor, request_birth_slice
from .display_requests import REQUEST_COLUMNS
from .display_stats_evidence import ResponseTiming
from .display_stats_requests import StatsCandidate, StatsRequestIdentity
from .display_stats_revision import StatsVersion, retained_stats_version
from .display_usage_reader import USAGE_SLICE, UsageInput


_SHAPE = tuple(REQUEST_COLUMNS.index(column) for column in (
    "clock_ms", "dedup_tree", "provider", "model", "recorded_model", "known_fields", "effort", "request_ordinal",
))
_PRICING = REQUEST_COLUMNS.index("pricing")
_CATEGORY = slice(REQUEST_COLUMNS.index("input_cost"), _PRICING)


@dataclass(frozen=True, slots=True)
class SlotStatsCursor:
    version: StatsVersion
    birth: BirthCursor


@dataclass(frozen=True, slots=True)
class SlotStatsSlice:
    version: StatsVersion
    entries: tuple[StatsCandidate, ...]
    next_cursor: SlotStatsCursor | None


def slot_stats_candidates(db, source, *, slot, expected=None, cursor=None, limit=USAGE_SLICE):
    if not db.in_transaction:
        raise ValueError("slot Stats reads require a pinned transaction")
    if cursor is not None:
        if expected is not None and expected != cursor.version:
            return None
        expected = cursor.version
    version = retained_stats_version(db, source, expected)
    if version is None:
        return None
    page = request_birth_slice(db, source, version.usage.revision, slot=slot,
                               cursor=cursor.birth if cursor else None, limit=limit)
    if page is None:
        return None
    entries = tuple(_candidate(db, source, version.evidence, row) for row in page.rows)
    resume = SlotStatsCursor(version, page.next_cursor) if page.next_cursor is not None else None
    return SlotStatsSlice(version, entries, resume)


def _candidate(db, source, evidence, row):
    key, clock, fork, session, prompt, provider, model, recorded, account = row[:9]
    pricing = row[_PRICING]
    costs = None if pricing is None else tuple(map(Decimal, row[_CATEGORY]))
    usage = UsageInput(key, clock, session, prompt, provider, model, recorded, account,
                       row[9:14], row[14], costs, pricing)
    shape = tuple(row[index] for index in _SHAPE)
    *_, tree, ordinal, _ = row
    identity, timing = _compatible_evidence(db, source, evidence, key, shape)
    return StatsCandidate(usage, identity, timing, fork, tree, ordinal)


def _compatible_evidence(db, source, evidence, key, shape):
    evidence_row = db.execute("""
        SELECT r.clock_ms,r.dedup_tree,r.provider,r.model,r.recorded_model,r.known_fields,r.effort,r.request_ordinal,
               i.message_key,i.step_key,i.sample_hash,i.source_model_key,i.effort,
               t.start_ms,t.duration_ms,t.excluded
        FROM archive_requests AS r
        LEFT JOIN archive_stats_request_identity AS i ON (i.source,i.request_key)=(r.source,r.request_key)
                                                        AND i.first_revision<=?
        LEFT JOIN archive_response_timing AS t ON (t.source,t.request_key)=(r.source,r.request_key)
                                                 AND t.completion_ms=r.clock_ms AND t.first_revision<=?
        WHERE r.source=? AND r.request_key=?
    """, (evidence, evidence, source, key)).fetchone()
    if evidence_row is None:
        return None, None
    identity = (StatsRequestIdentity(*evidence_row[8:13])
                if evidence_row[:8] == shape and evidence_row[8] is not None else None)
    timing = (ResponseTiming(evidence_row[13], evidence_row[14], bool(evidence_row[15]))
              if evidence_row[:2] == shape[:2] and evidence_row[15] is not None else None)
    return identity, timing
