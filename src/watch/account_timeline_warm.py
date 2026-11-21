"""Bounded durable request facts for historical Accounts, never provider state."""
from dataclasses import replace
from decimal import InvalidOperation
import sqlite3

from src.analysis.cache import decode_trace_entry, dependency_signature, encode_trace_entry
from src.cache import warm_history
from src.cache.repository import CacheEntry
from src.cache.session_scope import root_key
from src.pricing.identities import MODEL_IDENTITY_SEMANTICS

NAMESPACE = 'account-timeline-history'
ALGORITHM = f'account-timeline-usage-1:{MODEL_IDENTITY_SEMANTICS}'
INDEX_NAMESPACE = 'account-timeline-warm-index'
INDEX_ALGORITHM = 'account-timeline-prefix-1'
INDEX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 8192
MAX_ROOT_BYTES = 24 * 1024
BATCH_SIZE = 128


def restore(repository, roots, revisions, membership, now):
    for start in range(0, len(roots), BATCH_SIZE):
        keys = {root_key(root.provenance, root.session_id): root.session_id for root in roots[start:start + BATCH_SIZE]}
        try:
            rows = repository.get_many(NAMESPACE, keys, busy_timeout_ms=warm_history.WAIT_MS)
        except (OSError, sqlite3.Error, ValueError, RecursionError):
            return
        for key, item in rows.items():
            sid = keys[key]
            if (item.algorithm_version, item.source_revision) != (ALGORITHM, revisions[sid]):
                continue
            try:
                value = warm_history.unseal(item.payload, limit=MAX_ROOT_BYTES)
                if value['membership'] != membership[sid] or now < value['observed']:
                    continue
                entries = tuple(decode_trace_entry(entry) for entry in value['entries'])
                if all(0 < entry.completed_at_ms <= now for entry in entries):
                    yield sid, entries
            except (KeyError, TypeError, ValueError, InvalidOperation, OverflowError, RecursionError):
                continue


def entry(root, revision, membership, entries, now, scope):
    # Preserve exact allocation keys and clone/physical identities, not account
    # labels or arbitrary provider error text. No prompt record is serialized.
    value = dict(observed=now, membership=membership, entries=[
        encode_trace_entry(replace(entry, error_name='error' if entry.error_name else None,
            account_ref=replace(entry.account_ref, account_label=None) if entry.account_ref else None))
        for entry in entries])
    payload = warm_history.sealed(value, limit=MAX_ROOT_BYTES)
    if payload is None:
        return None
    return CacheEntry(NAMESPACE, root_key(root.provenance, root.session_id), payload, revision, ALGORITHM, scope)


def publish(repository, entries):
    if not entries:
        return
    try:
        repository.put_many(entries, busy_timeout_ms=warm_history.WAIT_MS, capacity=(NAMESPACE, MAX_ROWS))
    except (OSError, sqlite3.Error, ValueError, TypeError, RecursionError):
        pass


def root_keys(roots, saved, revisions):
    return (root_key(root.provenance, root.session_id) for root in roots
            if (item := saved.get(root.session_id)) and item.complete and item.revision == revisions.get(root.session_id))


def index_binding(scope, used, prices, accounts):
    return dependency_signature((INDEX_ALGORITHM, ALGORITHM, scope, prices, sorted(accounts),
        [(key, value.revision, value.membership) for key, value in used]))


def restore_index(repository, binding, now):
    from src.analysis.period_ccost import PeriodCCostIndex
    value = warm_history.restore(repository, INDEX_NAMESPACE, 'last-complete', INDEX_ALGORITHM, binding, limit=INDEX_BYTES)
    if value is not None:
        try:
            if 0 <= now - value['observed'] <= warm_history.MAX_AGE_MS:
                return PeriodCCostIndex.from_summary(value['index'])
        except (KeyError, TypeError, ValueError, InvalidOperation, OverflowError):
            pass
    return None


def publish_index(repository, binding, index, now):
    warm_history.publish(repository, INDEX_NAMESPACE, 'last-complete', INDEX_ALGORITHM, binding,
                         dict(observed=now, index=index.summary()), limit=INDEX_BYTES)
