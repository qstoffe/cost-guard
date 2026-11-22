"""One process-lifetime acquisition owner, independent of HTTP/tab lifetimes."""
from threading import Event, Thread
import time

from src.sources.errors import SourceError
from src.watch.account_timeline import FOREGROUND_SLICE_MS
from src.watch.source_status import SourceStatus

from .contracts import record
from .live_projection import project_live
from .session_detail import SessionDetails
from .session_catalog import SessionCatalog
from .session_quota import source_scope


class LiveRuntime:
    def __init__(self, factory, publish, on_failure=None, *, timeline_demand=None, archive=None):
        self.factory = factory
        self.publish = publish
        self.on_failure = on_failure
        self.timeline_demand = timeline_demand
        self.stopping = Event()
        self.thread = None
        self.failure = None
        self.details = SessionDetails(archive=archive)
        self.catalog = SessionCatalog(archive=archive)
        self.driver = None
        self.source_failure = None
        self.observed = Event()
        self.working = Event()
        self.startup_health = SourceStatus()

    def start(self):
        if self.thread is not None:
            raise RuntimeError("live_already_started")
        self.thread = Thread(target=self._run, name="cost-guard-live")
        self.thread.start()

    def _run(self):
        driver = None
        try:
            while driver is None and not self.stopping.is_set():
                try:
                    driver = self.factory()
                except SourceError as error:
                    self.startup_health.fail(error)
                    if error.terminal or not error.watch_retryable:
                        raise
                    self.publish("live", record(state="source_unavailable", view=None,
                        source_health=record(**self.startup_health.reachability())))
                    self.stopping.wait(5)
            if driver is None:
                return
            self.driver = driver
            publication_due = time.monotonic()
            timeline_due = publication_due
            coordinator = driver.coordinator
            timeline = getattr(coordinator, 'account_timeline', None) if self.timeline_demand is not None else None
            frame = None
            while not self.stopping.is_set():
                now = time.monotonic()
                if now < publication_due:
                    ready = getattr(coordinator, 'work_ready', self.stopping)
                    if ready is not self.stopping and ready.is_set():
                        # Clear BEFORE servicing: completion during the bounded
                        # turn remains signalled. Callbacks never mutate owners.
                        ready.clear()
                        if driver.error is None:
                            self.working.set()
                            try:
                                coordinator.service_completed()
                            finally:
                                self.working.clear()
                    if timeline is not None and timeline.fast and now >= timeline_due:
                        # Only service the isolated bounded history lane here.
                        # Do not repeat Watch acquisition, projection or SSE.
                        self._tick_timeline(driver, frame)
                        timeline_due = time.monotonic() + FOREGROUND_SLICE_MS / 1000
                    deadline = min(publication_due, timeline_due) if timeline is not None and timeline.fast else publication_due
                    ready.wait(max(0, deadline - time.monotonic()))
                    continue
                self.working.set()
                try:
                    frame = driver.tick()
                    if callable(getattr(type(driver.coordinator), "tick_catalog", None)):
                        selection = coordinator.report_service.selection
                        if driver.error is None:
                            self.catalog.bind_archive(selection.selected, selection.source.source_instance)
                            if self.catalog.archive is not None:
                                self.details.bind_archive(self.catalog.archive.partition)
                        health = getattr(driver, 'source_status', None)
                        driver.coordinator.tick_catalog(self.catalog, unavailable=driver.error is not None,
                            source_interrupted=driver.terminal or isinstance(health, SourceStatus) and health.outage_confirmed())
                    if callable(getattr(type(driver.coordinator), "catalog_frame", None)):
                        frame = driver.coordinator.catalog_frame(self.catalog, frame)
                    if callable(getattr(type(driver.coordinator), "tick_details", None)):
                        driver.coordinator.tick_details(self.details, unavailable=driver.error is not None)
                    else:
                        self.details.tick(driver.coordinator.report_service, unavailable=driver.error is not None)
                    self._publish_frame(driver, frame)
                finally:
                    self.working.clear()
                if driver.terminal:
                    break
                # Yield between history slices and keep account-only updates timely.
                publication_due = time.monotonic() + (0.25 if driver.coordinator.today_ccost.history_pending else 1)
                timeline_due = time.monotonic() + FOREGROUND_SLICE_MS / 1000
        except SourceError as error:
            self.source_failure = error
            self.publish("live", record(state="failed", error_code=error.code.value, view=None,
                source_health=record(**self.startup_health.reachability())))
        except BaseException as error:
            self.failure = error
            self.publish("live", record(state="internal_error", view=None))
            if self.on_failure:
                self.on_failure(error)
            else:
                raise
        finally:
            if driver is not None:
                try:
                    driver.close()
                except BaseException as error:
                    self.failure = self.failure or error
                    if self.on_failure:
                        self.on_failure(error)
                    else:
                        raise

    def _tick_timeline(self, driver, frame):
        coordinator = driver.coordinator
        if self.timeline_demand is not None and callable(getattr(type(coordinator), 'tick_account_timeline', None)):
            verified = frame is not None and driver.error is None and driver.observed_at_ms is not None
            return coordinator.tick_account_timeline(frame, self.timeline_demand,
                available=verified, terminal=driver.terminal)
        return None

    def _publish_frame(self, driver, frame):
        health = getattr(driver, 'source_status', None)
        selection = getattr(driver.coordinator, "selection", None)
        generation = getattr(selection, "selected", None)
        verified = frame is not None and driver.error is None and driver.observed_at_ms is not None
        timeline_scope = self._tick_timeline(driver, frame)
        if frame is not None:
            self.details.observe_accounts(frame.quota, source_scope(driver.coordinator.report_service.source),
                frame.now_ms, stale=frame.quota_stale or not verified)
        self.publish("live", record(state=driver.source_state,
             account_timeline_scope=timeline_scope,
             catalog_hint=self.catalog.live_hint(),
             detail_hints=tuple(record(**hint) for hint in self.details.live_hints()),
            source_generation=generation if verified and generation in {"v1", "v2"} else "unknown",
            source_observed_at_ms=driver.observed_at_ms,
            error_code=driver.error.code.value if driver.error else None,
            source_health=record(**health.reachability()) if isinstance(health, SourceStatus) else None,
            view=project_live(frame, driver.coordinator.report_service.timezone_id,
                 driver.coordinator.report_service.config.get("ccostDisplayUnit", "credits")) if frame is not None else None))
        if frame is not None and driver.error is None and driver.observed_at_ms is not None:
            self.observed.set()

    def close(self):
        self.stopping.set()
        if self.driver is not None and callable(getattr(type(self.driver), "cancel", None)):
            self.driver.cancel()
        if self.thread is not None:
            self.thread.join(timeout=10)
            if self.thread.is_alive():
                raise RuntimeError("live_shutdown_timeout")
