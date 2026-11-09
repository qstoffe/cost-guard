"""Reconstructible root-tree CCost contributions, independent of card membership.

Source revisions trigger reconciliation, never blind reuse. Each authoritative
snapshot checks request fingerprints; only new/changed requests are revalued.
No prompt text, source paths, tokens or credentials are persisted here.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import sqlite3

from .cache import ANALYSIS_ALGORITHM_VERSION, dependency_signature
from .causal import trace_entries
from .valuation import ComparisonCost, comparison_cost, unique_usage
from src.domain.reference_cost import bounded_issues
from src.cache.session_scope import snapshot_scope
from src.pricing.identities import MODEL_IDENTITY_SEMANTICS, unverified_alias

NAMESPACE = "session-ccost-v1"
ALGORITHM = ANALYSIS_ALGORITHM_VERSION + "/root-tree-reference-1"


@dataclass(frozen=True, slots=True)
class SessionCost:
    total: ComparisonCost
    source_complete: bool
    cache_available: bool
    checked_requests: int = 0
    valued_requests: int = 0
    cache_written: bool = False
    source_revision: str = ""
    valuation_revision: str = ""


def session_cost_source_key(snapshot):
    """Constant-time source identity/revision gate, not a capture or wall clock."""
    provenance = snapshot.root.provenance
    return (provenance.source_type, provenance.source_generation, provenance.source_instance,
        snapshot.root.session_id, snapshot.source_revision, snapshot.complete,
        tuple(dict.fromkeys(request.model.resolution for request in snapshot.invocations if request.model.resolution)))


def _checkpoint(payload):
    """Malformed optional cache data is a miss, not source evidence."""
    try:
        values = payload["contributions"]
        for key, value in values.items():
            if not isinstance(key, str) or not isinstance(value["fingerprint"], str):
                return None
            amount = value["amount"]
            if amount is not None and (not Decimal(amount).is_finite() or Decimal(amount) < 0):
                return None
        total = Decimal(payload["known_ccost"])
        priced = payload["priced_requests"]
        if not total.is_finite() or total < 0 or priced != sum(value["amount"] is not None for value in values.values()):
            return None
        return values, ComparisonCost(total, len(values), priced)
    except (KeyError, TypeError, AttributeError, ValueError, InvalidOperation):
        return None


def _known_amount(contribution):
    return Decimal(contribution["amount"]) if contribution["amount"] is not None else Decimal(0)


def reconcile_session_cost(repository, snapshot, catalog):
    provenance = snapshot.root.provenance
    key = dependency_signature((provenance.source_type, provenance.source_generation,
        provenance.source_instance, snapshot.root.session_id, ALGORITHM, catalog.analysis_signature))
    available = True
    try:
        cached = repository.get(NAMESPACE, key, busy_timeout_ms=50)
    except (sqlite3.Error, OSError):
        cached, available = None, False
    checkpoint = _checkpoint(cached.payload) if cached is not None and cached.algorithm_version == ALGORITHM else None
    old, previous = checkpoint if checkpoint is not None else ({}, ComparisonCost())
    total, observed, priced = previous.known_ccost, previous.observed_requests, previous.priced_requests
    current, valued = {}, 0
    issues = set()
    entries = unique_usage(trace_entries(snapshot))
    for entry in entries:
        invocation = snapshot.invocations[entry.sort_order]
        identity = dependency_signature((entry.source_instance, entry.session_id, invocation.invocation_id))
        fingerprint = dependency_signature((entry.model, entry.tokens, entry.completed_at_ms))
        if unverified_alias(entry.model.model, entry.model.provider):
            fingerprint = dependency_signature((fingerprint, MODEL_IDENTITY_SEMANTICS))
        prior = old.get(identity)
        if prior is not None and prior["fingerprint"] == fingerprint:
            current[identity] = prior
        else:
            if prior is not None:
                total -= _known_amount(prior)
                priced -= prior["amount"] is not None
            else:
                observed += 1
            cost = comparison_cost((entry,), catalog.reference_valuation)
            valued += 1
            total += cost.known_ccost
            priced += cost.priced_requests
            current[identity] = {"fingerprint": fingerprint,
                "amount": str(cost.known_ccost) if cost.complete else None}
        if current[identity]["amount"] is None:
            issues.add(catalog.reference_issue(entry.model, entry.tokens))
    for identity in old.keys() - current.keys():
        total -= _known_amount(old[identity])
        observed -= 1
        priced -= old[identity]["amount"] is not None
    coverage = ComparisonCost(total, observed, priced, unavailable=bounded_issues(issues))
    written = False
    # Partial source brackets cannot replace an authoritative persisted checkpoint.
    if snapshot.complete and (current != old or checkpoint is None or cached.source_revision != snapshot.source_revision):
        try:
            repository.put(NAMESPACE, key, {"contributions": current, "known_ccost": str(total),
                "priced_requests": priced}, source_revision=snapshot.source_revision,
                algorithm_version=ALGORITHM, busy_timeout_ms=50, session_scope=snapshot_scope(snapshot))
            written = True
        except (sqlite3.Error, OSError):
            available = False
    return SessionCost(coverage, snapshot.complete, available, len(entries), valued, written,
        snapshot.source_revision, catalog.diagnostic_signature)
