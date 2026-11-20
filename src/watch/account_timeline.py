"""Demand-driven account history, isolated from Live's native quota and card lanes."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import sqlite3
from threading import Lock
from uuid import uuid4

from src.analysis.account_timeline import period_start
from src.analysis.causal import trace_entries
from src.analysis.coverage import snapshot_coverage_complete
from src.analysis.period_ccost import PeriodCCostIndex
from src.application.account_timeline import quota_roster, retain_compatible_quotas, timeline_view
from src.application.session_quota import source_scope
from src.domain.session_tree import root_activity
from src.reports.history_snapshots import load as load_snapshots
from src.runtime_errors import recoverable, recovered
from src.sources.errors import SourceError


ROOTS_PER_TURN = 12
RETRY_MS = 30_000
PARTIAL_MS = 15_000


@dataclass(frozen=True, slots=True)
class RootUsage:
    revision: str
    entries: tuple
    complete: bool
    retry_at_ms: int = 0
    acquired: bool = True


class TimelineHistory:
    """One isolated worker owns revision-keyed facts; only summary values leave it."""

    def __init__(self, factory, reads):
        self.factory, self.reads = factory, reads
        self.source = None
        self.roots = {}
        self.seen = set()
        self.index_key = self.index = None
        self.index_facts = ()
        self.partial_at = {}
        self.covered_periods = set()
        self.observation = None
        self.prices = None
        self.prices_due_ms = 0

    def _load(self, roots, observation, scope, now_ms):
        service = self.factory(now_ms)
        try:
            with self.reads.using(service.source):
                if source_scope(service.source) != scope:
                    return False
                service.allow_partial_history = True
                snapshots = load_snapshots(service, roots)
                if source_scope(service.source) != scope:
                    return False
                for root in roots:
                    key = root.session_id
                    revision = observation.revisions[key]
                    snapshot = snapshots.get(key)
                    if (snapshot is None or snapshot.root.provenance != root.provenance
                            or snapshot.source_revision != revision):
                        self.roots[key] = RootUsage(revision, (), False, now_ms + RETRY_MS, acquired=False)
                        continue
                    entries = trace_entries(snapshot)
                    complete = snapshot_coverage_complete(snapshot, entries) and all(
                        0 < entry.completed_at_ms <= now_ms for entry in entries)
                    self.roots[key] = RootUsage(revision, entries, complete,
                                                0 if complete else now_ms + RETRY_MS)
        except SourceError as error:
            if error.terminal:
                raise
            for root in roots:
                key = root.session_id
                self.roots[key] = RootUsage(observation.revisions[key], (), False, now_ms + RETRY_MS, acquired=False)
        finally:
            service.close_accounts()
        return True

    def step(self, scope, observation, periods, roster, zone, catalog, prices, migration_gap, now_ms):
        if self.source != scope:
            self.source = scope
            self.roots.clear()
            self.seen.clear()
            self.index_key = self.index = None
            self.index_facts = ()
            self.observation = None
            self.partial_at.clear()
            self.covered_periods.clear()
        if now_ms >= self.prices_due_ms:
            self.prices_due_ms = now_ms + 15_000
            try:
                self.prices = prices() or self.prices
            except (OSError, sqlite3.Error):
                pass  # Existing price observation remains usable on a cache miss.
        catalog = self.prices or catalog

        if observation is not self.observation:
            self.activity = root_activity(observation.sessions, observation.root_by_session)
            first = {}
            for session in observation.sessions:
                key = observation.root_by_session[session.session_id]
                first[key] = min(first.get(key, session.created_at_ms), session.created_at_ms)
            self.first = first
            self.observation = observation
        activity, first = self.activity, self.first
        active = observation.active_candidates | observation.live_candidates
        starts = {period: period_start(period, now_ms, zone) for period in periods}
        cutoff = min(starts.values()) - 60_000
        roots = [root for root in observation.sessions if root.parent_session_id is None and (
            root.session_id in active or activity[root.session_id] >= cutoff)]
        removed = bool(set(self.roots) - observation.revisions.keys())
        self.seen.intersection_update(observation.revisions)
        self.roots = {key: value for key, value in self.roots.items()
                      if observation.revisions.get(key) == value.revision}
        pending = [root for root in roots if root.session_id in observation.revisions and (
            (saved := self.roots.get(root.session_id)) is None or 0 < saved.retry_at_ms <= now_ms)]
        pending.sort(key=lambda item: (item.session_id in self.seen, item.session_id in self.roots,
                                       -activity[item.session_id], item.session_id))
        batch, remaining = pending[:ROOTS_PER_TURN], pending[ROOTS_PER_TURN:]
        if batch:
            if not self._load(batch, observation, scope, now_ms):
                return {}, False, removed, ()
            self.seen.update(root.session_id for root in batch)

        # Do not reprice the growing population after every acquisition slice.
        # Shorter scopes can settle while a longer requested window is loading.
        newest_pending = max((now_ms if root.session_id in active else activity[root.session_id]
                              for root in remaining), default=-1)
        covered = {period for period in periods if not remaining or starts[period] > newest_pending}
        ready = tuple(period for period in periods if not remaining or removed
                      or period in covered - self.covered_periods
                      or now_ms >= self.partial_at.get(period, 0) + PARTIAL_MS)
        self.covered_periods = covered
        if not ready:
            return {}, bool(remaining), removed, ()

        unread = {root.session_id for root in remaining if root.session_id not in self.roots}
        acquiring = []
        gaps = []
        if migration_gap is not None and migration_gap.has_gap:
            gaps.extend((item.first_ms, item.last_ms + 1) for item in migration_gap.sessions)
            if not migration_gap.sessions:
                gaps.append((0, now_ms))
        for root in roots:
            key = root.session_id
            saved = self.roots.get(key)
            if saved is None or not saved.complete:
                # Use the same activity bound as history candidate selection.
                # Unread active trees and unrooted sessions can affect Now.
                intervals = acquiring if key in unread else gaps
                intervals.append((first[key], now_ms if key in active else max(first[key] + 1, activity[key] + 1)))
        gaps.extend((stamp, now_ms) for key, stamp in first.items() if key not in observation.revisions)
        covered_from = min(first.values(), default=None)
        used = tuple(sorted(self.roots.items()))
        index_key = (catalog.diagnostic_signature, tuple((key, id(value)) for key, value in used)) if catalog else None
        if catalog is not None and self.index_key != index_key:
            self.index = PeriodCCostIndex((entry for _, value in used for entry in value.entries),
                                          catalog.reference_valuation, verified_models=True)
            # Holding the facts also prevents object ID reuse in the index key.
            self.index_key, self.index_facts = index_key, used
        by_period = {period: timeline_view(period, now_ms, zone, roster, self.index if catalog else None,
            first_covered_ms=covered_from, gaps=gaps, pending=acquiring) for period in ready}
        self.partial_at.update((period, now_ms) for period in ready if remaining)
        failed = {root.session_id for root in roots if (value := self.roots.get(root.session_id)) and not value.acquired}
        interrupted = tuple(period for period in ready if any(
            key in active or activity[key] >= starts[period] for key in failed))
        return by_period, bool(remaining), removed, interrupted


class AccountTimeline:
    """Live schedules at most one small slice; HTTP reads detached summaries only."""

    def __init__(self, factory, reads):
        self.history = TimelineHistory(factory, reads)
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='cost-guard-account-timeline')
        self.lock = Lock()
        self.scope = None
        self.marker = uuid4().hex
        self.results = {}
        self.frame_revision = 0
        self.job = None
        self.demand = frozenset()
        self.roster = ()
        self.public_roster = ()
        self.public_ready = False
        self.native_accounts = {}
        self.source = None
        self.due = self.last_started = 0
        self.closed = False

    def lookup(self, period, revision=None):
        with self.lock:
            value = self.results.get(period)
            marker, current = self.marker, self.frame_revision
            roster, ready = self.public_roster, self.public_ready
        return dict(scope=marker, revision=current, unchanged=value is not None and revision == current,
                    view=value if revision != current else None, series=roster if value is None else (), ready=ready)

    def tick(self, *, source, observation, accounts, periods, boosted, zone, catalog, prices, migration_gap,
             now_ms, available=True, terminal=False):
        changed_source = source is not None and source != self.source
        if changed_source:
            self.source, self.native_accounts = source, {}
        if available:
            compatible = retain_compatible_quotas(accounts, self.native_accounts)
            self.native_accounts = {item.account.key: item.account for item in compatible}
            roster = quota_roster(compatible)
        else:
            source, roster = self.source, () if changed_source else self.roster
        # Names and ordering can change without losing selections. Keys and
        # compatible account routes, unlike balances/labels, define membership.
        scope = (source, zone, frozenset((entry.key, entry.routes, entry.estimates) for entry in roster))
        if terminal:
            self.source, self.native_accounts = None, {}
            roster = ()
            scope = None
        with self.lock:
            if available or changed_source or terminal:
                self.public_ready = available and not terminal
            if roster != self.roster or terminal:
                self.public_roster = tuple(dict(id=item.key, account=item.label, quota=item.quota, primary=item.primary)
                                           for item in roster) if not terminal else ()
            if scope != self.scope:
                self.scope, self.marker = scope, uuid4().hex
                self.results.clear()
                self.frame_revision += 1
                self.due = 0
            marker = self.marker

        if self.job is not None and self.job.done():
            try:
                job_marker, values, more, removed, interrupted = self.job.result()
                if job_marker == marker and available:
                    if not removed:
                        values = {period: value for period, value in values.items()
                                  if period not in interrupted or period not in self.results
                                  or (period != '7-days' and value['start_ms'] != self.results[period]['start_ms'])
                                  or self.results[period]['pending_buckets']}
                    if values or removed:
                        with self.lock:
                            if removed:
                                self.results.clear()
                            self.results.update(values)
                            self.frame_revision += 1
                    self.due = self.last_started + ((1000 if boosted else 4000) if more else 15_000)
                recovered('account-timeline')
            except SourceError:
                self.due = self.last_started + RETRY_MS
            except Exception as error:
                recoverable(error, 'account-timeline')
                self.due = self.last_started + RETRY_MS
            self.job = None

        if periods != self.demand or self.roster != roster:
            self.demand, self.roster = periods, roster
            self.due = 0
        if (self.closed or terminal or not available or not periods or observation is None or
                not roster or self.job is not None or now_ms < max(self.due, self.last_started + 1000)):
            return marker
        self.last_started = now_ms

        def step():
            values, more, removed, interrupted = self.history.step(source, observation, sorted(periods), roster,
                zone, catalog, prices, migration_gap, now_ms)
            return marker, {period: value.to_json() for period, value in values.items()}, more, removed, interrupted

        self.job = self.pool.submit(step)
        return marker

    def close(self):
        self.closed = True
        self.pool.shutdown(wait=True, cancel_futures=True)
