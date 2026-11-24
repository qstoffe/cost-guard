"""Shared live catalog, bounded scalar indexing and stable server-side page epochs.

HTTP reads never acquire history. Metric ordering is admitted only with keys for
every period-eligible root; an unindexed root is not a canonically unknown metric.
"""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from heapq import nsmallest
from threading import Event, Lock
import time
from uuid import uuid4

from src.analysis.cache import dependency_signature
from src.analysis.model_identity import payload_current
from src.cache.web_archive import scope_partition, source_partition
from src.domain.session_tree import root_activity
from src.pricing.base import PricingUnavailableError
from src.reports.models import SessionUsageRow
from src.reports.session_summary import session_summary
from src.reports import web_history_evidence
from src.sources.errors import SourceError
from src.watch.models import SessionPreview

from .detail_archive import acquired_detail
from .session_active_snapshots import ActiveSnapshotOffers
from .session_archive import SessionArchive, cached_page, retain_pending_metrics, retain_readable_fields
from .session_epoch_page import ARRIVAL_SECONDS, epoch_page, ordered, recent_live_roots, sort_value
from .session_quota import source_scope
from .session_catalog_scope import (
    PAGE_SIZE, PERIODS, activity_time, catalog_window, candidate_population, in_window, retain_live_arrivals,
)

SORTS = ("activity", "name", "model", "ccost", "prompts", "duration", "ctx")

PASSIVE_ATTEMPTS = 4
ARCHIVE_QUALIFICATION_ATTEMPTS = 3
INTERACTIVE_ATTEMPTS = 12
INTERACTIVE_ADMISSION_SECONDS = 0.35
PROMPT_FRESHNESS_MS = 15_000
UNCHANGED_ACTIVE_READ_SECONDS = 15
FINISH_PLACEMENT_MS = 120_000
# Maximum Mini viewport (10) plus a small scrollback window. The card
# scheduler still owns bounded source admission; this shortlist is in-memory.
MINI_PREVIEW_LIMIT = 15


@dataclass(frozen=True, slots=True)
class PromptEvidence:
    observed_ms: int
    prompt_id: str
    start_ms: int
    running: bool
    finish_ms: int | None
    ended: bool = False
    revision: str | None = None

    @property
    def identity(self):
        return self.start_ms, self.prompt_id


