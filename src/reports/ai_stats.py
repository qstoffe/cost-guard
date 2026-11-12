"""Shared bounded AI Stats acquisition; checkpoints are derived evidence, not history."""
from dataclasses import replace
from decimal import Decimal
import sqlite3

from src.analysis.ai_stats import StatsObservation, windows
from src.analysis.cache import dependency_signature
from src.analysis.matched_runs import period_fact
from src.cache.repository import CacheEntry
from src.cache.session_scope import snapshot_scope
from src.domain.progress import WorkProgress
from src.domain.session_tree import root_by_session
from src.pricing.base import PricingUnavailableError
from src.pricing.catalog import PricingCatalog
from .ai_stats_evidence import (ALGORITHM, NAMESPACE, COVERAGE, INVALID, ModelCatalogChanged, coverage, coverage_key,
                                decoded, exclusion, payload)
from .migration_notice import migration_gap_notes
from .models import ReportKind, ReportProjection
from .token_mix_cache import cache_key
from .history_snapshots import load as load_snapshots

BATCH_SIZE = 64
SLICE_ROOTS = 256
MAX_ROOTS = 100_000
MAX_FACTS = 250_000
TRANSIENT = 'ai-stats-transient'


class StatsCheckpointError(Exception):
    """A bounded acquisition cannot make durable forward progress."""


def _revisions(service, roots):
    ids = tuple(root.session_id for root in roots)
    bulk = getattr(service.source, 'get_session_tree_revisions', None)
    with service.metrics.measure('ai_stats_revisions'):
        return bulk(ids) if callable(bulk) else {sid: service.source.get_session_tree_revision(sid) for sid in ids}


def _read(service, namespace, keys):
    try:
        with service.metrics.measure('ai_stats_cache_read'):
            service.metrics.add('ai_stats_cache_batches')
            return service.cache_repository.get_many(namespace, keys, busy_timeout_ms=50)
    except (OSError, sqlite3.Error):
        return {}


