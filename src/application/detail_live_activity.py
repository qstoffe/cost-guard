"""Display-only execution proof from an already qualified Watch capture."""
from .projection import identity
from .session_catalog import PROMPT_FRESHNESS_MS


def detail_activity(observation, key, card):
    if (card is None or card.snapshot is None or card.capture is None
            or card.verified_generation != card.generation or card.source_status.failed_at is not None):
        return None
    capture = card.capture
    if (not capture.authoritative or capture.retained or capture.source_epoch != observation.source_epoch
            or card.snapshot.source_revision != observation.revisions.get(key)):
        return None
    provenance = card.snapshot.root.provenance
    scope = identity((provenance.source_type, provenance.source_generation, provenance.source_instance,
                      observation.source_epoch, key))
    running = tuple(sorted(row.event_id for row in capture.rows
                           if row.event_id in capture.observed_ids and row.in_progress
                           and not row.execution_unverified))
    ended = tuple(sorted(prompt for _, prompt in capture.catalog_prompt_ends))
    return dict(scope=scope, observed_at_ms=capture.observed_at_ms, running=running, ended=ended)


def current_activity(fact, proof):
    if not proof or fact is None or proof['observed_at_ms'] <= (fact.observed_ms or 0):
        return None
    activity = fact.value.get('activity') or {}
    return proof if activity.get('scope') == proof['scope'] else None


def fresh_activity(proof, now_ms):
    return proof if proof and 0 <= now_ms - proof['observed_at_ms'] <= PROMPT_FRESHNESS_MS else None
