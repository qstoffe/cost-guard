"""Bounded Web AI Stats acquisition with disposable, revision-checked root evidence."""
from decimal import Decimal, InvalidOperation
from dataclasses import replace
import sqlite3

from src.analysis.ai_stats import StatsRoot, period_stats, windows
from src.analysis.cache import dependency_signature
from src.analysis.matched_runs import period_fact
from src.cache.repository import CacheEntry
from src.domain.progress import WorkProgress
from src.domain.session_tree import root_by_session
from .migration_notice import migration_gap_notes
from .models import ReportKind, ReportProjection
from .token_mix_cache import cache_key, encode, decode
from .matched_runs import project_run, encode_run, decode_run

ALGORITHM = 'ai-stats-evidence-2-matched-first-input-1'
NAMESPACE = 'ai-stats-evidence'
BATCH_SIZE = 64  # Existing finite historical-report bound; source overlaps at most four reads.


def _payload(bundle, reference, snapshot, config):
    intervals = [(p.prompt_time_ms, p.execution_duration_ms, p.in_progress) for p in bundle.prompts]
    intervals.extend((c.created_at_ms, c.duration_ms, c.in_progress) for c in bundle.compactions)
    return dict(usage=encode(bundle, reference), intervals=intervals,
                matched=encode_run(project_run(snapshot, bundle, reference, config)),
                pending=any(p.in_progress and not p.entries for p in bundle.prompts))


def _decode(payload, root):
    facts = decode(payload['usage'])
    intervals = payload['intervals']
    if not isinstance(intervals, list) or type(payload['pending']) is not bool:
        raise ValueError('invalid_timing')
    for left, duration, running in intervals:
        if (type(left) is not int or duration is not None and (type(duration) is not int or duration < 0)
                or type(running) is not bool):
            raise ValueError('invalid_timing')
    matched = decode_run(payload['matched'])
    if matched is not None and matched.session_id != root.session_id:
        raise ValueError('invalid_match_root')
    return StatsRoot(root.session_id, root.title, tuple(e for e, _p, _c in facts),
                     tuple(tuple(pair) for pair in intervals), payload['pending']), facts, matched


def build_ai_stats(service, scope):
    service.metrics.mode = 'ai-stats'
    service.progress(WorkProgress('Loading reference prices', 'pricing'))
    reference = service._load_comparison_catalog()
    periods = windows(service.timezone_id, service.now_ms)
    cutoff = dict(periods)[scope]
    service.progress(WorkProgress('Checking history revisions', 'catalog'))
    sessions = service.session_catalog()
    roots, activity = service._ordered_roots(sessions)
    ancestry = root_by_session(sessions)
    active = {ancestry.get(s.session_id) for s in sessions if s.active is True}
    roots = tuple(root for root in roots if cutoff is None or activity.get(root.session_id, root.updated_at_ms) >= cutoff
                  or root.session_id in active)
    bulk = getattr(service.source, 'get_session_tree_revisions', None)
    revisions = (bulk(tuple(root.session_id for root in roots)) if callable(bulk) else
                 {root.session_id: service.source.get_session_tree_revision(root.session_id) for root in roots})
    keys = {root.session_id: dependency_signature((ALGORITHM, cache_key(service, root, reference))) for root in roots}
    try:
        cached = service.cache_repository.get_many(NAMESPACE, keys.values(), busy_timeout_ms=50)
    except (OSError, sqlite3.Error):
        cached = {}
    evidence, costs, pending, matched = [], {}, [], []
    match_complete = True

    def include(decoded):
        root, facts, run = decoded
        evidence.append(root)
        matched.append(replace(run, title=root.title) if run else None)
        for entry, _prompt, parts in facts:
            costs[entry.model, entry.tokens] = None if parts is None else sum(parts, Decimal(0))

    for index, root in enumerate(roots):
        item = cached.pop(keys[root.session_id], None)
        decoded = None
        if item and item.source_revision == revisions[root.session_id] and item.algorithm_version == ALGORITHM:
            try:
                decoded = _decode(item.payload, root)
            except (KeyError, IndexError, TypeError, ValueError, InvalidOperation):
                pass
        service.metrics.add('ai_stats_cache_hits' if decoded else 'ai_stats_cache_misses')
        if decoded:
            include(decoded)
            service._acquisition.revisions[root.session_id] = revisions[root.session_id]
        else:
            pending.append(root)
        service.progress(WorkProgress('Checking history cache', 'history', index + 1, len(roots), stage='history-cache'))
    service.progress(WorkProgress('Updating changed roots', 'history', 0, len(pending), stage='history-load'))
    for start in range(0, len(pending), BATCH_SIZE):
        chunk = pending[start:start + BATCH_SIZE]
        service.prepare_roots(chunk, detail=True, progress_scope='date')
        writes = []
        for root in chunk:
            item = service._analyze(root, detail=True)
            bundle = item.bundle
            match_complete = match_complete and item.snapshot.complete and bundle.source_revision == revisions[root.session_id]
            payload = _payload(bundle, reference, item.snapshot, service.config)
            include(_decode(payload, root))
            service.metrics.add('ai_stats_valued_requests', len(bundle.trace_entries))
            if bundle.cacheable and bundle.source_revision == revisions[root.session_id]:
                writes.append(CacheEntry(NAMESPACE, keys[root.session_id], payload, bundle.source_revision, ALGORITHM))
            service._analyzed.pop(root.session_id, None)
        try:
            service.cache_repository.put_many(writes, busy_timeout_ms=50)
        except (OSError, sqlite3.Error):
            pass
        service.progress(WorkProgress('Updating changed roots', 'history', start + len(chunk), len(pending), stage='history-load'))
    gaps = migration_gap_notes(service.selection.migration_gap, start_ms=cutoff)
    complete = not service.selection.warnings and not gaps
    service.progress(WorkProgress('Preparing AI Stats', 'projection', stage='history-projection'))
    stats = tuple(replace(period_stats(evidence, lambda model, tokens: costs[model, tokens], period=name,
        start=left, now=service.now_ms, zone=service.timezone_id, source_complete=complete),
        matched=period_fact([run for run in matched if run], left, service.now_ms,
            complete=complete and match_complete and all(run is not None for run in matched)))
        for name, left in periods if cutoff is None or left is not None and left >= cutoff)
    return ReportProjection(ReportKind.AI_STATS, 'AI Stats', service.selection.selected.upper(),
        tuple(service.selection.warnings), notes=gaps, ai_stats=stats)