class StatsAcquisition:
    def __init__(self, service, scope):
        self.service, self.scope = service, scope
        service.metrics.mode = 'ai-stats'
        service.progress(WorkProgress('Loading reference prices', 'pricing'))
        # A typed price outage cannot erase independently observed token traffic.
        # These empty catalogs are local to this finite Stats service, not provider
        # or shared-price-cache writes; existing fun cost fallback stays separate.
        try:
            service._load_catalog()
        except PricingUnavailableError:
            service.catalog = PricingCatalog(())
        try:
            self.reference = service._load_comparison_catalog()
        except PricingUnavailableError:
            self.reference = service.comparison_pricing_catalog = PricingCatalog(())
        self.periods = windows(service.timezone_id, service.now_ms)
        service.progress(WorkProgress('Checking history revisions', 'catalog'))
        sessions = service.session_catalog()
        self.roots, _activity = service._ordered_roots(sessions)
        self.provenance = {r.session_id: r.provenance for r in self.roots}
        ancestry = root_by_session(sessions)
        self.active = {ancestry.get(s.session_id) for s in sessions if s.active is True}
        if len(self.roots) > MAX_ROOTS:
            raise StatsCheckpointError('ai_stats_resource_limit')
        self.revisions = _revisions(service, self.roots)
        self.keys = {r.session_id: dependency_signature((ALGORITHM, cache_key(service, r, self.reference))) for r in self.roots}
        self.bounds = {}
        self.evidence = {}
        self.fact_count = 0
        self.fresh = set()
        self.unavailable = set()
        self.pending = []
        self.checkpoint_busy = True
        self.checkpoint_error = None
        self.scan = getattr(service, 'stats_scan', None)
        with service.metrics.measure('ai_stats_restore'):
            self._restore()

    def _restore(self):
        # Volatile evidence belongs only to this pinned logical observation. It is
        # rehydrated before publication, never reused as a stable cache hit.
        for start in range(0, len(self.roots), BATCH_SIZE):
            roots = self.roots[start:start + BATCH_SIZE]
            keys = [self.keys[r.session_id] for r in roots]
            cached = _read(self.service, NAMESPACE, keys)
            self._restore_batch(roots, cached)
        if self.pending:
            self.bounds = _read(self.service, COVERAGE, (coverage_key(r) for r in self.pending))
        # Unknown roots remain candidates in EVERY period. Bounds only prioritize
        # demonstrably broader-only work, never turn missing evidence into zeros.
        cutoffs = [dict(self.periods)[name] for name in ('today', '7-days', self.scope)]
        self.pending.sort(key=lambda r: tuple(self._excludes(r, cutoff) for cutoff in cutoffs))

    def _excludes(self, root, start):
        return root.session_id not in self.active and exclusion(self.bounds.get(coverage_key(root)),
            self.revisions[root.session_id], start)

    def _restore_batch(self, roots, cached):
        stable = {root.session_id: self._decode(cached.get(self.keys[root.session_id]), root,
            self.revisions[root.session_id], self.service.source, self.service.now_ms) if root.session_id not in self.active else None for root in roots}
        missing = [self.keys[r.session_id] for r in roots if stable[r.session_id] is None]
        transient = _read(self.service, TRANSIENT, missing) if self.scan and missing else {}
        for root in roots:
            key, revision = self.keys[root.session_id], self.revisions[root.session_id]
            value = stable.pop(root.session_id)
            volatile = False
            if value is None and self.scan:
                checkpoint = transient.get(key)
                if checkpoint and isinstance(checkpoint.payload, dict) and checkpoint.payload.get('scan') == self.scan:
                    value = self._decode(replace(checkpoint, payload=checkpoint.payload.get('evidence')), root, revision,
                                         self.service.source, self.service.now_ms)
                volatile = value is not None
            self.service.metrics.add('ai_stats_cache_hits' if value else 'ai_stats_cache_misses')
            if value:
                self._retain(root.session_id, value, volatile)
            else:
                self.pending.append(root)

    @staticmethod
    def _decode(item, root, revision, source=None, now=None):
        if item and item.source_revision == revision and item.algorithm_version == ALGORITHM:
            try:
                return decoded(item.payload, root, source, now=now)
            except INVALID:
                pass
        return None

    def _retain(self, sid, value, volatile):
        previous = self.evidence.get(sid)
        if previous:
            self.fact_count -= len(previous[0][0].entries) + len(previous[0][0].intervals)
        self.fact_count += len(value[0].entries) + len(value[0].intervals)
        if self.fact_count > MAX_FACTS:
            raise StatsCheckpointError('ai_stats_resource_limit')
        self.evidence[sid] = value, volatile

    def _discard(self, sid):
        previous = self.evidence.pop(sid, None)
        if previous:
            self.fact_count -= len(previous[0][0].entries) + len(previous[0][0].intervals)
        self.service._acquisition.revisions.pop(sid, None)

    def _batch(self, roots):
        service = self.service
        with service.metrics.measure('ai_stats_snapshots'):
            snapshots = load_snapshots(service, roots)
        writes = []
        for root in roots:
            snapshot = snapshots.get(root.session_id)
            if snapshot is None:
                self.unavailable.add(root.session_id)
                self._discard(root.session_id)
                continue
            # The compact evidence cache is sufficient here: do not also persist
            # the much larger full analysis bundle in one SQLite transaction/root.
            bundle = service._analyze_snapshot(snapshot)
            with service.metrics.measure('ai_stats_evidence'):
                value = payload(bundle, self.reference, snapshot, service.config, now=service.now_ms)
                try:
                    facts = decoded(value, root, service.source)
                except ModelCatalogChanged as error:
                    raise StatsCheckpointError('ai_stats_revision_churn') from error
            volatile = not bundle.cacheable or root.session_id in self.active
            self._retain(root.session_id, facts, volatile)
            self.fresh.add(root.session_id)
            self.revisions[root.session_id] = snapshot.source_revision
            service.metrics.add('ai_stats_valued_requests', len(bundle.trace_entries))
            namespace = TRANSIENT if volatile and self.scan else NAMESPACE if not volatile else None
            scope = snapshot_scope(snapshot)
            if namespace:
                saved = dict(scan=self.scan, evidence=value) if volatile else value
                writes.append(CacheEntry(namespace, self.keys[root.session_id], saved, snapshot.source_revision, ALGORITHM, scope))
            if not volatile:
                proof = coverage(value)
                self.bounds[coverage_key(root)] = CacheEntry(COVERAGE, coverage_key(root), proof, snapshot.source_revision, COVERAGE, scope)
                writes.append(self.bounds[coverage_key(root)])
                if getattr(service, 'shared_web_evidence', False) and snapshot.complete:
                    from .shared_evidence import entries
                    # Stats and coverage are already in this batch. Publish only
                    # the other compatible products, without duplicate writes.
                    writes.extend(entry for entry in entries(service, root, snapshot.source_revision, value, scope)
                                  if entry.namespace not in (NAMESPACE, COVERAGE))
        try:
            with service.metrics.measure('ai_stats_cache_write'):
                service.cache_repository.put_many(writes, busy_timeout_ms=50)
            service.metrics.add('ai_stats_compact_writes', len(writes))
        except (OSError, sqlite3.Error) as error:
            code = getattr(error, 'sqlite_errorcode', None)
            self.checkpoint_busy &= (type(code) is int and code & 255 in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED))
            return False
        return True

    def acquire(self):
        service = self.service
        limit = getattr(service, 'stats_slice_roots', None)
        count = min(len(self.pending), limit) if limit else len(self.pending)
        persisted = True
        size = getattr(service, 'stats_batch_size', BATCH_SIZE)
        for start in range(0, count, size):
            persisted &= self._batch(self.pending[start:min(count, start + size)])
            service.progress(WorkProgress('Verifying shared history', 'history',
                len(self.evidence), len(self.roots), stage='history-load'))
        self.pending = self.pending[count:]
        if self.pending and limit and not persisted:
            self.checkpoint_error = 'ai_stats_checkpoint_busy' if self.checkpoint_busy else 'ai_stats_checkpoint_unavailable'
        # Changed/active roots cannot silently reuse a prior slice's timing. Wait
        # until stable coverage is ready, then refresh all volatile evidence once.
        volatile = [r for r in self.roots if r.session_id in self.evidence and self.evidence[r.session_id][1]
                    and r.session_id not in self.fresh]
        narrower_ready = any(all(self._excludes(r, left) for r in self.pending) for _name, left in self.periods)
        if narrower_ready and volatile:
            if limit and len(volatile) > limit:
                raise StatsCheckpointError('ai_stats_resource_limit')
            for start in range(0, len(volatile), size):
                self._batch(volatile[start:start + size])
        with service.metrics.measure('ai_stats_verification'):
            self._verify()

    def _verify(self):
        # Fresh complete membership AND tree revisions after the work. Earlier
        # roots may have changed while later roots were being acquired.
        service = self.service
        service.progress(WorkProgress('Verifying history coverage', 'catalog', stage='history-verify'))
        sessions = service.source.list_sessions()
        latest, _activity = service._ordered_roots(sessions)
        if len(latest) > MAX_ROOTS:
            raise StatsCheckpointError('ai_stats_resource_limit')
        if any(r.session_id in self.provenance and r.provenance != self.provenance[r.session_id] for r in latest):
            raise StatsCheckpointError('source_identity_changed')
        ancestry = root_by_session(sessions)
        self.active = {ancestry.get(s.session_id) for s in sessions if s.active is True}
        revisions = _revisions(service, latest)
        previous = {r.session_id for r in self.roots}
        invalid = {sid for sid, revision in self.revisions.items() if revisions.get(sid) != revision}
        invalid.update(r.session_id for r in latest if r.session_id not in previous)
        invalid.update(self.active - self.fresh)
        self.unavailable.update(invalid & (self.evidence.keys() | self.fresh))
        self.unavailable.intersection_update(r.session_id for r in latest)
        for sid in invalid:
            # Keep this observation's usable slice for fun figures. Do not certify
            # it against a newer revision or promote it to a stable cache hit.
            service._acquisition.revisions.pop(sid, None)
        for sid in previous - {r.session_id for r in latest}:
            self._discard(sid)
        self.roots, self.revisions = latest, revisions
        self.pending = [r for r in latest if r.session_id not in self.evidence]
        for root in latest:
            if root.session_id in self.evidence and root.session_id not in invalid:
                service._acquisition.revisions[root.session_id] = revisions[root.session_id]

    def project(self):
        service = self.service
        evidence, costs, matches = [], {}, []
        for root in self.roots:
            item = self.evidence.get(root.session_id)
            if not item:
                continue
            stat, facts, run = item[0]
            evidence.append(stat)
            matches.append(replace(run, title=stat.title) if run else None)
            for entry, _prompt, parts in facts:
                costs[entry.model, entry.tokens] = None if parts is None else sum(parts, Decimal(0))
        rows, scopes = [], {}
        calculation = StatsObservation(evidence, lambda model, tokens: costs[model, tokens],
                                       now=service.now_ms, zone=service.timezone_id,
                                       workday_calendar=service.config.get('workdayCalendar', 'SE'))
        for name, start in self.periods:
            excluded = [self.bounds.get(coverage_key(r)) for r in self.pending
                        if r.session_id not in self.unavailable and self._excludes(r, start)]
            omitted = sum(r.session_id in self.unavailable for r in self.pending)
            ready = len(excluded) + omitted == len(self.pending) and all(
                not volatile or sid in self.fresh for sid, (_facts, volatile) in self.evidence.items())
            scopes[name] = dict(completed=len(self.roots) - len(self.pending) + len(excluded), total=len(self.roots), ready=ready)
            gaps = migration_gap_notes(service.selection.migration_gap, start_ms=start)
            complete = not service.selection.warnings and not gaps and not self.unavailable and ready
            rows.append(replace(calculation.period(period=name, start=start, source_complete=complete),
                matched=period_fact([m for m in matches if m], start, service.now_ms,
                    complete=complete and all(r.source_complete for r in evidence) and all(matches)
                    and all(item.payload['matched'] for item in excluded))))
        gaps = migration_gap_notes(service.selection.migration_gap, start_ms=dict(self.periods)[self.scope])
        return ReportProjection(ReportKind.AI_STATS, 'AI Stats', service.selection.selected.upper(),
            (*service.selection.warnings, *((f'AI Stats roots not verified: {len(self.unavailable)}',) if self.unavailable else ())),
            notes=gaps, ai_stats=tuple(rows), history_omitted_roots=len(self.unavailable - self.evidence.keys()),
             ai_stats_work=dict(scopes=scopes, remaining=len(self.pending), completed=len(self.roots) - len(self.pending),
                                total=len(self.roots), checkpoint_error=self.checkpoint_error))


def build_ai_stats(service, scope):
    acquisition = StatsAcquisition(service, scope)
    acquisition.acquire()
    with service.metrics.measure('ai_stats_projection'):
        return acquisition.project()
