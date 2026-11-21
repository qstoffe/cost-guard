"""One host's source authorization for the local display archive."""
from concurrent.futures import ThreadPoolExecutor
from itertools import islice
import sqlite3
import time
from uuid import uuid4

from src.application.cached_session_views import CachedSessionViews
from src.application.session_archive_owner import SessionArchiveOwner
from src.application.session_archive_sweep import SessionArchiveSweep
from src.cache.display_history import BATCH_LIMIT, DisplayHistory
from src.sources.errors import SourceError
from src.sources.opencode_v2 import OpenCodeV2Source

from .display_binding import selected_display_binding


class DisplayArchive:
    def __init__(self, root, publish):
        self.history = DisplayHistory(root)
        self.sessions = SessionArchiveOwner(self.history, publish)
        self.sweep = SessionArchiveSweep()
        self.views = None
        self._binding = None
        self._observing = None
        self._catalog_key = None
        self._catalog_iter = iter(())
        self._pending = ()
        self._membership_after = None
        self._retry_at = 0
        self._running_writer = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cost-guard-display-live")
        self._running_write = None
        self._running_offered = None
        self._running_committed = None
        self._running_retry_at = 0

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
        self._set_binding(binding, service.timezone_id)

    def unbind(self):
        self._set_binding(None)

    def close(self):
        self.unbind()
        self._running_writer.shutdown(wait=True, cancel_futures=True)

    def publish_running(self, running):
        """Offer the newest qualified observation without queueing future turns."""
        if self._running_write is not None:
            if not self._running_write.done():
                return
            if self._running_write.result():
                self._running_committed = self._running_offered
            else:
                self._running_retry_at = time.monotonic() + 2
            self._running_write = None
        views = self.views
        if views is None or time.monotonic() < self._running_retry_at:
            return
        offered = views.source, views.binding, running
        if self._running_committed == offered:
            return
        self._running_offered = offered
        self._running_write = self._running_writer.submit(self._write_running, *offered)

    def _write_running(self, source, binding, running):
        try:
            self.sessions.commit_running(source, binding, running)
        except (OSError, sqlite3.Error):
            return False  # No failed or partial transaction becomes a cache event.
        return True

    def _set_binding(self, binding, timezone_id="UTC"):
        if binding == self._binding:
            return
        self.views = None
        self._binding = binding
        if binding is None:
            self.sessions.bind("", "", announce=True)
            return
        epoch = uuid4().hex
        self.views = CachedSessionViews(self.history, binding.scope, timezone_id, epoch)
        self.sessions.bind(binding.scope, epoch, announce=True)

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

    def catalog_pending(self, catalog):
        """Cheap scheduling hint, checked on Live without scanning or writing."""
        views = self.views
        return (views is not None and catalog.state == "observed" and time.monotonic() >= self._retry_at
                and (self._catalog_key != (views.binding, catalog.membership_generation)
                      or self._pending is not None or self._membership_after is not None))

    def summary_pending(self, catalog):
        views = self.views
        return (views is not None and time.monotonic() >= self._retry_at
                and self.sweep.due(catalog, views.binding))

    def priority_summary_pending(self, catalog):
        return (self.views is not None and catalog.state == "observed" and time.monotonic() >= self._retry_at
                and self.sweep.priority_due(catalog))

    def completed_summary_keys(self, binding, revisions, dependency):
        completed = None

        def read():
            nonlocal completed
            views = self.views
            if views is not None and (views.source, views.binding) == binding:
                completed = self.history.completed_sessions(binding[0], revisions, dependency)

        self._cache_write(read)
        return completed

    def acquire_summaries(self, catalog, service):
        binding = self._writer_binding(service)
        if binding is not None and time.monotonic() >= self._retry_at:
            self.sweep.tick(catalog, self, service, binding)

    def publish_catalog(self, catalog, service):
        """One bounded write slice on the existing Sessions acquisition lane."""
        binding = self._writer_binding(service)
        if binding is None:
            return
        with catalog.lock:
            if catalog.state != "observed":
                return
            key = (binding[1], catalog.membership_generation)
            if self._catalog_key != key and (not self._catalog_key or self._catalog_key[0] != binding[1]
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
            observed = catalog.last_observation
        if self._pending is None:
            self._mark_missing(catalog, service, binding, observed)
            return

        def write():
            admission = self.sessions.admit(revisions, binding=binding)
            if admission is not None:
                self.sessions.publish_catalog(admission, titles, revisions, activity=activity)

        if self._cache_write(write):
            self._pending = ()

    def _mark_missing(self, catalog, service, binding, observed):
        if self._membership_after is None:
            return

        def reconcile():
            batch = self.history.session_membership_slice(binding[0], self._membership_after)
            with catalog.lock:
                # An auth/load failure or a different membership snapshot
                # cannot be treated as a deletion, even for the same source.
                if (catalog.state != "observed" or catalog.last_observation is not observed
                        and self._catalog_key != (binding[1], catalog.membership_generation)):
                    return
                missing = {key: checkpoint for key, checkpoint, present in batch if present and key not in catalog.roots}
            if self._writer_binding(service) != binding:
                return
            admission = self.sessions.admit({key: checkpoint.revision for key, checkpoint in missing.items()}, binding=binding)
            if admission is not None:
                # Preserve the checkpoint from the membership slice. Do not
                # mark a later write absent on the strength of an old scan.
                absent = tuple(proof.session_id for proof in admission.facts
                               if proof.checkpoint == missing[proof.session_id])
                self.sessions.commit(admission, {}, {}, missing=absent)
                self._membership_after = batch[-1][0] if len(batch) == BATCH_LIMIT else None

        self._cache_write(reconcile)

    def admit_summary(self, service, session_id, revision):
        binding = self._writer_binding(service)
        if binding is None or not revision:
            return None
        admission = None

        def admit():
            nonlocal admission
            admission = self.sessions.admit({session_id: revision}, binding=binding)

        self._cache_write(admit)
        return admission

    def publish_summary(self, service, admission, row, revision, *, dependency=None, eligible=None):
        if admission is None or self._writer_binding(service) != (admission.source, admission.epoch):
            return False
        accepted = False

        def check():
            nonlocal accepted
            accepted = eligible is None or eligible()
            return accepted

        if self._cache_write(lambda: self.sessions.commit(admission, {row.session_id: row},
                {row.session_id: revision}, dependency=dependency, eligible=check)):
            return accepted
        return False
