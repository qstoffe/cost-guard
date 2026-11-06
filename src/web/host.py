"""One shutdown owner; native GUI remains on main thread, HTTP on an owned thread."""
import os
import secrets
from threading import Event, Lock, Thread
import time
import webbrowser

from src.version import VERSION
from src.application.live import LiveRuntime
from .change_guard import SourceGuard
from .http import LoopbackServer
from .instance_state import SCHEMA
from .jobs import ReportJobs
from .events import EventHub
from .process_identity import process_identity
from .observations import WebObservations
from .security import BrowserLinkUnavailable
from .dispatch import DataDispatcher, source_identity


class WebHost:
    def __init__(self, root, *, store=None, nonce=None, jobs=None, live_factory=None):
        self.root = root
        self.store = store
        self.nonce = nonce or secrets.token_hex(16)
        self.control = secrets.token_hex(32)
        self.stopping = Event()
        self.stopped = Event()
        self._lock = Lock()
        self.reason = None
        self.ready = False
        self.failure = None
        self._source_identity = None
        self.guard = SourceGuard(root)
        self.jobs = jobs or ReportJobs()
        self.dispatcher = DataDispatcher(self.jobs) if jobs is None else None
        self.dependencies = None
        if jobs is None:
            from .composition import dispatch_dependencies
            self.dependencies = dispatch_dependencies(root)
        self.events = EventHub(self.nonce)
        self.observations = WebObservations()
        self.source_startup = None
        if live_factory is None and jobs is None:
            from .source_startup import SourceStartup
            self.source_startup = SourceStartup(root, self.events.publish, self.stopping)
            live_factory = self.source_startup.acquire
        self.live = LiveRuntime(live_factory, self.events.publish, self.runtime_failed) if live_factory else None
        self.server = None
        self.thread = None

    def runtime_failed(self, error):
        self.failure = self.failure or error
        self.stop("runtime_fault")
        with self._lock:
            self.reason = "runtime_fault"  # Cleanup failure cannot remain a normal stop.

    def authorized(self, token):
        return isinstance(token, str) and token.isascii() and secrets.compare_digest(token, self.control)

    def identity(self):
        return {"nonce": self.nonce, "schema": SCHEMA, "build": VERSION,
                "ready": self.ready and not self.stopping.is_set()}

    def public_status(self):
        return {"instance": self.nonce, "state": self.reason or "running",
                "source_guard": self.guard.status,
                "diagnostics": ("not_recorded" if not self.store else
                                "unavailable" if self.observations.write_failed else "available")}

    def stop(self, reason="menu"):
        if reason not in {"menu", "launcher", "source_changed", "runtime_fault", "gui_unavailable"}:
            reason = "runtime_fault"
        with self._lock:
            if not self.stopping.is_set():
                self.reason = reason
                self.stopping.set()
                self.events.close(reason)
                if self.live:
                    self.live.stopping.set()

    def browser_url(self):
        if self.stopping.is_set() or not self.ready:
            raise BrowserLinkUnavailable("instance_stopping")
        return f"{self.server.origin}/#bootstrap={self.server.session.bootstrap(renew=True)}"

    def open_browser(self, opener=webbrowser.open):
        # Native icon Open retries browser failure; never restarts the host.
        try:
            return bool(opener(self.browser_url()))
        except Exception:
            return False

    def copy_browser_link(self, copier):
        """Trusted native handoff only; failed copies must not fill pending slots."""
        url = None
        try:
            url = self.browser_url()
            copier(url)
            return True
        except BaseException as error:
            if url is not None:
                self.server.session.discard_bootstrap(url.split("#bootstrap=", 1)[1])
            if isinstance(error, (OSError, BrowserLinkUnavailable)):
                return False
            raise

    def publish_ready(self):
        """GUI calls this only after its required native icon/event loop is usable."""
        with self._lock:
            if self.stopping.is_set() or self.ready:
                return
            if self.store:
                identity = process_identity(os.getpid())
                if identity is None:
                    raise RuntimeError("process_identity_unavailable")
                self.store.write({"schema": SCHEMA, "checkout": self.store.key,
                                  "nonce": self.nonce, "control": self.control, "pid": os.getpid(),
                                  "process": identity, "address": "127.0.0.1",
                                  "port": self.server.server_port, "build": VERSION,
                                  "ready_ns": time.time_ns()})
                self.store.log("ready")
            self.ready = True

    def _serve(self):
        try:
            while not self.stopping.is_set():
                self.server.handle_request()
                previous = self.guard.status
                status = self.guard.check()
                if status == "source_changed":
                    self.stop("source_changed")
                elif status == "source_check_unavailable" and previous != status and self.store:
                    self.store.log(status)
                self.observations.persist(self)
                if (self.dependencies and self.live and self.live.observed.is_set()
                        and not self.dependencies.check(self.dispatcher)):
                    self.stop('source_changed')
                if not self.stopping.is_set():
                    if self.source_startup is None or self.source_startup.finished.is_set():
                        if self.dispatcher:
                            driver = self.live.driver if self.live else None
                            selection = driver.coordinator.report_service.selection if driver else None
                            identity = source_identity(selection) if selection else ''
                            if identity and self._source_identity and identity != self._source_identity:
                                self.live.details.invalidate()
                                with self.live.catalog.lock:
                                    self.live.catalog.leases.clear()
                            self._source_identity = identity
                            error = driver.error if driver else self.live.source_failure if self.live else None
                            self.dispatcher.tick(identity=identity,
                                ready=driver is not None and driver.error is None and self.live.observed.is_set(),
                                error=error.code.value if error else None,
                                terminal=bool(driver.terminal if driver else error))
                            if self.live:
                                self.live.catalog.enable_warm(self.dispatcher.warm_allowed)
                        self.jobs.tick()
                    self.events.publish("progress", self.jobs.updates() if hasattr(self.jobs, "updates")
                                        else self.jobs.readiness())
        except BaseException as error:
            self.runtime_failed(error)
        finally:
            self.stopping.set()
            try:
                try:
                    self.jobs.close()
                finally:
                    try:
                        if self.live:
                            self.live.close()
                    finally:
                        self.events.close(self.reason or "runtime_fault")
                        self.server.server_close()
            except BaseException as error:
                self.runtime_failed(error)
            finally:
                self.stopped.set()  # GUI must observe this even on cleanup failure.

    def start(self):
        self.server = LoopbackServer(self.jobs, self)
        if self.live:
            self.live.start()
        self.thread = Thread(target=self._serve, name="cost-guard-web")
        self.thread.start()

    def close(self):
        self.stop()
        if self.thread:
            self.thread.join(timeout=10)
            if self.thread.is_alive():
                raise RuntimeError("web_shutdown_timeout")
        try:
            # The serving thread's bounded attempt may have retained a child
            # whose exit was not yet confirmed. Main remains its cleanup owner.
            self.jobs.close()
        except BaseException as error:
            self.runtime_failed(error)
            raise
        finally:
            try:
                if not self.thread and self.live:
                    self.live.close()
            finally:
                if self.store:
                    self.observations.persist(self, final=True)
                    self.store.remove(self.nonce)
                    self.store.log(self.reason if self.reason in {"source_changed", "runtime_fault"} else "stopped")

    def run_gui(self, gui):
        """Adapter.run(owner) on main thread; poll owner.stopped, finally remove icon.

        Adapter startup failure MUST raise, not call publish_ready. Returning from
        its event loop is terminal. close() must be idempotent and main-thread safe.
        """
        try:
            self.start()
            gui.run(self)
            if not self.ready:
                self.stop("gui_unavailable")
        except BaseException:
            self.stop("runtime_fault")
            raise
        finally:
            try:
                gui.close()
            finally:
                self.close()
