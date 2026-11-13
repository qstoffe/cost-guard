"""Bounded, deterministic response-throughput samples for the fun Stats page only."""
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from bisect import insort
import json

from .models import TraceEntry
from .billing import billing_request_fingerprint
from .effort_defaults import effort_evidence

SAMPLE_LIMIT = 32
RECENT_CALLS = 8


@dataclass(frozen=True, slots=True)
class ResponseCall:
    entry: TraceEntry
    duration_ms: int


@dataclass(frozen=True, slots=True)
class ModelResponse:
    provider: str
    model: str
    variant: str
    output_tokens: int
    duration_ms: int
    sampled_calls: int
    recorded_models: tuple[str, ...] = ()
    catalog_estimate: bool = False
    effort_evidence: tuple = ()

    @property
    def tokens_per_second(self):
        return Decimal(self.output_tokens) * 1000 / self.duration_ms


def model_key(entry):
    # Exact observed route/model, with effort kept separate, never fuzzy aliases.
    return entry.model.provider, entry.model.model, entry.variant or ''


def call_key(entry):
    return (entry.source_instance or '', entry.session_id, entry.message_id or '',
            entry.step_part_id or '', entry.parent_event_id or '', entry.sort_order)


def _priority(call):
    return sha256(json.dumps(call_key(call.entry), separators=(',', ':')).encode()).digest(), call_key(call.entry)


def sample(calls):
    """Newest eight, then lowest identity hashes from the rest, at both tiers.

    Root summaries are bounded too; historical-window samples are consequently
    hierarchical approximations, not uniform reservoirs over all period calls.
    """
    groups = {}
    for call in calls:
        entry = call.entry
        if (type(call.duration_ms) is not int or call.duration_ms <= 0 or entry.completed_at_ms <= 0
                or 'output' not in entry.tokens.known_fields or entry.tokens.output + entry.tokens.reasoning <= 0
                or entry.error_name or entry.finish_reason in ('error', 'aborted')):
            continue
        recent, spread, retained = groups.setdefault(model_key(entry), ([], [], set()))
        identity = call_key(entry)
        if identity in retained:
            continue
        retained.add(identity)
        insort(recent, (-entry.completed_at_ms, identity, call))
        if len(recent) > RECENT_CALLS:
            _stamp, identity, displaced = recent.pop()
            # Hash each displaced candidate once, not every retained item on
            # every insertion. Lists/identity set stay <=32 references/model.
            insort(spread, (_priority(displaced), identity, displaced))
            if len(spread) > SAMPLE_LIMIT - RECENT_CALLS:
                retained.remove(spread.pop()[1])
    return tuple(item[2] for key in sorted(groups) for bucket in groups[key][:2] for item in bucket)


def podium(roots, entries, start, now):
    # Reconcile canonical step/message/clone precedence before final sampling.
    durations = {call_key(c.entry): c.duration_ms for root in roots for c in root.responses}
    # A canonical clone survivor may lack timing while its same physical request
    # in another root retains it. Borrow only the existing exact clone fingerprint.
    cloned = {(c.entry.source_instance, billing_request_fingerprint(c.entry)): c.duration_ms
              for root in roots for c in root.responses if billing_request_fingerprint(c.entry)}
    def duration(entry):
        return durations.get(call_key(entry), cloned.get((entry.source_instance, billing_request_fingerprint(entry))))
    selected = sample(ResponseCall(e, elapsed) for e in entries
                      if (elapsed := duration(e)) is not None and (start is None or e.completed_at_ms >= start)
                      and e.completed_at_ms <= now)
    groups = {}
    for call in selected:
        key = model_key(call.entry)
        values = groups.setdefault(key, [0, 0, 0, set(), False, []])
        values[0] += call.entry.tokens.output + call.entry.tokens.reasoning
        values[1] += call.duration_ms
        values[2] += 1
        values[3].add(call.entry.model.recorded_model)
        values[4] |= bool(call.entry.model.resolution and call.entry.model.display_name)
        values[5].append(call.entry)
    rows = [ModelResponse(*key, *values[:3], tuple(sorted(values[3])), values[4], effort_evidence(values[5]))
        for key, values in groups.items()]
    return tuple(sorted(rows, key=lambda r: (-r.tokens_per_second, r.provider, r.model, r.variant))[:3])
