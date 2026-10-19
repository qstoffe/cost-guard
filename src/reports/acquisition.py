"""Revision-aware root acquisition and bounded source batch/cache orchestration."""
from __future__ import annotations

from typing import Callable, Sequence

from src.analysis.cache import AnalysisDependencies, DerivedAnalysisCache, analyze_with_cache, cached_analysis
from src.analysis.models import RootAnalysisBundle
from src.domain import NormalizedSession, SessionSnapshot
from src.domain.acquisition import AcquisitionMetrics
from src.sources.base import SessionSource
from .sampling import AnalyzedRoot


class RootAcquisition:
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

    def analyze(self, root: NormalizedSession, *, now_ms: int, detail: bool = False, force_fresh: bool = False,
                snapshot: SessionSnapshot | None = None) -> AnalyzedRoot:
        existing = self.analyzed.get(root.session_id)
        if not force_fresh and existing is not None and (not detail or existing.snapshot is not None):
            return existing
        self.metrics.add("analysis_candidate_roots")
        self.progress(f"Analyzing {root.session_id}")
        if force_fresh:
            # Live payloads may advance in place even when a cheap revision does
            # not. Running roots are authoritatively hydrated on every poll.
            snapshot = snapshot or self.source.load_session_snapshot(root.session_id)
            analyzed = AnalyzedRoot(root, self.analyzer(snapshot), False, snapshot)
        else:
            with self.metrics.measure("cache_and_acquisition"):
                result = analyze_with_cache(self.source, root, self.cache, self.dependencies(), self.analyzer, snapshot=snapshot)
            snapshot = result.snapshot or (existing.snapshot if existing else None)
            if detail and snapshot is None:
                snapshot = self.source.load_session_snapshot(root.session_id)
                if snapshot.source_revision != result.bundle.source_revision:
                    result = analyze_with_cache(self.source, root, self.cache, self.dependencies(), self.analyzer, snapshot=snapshot)
            analyzed = AnalyzedRoot(root, result.bundle, result.cache_hit, snapshot)
        self.analyzed[root.session_id] = analyzed
        self.analyzed_at_ms[root.session_id] = now_ms
        return analyzed

    def prepare(self, roots: Sequence[NormalizedSession], *, now_ms: int, detail: bool = False,
                force_fresh_ids: Sequence[str] = ()) -> frozenset[str]:
        """Batch only required snapshots; stable derived hits need no message reads."""
        batch = getattr(self.source, "load_session_snapshots", None)
        if not callable(batch):
            return frozenset()
        force = set(force_fresh_ids)
        pending = []
        for root in roots:
            existing = self.analyzed.get(root.session_id)
            if root.session_id not in force and existing is None:
                _, bundle = cached_analysis(self.source, root, self.cache, self.dependencies())
                if bundle is not None:
                    existing = AnalyzedRoot(root, bundle, True)
                    self.analyzed[root.session_id] = existing
            if root.session_id in force or existing is None or (detail and existing.snapshot is None):
                pending.append(root)
        if not pending:
            return frozenset()
        snapshots = batch(tuple(root.session_id for root in pending))
        for root in pending:
            snapshot = snapshots[root.session_id]
            existing = self.analyzed.get(root.session_id)
            if root.session_id not in force and existing is not None and existing.bundle.source_revision == snapshot.source_revision:
                existing.snapshot = snapshot
            else:
                self.analyzed.pop(root.session_id, None)
                self.analyze(root, now_ms=now_ms, detail=detail, force_fresh=root.session_id in force, snapshot=snapshot)
        return frozenset(snapshots)
