"""Publish compatible compact facts once; each report keeps its own projection.

No raw text or source snapshot is persisted. Existing revision, algorithm, source,
configuration and price signatures remain the cache admission authority.
"""
import sqlite3

from src.analysis.cache import dependency_signature
from src.cache.repository import CacheEntry
from . import ai_stats_evidence as stats
from . import token_mix_cache as mix


def entries(service, root, revision, value):
    from .matched_inputs import ALGORITHM, NAMESPACE
    key = mix.cache_key(service, root, service._load_comparison_catalog())
    return [CacheEntry(mix.NAMESPACE, key, value['usage'], revision, mix.ALGORITHM),
        CacheEntry(stats.NAMESPACE, dependency_signature((stats.ALGORITHM, key)), value, revision, stats.ALGORITHM),
        CacheEntry(stats.COVERAGE, stats.coverage_key(root), stats.coverage(value), revision, stats.COVERAGE),
        CacheEntry(NAMESPACE, dependency_signature((ALGORITHM, key)), value['matched'], revision, ALGORITHM)]


def publish(service, snapshot, bundle):
    if (not getattr(service, 'shared_web_evidence', False) or getattr(service, 'stats_scan', None)
            or not bundle.cacheable or not snapshot.complete):
        return
    value = stats.payload(bundle, service._load_comparison_catalog(), snapshot, service.config)
    if service.source.get_session_tree_revision(snapshot.root.session_id) != bundle.source_revision:
        return
    pending = getattr(service, '_shared_pending', None)
    if pending is None:
        pending = service._shared_pending = []
    pending.extend(entries(service, snapshot.root, bundle.source_revision, value))
    if len(pending) >= 256:
        flush(service)


def flush(service):
    pending = getattr(service, '_shared_pending', ())
    service._shared_pending = []
    try:
        service.cache_repository.put_many(pending, busy_timeout_ms=50)
    except (OSError, sqlite3.Error):
        pass  # Disposable acceleration; never a fabricated successful checkpoint.
