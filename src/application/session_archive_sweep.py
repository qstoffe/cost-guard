"""Fair bounded Sessions history slices on the existing scalar acquisition lane."""
from collections import deque
from itertools import islice

from src.analysis.cache import dependency_signature
from src.reports.session_summary import ALGORITHM, EFFORT_REVISION, session_summary
from src.sources.errors import SourceError


SCAN_WINDOW = 32
RETRY_SECONDS = 60
RECHECK_SECONDS = 900
PROJECTION_REVISION = "sessions-activity-provenance-1"


def scalar_dependency(service):
    return dependency_signature((ALGORITHM, EFFORT_REVISION,
        service._dependencies(service._load_catalog()), service._load_comparison_catalog().diagnostic_signature))


def checkpoint_dependency(base, model_authorities):
    return dependency_signature((PROJECTION_REVISION, base,
                                 sorted(dependency_signature(value) for value in model_authorities)))


class SessionArchiveSweep:
    """Use the current observation, not a second independently enumerated catalog.

    Each slice scans a bounded window and acquires at most one root. A whole
    walk, or even a matching per-root marker, is not a coverage declaration.
    """
    def __init__(self):
        self._walk = None
        self._snapshot = None
        self._queue = deque()
        self._next_walk = 0
        self._incomplete = False

    def due(self, catalog, binding):
        return (catalog.state == "observed" and binding is not None and
                (self._snapshot != (binding, catalog.membership_generation) or catalog.clock() >= self._next_walk))

    def _candidates(self, catalog, binding):
        with catalog.lock:
            if not self.due(catalog, binding):
                return {}
            snapshot = binding, catalog.membership_generation
            if self._snapshot is None or self._snapshot[0] != binding or self._walk is None:
                self._snapshot = snapshot
                self._walk = iter(catalog.roots)
                self._queue.clear()
                self._incomplete = False
                self._next_walk = 0
            if not self._queue:
                self._queue.extend(islice(self._walk, SCAN_WINDOW))
                if not self._queue:
                    self._walk = None
                    self._next_walk = catalog.clock() + (RETRY_SECONDS if self._incomplete else RECHECK_SECONDS)
                    return {}
            observation = catalog.last_observation
            results = {}
            for key in self._queue:
                revision = catalog.revisions.get(key)
                if key not in catalog.roots:
                    continue
                if not revision or key in catalog.active or key in catalog.running_roots:
                    self._incomplete = True
                    continue
                results[key] = catalog.roots[key], revision, observation.source_epoch
            return results

    def tick(self, catalog, archive, service, binding):
        candidates = self._candidates(catalog, binding[1])
        if not candidates:
            self._queue.clear()
            return
        base = scalar_dependency(service)
        # v1 has no separate mutable model registry to validate. A v2 digest
        # alone cannot revalidate its native provider model observations.
        completed = archive.completed_summary_keys(binding, {
            key: revision for key, (_, revision, _) in candidates.items()
        }, checkpoint_dependency(base, ())) if service.selection.selected == "v1" else frozenset()
        if completed is None:
            self._incomplete = True
            return
        while self._queue:
            key = self._queue.popleft()
            if key in completed or key not in candidates:
                continue
            root, revision, epoch = candidates[key]
            admission = archive.admit_summary(service, key, revision)
            if admission is None:
                self._incomplete = True
                return
            authorities = []
            service.retain_derived_cache_read_only()
            try:
                row, actual = session_summary(service, root, revision, on_dependencies=authorities.extend,
                                              persist_legacy=False)
            except SourceError:
                # A temporarily unreadable root must not starve other roots.
                self._incomplete = True
                return
            with catalog.lock:
                current = (catalog.state == "observed" and catalog.roots.get(key) == root and actual == revision
                           and catalog.revisions.get(key) == revision and catalog.last_observation.source_epoch == epoch
                           and key not in catalog.active and key not in catalog.running_roots)
            published = current and archive.publish_summary(
                service, admission, row, actual, dependency=checkpoint_dependency(base, authorities))
            self._incomplete |= (not published or row.running or bool(row.ccost_unavailable) or not row.complete
                                 or not row.activity_qualified or not row.context_qualified or row.model_pending)
            return
