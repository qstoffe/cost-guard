"""Bounded verification of a source's older Sessions cohort, outside the display path."""
from itertools import islice

from src.cache.display_history import SessionCoverage
from src.pricing.base import PricingUnavailableError
from src.sources.errors import SourceError

from .session_archive_sweep import checkpoint_dependency, scalar_dependency
from .session_catalog_lifecycle import is_running, terminal_prompt

SLICE_SIZE = 256
RECENT_GRACE_MS = 10 * 60 * 1000


def in_recent_tail(floor, now_ms):
    return 0 < floor <= now_ms and floor >= now_ms - RECENT_GRACE_MS


def older_roster_changed(prior, current, now_ms):
    if not current.atomic_archive_roster or prior is None or not prior.atomic_archive_roster:
        return prior is not current
    previous, latest = prior.revisions, current.revisions
    before, after = prior.activity_floor or {}, current.activity_floor or {}
    # Source disappearance doesn't open a backfill gap in the local archive.
    # A later correction or return does, unless both clocks prove recent-only.
    for key, revision in latest.items():
        floor = after.get(key, 0)
        if key not in previous:
            if not in_recent_tail(floor, now_ms):
                return True
        elif (previous[key] != revision or before.get(key, 0) != floor) and not (
                in_recent_tail(floor, now_ms) and in_recent_tail(before.get(key, 0), now_ms)):
            return True
    return False


class SessionCoverageSweep:
    def __init__(self):
        self._walk = None
        self._key = None
        self._next = 0

    @staticmethod
    def _roster(catalog, binding, fence):
        return binding, fence, catalog.archive_incarnation, catalog.roster_sequence

    def due(self, catalog, binding, fence):
        observed = catalog.last_observation
        return (catalog.state == "observed" and observed is not None and observed.atomic_archive_roster
                and (self._walk is not None or self._key != self._roster(catalog, binding, fence)
                     or catalog.clock() >= self._next))

    def tick(self, catalog, archive, service, binding, fence):
        with catalog.lock:
            if not self.due(catalog, binding, fence):
                return
            key = self._roster(catalog, binding, fence)
            observed = catalog.last_observation
            invalidated = self._key is not None and self._key[:2] == key[:2] and self._key != key
            if key != self._key or self._walk is None:
                self._key = key
                self._walk = iter(catalog.roots)
                self._observed_ms = catalog.clock_ms()
                self._incomplete = self._unknown_clock = False
                self._published_gap = None
                self._newest_gap = None
                self._base = None
            scanned = tuple(islice(self._walk, SLICE_SIZE))
            batch = {root: catalog.revisions.get(root) for root in scanned if root in catalog.roots}
            terminals = {root: terminal for root in batch if (terminal := terminal_prompt(catalog, root)) is not None}
            running = {root for root in batch if is_running(catalog, root)}

        def eligible():
            with catalog.lock:
                return catalog.state == "observed" and key == self._roster(catalog, binding, fence)

        def widen_pending(*, unknown, newest=None):
            gap = SessionCoverage(self._observed_ms, True, unknown, newest)
            if self._published_gap is not None:
                gap = gap.with_gaps_from(self._published_gap)
            if gap != self._published_gap and archive.publish_coverage(
                    binding, fence, gap, eligible=eligible, widen_only=True):
                self._published_gap = gap

        # Do not leave an obsolete complete proof visible while processing a
        # known older revision, even when reading its price dependencies stalls.
        if invalidated:
            widen_pending(unknown=True)

        if self._base is None:
            try:
                self._base = scalar_dependency(service)
            except (SourceError, PricingUnavailableError):
                self._walk = None
                self._next = catalog.clock() + 30
                raise
        if scanned:
            if not batch:
                return
            checks = archive.coverage_slice(binding, batch)
            if checks is None:
                self._walk = None
                self._next = catalog.clock() + 5
                return
            floors = observed.activity_floor or {}
            regular = checkpoint_dependency(self._base, ())
            for root in batch:
                dependency, clock_known, clock = checks.get(root, (None, False, None))
                terminal = terminals.get(root)
                required = regular if terminal is None else checkpoint_dependency(self._base, (), terminal)
                floor = floors.get(root, 0)
                recent = in_recent_tail(floor, self._observed_ms) and (clock is None or clock >= floor)
                if (dependency == required and root not in running) or recent:
                    continue
                self._incomplete = True
                if not clock_known:
                    self._unknown_clock = True
                elif clock is not None:
                    self._newest_gap = max(clock, self._newest_gap or clock)
            if self._incomplete:
                widen_pending(unknown=self._unknown_clock, newest=self._newest_gap)
            return

        self._walk = None
        # A long roster walk may span multiple pricing observations. Don't
        # publish completion using a dependency that is no longer current.
        self._next = catalog.clock() + 5
        if self._base != scalar_dependency(service):
            widen_pending(unknown=True)
            return
        proof = SessionCoverage(self._observed_ms, self._incomplete, self._unknown_clock, self._newest_gap)
        if archive.publish_coverage(binding, fence, proof, eligible=eligible):
            self._next = catalog.clock() + (5 if self._incomplete else 30)