class SessionCatalog:
    def __init__(self, *, clock=time.monotonic, clock_ms=lambda: int(time.time() * 1000),
                 timezone_id="UTC", archive=None, legacy_archive=None, archive_upgrade=None):
        self.clock = clock
        self.clock_ms = clock_ms
        self.lock = Lock()
        self.roots = OrderedDict()
        self.rows = {}
        self.revisions = {}
        self.valid = {}
        self.attempted = {}
        self.failures = {}
        self.failure_counts = {}
        self.failure_reasons = {}
        self.generation = 0
        self.metrics = dict(cache_hits=0, cache_misses=0, attempts=0, retries=0, settled=0)
        self.work = None
        self.work_sequence = 0
        self.activity = {}
        self.activity_index = ()
        self.activity_valid = {}
        self.changed_roots = set()
        self.active = frozenset()
        self.prompt_activity = {}
        self.running_roots = set()
        self.active_snapshots = ActiveSnapshotOffers()
        self.recent_finishes = {}
        self.interrupted = False
        self.lifecycle_cutoff_ms = 0
        self.leases = OrderedDict()
        self.state = "loading"
        self.dependencies = None
        self.model_dependencies = {}
        self.timezone_id = timezone_id
        self.unit = "credits"
        self.turn = 0
        self.checked_at = -100
        self.index_unavailable = False
        self.index_failure = None
        self.index_terminal = False
        self.warm = False
        self.last_page = ()
        self.background_due = 0
        self.observed = None
        self.observed_ms = None
        self.last_observation = None
        self.orders = OrderedDict()
        self.discovery = {}
        self.recent_arrivals = {}
        self.live_arrivals = set()
        self.discovery_sequence = 0
        self.preview_totals = {}
        self.wake_identity = uuid4().hex
        self.wake_revision = 0
        self.archive = (SessionArchive(archive, legacy_archive, timezone_id=timezone_id, upgrade=archive_upgrade)
                        if archive is not None else None)
        self.history_pending = {}
        self.history_turn = False
        self.archive_rejections = {}
        self.archive_attempts = 0
        self.archive_revision = 0
        self.archive_retry_at = 0
        self.archive_target = None
        self.archive_job = None
        self.legacy_job = None
        self.legacy_attempts = 0
        self.legacy_retry_at = 0
        self.legacy_done = False
        self.archive_stopping = Event()
        self.archive_pool = (ThreadPoolExecutor(max_workers=1, thread_name_prefix='cost-guard-archive-restore')
                             if self.archive is not None else None)

    def bind_archive(self, generation, instance, epoch=None):
        if self.archive is None:
            return
        partition = source_partition(generation, instance, epoch)
        with self.lock:
            if partition != self.archive_target:
                self.archive_target = partition
                self.archive.partition = partition if self.archive.loaded else None
                self.archive_rejections.clear()
                self.history_pending.clear()
                self.live_arrivals.clear()
                self.rows.clear()
                self.valid.clear()
                self.orders.clear()
                self.wake_revision += 1
            return self.archive.partition, self.archive_target

    def archive_maintenance(self):
        """Advance storage recovery independently of the source binding."""
        archive = self.archive
        if archive is None:
            return
        with self.lock:
            if self.archive_stopping.is_set():
                return
            now = self.clock()
            if not archive.loaded:
                if self.archive_job is not None or now < self.archive_retry_at:
                    return
                self.archive_attempts += 1
                self.archive_job = job = self.archive_pool.submit(archive.load)
                complete = self._archive_complete
            else:
                if (archive.legacy is None or self.legacy_done or self.legacy_job is not None
                        or now < self.legacy_retry_at):
                    return
                self.legacy_attempts += 1
                self.legacy_job = job = self.archive_pool.submit(archive.load_legacy, self.archive_stopping.is_set)
                complete = self._legacy_complete
        # A completed future calls back immediately; never attach under self.lock.
        job.add_done_callback(complete)

    @staticmethod
    def _archive_backoff(attempt):
        return min(60, 5 * 2 ** min(4, attempt - 1))

    def _archive_complete(self, job):
        if job.cancelled():
            return
        saved = job.result()
        with self.lock:
            self.archive_job = None
            if self.archive_stopping.is_set():
                return
            if saved is None:
                self.archive_retry_at = self.clock() + self._archive_backoff(self.archive_attempts)
            else:
                self.archive.loaded = True
                self.archive.partition = self.archive_target
                self.archive.rows, self.archive.authorities = saved
                self.archive_revision += 1
                self._restore_archived_rows()
            self._archive_publication()

    def _legacy_complete(self, job):
        if job.cancelled():
            return
        (rows, authorities), retry = job.result()
        with self.lock:
            self.legacy_job = None
            if self.archive_stopping.is_set():
                return
            changed = False
            for key, imported in rows.items():
                existing = self.archive.rows.get(key)
                # A batch can complete after a newer live write. Fill gaps but
                # never replace an acquired row with its legacy counterpart.
                authority = authorities[key]
                previous = self.archive.authorities.get(key)
                if previous is None or self.archive.prefers(authority, previous):
                    row = retain_readable_fields(imported, existing)
                    self.archive.authorities[key] = authority
                else:
                    row = retain_readable_fields(existing, imported)
                if row != existing:
                    changed = True
                    self.archive.rows[key] = row
                    if key in self.rows:
                        self.rows[key] = retain_readable_fields(self.rows[key], row)
            self.legacy_done = not retry
            self.legacy_retry_at = self.clock() + self._archive_backoff(self.legacy_attempts)
            if changed:
                self.archive_revision += 1
            if changed or self.legacy_attempts == 1 or self.legacy_done:
                self._archive_publication()

    def _archive_publication(self):
        self._record_history_pending()
        self.orders.clear()
        self.generation += 1
        self.wake_revision += 1

    def close(self):
        if self.archive_pool is not None:
            with self.lock:
                self.archive_stopping.set()
            self.archive_pool.shutdown(wait=True, cancel_futures=True)

    def _restore_archived_rows(self):
        if self.archive is None or self.dependencies is None:
            return
        for key in self.archive.rows.keys() & self.roots.keys():
            revision, dependencies, models, partition, _ = self.archive.authorities[key]
            if key in self.rows or key in self.active or key in self.running_roots:
                continue
            if (partition == self.archive.partition and dependencies == self.dependencies
                    and revision == self.revisions.get(key)):
                row = self.archive.rows[key]
                self.rows[key] = row
                self.valid[key] = self.revisions[key], self.clock()
                self.activity_valid[key] = self.revisions[key]
                self.model_dependencies[key] = models

    def live_hint(self):
        """Constant-size wake hint, not row/membership or scalar-value proof."""
        with self.lock:
            return f"{self.wake_identity}:{self.wake_revision}"

    def enable_warm(self, enabled=True):
        with self.lock:
            self.warm = enabled

    def interest(self, token, visible):
        with self.lock:
            lease = self.leases.get(token)
            if lease is None:
                raise KeyError('catalog_expired')
            lease['interest_until'] = self.clock() + 90 if visible else self.clock()

    def _browsing(self, lease):
        return (self.clock() < lease['interest_until'] if 'interest_until' in lease
                else self.clock() - lease['touched'] <= 300)

    def _targets(self):
        if self.archive is not None:
            return self.roots.keys()
        browsing = [lease for lease in self.leases.values() if self._browsing(lease)]
        selected = set()
        for lease in browsing:
            # A verified pinned page has complete cohort coverage. A provisional
            # page does not prove that offscreen live candidates are absent.
            if not lease.get('pinned') or not lease.get('cohort_verified'):
                selected.update(self.active)
                selected.update(self.running_roots)
                selected.update(key for key, proof in self.prompt_activity.items()
                    if proof.ended and proof.finish_ms is None and not self._activity_current(key))
            navigation = lease.get('navigation')
            if navigation is not None:
                if navigation.invalid:
                    continue
                selected.update(navigation.pending)
                # A previously released live lane stays eligible under repeated
                # clicks, but never admits arrivals before the first application.
                if lease.get('released'):
                    lease['candidates'] = self._population(lease['period'])[1]
                    selected.update(lease['candidates'])
                continue
            selected.update(lease.get('visible', ()))
            selected.update(lease.get('nearby', ()))
            if not lease.get('pinned') and (lease.get('sort') not in (None, 'name')
                                          or lease.get('period') != 'all'):
                lease['candidates'] = self._population(lease['period'])[1]
                selected.update(lease['candidates'])
        if browsing:
            return selected & self.roots.keys()
        if not self.warm or self.clock() < self.background_due:
            return set()
        now = self.clock_ms()
        return set(nsmallest(PAGE_SIZE, self.roots,
            key=lambda key: (-(self.activity.get(key) or 0) if (self.activity.get(key) or 0) <= now else 0, key)))

    def _population(self, period):
        window = catalog_window(period, self.timezone_id, self.clock_ms())
        lifecycle = self.running_roots | self.recent_finishes.keys() | {key for key, proof in self.prompt_activity.items()
            if in_window(proof.finish_ms or proof.start_ms, window)}
        return window, candidate_population(self.roots, self.activity, self.activity_index,
            self.rows, self.changed_roots | self.active | lifecycle, window)

    def _finish_known(self, key):
        proof = self.prompt_activity.get(key)
        return (proof is not None and proof.finish_ms is not None
                and proof.revision == self.revisions.get(key))

    def _activity_current(self, key):
        return (key in self.rows and self.rows[key].activity_qualified
                and self.activity_valid.get(key, self.valid.get(key, (None,))[0]) == self.revisions.get(key))

    def _invalidate_navigation(self, keys=None):
        for lease in self.leases.values():
            navigation = lease.get('navigation')
            if navigation is not None and (keys is None or navigation.roots.keys() & set(keys)):
                navigation.invalid = True

    def _clear_epochs(self):
        for lease in self.leases.values():
            lease['epochs'].clear()

    def observe(self, observation, *, unavailable=False, source_interrupted=True, timezone_id=None):
        with self.lock:
            if timezone_id is not None:
                if timezone_id != self.timezone_id:
                    self._invalidate_navigation()
                    self._clear_epochs()
                    self.valid.clear()
                    self.orders.clear()
                    self.generation += 1
                self.timezone_id = timezone_id
            if unavailable or observation is None:
                self.active_snapshots.clear()
                if self.state != "source_unavailable" or source_interrupted and not self.interrupted:
                    self.wake_revision += 1
                if source_interrupted and not self.interrupted:
                    # Recovery must supply new prompt evidence, not replay a
                    # capture that predates the confirmed outage.
                    self.interrupted = True
                    self.lifecycle_cutoff_ms = self.clock_ms()
                    self.recent_finishes.clear()
                    self.live_arrivals.clear()
                self.state = "source_unavailable"
                return
            if observation is self.last_observation:
                return  # Publishing the same old catalog cannot renew source age.
            source_changed = bool(self.last_observation
                and self.last_observation.source_epoch != observation.source_epoch)
            if source_changed:
                self._invalidate_navigation()
                for name in ('rows', 'valid', 'activity_valid', 'attempted', 'failures', 'failure_counts',
                             'failure_reasons', 'prompt_activity', 'running_roots', 'recent_finishes',
                              'model_dependencies', 'orders',
                              'archive_rejections', 'active_snapshots'):
                    getattr(self, name).clear()
                self._clear_epochs()
                self.index_terminal = False
            self.last_observation = observation
            previous_roots = self.roots
            self.roots = OrderedDict((root.session_id, root) for root in observation.sessions
                                      if root.parent_session_id is None)
            now = self.clock()
            now_ms = self.clock_ms()
            self.recent_arrivals = {} if source_changed else {key: at for key, at in self.recent_arrivals.items()
                if key in self.roots and self.roots[key].provenance == previous_roots[key].provenance
                and now - at < ARRIVAL_SECONDS}
            if self.observed is not None and not source_changed:
                added = self.roots.keys() - previous_roots.keys()
                self.recent_arrivals.update((key, now) for key in added)
                since_ms = None if self.interrupted or self.archive is None else self.observed_ms
                self.live_arrivals = retain_live_arrivals(
                    self.live_arrivals, self.roots, previous_roots, added, since_ms, now_ms)
                if added:
                    self.background_due = min(self.background_due, now + 15)
            elif source_changed:
                self.background_due = now
                self.live_arrivals.clear()
            self.discovery = {key: age for key, age in self.discovery.items() if key in self.roots}
            for key in self.roots:
                if key not in self.discovery:
                    self.discovery_sequence += 1
                    self.discovery[key] = self.discovery_sequence
            if any(previous_roots[key].provenance != root.provenance
                   for key, root in self.roots.items() if key in previous_roots):
                self._invalidate_navigation()
                self._clear_epochs()
                self.last_page = ()
            removed = previous_roots.keys() - self.roots.keys()
            if removed:
                for lease in self.leases.values():
                    epochs = lease['epochs']
                    for epoch, snapshot in tuple(epochs.items()):
                        if any(row.session_id in removed for row in snapshot.rows):
                            del epochs[epoch]
            self.activity = {key: at for key, at in root_activity(observation.sessions).items() if at > 0}
            self.activity_index = tuple(sorted((at, key) for key, at in self.activity.items()
                if key in self.roots and type(at) is int and at > 0))
            previous_active, self.active = self.active, observation.live_candidates
            previous_revisions = self.revisions
            self.revisions = dict(observation.revisions)
            self.archive_rejections = {key: proof for key, proof in self.archive_rejections.items()
                                       if key in self.roots and self._archive_signature(key) == proof[0]}
            if source_changed:
                self.changed_roots.clear()
            else:
                self.changed_roots.intersection_update(self.roots)
                self.changed_roots.update(key for key in self.roots
                    if key in previous_revisions and previous_revisions[key] != self.revisions.get(key))
                if self.observed is not None:
                    self.changed_roots.update(self.roots.keys() - previous_roots.keys())
            if (source_changed or self.state != "observed" or previous_active != self.active
                    or tuple(previous_roots) != tuple(self.roots) or any(
                    key not in previous_roots or previous_roots[key] != root
                    for key, root in self.roots.items()) or previous_revisions != self.revisions):
                self.generation += 1
                self.wake_revision += 1
            self.rows = {key: row for key, row in self.rows.items() if key in self.roots}
            self.valid = {key: value for key, value in self.valid.items()
                           if key in self.roots and value[0] == self.revisions.get(key)
                             and previous_roots[key].provenance == self.roots[key].provenance}
            # An authoritative unchanged revision validates stable scalar facts;
            # navigation and failed observations never renew this proof.
            self.valid = {key: (value[0], self.clock()) if key not in self.active and key not in self.running_roots
                          else value for key, value in self.valid.items()}
            self.rows = {key: row for key, row in self.rows.items()
                           if previous_roots[key].provenance == self.roots[key].provenance}
            self.activity_valid = {key: value for key, value in self.activity_valid.items()
                if key in self.rows and value == self.revisions.get(key)}
            self.model_dependencies = {key: value for key, value in self.model_dependencies.items()
                                       if key in self.rows}
            self.prompt_activity = {key: value for key, value in self.prompt_activity.items()
                if key in self.roots and self.roots[key].archived_at_ms is None
                and previous_roots[key].provenance == self.roots[key].provenance}
            self.running_roots.intersection_update(self.prompt_activity)
            self.recent_finishes = {key: at for key, at in self.recent_finishes.items()
                                    if key in self.prompt_activity}
            self.failures = {key: failure for key, failure in self.failures.items()
                             if key in self.roots and previous_roots[key].provenance == self.roots[key].provenance
                              and failure[0] == self.revisions.get(key)}
            self.failure_counts = {key: value for key, value in self.failure_counts.items() if key in self.failures}
            self.failure_reasons = {key: value for key, value in self.failure_reasons.items() if key in self.failures}
            if self.state == 'source_unavailable':
                self.index_terminal = False
            self.state = "observed"
            self.interrupted = False
            self.observed = self.clock()
            self.observed_ms = now_ms
            if self.archive is not None:
                self._restore_archived_rows()
                self._record_history_pending()

    def _record_history_pending(self):
        self.history_pending = {key: self.activity.get(key) for key in self.roots
            if self._archive_needs_capture(key) and not self._archive_unavailable(key)}

    def _archive_needs_capture(self, key):
        return self.archive.needs_capture(key, self.revisions.get(key), self.archive_target,
                                          self.activity.get(key) or 0, key in self.changed_roots)

    def history_live_roots(self):
        return self.active | self.running_roots | self._new_live_roots()

    def history_progress_live_roots(self):
        """Live additions do not reopen historical acquisition when their UI grace expires."""
        return self._archive_urgent() | self.live_arrivals | {
            key for key in self.prompt_activity if self._finish_known(key)}

    def history_refresh_roots(self):
        return self.archive.refresh_roots(self.history_pending, self.archive_target)

    def _new_live_roots(self):
        latest = self.clock_ms()
        return recent_live_roots(self.recent_arrivals, self.activity, self.clock(), latest)

    def _archive_signature(self, key):
        return self.archive_target, self.revisions.get(key), self.dependencies

    def _archive_unavailable(self, key):
        saved = self.archive_rejections.get(key)
        terminal = self.failures.get(key)
        return (bool(terminal and terminal == (self.revisions.get(key), True))
                or bool(saved and saved[0] == self._archive_signature(key) and
                        saved[1] >= ARCHIVE_QUALIFICATION_ATTEMPTS))

    def unavailable_history(self):
        return frozenset(key for key in self.archive_rejections.keys() | self.failures.keys()
                         if self._archive_unavailable(key))

    def _record_archive_rejection(self, key):
        signature = self._archive_signature(key)
        former = self.archive_rejections.get(key)
        tries = (former[1] if former and former[0] == signature else 0) + 1
        self.archive_rejections[key] = signature, tries
        if tries == ARCHIVE_QUALIFICATION_ATTEMPTS:
            self.history_pending.pop(key, None)
            self.generation += 1
            self.wake_revision += 1

    def observe_prompts(self, evidence):
        """Canonical Watch captures only: root identity, revision and original time.

        An omitted prompt is not a lifecycle event. Resolve each supplied fact
        against the same per-root evidence used by the scalar lane and page order.
        """
        with self.lock:
            self._expire_recent_finishes()
            if self.state != "observed":
                return
            now = self.clock_ms()
            for root, revision, captured_at, prompt_id, start, running, finish, ended in evidence:
                key = root.session_id
                if (key not in self.roots or root.provenance != self.roots[key].provenance
                        or not 0 <= now - captured_at <= PROMPT_FRESHNESS_MS
                        or revision != self.revisions.get(key) and not running):
                    continue
                self._record_prompt(key, PromptEvidence(captured_at, prompt_id, start, running, finish, ended, revision),
                                    wake=True)

    def observe_prompt_ends(self, observations):
        """A current Watch capture can stop the accepted prompt, not pick its finish clock."""
        with self.lock:
            if self.state != "observed":
                return
            now = self.clock_ms()
            for root, revision, at, ended in observations:
                key = root.session_id
                if (key in self.running_roots and root.provenance == self.roots[key].provenance
                        and revision == self.revisions.get(key) and 0 <= now - at <= PROMPT_FRESHNESS_MS):
                    previous = self.prompt_activity[key]
                    if previous.identity in ended:
                        self._record_prompt(key, PromptEvidence(at, previous.prompt_id, previous.start_ms,
                            False, None, ended=True, revision=revision), wake=True)

    def offer_active_snapshots(self, epoch, snapshots):
        """Replace Watch's offers; a missing, failed, or changed capture cannot be replayed."""
        with self.lock:
            if self.state != 'observed' or epoch is None or epoch != self.last_observation.source_epoch:
                return
            self.active_snapshots.replace(snapshots, self.lifecycle_cutoff_ms)

    def withdraw_prompts(self, failures):
        """Terminal Watch read failures invalidate execution, not prove a finish."""
        with self.lock:
            removed = False
            for root, attempted_at in failures:
                key = root.session_id
                if (key in self.running_roots and root.provenance == self.roots[key].provenance
                        and attempted_at >= self.prompt_activity[key].observed_ms):
                    self.running_roots.remove(key)
                    self.prompt_activity[key] = replace(self.prompt_activity[key], observed_ms=attempted_at)
                    removed = True
            if removed:
                self.generation += 1
                self.wake_revision += 1

    def _expire_recent_finishes(self):
        now = self.clock_ms()
        finished = {key for key, at in self.recent_finishes.items() if now - at >= FINISH_PLACEMENT_MS}
        if finished:
            for key in finished:
                del self.recent_finishes[key]
            self.generation += 1
            self.wake_revision += 1

    def _record_prompt(self, key, evidence, *, wake=False):
        now = self.clock_ms()
        if (self.roots[key].archived_at_ms is not None or not isinstance(evidence.prompt_id, str)
                or not self.lifecycle_cutoff_ms < evidence.observed_ms <= now
                or not evidence.prompt_id or type(evidence.start_ms) is not int
                or not 0 < evidence.start_ms <= now
                or evidence.finish_ms is not None and not evidence.start_ms <= evidence.finish_ms <= now):
            return
        previous = self.prompt_activity.get(key)
        was_running = self._running(key)
        if evidence.finish_ms is not None:
            evidence = replace(evidence, ended=True)
        if not evidence.running and not evidence.ended:
            return
        if previous is None:
            if not evidence.running:
                return  # Ordinary history belongs to the scalar index.
        else:
            # An older prompt can still own active background work. Only a
            # newer qualified positive can move the focal identity backward.
            if (evidence.observed_ms < previous.observed_ms
                    or evidence.identity < previous.identity
                    and (not evidence.running or evidence.observed_ms == previous.observed_ms)):
                return
            if evidence.prompt_id == previous.prompt_id:
                if (evidence.start_ms != previous.start_ms or (evidence.running and previous.finish_ms is not None
                        and (evidence.revision == previous.revision or not wake))
                        or evidence.observed_ms == previous.observed_ms and evidence.running):
                    return
                if evidence.ended and evidence.finish_ms is None and previous.finish_ms is not None:
                    evidence = replace(evidence, finish_ms=previous.finish_ms, revision=previous.revision)
        previous_finish = self.recent_finishes.get(key)
        if evidence.running or evidence.finish_ms is not None:
            self.recent_finishes.pop(key, None)
        elif was_running:
            # Sort/membership hint only, never a displayed or durable finish.
            self.recent_finishes[key] = evidence.observed_ms
        elif previous is not None and previous.identity != evidence.identity:
            self.recent_finishes.pop(key, None)
        self.prompt_activity[key] = evidence
        if evidence.running:
            self.running_roots.add(key)
        else:
            self.running_roots.discard(key)
        if self.archive is not None and (was_running != evidence.running
                or previous_finish != self.recent_finishes.get(key)):
            self.generation += 1
        if wake and (previous is None or was_running != evidence.running or previous.identity != evidence.identity
                     or previous.finish_ms != evidence.finish_ms):
            self.wake_revision += 1

    def _running(self, key):
        # A quiet but qualified Live card may not change for minutes. Clock
        # age limits admission of new Watch facts, not existing execution.
        return (not self.interrupted and key in self.running_roots
                and self.prompt_activity[key].observed_ms > self.lifecycle_cutoff_ms)

    def _current(self, key):
        value = self.valid.get(key)
        return (not self.index_unavailable and value is not None and value[0] == self.revisions.get(key)
                and key in self.rows and not self.failures.get(key, (None, False))[1])

    def needed(self):
        with self.lock:
            targets = self._targets()
            if self.index_unavailable:
                return (not self.index_terminal and self.state == "observed" and bool(targets)
                    and self.clock() - self.checked_at >= 30)
            work = any(self._eligible(key) for key in targets)
            return self.state == "observed" and bool(targets) and (work or self.clock() - self.checked_at >= 60)

    def history_ready(self):
        """Only eligible historical roots can advance the scalar lane between Live ticks."""
        with self.lock:
            if self.archive is None or self.state != 'observed' or self.index_unavailable:
                return False
            urgent = self._archive_urgent()
            return any(key not in urgent and self._eligible(key) for key in self.history_pending)

    def index_failed(self, reason='index_unavailable', *, terminal=False):
        with self.lock:
            if not self.index_unavailable or self.index_failure != reason:
                self.wake_revision += 1
            self.index_unavailable = True
            self.index_failure = reason
            self.index_terminal = terminal
            self.checked_at = self.clock()

    def _eligible(self, key):
        failure = self.failures.get(key)
        if failure and failure[1]:
            return False  # Unsupported/auth failures require changed source evidence.
        delay = min(120, 30 * 2 ** min(2, self.failure_counts.get(key, 1) - 1)) if failure else 5
        if self.archive is not None and not failure and self._unchanged_watch_scalar(key):
            # The qualified Watch lane is still updating. Give history the
            # transport slot only when rereading the same active scalar would
            # be redundant; changed revisions/prompts and fresh offers stay due.
            if any(other not in self.active and other not in self.running_roots
                   for other in self.history_pending):
                delay = UNCHANGED_ACTIVE_READ_SECONDS
        if self.clock() - self.attempted.get(key, -100) < delay:
            return False
        if self.archive is not None:
            if not self.archive.loaded or not self.archive.partition:
                return False
            return (key in self.active or key in self.running_roots or not self._archive_unavailable(key) and (
                key in self.recent_finishes or self._archive_needs_capture(key)))
        navigation_pending = any(self._browsing(lease) and lease.get('navigation') is not None
            and not lease['navigation'].invalid
            and key in lease['navigation'].roots and key not in lease['navigation'].facts
            for lease in self.leases.values())
        return (navigation_pending or not self._current(key) or (key in self.active or key in self.running_roots)
                      or not self.rows[key].context_qualified and self._requested(key, 'ctx')
                      or not self.rows[key].effort_qualified and self._requested(key, 'effort')
                      or not self._activity_current(key) and any(self._browsing(lease)
                          and key in lease.get('candidates', ()) and (
                              lease.get('sort') == 'activity' or lease.get('period') != 'all')
                           for lease in self.leases.values()))

    def _unchanged_watch_scalar(self, key):
        if not self._running(key) or not self._current(key):
            return False
        return self.active_snapshots.has_unchanged_scalar(
            self.rows[key], self.prompt_activity[key], self.revisions.get(key), self.clock_ms())

    def _requested(self, key, sort):
        return any(lease.get('sort') == sort and self._browsing(lease)
                   and key in lease.get('candidates', ()) for lease in self.leases.values())

    def _archive_urgent(self):
        return self.history_live_roots() | self.recent_finishes.keys()

    def _candidate(self, *, extension=False, history_turn=False):
        # Only requested rows, or scoped scalar keys required by a requested
        # metric/activity sort or final period membership. Pinned navigation
        # acquires only visible rows; HTTP reads never acquire history.
        candidates = [key for key in self._targets() if self._eligible(key)]
        if not candidates:
            return None
        if self.archive is not None:
            if extension:
                return None
            visible = {key for lease in self.leases.values() if self._browsing(lease)
                       for key in lease.get('visible', ())}
            urgent = self._archive_urgent()
            now = self.clock_ms()
            today = catalog_window('today', self.timezone_id, now).start_ms

            def priority(key):
                observed = self.activity.get(key, 0)
                if not 0 < observed <= now:
                    created = self.roots[key].created_at_ms
                    observed = created if 0 < created <= now else 0
                # Do not let a visible older page cross the Today boundary
                # even when the day starts inside a recency bucket.
                return ((key in urgent) == history_turn, observed < today,
                         key in self.failures or key in self.archive_rejections, -(observed // 900_000),
                         key not in visible, -observed, -self.discovery[key], key)

            return min(candidates, key=priority)
        navigations = [lease['navigation'] for lease in self.leases.values() if self._browsing(lease)
            and lease.get('navigation') is not None and not lease['navigation'].invalid]
        if extension and not any(nav.expanded_period and any(
                key in nav.roots and key not in nav.facts for key in candidates) for nav in navigations):
            return None
        self.turn += 1
        pending = {key for nav in navigations for key in nav.pending}
        priority = pending.intersection(candidates)
        if self.turn % 8 and priority:
            return min(priority,
                       key=lambda key: (self.attempted.get(key, -100), self.discovery[key]))
        visible = dict.fromkeys(key for lease in sorted(self.leases.values(), key=lambda item: -item["touched"])
                                if self._browsing(lease) for key in lease.get("visible", ()))
        priority = [key for key in visible if key in candidates]
        if self.turn % 8 and priority:
            return min(priority, key=lambda key: (self._current(key), self.attempted.get(key, -100)))
        if self.turn % 4:
            nearby = dict.fromkeys(key for lease in self.leases.values() if self._browsing(lease)
                                   for key in lease.get("nearby", ()))
            priority = [key for key in nearby if key in candidates]
            if priority:
                return min(priority, key=lambda key: self.attempted.get(key, -100))
        return min(candidates, key=lambda key: (self.attempted.get(key, -100), self.discovery[key]))

    def tick(self, service, *, fresh_snapshots=False):
        scope = source_scope(service.source) if self.archive is not None else None
        dependencies = dependency_signature((service._dependencies(service._load_catalog()),
                                              service._load_comparison_catalog().diagnostic_signature))
        with self.lock:
            self.checked_at = self.clock()
            if self.index_unavailable:
                self.wake_revision += 1
            self.index_unavailable = False
            self.index_failure = None
            self.index_terminal = False
            if dependencies != self.dependencies:
                if self.dependencies is not None:
                    self._invalidate_navigation()
                    self._clear_epochs()
                    self.orders.clear()
                self.valid.clear()
                self.failures.clear()
                self.failure_counts.clear()
                self.failure_reasons.clear()
                self.generation += 1
                self.dependencies = dependencies
                self.archive_rejections.clear()
                self._restore_archived_rows()
                if self.archive is not None:
                    self._record_history_pending()
            self.timezone_id = service.timezone_id
            self.unit = service.config.get("ccostDisplayUnit", "credits")
        start = self.clock()
        with self.lock:
            targets = self._targets()
            identities = {key: self.model_dependencies[key] for key in targets
                          if key in self.valid and key in self.model_dependencies}
            if self.archive is not None:
                identities = {key: values for key, values in identities.items()
                              if key in self.active or key in self.changed_roots}
        # Native model/default observations can change without a history revision.
        # Validate only this lane's eligible roots, using the source's bounded catalog.
        changed = [key for key, values in identities.items() if not payload_current(service.source, values)]
        with self.lock:
            for key in changed:
                self.valid.pop(key, None)
                self.failures.pop(key, None)
                self.failure_counts.pop(key, None)
                self.failure_reasons.pop(key, None)
                self.attempted.pop(key, None)
            if changed:
                self._invalidate_navigation(changed)
                self._clear_epochs()
                self.generation += 1
        for number in range(INTERACTIVE_ATTEMPTS):
            extension = number >= PASSIVE_ATTEMPTS
            # Spend the extra budget only while there is eligible expanded
            # navigation demand. The next root rechecks interest/cancellation;
            # slow transport and passive work keep their original admission cap.
            if extension and self.clock() - start >= INTERACTIVE_ADMISSION_SECONDS:
                break
            with self.lock:
                if self.state != "observed":
                    return
                key = self._candidate(extension=extension, history_turn=self.history_turn)
                if key is None:
                    break
                root, revision = self.roots[key], self.revisions.get(key)
                epoch = self.last_observation.source_epoch
                if scope is not None and scope[2] != epoch:
                    return
                partition = self.archive.partition if self.archive is not None else None
                if partition is not None and scope_partition(scope) != partition:
                    return
                active = key in self.active or key in self.running_roots
                if self.archive is not None:
                    # An urgent read can use the entire slice. Keep the next
                    # turn across slices rather than starving cold history.
                    self.history_turn = key in self._archive_urgent()
                captured_at = self.clock_ms()
                prompt_observed_at, active_snapshot = (self.active_snapshots.take(root, revision, captured_at)
                    if fresh_snapshots and active else (captured_at, None))
                self.attempted[key] = self.clock()
                self.metrics['attempts'] += 1
                self.metrics['retries'] += int(key in self.failures)
                retrying = key in self.failures
                navigations = [lease['navigation'] for lease in self.leases.values()
                    if self._browsing(lease) and lease.get('navigation') is not None
                    and not lease['navigation'].invalid
                    and key in lease['navigation'].roots and key not in lease['navigation'].facts]
                memberships = {}
                windows = {nav.window for nav in navigations if nav.window.period != 'all'}
            try:
                identity_values = []
                evidence = []
                ended_prompts = set()
                row, actual = session_summary(service, root, revision, active=active, metrics=self.metrics,
                     fresh_snapshot=fresh_snapshots, active_snapshot=active_snapshot,
                    on_stage=lambda stage: self._stage(stage, retrying),
                    on_dependencies=identity_values.extend,
                    on_prompt_ends=ended_prompts.update if active else None,
                    on_evidence=(lambda item: evidence.append(item)) if partition and not active else None,
                    activity_end_ms=min((window.end_ms for window in windows), default=None),
                    on_activity=lambda values, complete: memberships.update(
                        (window, any(in_window(at, window) for at in values)) for window in windows if complete))
                if scope is not None and source_scope(service.source) != scope:
                    continue
                saved = False
                unqualified = bool(partition and not active and not row.running and actual == revision)
                if (unqualified and evidence and isinstance(actual, str) and row.activity_qualified
                        and row.context_qualified and row.effort_qualified and not row.effort_pending
                        and not row.model_pending):
                    item, = evidence
                    usage = web_history_evidence.acquired_usage(service, item)
                    detail = acquired_detail(service, item) if usage is not None else None
                    if detail is not None:
                        unqualified = False
                    if detail is not None and fresh_snapshots:
                        # The isolated V2 reader already checked the tree
                        # after messages. Refresh service identity without
                        # repeating global discovery for this one root.
                        service.source.refresh_observation_epoch()
                    if (detail is not None and (fresh_snapshots or service.source.get_session_tree_revision(key) == actual)
                            and source_scope(service.source) == scope):
                        with self.lock:
                            current = (key in self.roots and self.archive.partition == partition
                                       and self.revisions.get(key) == actual
                                       and self.last_observation.source_epoch == epoch
                                       and self.roots[key].provenance == root.provenance
                                       and key not in self.active and key not in self.running_roots)
                        if current:
                            saved = self.archive.save(partition, key, actual, row, captured_at,
                                                      dependencies, identity_values, usage, detail)
            except Exception as error:
                with self.lock:
                    if (key in self.roots and root.provenance == self.roots[key].provenance
                            and revision == self.revisions.get(key)
                            and epoch == self.last_observation.source_epoch):
                        terminal = isinstance(error, SourceError) and error.terminal
                        newly_terminal = terminal and self.failures.get(key) != (revision, True)
                        self.failures[key] = revision, terminal
                        if self.archive is not None and newly_terminal:
                            self.history_pending.pop(key, None)
                            self.generation += 1
                            self.wake_revision += 1
                        self.failure_counts[key] = self.failure_counts.get(key, 0) + 1
                        self.failure_reasons[key] = (str(error.code) if isinstance(error, SourceError) else
                            'pricing_unavailable' if isinstance(error, PricingUnavailableError) else 'scalar_worker_failed')
            else:
                with self.lock:
                    if (key in self.roots and root.provenance == self.roots[key].provenance
                            and epoch == self.last_observation.source_epoch
                            and (self.archive is None or self.archive.partition == partition)
                            and revision == self.revisions.get(key)):
                        if actual == revision:
                            previous_row = self.rows.get(key)
                            previous_display = previous_row
                            if previous_display is None and self.archive is not None:
                                previous_display = self.archive.rows.get(key)
                            self.rows[key] = retain_pending_metrics(row, previous_display)
                            if self.archive is not None:
                                self.rows[key] = retain_readable_fields(self.rows[key], previous_display)
                            self.model_dependencies[key] = identity_values
                            self.valid[key] = actual, self.clock()
                            if row.activity_qualified:
                                self.activity_valid[key] = actual
                            else:
                                self.activity_valid.pop(key, None)
                            self._record_summary_prompt(key, row, prompt_observed_at, historical=not active,
                                                        ended_prompts=ended_prompts)
                            partial = None if row.running else (
                                'context' if not row.context_qualified and self._requested(key, 'ctx') else
                                'effort' if not row.effort_qualified and self._requested(key, 'effort') else None)
                            if partial:
                                self.failures[key] = revision, False
                                self.failure_counts[key] = self.failure_counts.get(key, 0) + 1
                                self.failure_reasons[key] = 'partial_source_' + partial
                            else:
                                self.failures.pop(key, None)
                                self.failure_counts.pop(key, None)
                                self.failure_reasons.pop(key, None)
                            if self.archive is not None:
                                if self.rows[key] != previous_row:
                                    self.wake_revision += 1
                                if saved:
                                    self.archive.rows[key] = retain_readable_fields(row, self.archive.rows.get(key))
                                    self.archive.authorities[key] = actual, dependencies, identity_values, partition, captured_at
                                    self.archive_rejections.pop(key, None)
                                elif unqualified:
                                    self._record_archive_rejection(key)
                                if not self._archive_needs_capture(key):
                                    self.history_pending.pop(key, None)
                            for nav in navigations:
                                nav.capture(self, {key: memberships[nav.window]} if nav.window in memberships else None,
                                            keys=(key,))
                        else:
                            self.failures[key] = revision, False
                            self.failure_counts[key] = self.failure_counts.get(key, 0) + 1
                            self.failure_reasons[key] = ('snapshot_revision_mismatch' if fresh_snapshots else
                                                         'concurrent_source_change')
            finally:
                with self.lock:
                    self.work = None
                    self.metrics['settled'] += 1
            # One slow root is bounded by the source transport; no additional
            # work is admitted after the slice budget. Details have their own lane.
            if self.clock() - start >= 2:
                break
        with self.lock:
            finalizing = [lease['navigation'] for lease in self.leases.values()
                if lease.get('navigation') is not None and not lease['navigation'].pending
                and not lease['navigation'].invalid]
        # No extra history pass. Recheck dependency authority of the accepted
        # facts at the publication boundary, not only the remaining live targets.
        for nav in finalizing:
            if any(not payload_current(service.source, values) for values in nav.authorities.values()):
                with self.lock:
                    nav.invalid = True
        with self.lock:
            if not any(self._browsing(lease) for lease in self.leases.values()):
                self.background_due = self.clock() + (15 if any(
                    not self._current(key) for key in targets if key in self.roots) else 900)

    def _stage(self, stage, retrying):
        # One scalar lane owns these actual call boundaries, never a browser clock.
        with self.lock:
            self.work_sequence += 1
            self.work = dict(stage=stage, retrying=retrying, active=True, sequence=self.work_sequence)

    def _record_summary_prompt(self, key, row, captured_at, *, historical=False, ended_prompts=()):
        # A history job started without live context cannot overrule the
        # independent Watch lane. The latter can publish before this job ends.
        revision = self.revisions.get(key)
        prompt = row.prompt_started_ms, row.activity_prompt_id
        if row.running:
            self._record_prompt(key, PromptEvidence(captured_at, prompt[1], prompt[0], True, None, revision=revision))
        elif row.activity_qualified and (not historical or not self._running(key)):
            previous = self.prompt_activity.get(key)
            if self._running(key) and previous.identity != prompt:
                if previous.identity not in ended_prompts:
                    return
                self._record_prompt(key, PromptEvidence(captured_at, previous.prompt_id, previous.start_ms,
                    False, None, ended=True, revision=revision))
            self._record_prompt(key, PromptEvidence(captured_at, prompt[1], prompt[0], False, row.last_activity_ms,
                ended=prompt in ended_prompts, revision=revision))

    def _with_lifecycle(self, rows, lifecycle=None):
        if lifecycle is None:
            lifecycle = {row.session_id: row for row in self._rows(row.session_id for row in rows)}
        return tuple(replace(row, **{name: getattr(lifecycle[row.session_id], name)
            for name in ('running', 'last_activity_ms', 'prompt_started_ms', 'activity_prompt_id')})
            if row.running or row.session_id in self.prompt_activity else row for row in rows)

    def _rows(self, keys):
        rows = []
        now = self.clock_ms()
        for key in keys:
            root = self.roots[key]
            retained = self.archive.rows.get(key) if self.archive is not None else None
            value = self.rows.get(key) or retained or SessionUsageRow(key, root.title or "Untitled session", "N/A", False,
                                                        None, None, complete=False, activity_qualified=False)
            activity = value.last_activity_ms
            prompt = self.prompt_activity.get(key)
            running = self._running(key)
            started, prompt_id = value.prompt_started_ms, value.activity_prompt_id
            if prompt is not None and (prompt.running or value.activity_prompt_id == prompt.prompt_id
                    or key in self.recent_finishes or not self._activity_current(key) or value.running):
                started, prompt_id = prompt.identity
                # Preserve the scalar lane's causal finish (including linked
                # work), never the timestamp of a different prompt.
                activity = started if running else prompt.finish_ms if self._finish_known(key) else None
            elif value.running:
                activity = started = None
                prompt_id = ""
            title = root.title or "Untitled session"
            activity = activity if type(activity) is int and 0 < activity <= now else None
            started = started if type(started) is int and 0 < started <= now else None
            archived = root.archived_at_ms is not None
            # Bounded epochs share unchanged immutable facts instead of copying
            # every qualified row again for each burst's new ordering.
            if (title != value.title or activity != value.last_activity_ms or started != value.prompt_started_ms
                    or running != value.running or archived != value.archived or prompt_id != value.activity_prompt_id):
                value = replace(value, title=title, last_activity_ms=activity, prompt_started_ms=started,
                                activity_prompt_id=prompt_id, running=running, archived=archived)
            rows.append(value)
        return rows

    def _key_current(self, key, sort):
        if sort == 'activity':
            return self._activity_current(key)
        return (self._current(key) and not (sort == 'model' and self.rows[key].model_pending)
                and not (sort == 'effort' and (self.rows[key].effort_pending or not self.rows[key].effort_qualified))
                and not (sort == 'ctx' and not self.rows[key].context_qualified))

    def _progress(self, sort, pending, selected, indexed, pinned, candidates, scope=False):
        keys = candidates if pending or scope else tuple(row.session_id for row in selected)
        completed = indexed if pending or scope else sum(self._current(key) for key in keys)
        failed = [key for key in keys if key in self.failures and self.failures[key][1]]
        waiting = [key for key in keys if key in self.failures]
        reason = ('source_unavailable' if self.state == 'source_unavailable' else
                   self.index_failure if self.index_unavailable else
                  self.failure_reasons.get((failed or waiting)[0], 'source_key_unavailable') if waiting else None)
        return dict(generation=self.generation, phase='index' if pending else 'page',
             status='failed' if failed or self.index_terminal else 'pending' if reason or pending or completed < len(keys) else 'ready',
             retryable=not (failed or self.index_terminal),
            completed=completed, total=len(keys), reason=reason,
            failed=len(failed), waiting=sum(key in self.failures for key in keys),
            pinned=pinned, metrics=dict(self.metrics),
            revalidating=sum(key in self.rows and not self._key_current(key, sort) for key in keys),
            work=dict(self.work) if self.work else dict(active=False, sequence=self.work_sequence,
                stage='waiting_retry' if any(key in self.failures for key in keys) else
                      'queued' if pending or completed < len(keys) else 'ready'))

    def page(self, *, token=None, offset=0, sort="activity", direction=-1, epoch=None, period="today",
             navigation=None, applied=None, cancelled=None, passive=False):
        with self.lock:
            if period not in PERIODS:
                raise ValueError("invalid_request")
            self._expire_recent_finishes()
            if self.archive is not None:
                return cached_page(self, ordered, token=token, offset=offset, sort=sort, direction=direction,
                                   period=period, navigation=navigation)
            return epoch_page(self, token=token, offset=offset, sort=sort, direction=direction,
                              epoch=epoch, period=period, navigation=navigation, applied=applied,
                              cancelled=cancelled, passive=passive)

    def _expire(self):
        for token, lease in tuple(self.leases.items()):
            if self.clock() - lease["touched"] > 300:
                del self.leases[token]

    def previews(self, excluded=(), *, limit=5):
        """Small all-time Live projection; no lease, IO, hydration or proof gate.

        Reuse current shared scalar facts, never a browser's pinned epoch. Metadata
        is an activity estimate, not prompt completion. Next-context has a separate
        owner and is deliberately absent from this DTO.
        """
        with self.lock:
            limit = max(0, min(MINI_PREVIEW_LIMIT, limit))
            if self.last_observation is None or not limit:
                return ()
            excluded = set(excluded) | self.active
            now = self.clock_ms()
            def total_scope(key):
                return (self.revisions.get(key), self.roots[key].provenance,
                    self.last_observation.source_epoch, self.dependencies, self.timezone_id)
            def candidate(key):
                row = self.rows.get(key)
                current = (key in self.valid and self.valid[key][0] == self.revisions.get(key)
                    and not self.failures.get(key, (None, False))[1])
                if key in excluded or self._running(key):
                    return None
                at = row.last_activity_ms if self._activity_current(key) else self.activity.get(key)
                at = at if type(at) is int and 0 < at <= now else None
                scope = total_scope(key)
                previous = None if self.failures.get(key, (None, False))[1] else self.preview_totals.get(key)
                total = (row.ccost if current and row is not None and row.complete else
                    previous[1] if previous is not None and previous[0] == scope else None)
                failure = self.failures.get(key)
                if total is not None:
                    total_state = ("retained" if self.state != 'observed' or self.index_unavailable or failure
                        or not current or not row.complete else "ready")
                elif self.index_terminal or failure and failure[1]:
                    total_state = "unavailable"
                elif failure or self.index_unavailable or self.state == 'source_unavailable':
                    total_state = "retrying"
                else:
                    total_state = "partial" if current else "pending"
                return SessionPreview(key, self.roots[key].title or "Untitled session", at,
                    "events" if self._activity_current(key) else "catalog",
                    total, total is not None, total_state=total_state)
            # Bounded top-K output/memory; no full-history sort or capture.
            selected = tuple(nsmallest(limit, (value for key in self.roots
                if (value := candidate(key)) is not None),
                key=lambda value: (-(value.activity_ms or 0), value.session_id)))
            self.preview_totals = {value.session_id: (total_scope(value.session_id), value.total_ccost)
                for value in selected if value.total_ccost is not None}
            return selected

    def archived_previews(self, *, limit=10):
        """The Watch history worker uses recorded ranks even without a live catalog."""
        if not self.archive:
            return ()
        with self.lock:
            candidates = tuple(self.archive.rows.values())
        selected = nsmallest(limit, candidates, key=lambda row: (
            -(row.activity_latest_ms or row.last_activity_ms or 0), row.session_id))
        return tuple(SessionPreview(row.session_id, row.title, row.last_activity_ms or row.activity_latest_ms,
                                    'events' if row.last_activity_ms else 'catalog', row.ccost, row.complete,
                                    hydration_state='retained', total_state='retained' if row.ccost is not None
                                    else 'unavailable', empty_history=row.empty_history) for row in selected)
