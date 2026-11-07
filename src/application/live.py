"""One process-lifetime acquisition owner, independent of HTTP/tab lifetimes."""
from threading import Event, Thread

from src.sources.errors import SourceError

from .contracts import record
from .live_projection import project_live
from .session_detail import SessionDetails
from .session_catalog import SessionCatalog


class LiveRuntime:
    def __init__(self, factory, publish, on_failure=None):
        self.factory = factory
        self.publish = publish
        self.on_failure = on_failure
        self.stopping = Event()
        self.thread = None
        self.failure = None
        self.details = SessionDetails()
        self.catalog = SessionCatalog()
        self.driver = None
        self.source_failure = None
        self.observed = Event()

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
                    if error.terminal or not error.watch_retryable:
                        raise
                    self.publish("live", record(state="source_unavailable", view=None))
                    self.stopping.wait(5)
            if driver is None:
                return
            self.driver = driver
            while not self.stopping.is_set():
                frame = driver.tick()
                if callable(getattr(type(driver.coordinator), "tick_catalog", None)):
                    driver.coordinator.tick_catalog(self.catalog, unavailable=driver.error is not None)
                if callable(getattr(type(driver.coordinator), "tick_details", None)):
                    driver.coordinator.tick_details(self.details, unavailable=driver.error is not None)
                else:
                    self.details.tick(driver.coordinator.report_service, unavailable=driver.error is not None)
                self._publish_frame(driver, frame)
                if driver.terminal:
                    break
                # Yield between history slices and keep account-only updates timely.
                self.stopping.wait(0.25 if driver.coordinator.today_ccost.history_pending else 1)
        except SourceError as error:
            self.source_failure = error
            self.publish("live", record(state="failed", error_code=error.code.value, view=None))
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

    def _publish_frame(self, driver, frame):
        self.publish("live", record(state=driver.source_state,
            source_observed_at_ms=driver.observed_at_ms,
            error_code=driver.error.code.value if driver.error else None,
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
