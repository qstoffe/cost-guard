"""One host's source authorization for the local display archive."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from itertools import islice
import sqlite3
from threading import Lock
import time
from uuid import uuid4

from src.application.archive_mix_refresh import ArchiveMixRefresh
from src.application.cached_mix_view import cached_mix_groups, cached_mix_view
from src.application.cached_session_views import CachedSessionViews
from src.application.session_archive_owner import SessionArchiveOwner
from src.application.session_archive_sweep import SessionArchiveSweep
from src.application.session_coverage import SessionCoverageSweep
from src.application.watch_archive_projection import archive_watch_observation, cached_watch_view
from src.application.watch_native_quota import native_quotas
from src.cache.display_history import BATCH_LIMIT, DisplayHistory
from src.cache.display_watch import WatchObservation, withdraw_watch_liveness
from src.cache.display_watch_quota import WatchQuotaBatch
from src.sources.errors import SourceError
from src.sources.opencode_v1 import OpenCodeV1Source
from src.sources.opencode_v2 import OpenCodeV2Source

from .adaptive_dispatch import PROJECTIONS, ProjectionTurns
from .display_accounts import DisplayAccounts
from .display_binding import selected_display_binding
from .display_models import DisplayModels
from .display_stats import DisplayStats


class DisplayArchive:
    def __init__(self, root, publish, *, watch_enabled=False, mix_enabled=False, mix_groups=False, stats_enabled=False,
                 models_enabled=False, accounts_enabled=False):
        self.history = DisplayHistory(root)
        self.sessions = SessionArchiveOwner(self.history, publish)
        self._publish = publish
        self.watch_enabled = watch_enabled
        self.mix_refresh = ArchiveMixRefresh(grouped=mix_groups) if mix_enabled else None
        self.stats = DisplayStats(self, publish) if stats_enabled else None
        self.models = DisplayModels(self, publish) if models_enabled else None
        self.accounts = DisplayAccounts(self, publish) if accounts_enabled else None
        self.projection_turns = ProjectionTurns()
        self.visible_sections = frozenset
        self._mix_signal = Lock()
        self._mix_marks = {}
        self.sweep = SessionArchiveSweep()
        self.coverage = SessionCoverageSweep()
        self.views = None
        self._binding = None
        self._observing = None
        self._catalog_key = None
        self._catalog_iter = iter(())
        self._pending = ()
        self._membership_after = None
        self._retry_at = 0
        self._live_writer = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cost-guard-display-live")
        self._live_write = None
        self._live_offered = None
        self._live_committed = None
        self._live_retry = None
        self._live_health = None
        self._watch_bound_ms = 0
        self._watch_quota = None
        self._watch_quota_revision = 0

    def initialize(self):
        try:
            self.history.initialize()
        except (OSError, sqlite3.Error):
            # Let the Web host start. Reads distinguish this from a usable,
            # empty cache, and the background writer can retry initialization.
            return False
        return True

    def observe(self, driver, *, before_tick):
        """Called by Live only, never by a cached HTTP request."""
        service = getattr(driver.coordinator, "report_service", None)
        selection = getattr(service, "selection", None)
        if selection is None or driver.terminal:
            self._set_binding(None)
            return
        source = selection.source
        observation = getattr(driver.coordinator, "catalog_observation", None)
        prior = selected_display_binding(selection) if before_tick else None
        if isinstance(source, OpenCodeV2Source) and before_tick:
            try:
                source.refresh_observation_epoch()
            except SourceError:
                self._observing = None
                self._set_binding(None)
                return
        binding = selected_display_binding(selection)
        if before_tick:
            self._observing = (binding, observation)
        if binding is None or (driver.error is not None and
                (driver.error.terminal or driver.error.exception_type == "PermissionError")):
            self._set_binding(None)
            return
        if self._binding == binding:
            return
        self._set_binding(None)
        if driver.error is not None:
            return
        if before_tick:
            # A fresh source selection was already probed. Allow warm reads
            # before the first catalog or revision request completes.
            if observation is not None or prior != binding:
                return
        elif (self._observing is None or binding != self._observing[0]
              or observation is None or observation is self._observing[1]
              or isinstance(source, OpenCodeV2Source) and observation.source_epoch != binding.source_epoch):
            return
        self._set_binding(binding, service.timezone_id, coverage_supported=isinstance(source, OpenCodeV1Source),
                          native_export_supported=isinstance(source, OpenCodeV2Source))

    def unbind(self):
        self._set_binding(None)

    def close(self):
        self.unbind()
        self._live_writer.shutdown(wait=True, cancel_futures=True)

    def publish_live(self, running, frame=None, observed_ms=None, *, account_refresh=None, source_unavailable=False):
        """One in-flight turn, with independent proof for each display slice."""
        views = self.views
        if views is None:
            return None
        fence = self.sessions.clear_fence
        scope = (views.binding, fence)
        status = views.binding, source_unavailable
        if self._live_health is None or self._live_health[:2] != status:
            self._live_health = (*status, object())
        health = self._live_health
        now = int(time.time() * 1000)
        batch = self._offer_watch_quota(scope, account_refresh, now) if self.watch_enabled else None
        hint = dict(binding=views.binding, revision=batch.revision) if batch is not None else None
        if self._live_write is not None:
            if not self._live_write.done():
                return hint
            if self._live_write.result():
                self._live_committed = self._live_offered
            else:
                self._live_retry = self._live_offered[0], time.monotonic() + 2
            self._live_write = None
        if self._live_retry is not None and (scope, health) == self._live_retry[0] and time.monotonic() < self._live_retry[1]:
            return hint
        watch = None
        if self.watch_enabled:
            if frame is not None and not source_unavailable:
                watch = archive_watch_observation(frame, observed_ms, views.timezone_id)
            if watch is not None:
                watch = replace(watch, quotas=batch)
            elif batch is not None or source_unavailable:
                watch = WatchObservation(now, now, None, False, None, quotas=batch, withdraw_live=source_unavailable)
        if watch is None and running is None:
            return hint
        # Ignore projection time alone (and synthetic clocks for quota/outage-only turns).
        watch_key = (watch.observed_ms if watch.facts is not None else None, watch.state, watch.truncated,
                     watch.facts, watch.daily, watch.quotas, watch.withdraw_live) if watch is not None else None
        key = (scope, health), running, watch_key
        if key != self._live_committed:
            self._live_offered = key
            self._live_write = self._live_writer.submit(self._write_live, views, fence, health, running, watch)
        return hint

    def _offer_watch_quota(self, scope, refresh, now):
        if refresh is not None or self._watch_quota is not None:
            facts = native_quotas(refresh, bound_ms=self._watch_bound_ms, now_ms=now)
            if self._watch_quota is None or (scope, facts) != (self._watch_quota[0], self._watch_quota[1].facts):
                self._watch_quota_revision += 1
                self._watch_quota = scope, WatchQuotaBatch(self._watch_quota_revision, facts)
            return self._watch_quota[1]
        return None

    def _write_live(self, views, fence, health, running, watch):
        try:
            return self.sessions.commit_live(views.source, views.binding, running=running, watch=watch,
                clear_fence=fence, eligible=lambda: self.views is views and self._live_health is health)
        except (OSError, sqlite3.Error):
            return False  # No failed or partial transaction becomes a cache event.

    def watch_snapshot(self, *, live_eligible, presentation=False):
        views = self.views
        if views is None or not self.watch_enabled:
            return None
        fence = self.sessions.clear_fence
        now = int(time.time() * 1000)
        value = dict(binding=views.binding, **self.history.watch(views.source, views.binding, now,
                                         live_eligible=live_eligible(), timezone_id=views.timezone_id))
        if value["freshness"] == "current" and (not live_eligible() or
                int(time.time() * 1000) >= value["expires_ms"]):
            withdraw_watch_liveness(value)
        offered = self._watch_quota
        batch = value.pop("quotas")
        # A known revocation or newer roster must hide the old native data
        # immediately, even if SQLite cannot take the next write yet.
        matched = (offered is not None and offered[0] == (views.binding, fence)
                   and batch is not None and batch.revision == offered[1].revision)
        value["quota_revision"] = batch.revision if matched else None
        if presentation:
            value["view"] = cached_watch_view(value, views.timezone_id, quotas=batch if matched else None, now_ms=now)
            if offered is not self._watch_quota and matched:
                value["quota_revision"] = None
                value["view"]["accounts"] = None
        return value if self.views is views and self.sessions.clear_fence == fence else None

    def mix_total(self, period, *, orders=None, **groups):
        views = self.views
        if views is None:
            return None
        fence = self.sessions.clear_fence
        now = int(time.time() * 1000)
        args = self.history, views.source, views.timezone_id, period, now
        snapshot = cached_mix_groups(*args, **groups) if groups else cached_mix_view(*args, orders=orders)
        if self.views is views and self.sessions.clear_fence == fence:
            return dict(binding=views.binding, **snapshot)
        return None

    def mix_pending(self):
        views = self.views
        return self.mix_refresh is not None and self.mix_refresh.due(
            (views.binding, self.sessions.clear_fence) if views is not None else None)

    def next_projection(self, reference, *, history_pending=False):
        """Offer one fair turn; do not do any projection or I/O on Live."""
        due = {kind for kind, _ in PROJECTIONS if kind != "mix" and
               (projection := getattr(self, kind)) is not None and projection.pending()}
        if self.mix_pending():
            due.add("mix")
        selected = self.projection_turns.choose(due, self.visible_sections(), history_pending=history_pending)
        if selected == "mix":
            return lambda now_ms, *, active: self.advance_mix(now_ms, active=active, reference=reference)
        return getattr(self, selected).advance if selected is not None else None

    def advance_mix(self, now_ms, *, active, reference=lambda: None):
        if self.mix_refresh is None:
            return
        views = self.views
        if views is None or not active():
            self.mix_refresh.withdraw()
            return
        fence = self.sessions.clear_fence

        def eligible():
            return self.views is views and self.sessions.clear_fence == fence and active()

        published = self.mix_refresh.advance(self.history, views.source, views.timezone_id,
            (views.binding, fence), now_ms, eligible=eligible, reference=reference)
        if published is not None and published.changed_periods:
            with self._mix_signal:
                if not eligible():
                    return
                self._mix_marks.update({period: (published.version.revision, published.end_ms,
                                                published.group_marks.get(period))
                                        for period in published.changed_periods})
                self._publish("token-mix-cache", dict(binding=views.binding, archive_epoch=published.version.archive_epoch,
                    usage_revision=published.version.revision, end_ms=published.end_ms, periods=published.changed_periods,
                    marks=self._mix_marks.copy()))

    def close_catalog_work(self):
        if self.mix_refresh is not None:
            self.mix_refresh.withdraw()
        if self.stats is not None:
            self.stats.close()
        if self.accounts is not None:
            self.accounts.close()

    def _mix_reset(self, views, *, archive_epoch=None):
        if self.mix_refresh is not None:
            with self._mix_signal:
                if self.views is views:
                    self._mix_marks.clear()
                    self._publish("token-mix-cache", dict(binding=views.binding if views else None,
                        marks={}, archive_epoch=archive_epoch, cleared=archive_epoch is not None))

    def _set_binding(self, binding, timezone_id="UTC", *, coverage_supported=False, native_export_supported=False):
        if binding == self._binding:
            return
        self.views = None
        self._watch_quota = None
        self._binding = binding
        if self.accounts is not None:
            self.accounts.reset()
        if binding is None:
            self.sessions.bind("", "", announce=True)
            if self.watch_enabled:
                self._publish("watch-cache", dict(binding=None))
            self._mix_reset(None)
            if self.stats is not None:
                self.stats.reset(None)
            if self.models is not None:
                self.models.reset(None)
            return
        epoch = uuid4().hex
        views = CachedSessionViews(self.history, binding.scope, timezone_id, epoch,
                                   coverage_supported=coverage_supported, native_export_supported=native_export_supported)
        self.views = views
        self._watch_bound_ms = int(time.time() * 1000)
        self.sessions.bind(binding.scope, epoch, announce=True)
        if self.watch_enabled:
            self._publish("watch-cache", dict(binding=epoch))
        self._mix_reset(views)
        if self.stats is not None:
            self.stats.reset(views)
        if self.models is not None:
            self.models.reset(views)
        if self.accounts is not None:
            self.accounts.announce_binding(views)

    def _writer_binding(self, service):
        views = self.views
        binding = self._binding
        if (views is None or binding is None or binding.scope != views.source
                or selected_display_binding(service.selection) != binding or views is not self.views):
            return None
        return views.source, views.binding

    def _cache_write(self, action):
        if time.monotonic() < self._retry_at:
            return False
        try:
            action()
        except (OSError, sqlite3.Error):
            self._retry_at = time.monotonic() + 5
            self.initialize()
            return False
        return True

    def clear_snapshot(self):
        """Called only by the explicit confirmation flow, not normal page reads."""
        views = self.views
        if views is None:
            return None
        state = self.history.source_state(views.source)
        if self.views is views:
            return dict(binding=views.binding, generation=state.generation, archive_epoch=state.archive_epoch)
        return None

    def clear_confirmed(self, binding, expected, catalog, service, *, eligible):
        views = self.views
        if views is None or binding != views.binding:
            return None

        def current_observation():
            with catalog.lock:
                return catalog.observation_sequence

        state = self.sessions.clear(views.source, binding, expected, current_observation=current_observation,
            eligible=lambda: self.views is views and eligible() and
            self._writer_binding(service) == (views.source, binding))
        if state is not None:
            if self.watch_enabled and self.views is views:
                self._publish("watch-cache", dict(binding=binding, generation=0, archive_epoch=state.archive_epoch))
            self._mix_reset(views, archive_epoch=state.archive_epoch)
            if self.stats is not None:
                self.stats.reset(views, archive_epoch=state.archive_epoch)
            if self.models is not None:
                self.models.reset(views, archive_epoch=state.archive_epoch)
            if self.accounts is not None:
                self.accounts.reset()
            return dict(binding=binding, generation=state.generation, archive_epoch=state.archive_epoch)
        return None

    def catalog_pending(self, catalog):
        """Cheap scheduling hint, checked on Live without scanning or writing."""
        views = self.views
        fence = self.sessions.observation_fence(catalog.observation_sequence)
        return (views is not None and catalog.state == "observed" and time.monotonic() >= self._retry_at
                and fence is not None and
                (self._catalog_key != (views.binding, fence, catalog.membership_generation)
                 or self._pending is not None or self._membership_after is not None))

    def summary_pending(self, catalog):
        views = self.views
        return (views is not None and time.monotonic() >= self._retry_at
                and self.sessions.observation_fence(catalog.observation_sequence) is not None
                and self.sweep.due(catalog, (views.binding, self.sessions.clear_fence)))

    def priority_summary_pending(self, catalog):
        return (self.views is not None and catalog.state == "observed" and time.monotonic() >= self._retry_at
                and self.sessions.observation_fence(catalog.observation_sequence) is not None
                and self.sweep.priority_due(catalog))

    def prioritize_detail(self, catalog, binding, session_id):
        result = self.prioritize_visible(catalog, binding, (session_id,))
        return None if result is None else bool(result)

    def prioritize_visible(self, catalog, binding, session_ids):
        views = self.views
        if views is None or views.binding != binding:
            return None
        def eligible():
            return self.views is views and self.sessions.observation_fence(catalog.observation_sequence) is not None
        return self.sweep.prioritize_visible(catalog, session_ids, eligible=eligible)

    def export_epoch(self, service, views):
        """Only the currently authorized V2 partition can authorize native export."""
        if (views.native_export_supported and self.views is views
                and self._writer_binding(service) == (views.source, views.binding)):
            binding = self._binding
            if binding is not None and binding.scope == views.source and self.views is views:
                return binding.source_epoch
        return None

    def coverage_pending(self, catalog):
        views = self.views
        fence = self.sessions.observation_fence(catalog.observation_sequence)
        return (views is not None and fence is not None and time.monotonic() >= self._retry_at
                and self.coverage.due(catalog, (views.source, views.binding), fence))

    def check_coverage(self, catalog, service):
        binding = self._writer_binding(service)
        fence = self.sessions.observation_fence(catalog.observation_sequence)
        if binding is not None and fence is not None and self.coverage_pending(catalog):
            self.coverage.tick(catalog, self, service, binding, fence)

    def coverage_slice(self, binding, revisions):
        views = self.views
        if views is None or (views.source, views.binding) != binding:
            return None
        try:
            return self.history.session_coverage_slice(views.source, revisions)
        except (OSError, sqlite3.Error):
            return None

    def publish_coverage(self, binding, fence, proof, *, eligible, widen_only=False):
        return self._cache_write(lambda: self.sessions.publish_coverage(*binding, fence, proof, eligible=eligible,
                                                                       widen_only=widen_only))

    def completed_summary_keys(self, binding, revisions, dependency):
        completed = None

        def read():
            nonlocal completed
            views = self.views
            if views is not None and (views.source, views.binding) == binding:
                completed = self.history.completed_sessions(binding[0], revisions, dependency, with_history=True,
                                                            with_stats_requests=self.stats is not None)

        self._cache_write(read)
        return completed

    def acquire_summaries(self, catalog, service):
        binding = self._writer_binding(service)
        fence = self.sessions.observation_fence(catalog.observation_sequence)
        if binding is not None and fence is not None and time.monotonic() >= self._retry_at:
            self.sweep.tick(catalog, self, service, binding, fence)

    def publish_catalog(self, catalog, service):
        """One bounded write slice on the existing Sessions acquisition lane."""
        binding = self._writer_binding(service)
        if binding is None:
            return
        with catalog.lock:
            if catalog.state != "observed":
                return
            fence = self.sessions.observation_fence(catalog.observation_sequence)
            observed = catalog.last_observation
            if fence is None:
                return
            key = (binding[1], fence, catalog.membership_generation)
            if self._catalog_key != key and (not self._catalog_key or self._catalog_key[:2] != key[:2]
                    or self._pending is None and self._membership_after is None):
                self._catalog_key = key
                self._catalog_iter = iter(catalog.roots)
                self._pending = ()
                self._membership_after = ""
            if self._pending == ():
                self._pending = tuple(islice(self._catalog_iter, BATCH_LIMIT)) or None
            revisions = {key: catalog.revisions[key] for key in self._pending or ()
                         if key in catalog.roots and catalog.revisions.get(key)}
            titles = {key: catalog.roots[key].title or "Untitled session" for key in revisions}
            activity = {key: catalog.activity.get(key) for key in revisions}
        if self._pending is None:
            self._mark_missing(catalog, service, binding, observed, fence)
            return

        def write():
            admission = self.sessions.admit(revisions, binding=binding, clear_fence=fence)
            if admission is not None:
                self.sessions.publish_catalog(admission, titles, revisions, activity=activity)

        if self._cache_write(write):
            self._pending = ()

    def _mark_missing(self, catalog, service, binding, observed, fence):
        if self._membership_after is None:
            return

        def reconcile():
            batch = self.history.session_membership_slice(binding[0], self._membership_after)
            with catalog.lock:
                # An auth/load failure or a different membership snapshot
                # cannot be treated as a deletion, even for the same source.
                if (catalog.state != "observed" or catalog.last_observation is not observed
                        and self._catalog_key != (binding[1], fence, catalog.membership_generation)):
                    return
                missing = {key: checkpoint for key, checkpoint, present in batch if present and key not in catalog.roots}
            if self._writer_binding(service) != binding:
                return
            admission = self.sessions.admit({key: checkpoint.revision for key, checkpoint in missing.items()},
                                            binding=binding, clear_fence=fence)
            if admission is not None:
                # Preserve the checkpoint from the membership slice. Do not
                # mark a later write absent on the strength of an old scan.
                absent = tuple(proof.session_id for proof in admission.facts
                               if proof.checkpoint == missing[proof.session_id])
                self.sessions.commit(admission, {}, {}, missing=absent)
                self._membership_after = batch[-1][0] if len(batch) == BATCH_LIMIT else None

        self._cache_write(reconcile)

    def admit_summary(self, service, session_id, revision, *, observation_sequence):
        binding = self._writer_binding(service)
        fence = self.sessions.observation_fence(observation_sequence)
        if binding is None or fence is None or not revision:
            return None
        admission = None

        def admit():
            nonlocal admission
            admission = self.sessions.admit({session_id: revision}, binding=binding, clear_fence=fence)

        self._cache_write(admit)
        return admission

    def publish_summary(self, service, admission, row, revision, *, dependency=None, eligible=None, usage=None):
        if admission is None or self._writer_binding(service) != (admission.source, admission.epoch):
            return False
        accepted = False

        def write():
            nonlocal accepted
            accepted = self.sessions.commit_summary(admission, row, revision, dependency=dependency,
                                                     eligible=eligible, usage=usage)

        return self._cache_write(write) and accepted
