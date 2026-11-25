"""Host-warmed account history, isolated from Live's native quota and card lanes."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from decimal import Decimal
import sqlite3
from threading import Lock
from time import monotonic, thread_time, time_ns
from uuid import uuid4

from src.analysis.account_timeline import period_start, timeline_window
from src.analysis.account_timeline_cost import TimelineValuation
from src.analysis.causal import trace_entries
from src.analysis.coverage import snapshot_coverage_complete
from src.analysis.model_identity import current
from src.analysis.period_ccost import PeriodCCostIndex, reconcile_usage
from src.analysis.valuation import physical_usage_key
from src.application.account_timeline import account_roster, seed_today, timeline_view
from src.application.session_quota import source_scope
from src.cache.session_scope import snapshot_scope
from src.domain.session_tree import root_activity
from src.pricing.catalog import PricingCatalog
from src.reports.projection_cadence import cpu_cooldown
from src.reports.web_history_evidence import DOMAIN as ARCHIVED_USAGE
from src.reports.history_snapshots import load as load_snapshots
from src.reports.history_cohort import structure
from src.runtime_errors import recoverable, recovered
from src.sources.errors import SourceError
from . import account_timeline_warm as warm
from .account_timeline_projection import ArchivedAccountProjection
from .account_timeline_snapshots import AccountTimelineSnapshots


ROOTS_PER_TURN = 12
RETRY_MS = 30_000
PARTIAL_MS = 15_000
FOREGROUND_SLICE_MS = 200
FOREGROUND_PARTIAL_MS = 400
BACKGROUND_SLICE_MS = 2_000
BACKGROUND_REFRESH_MS = 60_000
BACKGROUND_START_MS = 3_000
ARCHIVE_BACKGROUND_MS = 5_000
ARCHIVE_BACKGROUND_CPU_SHARE = 0.05
ACTIVE_CUE_SECONDS = 4
REFRESH_MS = 15_000
NO_PUBLISHED_RATES = PricingCatalog(())


@dataclass(frozen=True, slots=True)
class RootUsage:
    revision: str
    provenance: object
    entries: tuple
    complete: bool
    retry_at_ms: int = 0
    membership: str | None = None


def _reconcile_entries(previous, entries, *, complete):
    saved = {key: entry for entry in previous if (key := physical_usage_key(entry)) is not None}
    current = []
    for entry in entries:
        old = saved.pop(physical_usage_key(entry), None)
        if old is not None and (old.model, old.account_ref) == (entry.model, entry.account_ref):
            entry = reconcile_usage(old, entry)
        current.append(entry)
    return tuple(current) if complete else (*current, *saved.values())


@dataclass(frozen=True, slots=True)
class CardToday:
    """Numeric Today values from the same qualified projection as the cards."""
    source: tuple
    zone: str
    day: int
    observed_at: int
    price_revision: str
    amounts: dict[tuple[str, str, str], Decimal]

    @classmethod
    def from_accounts(cls, accounts, source, zone, day, observed_at, history):
        amounts = {}
        for item in accounts:
            cost = dict(item.ccost_scopes).get('today')
            if cost is not None and cost.known_ccost > 0:
                amounts[item.account.key] = cost.known_ccost
        # The retention lane does not certify every chart candidate. A known
        # positive is useful provisionally; only chart coverage qualifies zeros.
        return cls(source, zone, day, observed_at, history.catalog.diagnostic_signature, amounts) if amounts else None


def _migration_gaps(gap, now_ms):
    if gap is not None and gap.has_gap:
        return tuple((item.first_ms, item.last_ms + 1) for item in gap.sessions) or ((0, now_ms),)
    return ()


class TimelineHistory:
    """One isolated worker owns revision-keyed facts; only summary values leave it."""

    def __init__(self, factory, reads, repository=None):
        self.factory, self.reads = factory, reads
        self.repository = repository
        self.attempted = {}
        self.active = frozenset()
        self.source = None
        self.roots = {}
        self.seen = set()
        self.index_key = self.index = None
        self.index_facts = ()
        self.partial_at = {}
        self.covered_periods = set()
        self.initial_periods = set()
        self.pending_periods = set()
        self.observation = None
        self.prices = None
        self.prices_due_ms = 0
        self.price_revision = None
        self.value_usage = None

    def _load(self, roots, observation, scope, now_ms):
        service = self.factory(now_ms)
        writes = []
        try:
            with self.reads.using(service.source):
                if source_scope(service.source) != scope:
                    return False
                service.allow_partial_history = True
                if callable(getattr(service.source, 'load_session_snapshots_available', None)):
                    snapshots = self._available(service, roots)
                else:
                    # On readers without partial batches, isolate a failed root
                    # rather than losing the other observations in the slice.
                    snapshots = {}
                    for root in roots:
                        snapshots.update(self._available(service, (root,)))
                if source_scope(service.source) != scope:
                    return False
                for root in roots:
                    key = root.session_id
                    revision = observation.revisions[key]
                    snapshot = snapshots.get(key)
                    previous = self.roots.get(key)
                    saved = previous.entries if previous is not None else ()
                    if (snapshot is None or snapshot.root.provenance != root.provenance
                            or snapshot.source_revision != revision):
                        self.roots[key] = RootUsage(revision, root.provenance, saved, False, now_ms + RETRY_MS)
                        continue
                    entries = trace_entries(snapshot)
                    complete = snapshot_coverage_complete(snapshot, entries) and all(
                        0 < entry.completed_at_ms <= now_ms for entry in entries)
                    if saved:
                        entries = _reconcile_entries(saved, entries, complete=complete)
                    membership = self.membership.get(key) if self.repository is not None else None
                    self.roots[key] = RootUsage(revision, root.provenance, entries, complete,
                                                0 if complete else now_ms + RETRY_MS, membership)
                    if (membership and complete and key not in observation.active_candidates
                            and key not in observation.live_candidates
                            and membership == structure(snapshot.sessions).get(key)):
                        lifecycle = snapshot_scope(snapshot)
                        if lifecycle.activity_ms is not None and (item := warm.entry(root, revision, membership,
                                entries, now_ms, lifecycle)) is not None:
                            writes.append(item)
        finally:
            service.close_accounts()
        if self.repository is not None:
            warm.publish(self.repository, writes)
        return True

    def _restore(self, roots, observation, active, scope, now_ms):
        candidates = [root for root in roots if root.session_id not in active
                      and observation.revisions.get(root.session_id) and root.session_id in self.membership
                      and self.attempted.get(root.session_id) != (observation.revisions[root.session_id],
                          self.membership[root.session_id]) and root.session_id not in self.roots]
        if not candidates:
            return
        for root in candidates:
            sid = root.session_id
            self.attempted[sid] = observation.revisions[sid], self.membership[sid]
        restored = dict(warm.restore(self.repository, candidates, observation.revisions, self.membership, now_ms))
        if not restored:
            return
        service = self.factory(now_ms)
        try:
            with self.reads.using(service.source):
                if source_scope(service.source) != scope:
                    return
                models = {(entry.model, entry.model.effort_default): entry.model
                          for entries in restored.values() for entry in entries}
                identities_current = current(service.source, models.values())
                validated = {}
                for root in candidates:
                    sid = root.session_id
                    entries = restored.get(sid)
                    if entries is not None and (identities_current
                            or current(service.source, (entry.model for entry in entries))):
                        validated[sid] = RootUsage(observation.revisions[sid], root.provenance, entries, True,
                                                   membership=self.membership[sid])
                if source_scope(service.source) == scope:
                    self.roots.update(validated)
                    self.seen.update(validated)
        except SourceError as error:
            if error.terminal:
                raise
        finally:
            service.close_accounts()

    @staticmethod
    def _available(service, roots):
        try:
            return load_snapshots(service, roots)
        except SourceError as error:
            if error.terminal:
                raise
            return {}

    def step(self, scope, observation, periods, roster, zone, catalog, prices, migration_gap, now_ms, *,
             foreground=False, preferred=(), shared_roots=None, require_prices=False):
        if self.source != scope:
            self.source = scope
            self.roots.clear()
            self.seen.clear()
            self.index_key = self.index = None
            self.index_facts = ()
            self.observation = None
            self.attempted = {}
            self.active = frozenset()
            self.partial_at.clear()
            self.covered_periods.clear()
            self.initial_periods.clear()
            self.pending_periods.clear()
            self.price_revision = self.value_usage = None
            self.prices, self.prices_due_ms = None, 0
        if now_ms >= self.prices_due_ms:
            self.prices_due_ms = now_ms + 15_000
            try:
                self.prices = prices() or self.prices
            except (OSError, sqlite3.Error):
                pass  # Existing price observation remains usable on a cache miss.
        catalog = self.prices or catalog
        if require_prices and not (catalog and catalog.models):
            self.pending_periods.clear()
            return {}, False, False
        price_revision = catalog.diagnostic_signature if catalog else None
        price_changed = self.price_revision != price_revision
        if price_changed or self.value_usage is None:
            self.price_revision = price_revision
            # Keep global request deduplication and prefix sums authoritative,
            # but don't revalue identical model/token inputs at every publication.
            previous = self.value_usage.catalog if self.value_usage else None
            self.value_usage = TimelineValuation(catalog or NO_PUBLISHED_RATES, previous)

        if observation is not self.observation:
            self.activity = root_activity(observation.sessions, observation.root_by_session)
            first = {}
            for session in observation.sessions:
                key = observation.root_by_session[session.session_id]
                first[key] = min(first.get(key, session.created_at_ms), session.created_at_ms)
            self.first = first
            if self.repository is not None:
                self.membership = structure(observation.sessions)
                self.attempted = {key: stamp for key, stamp in self.attempted.items()
                                  if key in observation.revisions}
            self.observation = observation
        activity, first = self.activity, self.first
        active = observation.active_candidates | observation.live_candidates
        starts = {period: period_start(period, now_ms, zone) for period in periods}
        cutoff = min(starts.values()) - 60_000
        roots = [root for root in observation.sessions if root.parent_session_id is None and (
            root.session_id in active or activity[root.session_id] >= cutoff)]
        provenance = {root.session_id: root.provenance for root in observation.sessions
                      if root.parent_session_id is None}
        retired = {key for key, value in self.roots.items()
                   if key not in provenance or provenance[key] != value.provenance
                   or self.repository is not None and value.membership is not None
                   and value.membership != self.membership.get(key)}
        retired.update((active - self.active) & self.roots.keys())
        self.active = active
        removed = bool(retired)
        self.seen.intersection_update(observation.revisions)
        self.seen.difference_update(retired)
        self.roots = {key: value for key, value in self.roots.items()
                      if key not in retired}
        if self.repository is not None and foreground:
            self._restore(roots, observation, active, scope, now_ms)
        # Use the card lane's already-acquired stable trees only at the same
        # source revision. Active/incomplete trees still get normal chart reads.
        for root in roots:
            key = root.session_id
            shared = shared_roots.get(key) if shared_roots is not None else None
            if (shared is not None and shared[0] == observation.revisions.get(key)
                    and key not in active and not ((saved := self.roots.get(key)) and
                        saved.complete and saved.revision == shared[0])
                    and all(entry.completed_at_ms <= now_ms for entry in shared[1])):
                self.roots[key] = RootUsage(shared[0], root.provenance, shared[1], True,
                    membership=self.membership.get(key) if self.repository is not None else None)
                self.seen.add(key)
        pending = [root for root in roots if root.session_id in observation.revisions and (
            (saved := self.roots.get(root.session_id)) is None
            or saved.revision != observation.revisions[root.session_id] or 0 < saved.retry_at_ms <= now_ms)]
        preferred_start = min((starts[period] for period in preferred), default=cutoff)
        pending.sort(key=lambda item: (item.session_id in self.seen,
                                        item.session_id not in active and activity[item.session_id] < preferred_start,
                                        item.session_id in self.roots,
                                        -activity[item.session_id], item.session_id))
        batch, remaining = pending[:ROOTS_PER_TURN], pending[ROOTS_PER_TURN:]
        if self.repository is not None and not foreground:
            self._restore(batch, observation, active, scope, now_ms)
            batch = [root for root in batch if not ((saved := self.roots.get(root.session_id))
                        and saved.complete and saved.revision == observation.revisions[root.session_id])]
        if batch:
            if not self._load(batch, observation, scope, now_ms):
                self.initial_periods.clear()
                self.pending_periods.clear()
                return {}, False, removed
            self.seen.update(root.session_id for root in batch)

        # Do not reprice the growing population after every acquisition slice.
        # Shorter scopes can settle while a longer requested window is loading.
        newest_pending = max((now_ms if root.session_id in active else activity[root.session_id]
                              for root in remaining), default=-1)
        newest_initial = max((now_ms if root.session_id in active else activity[root.session_id]
                              for root in remaining if root.session_id not in self.seen), default=-1)
        self.initial_periods = {period for period in periods if starts[period] <= newest_initial}
        self.pending_periods = {period for period in periods if starts[period] <= newest_pending}
        covered = {period for period in periods if not remaining or starts[period] > newest_pending}
        partial_ms = FOREGROUND_PARTIAL_MS if foreground else PARTIAL_MS
        ready = tuple(period for period in periods if not remaining or removed or price_changed
                      or period in covered - self.covered_periods
                      or now_ms >= self.partial_at.get(period, 0) + partial_ms)
        self.covered_periods = covered
        if not ready:
            return {}, bool(remaining), removed

        queued = {root.session_id for root in remaining}
        acquiring = []
        initial = []
        gaps = list(_migration_gaps(migration_gap, now_ms))
        for root in roots:
            key = root.session_id
            saved = self.roots.get(key)
            stale = saved is None or saved.revision != observation.revisions.get(key)
            if stale or not saved.complete:
                # Use the same activity bound as history candidate selection.
                # Unread active trees and unrooted sessions can affect Now.
                interval = (first[key], now_ms if key in active else max(first[key] + 1, activity[key] + 1))
                if key in queued and (stale or key not in self.seen):
                    acquiring.append(interval)
                    if key not in self.seen:
                        initial.append(interval)
                else:
                    gaps.append(interval)
        gaps.extend((stamp, now_ms) for key, stamp in first.items() if key not in observation.revisions)
        covered_from = min(first.values(), default=None)
        used = tuple(sorted(self.roots.items()))
        candidates = frozenset((route, item.account_key) for item in roster for route, _ in item.allocation)
        index_key = price_revision, candidates, tuple((key, id(value)) for key, value in used)
        if self.index_key != index_key:
            binding = None
            if (self.repository is not None and not active and not remaining and len(used) == len(roots)
                    and self.value_usage.previous is None
                    and all(value.complete and value.membership and value.revision == observation.revisions.get(key)
                            for key, value in used)):
                binding = warm.index_binding(scope, used, price_revision, candidates)
            self.index = warm.restore_index(self.repository, binding, now_ms) if binding is not None else None
            if self.index is None:
                self.index = PeriodCCostIndex((entry for _, value in used for entry in value.entries),
                    self.value_usage.reference, account_only=True, timeline_valuation=self.value_usage,
                    timeline_accounts=candidates)
                if binding is not None:
                    warm.publish_index(self.repository, binding, self.index, now_ms)
            # Holding the facts also prevents object ID reuse in the index key.
            self.index_key, self.index_facts = index_key, used
        by_period = {period: timeline_view(period, now_ms, zone, roster, self.index,
            first_covered_ms=covered_from, gaps=gaps, pending=acquiring, initial_pending=initial,
            price_revision=price_revision) for period in ready}
        self.partial_at.update((period, now_ms) for period in ready if remaining)
        if self.repository is not None and not remaining:
            self.repository.lifecycle.note_use(warm.root_keys(roots, self.roots, observation.revisions))
            self.repository.lifecycle.flush()
        return by_period, bool(remaining), removed


class AccountTimeline:
    """Live schedules at most one small slice; HTTP reads detached summaries only."""

    def __init__(self, factory, reads, repository=None, *, archived_usage=None, notify=None):
        self.archive = archived_usage.archive if archived_usage else None
        self.history = (ArchivedAccountProjection(self.archive) if self.archive
                        else TimelineHistory(factory, reads, repository))
        self.snapshots = AccountTimelineSnapshots(self.archive, notify) if self.archive else None
        self.archive_generation = None
        self.unavailable_history = frozenset()
        self.archive_live_roots = frozenset()
        self.archive_pending_history = frozenset()
        self.archive_coverage_confirmed = False
        self.archive_progress_roots = None
        self.archive_terminal = False
        self.archive_refresh_due = False
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='cost-guard-account-timeline')
        self.lock = Lock()
        self.scope = None
        self.day = None
        self.marker = uuid4().hex
        self.results = {}
        self.seeded = {}
        self.seed_input = None
        self.frame_revision = 0
        self.job = None
        self.fast = False
        self.initial_periods = set()
        self.pending_periods = set()
        self.active_periods = frozenset()
        self.active_until = 0
        self.price_revision = None
        self.demand = frozenset()
        self.foreground = frozenset()
        self.roster = ()
        self.public_roster = ()
        self.public_ready = False
        self.source = None
        self.due = self.last_started = 0
        self.archive_background_resume = 0
        self.retry_at = 0
        self.background_start = None
        self.closed = False

    def lookup(self, period, revision=None, *, zone=None):
        if self.snapshots is not None:
            return self.snapshots.lookup(period, revision, zone=zone, now=time_ns() // 1_000_000)
        with self.lock:
            value = self.seeded.get(period, self.results.get(period))
            marker, current = self.marker, self.frame_revision
            roster, ready = self.public_roster, self.public_ready
            acquiring = ready and period in self.active_periods and monotonic() < self.active_until
        return dict(scope=marker, revision=current, unchanged=value is not None and revision == current,
                      view=value if revision != current else None, series=roster if value is None else (), ready=ready,
                      acquiring=acquiring)

    def _publish_snapshots(self, periods, zone, now):
        if self.snapshots is not None:
            # Only this tick's owner mutates the report frames; HTTP readers
            # observe the previous batch until the next batch is committed.
            self.snapshots.publish(zone=zone, day=self.day, marker=self.marker, now=now, periods=periods,
                results={**self.results, **self.seeded}, roster=self.public_roster,
                ready=self.public_ready, active=self.active_periods, active_until=self.active_until)

    def tick(self, *, source, observation, accounts, periods, zone, catalog, prices, migration_gap,
             now_ms, available=True, terminal=False, card_today=None, shared_roots=None,
             foreground=None, require_background_prices=False, unavailable_history=frozenset(),
             live_roots=frozenset(), pending_history=frozenset(), coverage_confirmed=False, progress_roots=None):
        foreground = periods if foreground is None else foreground
        changed_source = source is not None and source != self.source
        if changed_source:
            self.source = source
        if available:
            roster = account_roster(accounts, now_ms=now_ms if self.archive else None)
        else:
            source, roster = self.source, () if changed_source else self.roster
        # Names and ordering can change without losing selections. Keys and
        # compatible account routes, unlike balances/labels, define membership.
        scope = ('shared-history', zone) if self.archive else (
            source, zone, frozenset((entry.key, entry.routes, entry.allocation) for entry in roster))
        if terminal:
            self.source = None
            roster = ()
            if not self.archive:
                scope = None
        day = period_start('today', now_ms, zone)
        day_changed = day != self.day
        self.day = day
        starts = {period: period_start(period, now_ms, zone) for period in periods}
        with self.lock:
            if self.archive or available or changed_source or terminal:
                self.public_ready = bool(self.archive) or available and not terminal
            if roster != self.roster or terminal:
                self.public_roster = tuple(dict(id=item.key, account=item.label)
                                           for item in roster) if not terminal else ()
            if scope != self.scope or day_changed:
                self.scope, self.marker = scope, uuid4().hex
                self.results.clear()
                self.seeded.clear()
                self.seed_input = None
                self.frame_revision += 1
                self.due = 0
                self.retry_at = 0
                self.archive_background_resume = 0
                self.initial_periods.clear()
                self.pending_periods.clear()
                self.active_periods = frozenset()
                self.price_revision = None
                self.background_start = None
            rolled = tuple(period for period, start in starts.items()
                           if period in self.results and self.results[period]['start_ms'] != start)
            if rolled:
                for period in rolled:
                    del self.results[period]
                    self.seeded.pop(period, None)
                self.frame_revision += 1
                self.due = 0
            marker = self.marker

        if self.job is not None and self.job.done():
            try:
                job_marker, job_revision, values, more, removed, initial, pending, elapsed, cpu = self.job.result()
                if job_marker == marker and (available or self.archive):
                    if self.archive is not None:
                        self.archive_background_resume = now_ms + int(
                            1000 * cpu_cooldown(cpu, ARCHIVE_BACKGROUND_CPU_SHARE))
                    self.initial_periods, self.pending_periods = initial, pending
                    values = {period: value for period, value in values.items()
                              if period_start('today', value['end_ms'], zone) == day
                              and value['start_ms'] == starts.get(period, value['start_ms'])}
                    price_revision = next(iter(values.values()))['price_revision'] if values else self.price_revision
                    repriced = price_revision != self.price_revision
                    if values or removed:
                        with self.lock:
                            if removed or repriced:
                                self.results.clear()
                            self.price_revision = price_revision
                            self.results.update(values)
                            self.frame_revision += 1
                            self._publish_today(periods, roster, card_today, source, zone, catalog, migration_gap, now_ms)
                    if foreground:
                        delay = FOREGROUND_SLICE_MS if pending & foreground else (
                            BACKGROUND_SLICE_MS if more else REFRESH_MS)
                    else:
                        rest = max(BACKGROUND_SLICE_MS, min(15_000, 3 * elapsed))
                        delay = elapsed + (rest if more else BACKGROUND_REFRESH_MS)
                    self.due = self.last_started + delay
                    if self.archive is not None and job_revision != self.archive.generation(ARCHIVED_USAGE):
                        # An earlier coherent snapshot may finish after a later
                        # publication; keep its own coverage and converge normally.
                        refresh = 1000 if foreground else ARCHIVE_BACKGROUND_MS
                        self.due = min(self.due, now_ms + refresh)
                    if rolled or day_changed:
                        self.due = 0
                recovered('account-timeline')
            except SourceError:
                self.retry_at = self.last_started + RETRY_MS
            except Exception as error:
                recoverable(error, 'account-timeline')
                self.retry_at = self.last_started + RETRY_MS
            self.job = None
            with self.lock:
                self.active_periods = frozenset()

        if periods != self.demand or self.roster != roster:
            self.demand, self.roster = periods, roster
            self.due = 0
        if foreground - self.foreground:
            if foreground - self.results.keys() or foreground & self.pending_periods:
                self.due = 0  # Promote incomplete work without bypassing source-error backoff.
            else:
                self.due = min(self.due, self.last_started + REFRESH_MS)
        if not foreground and self.foreground:
            self.due = max(self.due, self.last_started + BACKGROUND_SLICE_MS)
        self.foreground = foreground
        if self.archive:
            revision = self.archive.generation(ARCHIVED_USAGE)
            settled = (changed_source or terminal != self.archive_terminal
                       or coverage_confirmed != self.archive_coverage_confirmed
                       or unavailable_history != self.unavailable_history
                       or bool(self.archive_live_roots - live_roots)
                       or bool(self.archive_pending_history and not pending_history))
            if (revision, unavailable_history, live_roots, pending_history, coverage_confirmed, progress_roots) != (
                    self.archive_generation, self.unavailable_history, self.archive_live_roots,
                    self.archive_pending_history, self.archive_coverage_confirmed, self.archive_progress_roots):
                self.archive_generation = revision
                self.unavailable_history = unavailable_history
                self.archive_live_roots = live_roots
                self.archive_pending_history = pending_history
                self.archive_coverage_confirmed = coverage_confirmed
                self.archive_progress_roots = progress_roots
                # A warm idle timeline should notice new data without waiting
                # a minute, but a burst must not cancel the worker's backoff.
                if self.due >= self.last_started + BACKGROUND_REFRESH_MS:
                    interval = 1000 if foreground else ARCHIVE_BACKGROUND_MS
                    self.due = min(self.due, now_ms + interval)
            self.archive_terminal = terminal
            if settled:
                self.archive_refresh_due = True
        if available and not terminal:
            with self.lock:
                self._publish_today(periods, roster, card_today, source, zone, catalog, migration_gap, now_ms)
        if self.closed or not periods or (not self.archive and (
                terminal or not available or observation is None or not roster)):
            self.fast = False
            with self.lock:
                self.active_periods = frozenset()
            self._publish_snapshots(periods, zone, now_ms)
            return marker
        if self.background_start is None:
            self.background_start = now_ms + BACKGROUND_START_MS
        cold = (foreground - self.results.keys()) | (foreground & self.initial_periods)
        fast = cold or foreground & self.pending_periods
        due = max(0 if self.archive_refresh_due else self.due, self.retry_at,
                  self.background_start if not foreground else 0)
        if self.archive is not None and pending_history and not foreground and not self.archive_refresh_due:
            due = max(due, self.archive_background_resume)
        with self.lock:
            self.active_periods = cold if self.job is not None else frozenset()
        self.fast = bool(fast and (self.job is not None or due <= now_ms + FOREGROUND_SLICE_MS))
        minimum = FOREGROUND_SLICE_MS if fast else 1000 if foreground else BACKGROUND_SLICE_MS
        if self.archive is not None:
            minimum = (ARCHIVE_BACKGROUND_MS if pending_history and not foreground and not self.archive_refresh_due
                       else 1000)
        if self.job is not None or now_ms < max(due, self.last_started + minimum):
            self._publish_snapshots(periods, zone, now_ms)
            return marker
        self.last_started = now_ms
        self.archive_refresh_due = False

        def step():
            started = monotonic()
            cpu = thread_time()
            job_revision = self.archive.generation(ARCHIVED_USAGE) if self.archive else None
            extra = dict(unavailable_history=unavailable_history, live_roots=live_roots, progress_roots=progress_roots,
                          pending_history=pending_history, source_available=coverage_confirmed,
                          archive_revision=job_revision) if self.archive else {}
            values, more, removed = self.history.step(source, observation, sorted(periods), roster,
                zone, catalog, prices, migration_gap, now_ms, foreground=bool(fast), preferred=foreground,
                 shared_roots=shared_roots, require_prices=require_background_prices and not foreground, **extra)
            return (marker, job_revision, {period: value.to_json() for period, value in values.items()}, more, removed,
                      self.history.initial_periods.copy(), self.history.pending_periods.copy(),
                      int((monotonic() - started) * 1000),
                      thread_time() - cpu + (self.history.child_cpu if self.archive else 0))

        self.job = self.pool.submit(step)
        with self.lock:
            self.active_periods = cold
            self.active_until = monotonic() + ACTIVE_CUE_SECONDS
        self._publish_snapshots(periods, zone, now_ms)
        return marker

    def _publish_today(self, periods, roster, today, source, zone, catalog, migration_gap, now_ms):
        # Caller holds the frame lock: history, seeds and revision move together.
        daily = (periods | self.seeded.keys()) - {'today'}
        if not daily:
            return
        day = period_start('today', now_ms, zone)
        revision = self.price_revision or (catalog.diagnostic_signature if catalog else None)
        gaps = _migration_gaps(migration_gap, now_ms)
        if (today is None or (today.source, today.zone, today.day, today.price_revision) !=
                (source, zone, day, revision) or not day <= today.observed_at < now_ms):
            today = None
        signature = (today, frozenset(daily), self.frame_revision, roster, day)
        if signature == self.seed_input:
            return
        seeded = {}
        if today is not None:
            amounts = {item.key: today.amounts[item.account_key] for item in roster if item.account_key in today.amounts}
            for period in daily:
                view = self.results.get(period)
                if view is not None and view['end_ms'] <= today.observed_at:
                    continue
                if amounts and view is None and period in periods:
                    window = timeline_window(period, now_ms, zone)
                    pending = ((window.start, now_ms),)
                    view = timeline_view(period, now_ms, zone, roster, None, first_covered_ms=None,
                        gaps=gaps, pending=pending, price_revision=revision).to_json()
                if view is not None and (value := seed_today(view, day, amounts)) != view:
                    seeded[period] = value
        if seeded != self.seeded:
            self.seeded = seeded
            self.frame_revision += 1
        self.seed_input = (today, frozenset((periods | seeded.keys()) - {'today'}), self.frame_revision, roster, day)

    def close(self):
        self.closed = True
        if self.archive is not None:
            self.history.stop()
        self.pool.shutdown(wait=True, cancel_futures=True)
        if self.snapshots is not None:
            try:
                self.history.close()
            finally:
                self.snapshots.close()
