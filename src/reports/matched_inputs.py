"""Finite all-history acquisition with O(N) revision-aware compact match indexing."""
from dataclasses import replace
from decimal import InvalidOperation
import sqlite3

from src.analysis.cache import dependency_signature, cached_analysis
from src.analysis.input_identity import first_input, preview, IDENTITY_VERSION
from src.analysis.matched_runs import MatchGroup, MatchesPage, facts, grouped
from src.cache.repository import CacheEntry
from src.domain.progress import WorkProgress
from .history import session_catalog_revision
from .matched_runs import decode_run, encode_run, project_run
from .migration_notice import migration_gap_notes
from .models import ReportKind, ReportProjection
from .service import SessionCatalogChangedError
from .token_mix_cache import cache_key

ALGORITHM = 'matched-first-runs-1-' + IDENTITY_VERSION
NAMESPACE = 'matched-first-runs'
# Amortize V2's authoritative before/after catalog brackets while retaining a
# fixed bound on hydrated roots. The source still limits concurrent reads to four.
BATCH_SIZE = 128


def build_comparisons(service, request):
    reference = service._load_comparison_catalog()
    service.progress(WorkProgress('Checking all history revisions', 'catalog'))
    sessions = tuple(service.source.list_sessions())
    roots, activity = service._ordered_roots(sessions)
    service.metrics.counts.update(catalog_sessions=len(sessions), catalog_roots=len(roots))
    bulk = getattr(service.source, 'get_session_tree_revisions', None)
    revisions = (bulk(tuple(root.session_id for root in roots)) if callable(bulk) else
                 {root.session_id: service.source.get_session_tree_revision(root.session_id) for root in roots})
    keys = {root.session_id: dependency_signature((ALGORITHM, cache_key(service, root, reference))) for root in roots}
    try:
        cached = service.cache_repository.get_many(NAMESPACE, keys.values(), busy_timeout_ms=50)
    except (OSError, sqlite3.Error):
        cached = {}
    runs, pending, previews = [], [], {}
    complete = not service.selection.warnings and not migration_gap_notes(service.selection.migration_gap)

    def include(run, root):
        if run is not None:
            if run.session_id != root.session_id:
                raise ValueError('invalid_match_root')
            runs.append(replace(run, title=root.title[:240], activity_ms=activity.get(root.session_id, root.updated_at_ms)))

    for index, root in enumerate(roots):
        item = cached.pop(keys[root.session_id], None)
        hit = False
        if item and item.source_revision == revisions[root.session_id] and item.algorithm_version == ALGORITHM:
            try:
                include(decode_run(item.payload), root)
                service._acquisition.revisions[root.session_id] = revisions[root.session_id]
                hit = True
            except (KeyError, IndexError, TypeError, ValueError, InvalidOperation):
                pass
        service.metrics.add('comparison_cache_hits' if hit else 'comparison_cache_misses')
        if not hit:
            pending.append(root)
        service.progress(WorkProgress('Checking match index', 'history', index + 1, len(roots), stage='history-cache'))
    service.progress(WorkProgress('Updating changed first inputs', 'history', 0, len(pending), stage='history-load'))
    for start in range(0, len(pending), BATCH_SIZE):
        chunk = pending[start:start + BATCH_SIZE]
        snapshots = _snapshots(service, chunk)
        writes = []
        for root in chunk:
            snapshot = snapshots[root.session_id]
            _revision, bundle = cached_analysis(service.source, root, service._derived,
                service._dependencies(service._load_catalog()))
            if bundle is None or bundle.source_revision != snapshot.source_revision:
                bundle = service._analyze_snapshot(snapshot)
            service._acquisition.revisions[root.session_id] = snapshot.source_revision
            run = project_run(snapshot, bundle, reference, service.config)
            include(run, root)
            if run is not None:
                previews[root.session_id] = preview(first_input(snapshot))
            complete = complete and snapshot.complete and bundle.source_revision == revisions[root.session_id]
            if bundle.cacheable and snapshot.complete and bundle.source_revision == revisions[root.session_id]:
                writes.append(CacheEntry(NAMESPACE, keys[root.session_id], encode_run(run), bundle.source_revision, ALGORITHM))
        try:
            service.cache_repository.put_many(writes, busy_timeout_ms=50)
        except (OSError, sqlite3.Error):
            pass
        service.progress(WorkProgress('Updating changed first inputs', 'history', start + len(chunk), len(pending), stage='history-load'))
    service.progress(WorkProgress('Preparing matched groups', 'projection', stage='history-projection'))
    groups = grouped(runs)
    revision = dependency_signature((ALGORITHM, session_catalog_revision(service.selection.selected, sessions),
                                    sorted(revisions.items()), reference.analysis_signature))
    if request.comparison_revision and request.comparison_revision != revision:
        raise SessionCatalogChangedError('Comparison ordering changed')
    offset = min(request.comparison_offset, max(0, (len(groups) - 1) // 10 * 10))
    page = []
    # Only displayed group previews need source text. Never persist them; warm
    # checks hydrate at most ten representatives, not every stable archived root.
    visible = groups[offset:offset + 10]
    by_id = {root.session_id: root for root in roots}
    missing = [by_id[group[0].session_id] for group in visible if group[0].session_id not in previews]
    snapshots = _snapshots(service, missing) if missing else {}
    for group in visible:
        label = previews.get(group[0].session_id)
        if label is None:
            snapshot = snapshots[group[0].session_id]
            if snapshot.source_revision != revisions[group[0].session_id]:
                raise SessionCatalogChangedError('Comparison input revision changed')
            label = preview(first_input(snapshot))
        page.append(MatchGroup(group, label, facts(group)))
    after = tuple(service.source.list_sessions())
    complete = complete and session_catalog_revision(service.selection.selected, sessions) == session_catalog_revision(service.selection.selected, after)
    return ReportProjection(ReportKind.COMPARISONS, 'Comparisons', service.selection.selected.upper(),
        tuple(service.selection.warnings), comparisons=MatchesPage(tuple(page), offset, len(groups), revision,
            complete, len(roots), len(roots) - len(runs)))


def _snapshots(service, roots):
    """Reuse bounded source batches without persisting raw prompt analysis/text."""
    ids = tuple(root.session_id for root in roots)
    observed = getattr(service.source, 'load_session_snapshots_observed', None)
    if callable(observed):
        return observed(ids, lambda step, done, total: service.progress(WorkProgress(
            'Loading changed input history', 'history', done, total, stage='date-' + step)))
    batch = getattr(service.source, 'load_session_snapshots', None)
    if callable(batch):
        return batch(ids)
    return {sid: service.source.load_session_snapshot(sid) for sid in ids}
