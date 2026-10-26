"""One process-lifetime acquisition owner, independent of HTTP/tab lifetimes."""
from threading import Event, Thread

from src.sources.errors import SourceError

from .contracts import record
from .live_projection import project_live
from .session_detail import SessionDetails


class LiveRuntime:
    def __init__(self, factory, publish, on_failure=None):
        self.factory = factory
        self.publish = publish
        self.on_failure = on_failure
        self.stopping = Event()
        self.thread = None
        self.failure = None
        self.details = SessionDetails()

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
            while not self.stopping.is_set():
                frame = driver.tick()
                self.details.tick(driver.coordinator.report_service, unavailable=driver.error is not None)
                self.publish("live", record(state="failed" if driver.terminal else
                    "recovering" if driver.error else "running",
                    source_observed_at_ms=driver.observed_at_ms,
                    error_code=driver.error.code.value if driver.error else None,
                    view=project_live(frame) if frame is not None else None))
                if driver.terminal:
                    break
                # Yield between history slices and keep account-only updates timely.
                self.stopping.wait(0.25 if driver.coordinator.today_ccost.history_pending else 1)
        except SourceError as error:
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

    def close(self):
        self.stopping.set()
        if self.thread is not None:
            self.thread.join(timeout=10)
            if self.thread.is_alive():
                raise RuntimeError("live_shutdown_timeout")
