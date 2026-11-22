"""Fair bounded Sessions history slices on the existing scalar acquisition lane."""
from collections import deque
from dataclasses import dataclass
from itertools import islice

from src.analysis.cache import dependency_signature
from src.domain import NormalizedSession
from src.pricing.base import PricingUnavailableError
from src.reports.session_summary import ALGORITHM, EFFORT_REVISION, session_summary
from src.sources.errors import SourceError

from .request_archive_projection import request_roster
from .session_catalog_lifecycle import is_running, terminal_prompt
from .session_demand import SessionDemand

SCAN_WINDOW = 32
RETRY_SECONDS = 60
RECHECK_SECONDS = 900
PRIORITY_BACKOFF = (2, 5, 15)
PROJECTION_REVISION = "sessions-qualified-detail-6"


def scalar_dependency(service):
    return dependency_signature((ALGORITHM, EFFORT_REVISION,
        service._dependencies(service._load_catalog()), service._load_comparison_catalog().diagnostic_signature))


def checkpoint_dependency(base, model_authorities, terminal=None):
    values = (PROJECTION_REVISION, base, sorted(dependency_signature(value) for value in model_authorities))
    return dependency_signature(values if terminal is None else (*values, terminal))


def verified_finish(row, terminal):
    return (row.activity_qualified and not row.running and row.last_activity_ms is not None
            and (row.prompt_started_ms, row.activity_prompt_id) == terminal)


@dataclass(frozen=True, slots=True)
class SummaryCandidate:
    root: NormalizedSession
    revision: str
    incarnation: int
    terminal: tuple[int, str] | None


