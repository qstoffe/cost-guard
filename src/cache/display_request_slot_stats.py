"""Stats request candidates for a pinned private usage slot, not live readiness."""
from dataclasses import dataclass
from decimal import Decimal

from .display_request_overlay import BirthCursor, request_birth_slice
from .display_requests import REQUEST_COLUMNS
from .display_stats_evidence import ResponseTiming
from .display_stats_requests import StatsCandidate, StatsRequestIdentity
from .display_stats_revision import StatsVersion, retained_stats_version
from .display_usage_reader import USAGE_SLICE, UsageInput


TIMING_SHAPE = ("clock_ms", "dedup_tree")
IDENTITY_SHAPE = (*TIMING_SHAPE, "provider", "model", "recorded_model", "known_fields", "effort", "request_ordinal",
                  "logical_prompt_id")
_SHAPE = tuple(REQUEST_COLUMNS.index(column) for column in IDENTITY_SHAPE)
_BASE_SHAPE = ",".join(f"r.{column}" for column in IDENTITY_SHAPE)
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
    entries = tuple(_candidate(db, source, version.evidence, slot, row) for row in page.rows)
    resume = SlotStatsCursor(version, page.next_cursor) if page.next_cursor is not None else None
    return SlotStatsSlice(version, entries, resume)


def _candidate(db, source, evidence, slot, row):
    key, clock, fork, session, prompt, provider, model, recorded, account = row[:9]
    pricing = row[_PRICING]
    costs = None if pricing is None else tuple(map(Decimal, row[_CATEGORY]))
    usage = UsageInput(key, clock, session, prompt, provider, model, recorded, account,
                       row[9:14], row[14], costs, pricing)
    shape = tuple(row[index] for index in _SHAPE)
    *_, tree, ordinal, _ = row
    identity, timing = _compatible_evidence(db, source, evidence, slot, key, shape)
    return StatsCandidate(usage, identity, timing, fork, tree, ordinal)


def _compatible_evidence(db, source, evidence, slot, key, shape):
    evidence_row = db.execute(f"""
        SELECT {_BASE_SHAPE},
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
    base, (message, step, sample, model, effort, start, duration, excluded) = (
        evidence_row[:len(_SHAPE)], evidence_row[len(_SHAPE):])
    identity = StatsRequestIdentity(message, step, sample, model, effort) if base == shape and message is not None else None
    if identity is not None and slot is not None:
        observed = slot_stats_recipe(db, slot, key)
        if observed is not None and observed != (message, step, sample, model, effort):
            identity = None
    timing = ResponseTiming(start, duration, bool(excluded)) if base[:2] == shape[:2] and excluded is not None else None
    return identity, timing


def slot_stats_recipe(db, slot, key):
    """None means no sparse after-image; a tuple of NULLs means no recipe."""
    compatible = " AND ".join(f"i.{name} IS p.{name}" for name in IDENTITY_SHAPE)
    values = ",".join(f"CASE WHEN {compatible} THEN i.{name} END"
                      for name in ("message_key", "step_key", "sample_hash", "source_model_key", "stats_effort"))
    return db.execute(f"""
        SELECT {values}
        FROM archive_request_preparations a
        JOIN archive_prepare_requests p ON p.source=a.attempt AND p.request_key=?
        JOIN archive_input_requests i ON i.source=a.run AND i.request_key=p.request_key
        WHERE a.attempt=?
    """, (key, slot.attempt)).fetchone()
