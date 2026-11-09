"""Revision-aware root acquisition and bounded source batch/cache orchestration."""
from __future__ import annotations

from typing import Callable, Mapping, Sequence

from src.analysis.cache import AnalysisDependencies, CacheObservation, DerivedAnalysisCache, analyze_with_cache, cached_analysis
from src.analysis.models import RootAnalysisBundle
from src.analysis.model_identity import current
from src.domain import NormalizedSession, SessionSnapshot
from src.domain.acquisition import AcquisitionMetrics
from src.domain.progress import WorkProgress
from src.sources.base import SessionSource
from src.sources.errors import FailureCode, SourceSnapshotMemberError
from .sampling import AnalyzedRoot


class RootAcquisition:
    sample_window_size = 2

    def __init__(self, source: SessionSource, cache: DerivedAnalysisCache, *,
                 dependencies: Callable[[], AnalysisDependencies], analyzer: Callable[[SessionSnapshot], RootAnalysisBundle],
                 progress: Callable[[str], None], metrics: AcquisitionMetrics) -> None:
        self.source = source
        self.cache = cache
        self.dependencies = dependencies
        self.analyzer = analyzer
        self.progress = progress
        self.metrics = metrics
        self.analyzed: dict[str, AnalyzedRoot] = {}
        self.analyzed_at_ms: dict[str, int] = {}
        # Retain revision evidence even when a deep scan releases hydrated roots.
        self.revisions: dict[str, str] = {}
        self._sample_snapshots: dict[str, SessionSnapshot] = {}
        self._sample_observations: dict[str, CacheObservation] = {}

    def clear_sample(self) -> None:
        """Unused speculative snapshots never become report-owned provenance."""
        self.metrics.add('sample_prefetch_discarded_roots', len(self._sample_snapshots.keys() | self._sample_observations.keys()))
        self._sample_snapshots.clear()
        self._sample_observations.clear()

    def prepare_sample(self, roots: Sequence[NormalizedSession]) -> None:
        """One bounded strict window, without analyzing or admitting its tail."""
        self.clear_sample()
        batch = getattr(self.source, 'load_session_snapshots_for_sampling', None)
        if not callable(batch) or len(roots) < 2:
            return
        if len(roots) > 8:
            raise ValueError('invalid_sampling_window')
        pending = []
        self.metrics.add('sample_prefetch_candidate_roots', len(roots))
        dependencies = self.dependencies()
        bulk = getattr(self.cache, 'observe_many', None)
        candidates = tuple(root for root in roots if root.session_id not in self.analyzed)
        if callable(bulk):
            self.progress(WorkProgress('Checking sample cache', 'history', stage='sampling-cache'))
            requests = tuple((root, self.source.get_session_tree_revision(root.session_id)) for root in candidates)
            self._sample_observations.update(bulk(requests, dependencies))
        for root in roots:
            if root.session_id not in self.analyzed:
                if callable(bulk):
                    bundle = self._sample_observations[root.session_id].bundle
                else:
                    self.progress(WorkProgress('Checking sample cache', 'history', stage='sampling-cache'))
                    revision, bundle = cached_analysis(self.source, root, self.cache, dependencies)
                    if bundle is not None:
                        self._sample_observations[root.session_id] = CacheObservation(root.session_id,
                            root.provenance, revision, dependencies, bundle)
                if bundle is None:
                    pending.append(root.session_id)
        if len(pending) < 2:
            return  # No bracket to amortize; staged hits still require current proof.
        self.metrics.add('sample_prefetch_batches')
        self.metrics.add('sample_prefetch_snapshot_roots', len(pending))
        try:
            self._sample_snapshots.update(batch(tuple(pending)))
        except SourceSnapshotMemberError as error:
            failure = error.failure
            local = failure.code in {FailureCode.DATA, FailureCode.CONCURRENT, FailureCode.RESET,
                FailureCode.DISCONNECTED, FailureCode.TIMEOUT}
            if error.session_id == roots[0].session_id or not local or failure.terminal:
                raise failure
            # No partial batch is accepted. Ordinary consumption now reads only
            # roots the sampler actually visits; no speculative retry loop.
            self.metrics.add('sample_prefetch_fallbacks')

    def observe(self, roots: Sequence[NormalizedSession], revisions: Mapping[str, str]) -> dict[str, CacheObservation]:
        """Bounded derived-cache windows for a caller-owned chunk; analyze rechecks every observation."""
        bulk = getattr(self.cache, 'observe_many', None)
        if not callable(bulk):
            return {}
        dependencies = self.dependencies()
        observations = {}
        for start in range(0, len(roots), 8):
            window = roots[start:start + 8]
            observations.update(bulk(tuple((root, revisions[root.session_id]) for root in window), dependencies))
        return observations

    def release(self, session_id: str, expected: AnalyzedRoot) -> None:
        """Drop an owned heavyweight value, preserving scalar provenance evidence."""
        if self.analyzed.get(session_id) is expected:
            self.analyzed.pop(session_id)
            self.analyzed_at_ms.pop(session_id, None)

    def analyze(self, root: NormalizedSession, *, now_ms: int, detail: bool = False, force_fresh: bool = False,
                snapshot: SessionSnapshot | None = None, report_progress: bool = True,
                observation: CacheObservation | None = None) -> AnalyzedRoot:
        existing = self.analyzed.get(root.session_id)
        if existing is not None and not current(self.source, (entry.model for entry in existing.bundle.trace_entries)):
            self.analyzed.pop(root.session_id, None)
            existing = None
        if not force_fresh and existing is not None and (not detail or existing.snapshot is not None):
            return existing
        prefetched = self._sample_snapshots.pop(root.session_id, None)
        staged = self._sample_observations.pop(root.session_id, None)
        observation = observation or staged
        if snapshot is None and not force_fresh and prefetched is not None:
            if (prefetched.root.session_id == root.session_id and prefetched.root.provenance == root.provenance
                    and prefetched.source_revision == self.source.get_session_tree_revision(root.session_id)):
                snapshot = prefetched
                self.metrics.add('sample_prefetch_consumed_roots')
            else:
                self.metrics.add('sample_prefetch_discarded_roots')
        self.metrics.add("analysis_candidate_roots")
        if report_progress:
            self.progress(WorkProgress(f"Analyzing {root.session_id}", "history"))
        if force_fresh:
            # Live payloads may advance in place even when a cheap revision does
            # not. Running roots are authoritatively hydrated on every poll.
            snapshot = snapshot or self.source.load_session_snapshot(root.session_id)
            analyzed = AnalyzedRoot(root, self.analyzer(snapshot), False, snapshot)
        else:
            with self.metrics.measure("cache_and_acquisition"):
                dependencies = self.dependencies()
                result = analyze_with_cache(self.source, root, self.cache, dependencies, self.analyzer,
                    snapshot=snapshot, observation=observation)
            snapshot = result.snapshot or (existing.snapshot if existing else None)
            if detail and snapshot is None:
                snapshot = self.source.load_session_snapshot(root.session_id)
                if snapshot.source_revision != result.bundle.source_revision:
                    result = analyze_with_cache(self.source, root, self.cache, self.dependencies(), self.analyzer, snapshot=snapshot)
            analyzed = AnalyzedRoot(root, result.bundle, result.cache_hit, snapshot)
        self.analyzed[root.session_id] = analyzed
        self.revisions[root.session_id] = analyzed.bundle.source_revision
        self.analyzed_at_ms[root.session_id] = now_ms
        return analyzed

    def prepare(self, roots: Sequence[NormalizedSession], *, now_ms: int, detail: bool = False,
                force_fresh_ids: Sequence[str] = (), progress_scope: str | None = None) -> frozenset[str]:
        """Batch only required snapshots; stable derived hits need no message reads."""
        batch = getattr(self.source, "load_session_snapshots", None)
        if not callable(batch):
            return frozenset()
        force = set(force_fresh_ids)
        pending = []
        def observe(label, step, completed=0, total=None):
            self.progress(WorkProgress(label, "history", completed, total,
                                      stage=f"{progress_scope}-{step}" if progress_scope else None))

        observe("Checking session cache", "cache", 0, len(roots))
        for index, root in enumerate(roots):
            existing = self.analyzed.get(root.session_id)
            if existing is not None and not current(self.source, (entry.model for entry in existing.bundle.trace_entries)):
                self.analyzed.pop(root.session_id, None)
                existing = None
            if root.session_id not in force and existing is None:
                _, bundle = cached_analysis(self.source, root, self.cache, self.dependencies())
                if bundle is not None:
                    existing = AnalyzedRoot(root, bundle, True)
                    self.analyzed[root.session_id] = existing
                    self.revisions[root.session_id] = bundle.source_revision
            if root.session_id in force or existing is None or (detail and existing.snapshot is None):
                pending.append(root)
            observe("Checking session cache", "cache", index + 1, len(roots))
        if not pending:
            observe("Session cache ready", "analysis", len(roots), len(roots))
            return frozenset()
        observe("Loading session snapshots", "load")
        observed_batch = getattr(self.source, "load_session_snapshots_observed", None)
        ids = tuple(root.session_id for root in pending)
        snapshots = (observed_batch(ids, lambda step, done, total: observe("Loading session snapshots", step, done, total))
                     if progress_scope == "date" and callable(observed_batch) else batch(ids))
        observe("Analyzing sessions", "analysis", 0, len(pending))
        for index, root in enumerate(pending):
            snapshot = snapshots[root.session_id]
            existing = self.analyzed.get(root.session_id)
            if root.session_id not in force and existing is not None and existing.bundle.source_revision == snapshot.source_revision:
                existing.snapshot = snapshot
            else:
                self.analyzed.pop(root.session_id, None)
                self.analyze(root, now_ms=now_ms, detail=detail, force_fresh=root.session_id in force,
                             snapshot=snapshot, report_progress=False)
            observe("Analyzing sessions", "analysis", index + 1, len(pending))
        return frozenset(snapshots)
