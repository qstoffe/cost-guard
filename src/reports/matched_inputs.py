"""Finite all-history acquisition with O(N) revision-aware compact match indexing."""
from dataclasses import replace
from decimal import InvalidOperation
import sqlite3

from src.analysis.cache import dependency_signature, cached_analysis
from src.analysis.input_identity import first_input, preview, IDENTITY_VERSION
from src.analysis.matched_runs import MatchGroup, MatchesPage, facts, grouped
from src.cache.repository import CacheEntry
from src.cache.session_scope import snapshot_scope
from src.domain.progress import WorkProgress
from .history import session_catalog_revision
from .matched_runs import decode_run, encode_run, project_run
from .migration_notice import migration_gap_notes
from .models import ReportKind, ReportProjection
from .service import SessionCatalogChangedError
from .token_mix_cache import cache_key
from .history_work import HistoryWork, HistoryCheckpointError, active_roots, revisions as root_revisions
from .history_snapshots import load as load_snapshots, warnings as history_warnings

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
    revisions = root_revisions(service, roots)
    work = HistoryWork(service, sessions, roots, revisions, reference)
    active = active_roots(sessions)
    keys = {root.session_id: dependency_signature((ALGORITHM, cache_key(service, root, reference))) for root in roots}
    try:
        cached = service.cache_repository.get_many(NAMESPACE, keys.values(), busy_timeout_ms=50)
    except (OSError, sqlite3.Error):
        cached = {}
    runs, pending, previews = [], [], {}
    unavailable = set()
    complete = not service.selection.warnings and not migration_gap_notes(service.selection.migration_gap)

    def include(run, root):
        if run is not None:
            if run.session_id != root.session_id:
                raise ValueError('invalid_match_root')
            runs.append(replace(run, title=root.title[:240], activity_ms=activity.get(root.session_id, root.updated_at_ms)))

    for index, root in enumerate(roots):
        item = cached.pop(keys[root.session_id], None)
        hit = False
        if (root.session_id not in active and item and item.source_revision == revisions[root.session_id]
                and item.algorithm_version == ALGORITHM):
            try:
                include(decode_run(item.payload), root)
                service._acquisition.revisions[root.session_id] = revisions[root.session_id]
                hit = True
                work.saved += 1
            except (KeyError, IndexError, TypeError, ValueError, InvalidOperation):
                pass
        service.metrics.add('comparison_cache_hits' if hit else 'comparison_cache_misses')
        if not hit:
            pending.append(root)
        service.progress(WorkProgress('Checking match index', 'history', index + 1, len(roots), stage='history-cache'))
    service.progress(WorkProgress('Updating changed first inputs', 'history', 0, len(pending), stage='history-load'))
    batch_size = getattr(service, 'history_batch_size', BATCH_SIZE)
    for start in range(0, len(pending), batch_size):
        chunk = pending[start:start + batch_size]
        snapshots = load_snapshots(service, chunk)
        writes = []
        for root in chunk:
            snapshot = snapshots.get(root.session_id)
            if snapshot is None:
                unavailable.add(root.session_id)
                continue
            _revision, bundle = cached_analysis(service.source, root, service._derived,
                service._dependencies(service._load_catalog()))
            if bundle is None or bundle.source_revision != snapshot.source_revision:
                bundle = service._analyze_snapshot(snapshot)
            service._acquisition.revisions[root.session_id] = snapshot.source_revision
            run = project_run(snapshot, bundle, reference, service.config)
            include(run, root)
            if run is not None and len(previews) < 10:
                previews[root.session_id] = preview(first_input(snapshot))
            complete = complete and snapshot.complete and bundle.source_revision == revisions[root.session_id]
            if (bundle.cacheable and snapshot.complete and root.session_id not in active
                    and bundle.source_revision == revisions[root.session_id]):
                writes.append(CacheEntry(NAMESPACE, keys[root.session_id], encode_run(run), bundle.source_revision, ALGORITHM,
                    snapshot_scope(snapshot)))
        try:
            service.cache_repository.put_many(writes, busy_timeout_ms=50)
        except (OSError, sqlite3.Error):
            writes = []
        service.progress(WorkProgress('Updating changed first inputs', 'history', start + len(chunk), len(pending), stage='history-load'))
        work.checkpoint(len(writes), processed=len(chunk), remaining=start + len(chunk) < len(pending))
    service.progress(WorkProgress('Preparing matched groups', 'projection', stage='history-projection'))
    unavailable.update(work.verify())
    if unavailable and len(unavailable) == len(roots):
        raise HistoryCheckpointError('history_revision_churn')
    runs = [run for run in runs if run.session_id not in unavailable]
    for sid in unavailable:
        service._acquisition.revisions.pop(sid, None)
    complete = complete and not unavailable
    groups = grouped(runs)
    signature = (ALGORITHM, session_catalog_revision(service.selection.selected, sessions),
                 sorted(revisions.items()), reference.analysis_signature)
    revision = dependency_signature((*signature, sorted(unavailable)) if unavailable else signature)
    if request.comparison_revision and request.comparison_revision != revision:
        raise SessionCatalogChangedError('Comparison ordering changed')
    offset = min(request.comparison_offset, max(0, (len(groups) - 1) // 10 * 10))
    page = []
    # Only displayed group previews need source text. Never persist them; warm
    # checks hydrate at most ten representatives, not every stable archived root.
    visible = groups[offset:offset + 10]
    by_id = {root.session_id: root for root in roots}
    missing = [by_id[group[0].session_id] for group in visible if group[0].session_id not in previews]
    snapshots = load_snapshots(service, missing) if missing else {}
    for group in visible:
        label = previews.get(group[0].session_id)
        if label is None:
            snapshot = snapshots.get(group[0].session_id)
            if snapshot is None:
                raise SessionCatalogChangedError('Comparison preview could not be verified')
            if snapshot.source_revision != revisions[group[0].session_id]:
                raise SessionCatalogChangedError('Comparison input revision changed')
            label = preview(first_input(snapshot))
        page.append(MatchGroup(group, label, facts(group)))
    after = tuple(service.source.list_sessions())
    complete = complete and session_catalog_revision(service.selection.selected, sessions) == session_catalog_revision(service.selection.selected, after)
    if work.verify(after) - unavailable:
        raise SessionCatalogChangedError('Comparison roots changed during preview acquisition')
    return ReportProjection(ReportKind.COMPARISONS, 'Comparisons', service.selection.selected.upper(),
        (*service.selection.warnings, *history_warnings(unavailable)), comparisons=MatchesPage(tuple(page), offset, len(groups), revision,
            complete, len(roots), len(roots) - len(runs)), history_omitted_roots=len(unavailable))
