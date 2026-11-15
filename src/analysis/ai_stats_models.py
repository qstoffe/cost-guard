"""Model standings over the same canonical period requests as the large totals."""
from dataclasses import dataclass
from decimal import Decimal

from .active_hour import USAGE_FIELDS
from .ai_stats_responses import call_key
from .ai_stats_buckets import effort_values, model_key, providers, selected_effort
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
    by_effort: tuple = ()


def observed_tokens(entry):
    if entry.completed_at_ms <= 0:
        return 0
    return sum(getattr(entry.tokens, name) for name in USAGE_FIELDS if name in entry.tokens.known_fields) + (
        entry.tokens.reasoning if 'output' in entry.tokens.known_fields else 0)


def ranked(groups):
    rows = [ModelStanding(providers(entries), name, amount,
                          tuple(sorted({e.model.recorded_model for e in entries})), effort_evidence(entries),
                          display_name=name, by_effort=effort_values(efforts))
            for name, (amount, entries, efforts) in groups.items() if amount > 0]
    return tuple(sorted(rows, key=lambda row: (-row.value, row.model, row.provider))[:3])


def standings(entries, values, key=model_key):
    groups = {}
    for entry, value in zip(entries, values):
        if not entry.model.recorded_model or value is None:
            continue
        group = groups.setdefault(key(entry), [0, [], {}])
        group[0] += value
        group[1].append(entry)
        effort = selected_effort(entry)
        group[2][effort] = group[2].get(effort, 0) + value
    return ranked(groups)


def model_costs(roots, entries, values, key=model_key):
    owner = {e.session_id: root.session_id for root in roots for e in root.entries}
    groups = {}
    for entry, value in zip(entries, values):
        if not entry.model.recorded_model:
            continue
        name = key(entry)
        group = groups.setdefault(name, [Decimal(0), set(), [], {}])
        group[0] += value
        group[1].add(owner[entry.session_id])
        group[2].append(entry)
        effort = selected_effort(entry)
        subtotal, sessions = group[3].setdefault(effort, [Decimal(0), set()])
        group[3][effort][0] = subtotal + value
        sessions.add(owner[entry.session_id])
    return (ranked({name: (amount, evidence, {effort: cost for effort, (cost, _) in efforts.items()})
                    for name, (amount, _sessions, evidence, efforts) in groups.items()}),
            ranked({name: (amount / len(sessions), evidence,
                           {effort: cost / len(roots) for effort, (cost, roots) in efforts.items()})
                    for name, (amount, sessions, evidence, efforts) in groups.items()}))


def model_time(roots, entries, start, now, union, key=model_key):
    # All attributable calls, NOT the bounded throughput sample. Canonical clone
    # survivors may borrow only the exact same physical request's interval.
    activity = [a for root in roots for a in root.activity]
    exact = {call_key(a.entry): a for a in activity}
    clones = {(a.entry.source_instance, billing_request_fingerprint(a.entry)): a
              for a in activity if billing_request_fingerprint(a.entry)}
    groups = {}
    for entry in entries:
        fact = exact.get(call_key(entry), clones.get((entry.source_instance, billing_request_fingerprint(entry))))
        if fact is None or not entry.model.recorded_model or entry.completed_at_ms <= 0:
            continue
        left, right = max(start or 1, fact.start_ms), min(now, fact.start_ms + fact.duration_ms)
        if right > left:
            pairs, evidence, efforts = groups.setdefault(key(entry), ([], [], {}))
            pairs.append((left, right))
            evidence.append(entry)
            efforts.setdefault(selected_effort(entry), []).append((left, right))
    def duration(pairs):
        return sum(b - a for a, b in union(pairs))
    return ranked({name: (duration(pairs), evidence,
                          {effort: duration(intervals) for effort, intervals in efforts.items()})
                   for name, (pairs, evidence, efforts) in groups.items()})
