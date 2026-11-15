"""Model standings over the same canonical period requests as the large totals."""
from dataclasses import dataclass
from decimal import Decimal

from .active_hour import USAGE_FIELDS
from .ai_stats_responses import call_key, identity_hint, model_key
from .billing import billing_request_fingerprint
from .effort_defaults import effort_evidence


@dataclass(frozen=True, slots=True)
class ModelActivity:
    entry: object
    start_ms: int
    duration_ms: int


@dataclass(frozen=True, slots=True)
class ModelStanding:
    provider: str
    model: str
    value: Decimal | int
    recorded_models: tuple
    effort_evidence: tuple
    display_name: str = ''
    catalog_estimate: bool = False
    catalog_model: str = ''
    identity_hint: str = ''


def observed_tokens(entry):
    if entry.completed_at_ms <= 0:
        return 0
    return sum(getattr(entry.tokens, name) for name in USAGE_FIELDS if name in entry.tokens.known_fields) + (
        entry.tokens.reasoning if 'output' in entry.tokens.known_fields else 0)


def standings(entries, values):
    groups = {}
    for entry, value in zip(entries, values):
        if not all(model_key(entry)[:2]) or value is None:
            continue
        group = groups.setdefault(model_key(entry), [0, []])
        group[0] += value
        group[1].append(entry)
    return ranked(groups)


def ranked(groups):
    rows = [ModelStanding(*key[:2], amount, tuple(sorted({e.model.recorded_model for e in entries})),
                          effort_evidence(entries), catalog_model=entries[0].model.model if key[2] else '',
                          identity_hint=identity_hint(key))
            for key, (amount, entries) in groups.items() if amount > 0]
    return tuple(sorted(rows, key=lambda row: (-row.value, row.provider, row.model, row.identity_hint))[:3])


def model_costs(roots, entries, values):
    owner = {e.session_id: root.session_id for root in roots for e in root.entries}
    groups = {}
    for entry, value in zip(entries, values):
        if not all(model_key(entry)[:2]):
            continue
        amount, sessions, evidence = groups.setdefault(model_key(entry), [Decimal(0), set(), []])
        groups[model_key(entry)][0] = amount + value
        sessions.add(owner[entry.session_id])
        evidence.append(entry)
    return (ranked({key: (amount, evidence) for key, (amount, _sessions, evidence) in groups.items()}),
            ranked({key: (amount / len(sessions), evidence)
                    for key, (amount, sessions, evidence) in groups.items()}))


def model_time(roots, entries, start, now, union):
    # All attributable calls, NOT the bounded throughput sample. Canonical clone
    # survivors may borrow only the exact same physical request's interval.
    activity = [a for root in roots for a in root.activity]
    exact = {call_key(a.entry): a for a in activity}
    clones = {(a.entry.source_instance, billing_request_fingerprint(a.entry)): a
              for a in activity if billing_request_fingerprint(a.entry)}
    groups = {}
    for entry in entries:
        fact = exact.get(call_key(entry), clones.get((entry.source_instance, billing_request_fingerprint(entry))))
        if fact is None or not all(model_key(entry)[:2]) or entry.completed_at_ms <= 0:
            continue
        left, right = max(start or 1, fact.start_ms), min(now, fact.start_ms + fact.duration_ms)
        if right > left:
            pairs, evidence = groups.setdefault(model_key(entry), ([], []))
            pairs.append((left, right))
            evidence.append(entry)
    return ranked({key: (sum(b - a for a, b in union(pairs)), evidence)
                   for key, (pairs, evidence) in groups.items()})
