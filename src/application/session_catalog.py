"""Shared live catalog, bounded scalar indexing and stable server-side page epochs.

HTTP reads never acquire history. Metric ordering is admitted only with keys for
every period-eligible root; an unindexed root is not a canonically unknown metric.
"""
from collections import OrderedDict
from dataclasses import replace
from heapq import nsmallest
from threading import Lock
import time
from uuid import uuid4

from src.analysis.metric_evidence import EMPTY_HISTORY
from src.analysis.model_identity import payload_current
from src.cache.display_history import BATCH_LIMIT
from src.domain.session_tree import root_activity
from src.pricing.base import PricingUnavailableError
from src.reports.models import ReportKind, ReportProjection, SessionUsageRow
from src.reports.session_summary import session_summary
from src.sources.errors import SourceError
from src.watch.models import SessionPreview

from .projection import project
from .session_archive_sweep import checkpoint_dependency, scalar_dependency, verified_finish
from .session_catalog_lifecycle import PromptEvidence, is_running, observe_prompts, record_prompt, running_snapshot, terminal_prompt
from .session_navigation import Navigation
from .session_catalog_scope import (
    CatalogEpoch, PAGE_SIZE, PERIODS, activity_time, catalog_window, candidate_population,
    event_members, in_window, live_activity_order, provisional_order, retained_positions,
)

SORTS = ("activity", "name", "model", "ccost", "prompts", "duration", "ctx")

PASSIVE_ATTEMPTS = 4
INTERACTIVE_ATTEMPTS = 12
INTERACTIVE_ADMISSION_SECONDS = 0.35
ARRIVAL_SLOTS = 5
ARRIVAL_SECONDS = 120
# Maximum Mini viewport (10) plus a small scrollback window. The card
# scheduler still owns bounded source admission; this shortlist is in-memory.
MINI_PREVIEW_LIMIT = 15


def effort_sort(key):
    if key is None:
        return None
    levels = ("none", "minimal", "low", "medium", "high", "xhigh", "max", "default", "multiple")
    return (levels.index(key) if key in levels else len(levels), key)


def sort_value(row, key):
    return {"activity": activity_time(row),
        "name": row.title.casefold(),
        "model": (row.model if row.model != "N/A" else row.selected_display_model).casefold() or None,
        "effort": effort_sort(row.effort_key),
        "ccost": row.ccost if row.complete else None, "prompts": row.prompt_count,
        "duration": row.duration_ms, "ctx": row.context_tokens if row.context_qualified else None}[key]


def ordered(rows, key, direction):
    # Stable value sorting preserves ascending IDs for ties in either direction.
    # Extract each value once; unknown values stay last, including descending.
    running, known, unknown = [], [], []
    for row in sorted(rows, key=lambda row: row.session_id):
        if row.running and type(row.prompt_started_ms) is int and row.prompt_started_ms > 0:
            running.append(row)
            continue
        value = sort_value(row, key)
        if value is None:
            unknown.append(row)
        else:
            known.append((value, row))
    known.sort(key=lambda item: item[0], reverse=direction == -1)
    running.sort(key=lambda row: -row.prompt_started_ms)
    return tuple(running) + tuple(row for _, row in known) + tuple(unknown)


def retain_pending_metrics(row, previous):
    """Display-only last-good fields; pending qualification still blocks sorting."""
    if previous is None:
        return row
    fields = {}
    if not row.context_qualified and row.context_tokens is None:
        fields.update(context_tokens=previous.context_tokens,
            context_detail="Previous same-session Ctx; source acquisition pending.")
    if row.model_pending and row.model == "N/A":
        for name in ("model", "multiple_models", "contributor_models", "main_models", "subagent_models"):
            fields[name] = getattr(previous, name)
    if not row.contributor_models_complete and previous.has_model_details:
        fields["has_model_details"] = True
        if row.linked_agent_count < previous.linked_agent_count:
            fields["linked_agent_count"] = previous.linked_agent_count
            fields["subagent_models"] = previous.subagent_models
    if (row.effort_pending or not row.effort_qualified) and row.effort_key is None:
        for name in ("effort", "effort_key", "effort_contributors", "effort_details_complete"):
            fields[name] = getattr(previous, name)
    return replace(row, **fields)