class SummaryCapture:
    def __init__(self, config):
        self.config = config
        self.usage = None

    def observe(self, snapshot, bundle, reference):
        self.usage = request_roster(snapshot, bundle, reference, config=self.config)


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
        self._urgent_turn = 0
        self._visible = SessionDemand()

    def due(self, catalog, binding):
        return (catalog.state == "observed" and binding is not None and
                (self.priority_due(catalog, binding) or self._background_due(catalog, binding)))

    def priority_due(self, catalog, binding):
        with catalog.lock:
            now = catalog.clock()
            return (self._visible.ready(self._demand_scope(catalog, binding), now)
                    or any(ready <= now for ready, _ in catalog.archive_urgent.values()))

    @staticmethod
    def _demand_scope(catalog, binding):
        return binding, catalog.archive_incarnation

    def offer_visible(self, catalog, binding, tab, sequence, keys, *, eligible):
        if not catalog.lock.acquire(blocking=False):
            return 0
        try:
            if catalog.state != "observed" or not eligible():
                return 0
            selected = tuple(key for key in keys if self._candidate(catalog, key) is not None)
            return self._visible.replace(self._demand_scope(catalog, binding), tab, sequence, selected, catalog.clock())
        finally:
            catalog.lock.release()

    def prioritize_detail(self, catalog, key, *, eligible):
        """A view hint can reorder existing work, but never open the source."""
        if not catalog.lock.acquire(blocking=False):
            return False
        try:
            if catalog.state != "observed" or not eligible() or self._candidate(catalog, key) is None:
                return False
            if key not in catalog.archive_urgent:
                catalog._archive_priority(key, front=True)
            else:
                catalog.archive_urgent.move_to_end(key, last=False)
            return True
        finally:
            catalog.lock.release()

    @staticmethod
    def _catalog_key(catalog, binding):
        return binding, catalog.archive_incarnation, catalog.membership_generation

    def _background_due(self, catalog, binding):
        return self._snapshot != self._catalog_key(catalog, binding) or catalog.clock() >= self._next_walk

    @staticmethod
    def _candidate(catalog, key):
        root, revision = catalog.roots.get(key), catalog.revisions.get(key)
        if root is None or not revision or is_running(catalog, key):
            return None
        # A captured terminal clears the Running overlay first. Whole-session
        # finish still requires the canonical scalar/linked activity function.
        terminal = terminal_prompt(catalog, key)
        if key in catalog.active and terminal is None:
            return None
        return SummaryCandidate(root, revision, catalog.archive_incarnation, terminal)

    def _candidates(self, catalog, binding):
        with catalog.lock:
            if catalog.state != "observed" or not self._background_due(catalog, binding):
                return {}
            snapshot = self._catalog_key(catalog, binding)
            if self._snapshot is None or self._snapshot[:2] != snapshot[:2] or self._walk is None:
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
            results = {}
            for key in self._queue:
                if key not in catalog.roots:
                    continue
                candidate = self._candidate(catalog, key)
                if candidate is None:
                    self._incomplete = True
                    continue
                if key not in catalog.archive_urgent:
                    results[key] = candidate
            return results

    def _urgent(self, catalog, binding):
        with catalog.lock:
            now = catalog.clock()
            scope = self._demand_scope(catalog, binding)
            ready = tuple((key, attempts) for key, (due, attempts) in catalog.archive_urgent.items() if due <= now)
            if catalog.state != "observed" or not (ready or self._visible.ready(scope, now)):
                return None
            self._urgent_turn += 1
            if self._urgent_turn % 4 == 0 and self._background_due(catalog, binding):
                return None  # Bounded burst of recent revisions, then old history.
            key = self._visible.take(scope, now)
            if key is not None and (candidate := self._candidate(catalog, key)) is not None:
                due, attempts = catalog.archive_urgent.get(key, (now, 0))
                if due <= now:
                    catalog.archive_urgent.pop(key, None)
                    return key, candidate, attempts
            for key, attempts in islice(ready, SCAN_WINDOW):
                del catalog.archive_urgent[key]
                candidate = self._candidate(catalog, key)
                if candidate is not None:
                    return key, candidate, attempts
            return None

    def tick(self, catalog, archive, service, binding, fence):
        cohort = binding[1], fence
        urgent = self._urgent(catalog, cohort)
        if urgent is not None:
            key, candidate, attempts = urgent
            try:
                base = scalar_dependency(service)
            except (PricingUnavailableError, SourceError):
                self._retry(catalog, key, candidate, attempts)
                raise
            if not self._try_acquire(catalog, archive, service, binding, base, key, candidate):
                self._retry(catalog, key, candidate, attempts)
            return
        candidates = self._candidates(catalog, cohort)
        if not candidates:
            self._queue.clear()
            return
        base = scalar_dependency(service)
        # v1 has no separate mutable model registry to validate. A v2 digest
        # alone cannot revalidate its native provider model observations.
        completed = archive.completed_summary_keys(binding, {
            key: candidate.revision for key, candidate in candidates.items() if candidate.terminal is None
        }, checkpoint_dependency(base, ())) if service.selection.selected == "v1" else frozenset()
        if completed is None:
            self._incomplete = True
            return
        while self._queue:
            key = self._queue.popleft()
            if key in completed or key not in candidates:
                continue
            candidate = candidates[key]
            if candidate.terminal is None:
                settled = self._acquire(catalog, archive, service, base, key, candidate)
            else:
                settled = self._try_acquire(catalog, archive, service, binding, base, key, candidate)
            self._incomplete |= not settled
            return

    def _try_acquire(self, catalog, archive, service, binding, base, key, candidate):
        if service.selection.selected == "v1":
            complete = archive.completed_summary_keys(binding, {key: candidate.revision},
                                                      checkpoint_dependency(base, (), candidate.terminal))
            if complete is None:
                return False
            if key in complete:
                return True
        return self._acquire(catalog, archive, service, base, key, candidate)

    def _retry(self, catalog, key, candidate, attempts):
        self._incomplete = True
        self._next_walk = min(self._next_walk, catalog.clock() + RETRY_SECONDS)
        if attempts >= len(PRIORITY_BACKOFF):
            return
        with catalog.lock:
            if (catalog.state == "observed" and self._candidate(catalog, key) == candidate
                    and key not in catalog.archive_urgent):
                catalog._archive_priority(key, delay=PRIORITY_BACKOFF[attempts], attempts=attempts + 1)

    def _acquire(self, catalog, archive, service, base, key, candidate):
        revision = candidate.revision
        with catalog.lock:
            if catalog.state != "observed" or self._candidate(catalog, key) != candidate:
                return False
            sequence = catalog.observation_sequence
        admission = archive.admit_summary(service, key, revision, observation_sequence=sequence)
        if admission is None:
            return False
        authorities = []
        capture = SummaryCapture(service.config)

        service.retain_derived_cache_read_only()
        try:
            row, actual = session_summary(service, candidate.root, revision, active=candidate.terminal is not None,
                                          on_dependencies=authorities.extend, persist_legacy=False,
                                          on_observation=capture.observe)
        except (PricingUnavailableError, SourceError):
            # A temporarily unreadable root must not starve other roots.
            return False
        if candidate.terminal is not None and not verified_finish(row, candidate.terminal):
            # A parent stop is not proof that its linked work also finished.
            # Preserve the previous as-of snapshot while final activity is unknown.
            return False
        def eligible():
            with catalog.lock:
                return catalog.state == "observed" and self._candidate(catalog, key) == candidate

        usage = capture.usage
        published = actual == revision and archive.publish_summary(
            service, admission, row, actual, eligible=eligible,
            dependency=checkpoint_dependency(base, authorities, candidate.terminal) if usage is not None else None,
            usage=usage)
        return (published and usage is not None and not row.running and not row.ccost_unavailable and row.complete
                 and row.activity_qualified and row.context_qualified and not row.model_pending)