class SessionCatalog:
    def __init__(self, *, clock=time.monotonic, clock_ms=lambda: int(time.time() * 1000), timezone_id="UTC",
                 display_archive=None):
        self.clock = clock
        self.clock_ms = clock_ms
        self.display_archive = display_archive
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
        self.membership_generation = 0
        self.metrics = dict(cache_hits=0, cache_misses=0, attempts=0, retries=0, settled=0)
        self.work = None
        self.work_sequence = 0
        self.activity = {}
        self.activity_index = ()
        self.activity_valid = {}
        self.changed_roots = set()
        self.archive_urgent = OrderedDict()
        self.archive_incarnation = 0
        self.observation_sequence = 0
        self.active = frozenset()
        self.prompt_activity = {}
        self.running_roots = set()
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
        self.last_observation = None
        self.orders = OrderedDict()
        self.discovery = {}
        self.recent_arrivals = {}
        self.discovery_sequence = 0
        self.preview_totals = {}
        self.wake_identity = uuid4().hex
        self.wake_revision = 0

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
        lifecycle = self.running_roots | {key for key, proof in self.prompt_activity.items()
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
                self.archive_urgent.clear()
                if self.state != "source_unavailable" or source_interrupted and not self.interrupted:
                    self.wake_revision += 1
                    self.archive_incarnation += 1
                if source_interrupted and not self.interrupted:
                    # Recovery must supply new prompt evidence, not replay a
                    # capture that predates the confirmed outage.
                    self.interrupted = True
                    self.lifecycle_cutoff_ms = self.clock_ms()
                self.state = "source_unavailable"
                return
            if observation is self.last_observation:
                return  # Publishing the same old catalog cannot renew source age.
            source_changed = bool(self.last_observation
                and self.last_observation.source_epoch != observation.source_epoch)
            if source_changed:
                self.archive_urgent.clear()
                self.archive_incarnation += 1
                self._invalidate_navigation()
                for name in ('rows', 'valid', 'activity_valid', 'attempted', 'failures', 'failure_counts',
                             'failure_reasons', 'prompt_activity', 'running_roots', 'model_dependencies', 'orders'):
                    getattr(self, name).clear()
                self._clear_epochs()
                self.index_terminal = False
            self.last_observation = observation
            previous_roots = self.roots
            self.roots = OrderedDict((root.session_id, root) for root in observation.sessions
                                      if root.parent_session_id is None)
            now = self.clock()
            self.recent_arrivals = {} if source_changed else {key: at for key, at in self.recent_arrivals.items()
                if key in self.roots and self.roots[key].provenance == previous_roots[key].provenance
                and now - at < ARRIVAL_SECONDS}
            if self.observed is not None and not source_changed:
                added = self.roots.keys() - previous_roots.keys()
                self.recent_arrivals.update((key, now) for key in added)
                if added:
                    self.background_due = min(self.background_due, now + 15)
            elif source_changed:
                self.background_due = now
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
            self.activity = root_activity(observation.sessions)
            self.activity_index = tuple(sorted((at, key) for key, at in self.activity.items()
                if key in self.roots and type(at) is int and at > 0))
            previous_active, self.active = self.active, observation.live_candidates
            previous_revisions = self.revisions
            self.revisions = dict(observation.revisions)
            if (source_changed or self.observed is None or self.roots.keys() != previous_roots.keys()
                    or self.revisions.keys() != previous_revisions.keys()):
                self.membership_generation += 1
            self.changed_roots.intersection_update(self.roots)
            revised = {key for key in self.roots if key in previous_roots
                       and (previous_revisions.get(key) != self.revisions.get(key)
                            or previous_roots[key].provenance != self.roots[key].provenance)}
            self.changed_roots.update(revised)
            if self.observed is not None:
                new = self.roots.keys() - previous_roots.keys()
                self.changed_roots.update(new)
                if self.display_archive is not None and not source_changed:
                    for key in tuple(self.archive_urgent):
                        if key not in self.roots or key in revised:
                            del self.archive_urgent[key]
                    newest = nsmallest(BATCH_LIMIT, (key for key in revised | new if self.revisions.get(key)),
                                       key=lambda key: (-self.activity.get(key, 0), key))
                    for key in newest:
                        self._archive_priority(key, now=now)
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
            self.observation_sequence += 1

    def observe_prompts(self, evidence):
        observe_prompts(self, evidence)

    def _archive_priority(self, key, *, now=None, delay=0, attempts=0):
        self.archive_urgent[key] = ((self.clock() if now is None else now) + delay, attempts)
        self.archive_urgent.move_to_end(key)
        if len(self.archive_urgent) > BATCH_LIMIT:
            self.archive_urgent.popitem(last=False)

    def archive_running(self, evidence):
        return running_snapshot(self, evidence)

    def _running(self, key):
        return is_running(self, key)

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
        if self.clock() - self.attempted.get(key, -100) < delay:
            return False
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

    def _requested(self, key, sort):
        return any(lease.get('sort') == sort and self._browsing(lease)
            and key in lease.get('candidates', ()) for lease in self.leases.values())

    def _candidate(self, *, extension=False):
        # Only requested rows, or scoped scalar keys required by a requested
        # metric/activity sort or final period membership. Pinned navigation
        # acquires only visible rows; HTTP reads never acquire history.
        candidates = [key for key in self._targets() if self._eligible(key)]
        if not candidates:
            return None
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

    def tick(self, service):
        archive = self.display_archive
        dependencies = scalar_dependency(service)
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
            self.timezone_id = service.timezone_id
            self.unit = service.config.get("ccostDisplayUnit", "credits")
        start = self.clock()
        with self.lock:
            targets = self._targets()
            identities = {key: self.model_dependencies[key] for key in targets
                          if key in self.valid and key in self.model_dependencies}
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
                key = self._candidate(extension=extension)
                if key is None:
                    break
                root, revision = self.roots[key], self.revisions.get(key)
                epoch = self.last_observation.source_epoch
                incarnation = self.archive_incarnation
                observation_sequence = self.observation_sequence
                active = key in self.active or self._running(key) or terminal_prompt(self, key) is not None
                captured_at = self.clock_ms()
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
            admission = (archive.admit_summary(service, key, revision, observation_sequence=observation_sequence)
                         if archive is not None else None)
            accepted = False
            try:
                identity_values = []
                row, actual = session_summary(service, root, revision, active=active, metrics=self.metrics,
                    on_stage=lambda stage: self._stage(stage, retrying),
                    on_dependencies=identity_values.extend,
                    activity_end_ms=min((window.end_ms for window in windows), default=None),
                    on_activity=lambda values, complete: memberships.update(
                        (window, any(in_window(at, window) for at in values)) for window in windows if complete))
            except Exception as error:
                with self.lock:
                    if (key in self.roots and root.provenance == self.roots[key].provenance
                            and revision == self.revisions.get(key)
                            and epoch == self.last_observation.source_epoch):
                        self.failures[key] = revision, isinstance(error, SourceError) and error.terminal
                        self.failure_counts[key] = self.failure_counts.get(key, 0) + 1
                        self.failure_reasons[key] = (str(error.code) if isinstance(error, SourceError) else
                            'pricing_unavailable' if isinstance(error, PricingUnavailableError) else 'scalar_worker_failed')
            else:
                with self.lock:
                    if (key in self.roots and root.provenance == self.roots[key].provenance
                            and epoch == self.last_observation.source_epoch
                            and revision == self.revisions.get(key)):
                        if actual == revision:
                            accepted = self.state == "observed"
                            self.rows[key] = retain_pending_metrics(row, self.rows.get(key))
                            self.model_dependencies[key] = identity_values
                            self.valid[key] = actual, self.clock()
                            if row.activity_qualified:
                                self.activity_valid[key] = actual
                            else:
                                self.activity_valid.pop(key, None)
                            self._record_summary_prompt(key, row, captured_at)
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
                            for nav in navigations:
                                nav.capture(self, {key: memberships[nav.window]} if nav.window in memberships else None,
                                            keys=(key,))
                        else:
                            self.failures[key] = revision, False
                            self.failure_counts[key] = self.failure_counts.get(key, 0) + 1
                            self.failure_reasons[key] = 'concurrent_source_change'
            finally:
                with self.lock:
                    self.work = None
                    self.metrics['settled'] += 1
            if accepted and admission is not None:
                # Native model identity can change without a root revision.
                # A checkpoint must name the exact observed identity authority;
                # callers cannot use it as a revision-only restart shortcut.
                with self.lock:
                    terminal = terminal_prompt(self, key)
                def eligible():
                    with self.lock:
                        return (self.state == "observed" and self.archive_incarnation == incarnation
                                and self.roots.get(key) == root and self.revisions.get(key) == actual
                                and not self._running(key) and terminal == terminal_prompt(self, key))

                if terminal is None or verified_finish(row, terminal):
                    archive.publish_summary(service, admission, row, actual,
                                             eligible=eligible,
                                             dependency=checkpoint_dependency(dependencies, identity_values, terminal))
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

    def _record_summary_prompt(self, key, row, captured_at):
        if row.running or row.activity_qualified:
            record_prompt(self, key, PromptEvidence(captured_at, row.activity_prompt_id, row.prompt_started_ms,
                row.running, None if row.running else row.last_activity_ms, revision=self.revisions.get(key)))

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
            value = self.rows.get(key) or SessionUsageRow(key, root.title or "Untitled session", "N/A", False,
                                                        None, None, complete=False, activity_qualified=False)
            activity = value.last_activity_ms
            prompt = self.prompt_activity.get(key)
            running = self._running(key)
            started, prompt_id = value.prompt_started_ms, value.activity_prompt_id
            if prompt is not None and (prompt.running or not self._activity_current(key) or value.running):
                started, prompt_id = prompt.identity
                # Preserve the scalar lane's causal finish (including linked
                # work), never the timestamp of a different prompt.
                activity = started if running else None if prompt.running else prompt.finish_ms
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
            # An epoch names an order independently of the slice, including
            # page one. Passive page-one reads use it only as a fallback.
            pinned = bool(offset or epoch and not passive)
            self._expire()
            if token is None:
                if pinned:
                    raise KeyError('catalog_expired')
                if len(self.leases) >= 32:
                    raise RuntimeError("catalog_busy")
                token = uuid4().hex
                self.leases[token] = dict(touched=self.clock(), epochs=OrderedDict())
            lease = self.leases.get(token)
            if lease is None:
                raise KeyError("catalog_expired")
            lease["touched"] = self.clock()
            if 'interest_until' in lease:
                lease['interest_until'] = self.clock() + 90
            nav = lease.get('navigation')
            if cancelled is not None:
                lease['navigation_sequence'] = max(cancelled, lease.get('navigation_sequence', 0))
            if nav is not None and cancelled == nav.sequence:
                lease.pop('navigation')
                nav = None
            if nav is not None and applied == nav.sequence and not nav.pending:
                lease.pop('navigation')
                lease['released'] = True
                nav = None
            issued = lease['epochs'].get(epoch)
            page_rows = issued.rows[offset:offset + PAGE_SIZE] if issued else ()
            compatible = (issued is not None and (issued.sort, issued.direction, issued.window.period,
                issued.window.timezone_id) == (sort, direction, period, self.timezone_id)
                and (offset == 0 or bool(page_rows))
                and all(row.session_id in self.roots for row in page_rows))
            current_window = (catalog_window(period, self.timezone_id, self.clock_ms()) if not offset else None)
            if not offset and compatible:
                compatible = issued.window.identity == current_window.identity
            if pinned and (not compatible or not offset and issued.provisional and not issued.browsable_candidates):
                raise KeyError('catalog_expired')
            usable = (self.state == 'observed' and not self.index_unavailable
                and not any(self.failures.get(row.session_id, (None, False))[1] for row in page_rows))
            # Older historical windows may still be displayed, but are not a
            # current-calendar warm hit. A continued action keeps its own facts.
            reuse = bool(pinned and compatible and usable and not issued.provisional and offset in issued.served
                and issued.window.identity == (current_window or catalog_window(
                    period, self.timezone_id, self.clock_ms())).identity
                and (navigation is None or nav is None or nav.sequence != navigation))
            # A live candidate epoch already owns the order of these slices.
            # Scalar qualification can improve cells without blocking navigation.
            reuse = reuse or bool(pinned and compatible and issued.browsable_candidates
                 and (nav is None or nav.sequence != navigation))
            retained_page = bool(compatible and navigation is None and nav is None
                and self.state == 'source_unavailable')
            reuse = reuse or retained_page
            if not pinned:
                window, candidates = self._population(period)
            if navigation is not None:
                intent = sort, direction, period, offset, epoch if pinned else None
                if nav is None or nav.sequence != navigation:
                    if navigation <= lease.get('navigation_sequence', 0):
                        raise ValueError('invalid_request')
                    lease['navigation_sequence'] = navigation
                    if reuse:
                        lease.pop('navigation', None)
                        lease['released'] = True
                        nav = None
                    else:
                        nav_window = issued.window if pinned else window
                        keys = (tuple(row.session_id for row in page_rows) if pinned else candidates)
                        previous_period = lease.get('period')
                        previous_start = (catalog_window(previous_period, self.timezone_id, window.end_ms - 1).start_ms
                            if previous_period is not None and previous_period != period and not pinned else None)
                        nav = Navigation(navigation, intent, nav_window,
                            {key: self.roots[key] for key in keys}, self.last_observation.source_epoch
                            if self.last_observation else None,
                            expanded_period=previous_start is not None and (
                                nav_window.start_ms is None or nav_window.start_ms < previous_start))
                        if pinned and issued.facts:
                            nav.facts.update((key, fact) for key, fact in issued.facts if key in nav.roots)
                        lease['navigation'] = nav
                elif nav.intent != intent:
                    raise ValueError('invalid_request')
                if nav is not None:
                    nav.check(self, issued.window if pinned else window)
                    nav.capture(self)
                    if not pinned:
                        window, candidates = nav.window, tuple(nav.roots)
            display_rows = {row.session_id: row for row in self._rows(candidates)} if not pinned else {}
            event_current = lambda key: self._activity_current(key) or self._finish_known(key)
            qualified = lambda key: (not pinned and display_rows[key].running or (
                (sort == 'name' or self._key_current(key, sort))
                and (period == 'all' and sort != 'activity' or self._activity_current(key))
                and (key not in self.active or self._activity_current(key))))
            live_page = passive and navigation is None and nav is None
            if not pinned:
                indexed = sum(qualified(key) for key in candidates)
                pending = indexed != len(candidates)
                if nav is not None and navigation is not None:
                    indexed, pending = len(nav.facts), bool(nav.pending)
            if not pinned and not reuse:
                applied = "activity" if pending and not live_page else sort
                order = -1 if pending and not live_page else direction
                cache_key = window.identity, applied, order, pending, live_page
                members = event_members(candidates, window, display_rows, event_current)
                latest, previous = next(((key, value) for key, value in reversed(lease["epochs"].items())
                    if (value.sort, value.direction, value.window.identity) == (applied, order, window.identity)),
                    (None, None))
                # An admission hint is not a prompt clock or a final period
                # match. Do not show unqualified out-of-window roots.
                metadata = {key: self.activity.get(key) for key in members
                    if in_window(self.activity.get(key), window)}
                if live_page:
                    members = tuple(key for key in members if display_rows[key].running
                         or event_current(key) or key in metadata or window.period == 'all')
                positions = {}
                arrivals = ()
                if live_page and pending and (sort, direction) != ("activity", -1):
                    # Only newly discovered, in-window roots get a temporary
                    # tier. Revisions do not renew it. Old unresolved positions
                    # remain display-only, never current-key proof.
                    arrivals = tuple(nsmallest(ARRIVAL_SLOTS, (key for key in members if key in metadata
                        and self.clock() - self.recent_arrivals.get(key, float('-inf')) < ARRIVAL_SECONDS
                        and not display_rows[key].running and not qualified(key)),
                        key=lambda key: (-metadata[key], key)))
                    if previous:
                        allowed = set(members)
                        positions = {row.session_id: index for index, row in enumerate(
                            row for row in previous.rows if not row.running and row.session_id not in previous.arrivals)
                            if row.session_id in allowed and not display_rows[row.session_id].running
                            and not qualified(row.session_id) and row.session_id not in arrivals}
                    members = tuple(key for key in members if display_rows[key].running or qualified(key))
                signature = (tuple((key, metadata.get(key), display_rows[key], event_current(key))
                                    for key in (*members, *positions, *arrivals)), tuple(positions.items()), arrivals)
                cached = self.orders.get(cache_key)
                if nav is not None and navigation is not None and not pending:
                    rows = ordered(self._with_lifecycle(nav.rows, display_rows), sort, direction)
                elif cached and cached[0] == signature:
                    rows = cached[1]
                else:
                    rows = ordered((display_rows[key] for key in members), applied, order)
                    if pending and (applied, order) == ("activity", -1):
                        rows = (live_activity_order(rows, metadata, event_current) if live_page else
                            provisional_order(rows, self.activity))
                    elif positions:
                        rows = retained_positions(rows, positions, display_rows)
                    if arrivals:
                        running_count = sum(row.running for row in rows)
                        rows = rows[:running_count] + tuple(display_rows[key] for key in arrivals) + rows[running_count:]
                self.orders[cache_key] = signature, rows
                self.orders.move_to_end(cache_key)
                while len(self.orders) > 32:
                    self.orders.popitem(last=False)
                if (previous is not None and (previous.sort, previous.direction) == (applied, order)
                        and previous.provisional == pending
                        and previous.browsable_candidates == (live_page and pending)
                        and previous.arrivals == frozenset(arrivals)
                        and previous.window.identity == window.identity and tuple(
                        row.session_id for row in previous.rows) == tuple(row.session_id for row in rows)
                        and (live_page or not previous.facts or previous.rows == rows)):
                    epoch = latest
                    window = previous.window
                else:
                    epoch = uuid4().hex
                    facts = tuple(nav.facts.items()) if nav is not None and navigation is not None and not pending else ()
                    lease["epochs"][epoch] = CatalogEpoch(rows, applied, order, window, pending, facts,
                        browsable_candidates=live_page and pending, arrivals=frozenset(arrivals))
                while len(lease["epochs"]) > 8:
                    lease["epochs"].popitem(last=False)
            else:
                rows, applied, order = issued.rows, issued.sort, issued.direction
                window = issued.window
                candidates = tuple(row.session_id for row in (page_rows if reuse else rows))
                indexed = sum(qualified(key) for key in candidates)
                # Published membership/order is independent of live scalar readiness.
                pending = False
            snapshot = lease['epochs'][epoch]
            frozen = not reuse and not live_page and (bool(snapshot.facts)
                or nav is not None and navigation is not None and not pending)
            lease.update(sort=sort, period=period, candidates=candidates, pinned=offset > 0 or snapshot.browsable_candidates and pinned,
                          cohort_verified=not snapshot.provisional)
            selected = rows[offset:offset + PAGE_SIZE]
            lease["visible"] = tuple(row.session_id for row in selected)
            lease["nearby"] = tuple(row.session_id for row in rows[
                offset + PAGE_SIZE:offset + PAGE_SIZE * 3]) if snapshot.browsable_candidates else ()
            self.last_page = lease['visible']
            # Older pages retain membership/order; only independently observed
            # values may change. Deleted rows retain their epoch evidence.
            if not frozen:
                fresh = {row.session_id: row for row in self._rows(lease['visible'])}
                selected = tuple(fresh.get(row.session_id, row) for row in selected)
            if nav is not None and navigation is not None and pinned:
                selected = tuple(nav.facts[row.session_id][0] if row.session_id in nav.facts else row
                                 for row in selected)
            if frozen:
                # Frozen metrics/membership are historical facts, not a license
                # to keep claiming an old prompt is currently executing.
                selected = self._with_lifecycle(selected)
            retained_order = reuse and any(
                old.running != fresh.running or (old.prompt_started_ms != fresh.prompt_started_ms if fresh.running
                    else sort_value(old, sort) != sort_value(fresh, sort))
                for old, fresh in zip(page_rows, selected))
            report = ReportProjection(ReportKind.SESSIONS, "Sessions", "OpenCode", (), session_usage=selected)
            result = project(report, self.timezone_id, self.unit).to_json()
            facts = (nav.facts if nav is not None and navigation is not None else {
                key: fact for key, fact in snapshot.facts if key in lease['visible']}) if frozen else {}
            # Reusing the same issued order must not freeze the metadata clock
            # on the live page. Explicitly pinned slices keep their own window.
            metadata_window = current_window if live_page and not pinned else window
            for row, usage in zip(result["session_usage"], selected):
                key = row["session_id"]
                current = key in self.roots and self._current(key)
                row["indexed"] = current
                activity_current = event_current(key)
                hint = self.activity.get(key)
                row["catalog_activity_ms"] = hint if (snapshot.browsable_candidates and not activity_current
                    and not row["running"] and in_window(hint, metadata_window)) else None
                row["new_arrival"] = key in snapshot.arrivals
                row["activity_state"] = ('retained' if row["last_activity_ms"] is not None else 'unavailable') if (
                    self.state == 'source_unavailable' or self.index_unavailable) else (
                        'ready' if activity_current else 'partial' if key in self.rows and not self.rows[key].activity_qualified
                        else 'retained' if row["last_activity_ms"] is not None
                         else 'unavailable' if key in self.failures else 'pending')
                if key in self.running_roots and not row["running"]:
                    row["activity_state"] = 'unverified'
                row["has_summary"] = key in self.rows or row["prompt_count"] is not None
                unavailable = self.index_unavailable or self.state == "source_unavailable" or key in self.failures or key not in self.roots
                row["metric_state"] = ("retained" if row["has_summary"] else "unavailable") if unavailable else (
                    "ready" if current else "retained" if row["has_summary"] else "pending")
                if current and (key in self.active or self.rows[key].running) and self.clock() - self.valid[key][1] > 15:
                    row["metric_state"] = "retained"
                # Running and its bound start were qualified before ordering (or
                # captured together in a frozen navigation fact), never upgraded
                # afterward from a boolean Watch hint with no prompt identity.
                row["metric_states"] = {name: row["metric_state"] for name in ("model", "effort", "ccost", "prompts", "duration", "ctx")}
                if current and not self.rows[key].context_qualified:
                    row["metric_states"]["ctx"] = "retained" if row["context_tokens"] is not None else "pending"
                if key in self.rows and (key not in self.valid or self.valid[key][0] != self.revisions.get(key)):
                    row["metric_states"]["ctx"] = ("retained" if row["context_tokens"] is not None else
                        "unavailable" if unavailable else "pending")
                if row["running"] and not unavailable and self.rows.get(key) and self.rows[key].model_pending:
                    row["metric_states"]["model"] = "pending"
                if current and not self.rows[key].effort_qualified:
                    row["metric_states"]["effort"] = "retained" if self.rows[key].effort_key is not None else "pending"
                if row["running"] and not unavailable and self.rows.get(key) and self.rows[key].effort_pending:
                    row["metric_states"]["effort"] = "pending"
                if (usage.empty_history and current and not unavailable and self.state == "observed"
                        and key not in self.active and not row["running"]
                        and (not frozen or key in facts and facts[key][1] is not None
                             and facts[key][1] == self.revisions.get(key))):
                    row["metric_absences"] = dict.fromkeys(("model", "ctx", "activity"), EMPTY_HISTORY)
                if key in facts:
                    row['snapshot_revision'] = facts[key][1]
                    if facts[key][1] is None:
                        # Frozen running order is not proof of current metrics.
                        row['snapshot_semantics'] = 'qualified-running-lifecycle; retained-scalars'
                        row['indexed'] = False
                        row['metric_state'] = 'retained' if row['has_summary'] else 'pending'
                        row['metric_states'] = {name: 'retained' if state == 'ready' else state
                            for name, state in row['metric_states'].items()}
                        continue
                    row['snapshot_semantics'] = 'independently-qualified-navigation-facts'
                    row['metric_state'] = 'snapshot'
                    row['metric_states'] = dict.fromkeys(row['metric_states'], 'snapshot')
                    evidence = facts[key][0]
                    if not evidence.context_qualified:
                        row['metric_states']['ctx'] = 'retained' if row['context_tokens'] is not None else 'pending'
                    if evidence.model_pending:
                        row['metric_states']['model'] = 'retained' if row['model'] != 'N/A' else 'pending'
                    row['indexed'] = False
            progress = self._progress(sort, pending, selected, indexed, pinned, candidates,
                scope=not pinned and not reuse and (period != 'all' or sort != 'name'))
            if nav is not None and navigation is not None:
                progress.update(completed=len(nav.facts), total=len(nav.roots),
                    phase='page' if pinned else 'index')
                if not nav.pending and not progress['reason']:
                    progress['status'] = 'ready'
            if (usable and not snapshot.provisional and not pending
                    and (nav is None or navigation is None or not nav.pending)
                    and (not offset or reuse or progress['status'] == 'ready')):
                snapshot.remember_page(offset)
            return dict(token=token, epoch=epoch, offset=offset, total=len(rows), size=PAGE_SIZE,
                page_reused=reuse, retained_order=retained_order,
                  passive=bool(passive and not offset and navigation is None and nav is None),
                 candidate_scope='source_catalog_metadata',
                 membership_pending=snapshot.provisional, candidate_navigation=snapshot.browsable_candidates,
                 order_state='provisional' if snapshot.provisional else 'verified',
                period=period, window=dict(start_ms=window.start_ms, end_ms=window.end_ms, timezone_id=window.timezone_id),
                sort=applied, direction=order, pending_sort=pending, indexed=indexed,
                available=len(rows) if reuse else len(candidates), state=self.state, view=result,
                requested_sort=sort, requested_direction=direction,
                navigation=navigation, progress=progress,
                age_ms=None if self.observed is None else int(max(0, self.clock() - self.observed) * 1000),
                page_ready=sum(self._current(row.session_id) for row in selected if row.session_id in self.roots))

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
