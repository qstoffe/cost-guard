"""One shutdown owner; native GUI remains on main thread, HTTP on an owned thread."""
import os
import secrets
from threading import Event, Lock, Thread
import time
import webbrowser

from src.version import VERSION
from src.application.live import LiveRuntime
from src.analysis.account_timeline import PERIODS
from src.cache.web_archive import WEB_ARCHIVE_FILENAME, WebArchive
from src.reports import ReportKind
from src.reports.archived_usage import ArchivedUsage
from src.log_housekeeping import LogHousekeeping
from src.config import ConfigError, load_configuration
from src.watch.account_timeline import AccountTimeline
from .change_guard import SourceGuard
from .http import LoopbackServer
from .instance_state import SCHEMA
from .jobs import ReportJobs
from .events import EventHub
from .process_identity import process_identity
from .observations import WebObservations
from .security import BrowserLinkUnavailable
from .dispatch import DataDispatcher, source_identity
from .cache_housekeeping import CacheHousekeeping
from .database_sizes import database_sizes
from .history_reports import HistoryReports
from .watch_history import WatchHistory


class WebHost:
    def __init__(self, root, *, store=None, nonce=None, jobs=None, live_factory=None,
                 archive_directory=None, previous_archive_directory=None):
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
        self.dispatcher = None
        self.dependencies = None
        if jobs is None:
            from .composition import dispatch_dependencies
            self.dependencies = dispatch_dependencies(root)
        self.events = EventHub(self.nonce)
        self.observations = WebObservations()
        self.source_startup = None
        archive = None
        archive_upgrade = None
        usage = None
        if live_factory is None and jobs is None:
            from .source_startup import SourceStartup
            directory = root / 'cache' if store or previous_archive_directory is not None else archive_directory
            archive = WebArchive(directory) if directory is not None else None
            previous = store.directory if store else previous_archive_directory
            if previous is not None:
                archive_upgrade = root, previous / WEB_ARCHIVE_FILENAME
            usage = ArchivedUsage(archive) if archive is not None else None
            self.source_startup = SourceStartup(root, self.events.publish, self.stopping)
            live_factory = self.source_startup.acquire
        if jobs is None:
            self.dispatcher = (DataDispatcher(self.jobs, owner_kinds=(ReportKind.NORMAL,))
                               if usage else DataDispatcher(self.jobs))
        self.history_reports = HistoryReports(usage, self.dependencies.prices) if usage else None
        self.history_accounts = AccountTimeline(None, None, archived_usage=usage) if usage else None
        self.watch_history = WatchHistory(usage, self.dependencies.prices, self.events.publish) if usage else None
        self.history_config = {}
        if usage:
            try:
                self.history_config = load_configuration(root).values
            except ConfigError:
                # Broken or unavailable source settings must not prevent host
                # authorization, lifecycle cleanup, or reading local history.
                pass
        self.history_zone = str(self.history_config.get('timezone') or ('Europe/Stockholm' if archive else 'UTC'))
        self.live = LiveRuntime(live_factory, self.events.publish, self.runtime_failed,
             timeline_demand=self.dispatcher.account_timeline_foreground if self.dispatcher and not usage else None,
             archive=archive, legacy_archive=root / 'cache' / 'cost-guard-display-v1.sqlite3' if archive else None,
             archive_upgrade=archive_upgrade,
             timezone_id=self.history_zone) if live_factory else None
        self.server = None
        self.thread = None
        self.cache_housekeeping = CacheHousekeeping(root)
        self.log_housekeeping = LogHousekeeping(root)
        from .benchmark import BenchmarkLane
        self.benchmark = BenchmarkLane(root)

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

    def database_sizes(self):
        driver = getattr(self.live, 'driver', None)
        selection = driver.coordinator.report_service.selection if driver else None
        archive = self.history_reports.archive if self.history_reports else None
        return database_sizes(selection, self.cache_housekeeping.lifecycle.database.paths.database, archive=archive)

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
            self.log_housekeeping.start()

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
                self.benchmark.tick()
                if self.dependencies and self.live and self.live.observed.is_set():
                    baseline = self.live.driver.coordinator.report_service.config
                    if not self.dependencies.check(self.dispatcher, baseline=baseline):
                        self.stop('source_changed')
                if not self.stopping.is_set():
                    if self.history_reports:
                        self.live.catalog.archive_maintenance()
                        self.events.publish('history', dict(catalog_hint=self.live.catalog.live_hint(),
                                            detail_hints=self.live.details.archive_hints()))
                        driver = self.live.driver
                        selection = driver.coordinator.report_service.selection if driver else None
                        self.history_reports.tick(selection=selection,
                            config=self.history_config, catalog=self.live.catalog,
                            ready=bool(driver and driver.error is None and self.live.observed.is_set()),
                            price_signature=self.dependencies.reference_signature,
                            foreground=self.dispatcher.history_foreground())
                        self._tick_history_accounts(selection)
                        self.watch_history.tick(self.live.catalog, self.history_zone,
                            self.history_config.get('ccostDisplayUnit', 'credits'), int(time.time() * 1000))
                    if self.source_startup is None or self.source_startup.finished.is_set():
                        if self.dispatcher:
                            driver = self.live.driver if self.live else None
                            selection = driver.coordinator.report_service.selection if driver else None
                            identity = source_identity(selection) if selection else ''
                            if not self.history_reports and identity and self._source_identity and identity != self._source_identity:
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
                        self.cache_housekeeping.tick(self)
                    progress = self.jobs.updates() if hasattr(self.jobs, "updates") else self.jobs.readiness()
                    self.events.publish("progress", progress)
                    if self.history_reports:
                        caught_up = self._history_idle(progress.get('jobs', ()))
                        if caught_up:
                            self.live.caught_up_web.set()
                        else:
                            self.live.caught_up_web.clear()
                        self.server.timeout = 0.5 if caught_up else 0.05
        except BaseException as error:
            self.runtime_failed(error)
        finally:
            self.stopping.set()
            try:
                try:
                    try:
                        self.benchmark.close()
                    finally:
                        self.jobs.close()
                finally:
                    try:
                        try:
                            if self.live:
                                self.live.close()
                        finally:
                            self._close_history()
                    finally:
                        self.events.close(self.reason or "runtime_fault")
                        self.server.server_close()
            except BaseException as error:
                self.runtime_failed(error)
            finally:
                self.stopped.set()  # GUI must observe this even on cleanup failure.

    def start(self):
        self.cache_housekeeping.start()
        self.server = LoopbackServer(self.jobs, self)
        if self.live:
            self.live.start()
        self.thread = Thread(target=self._serve, name="cost-guard-web")
        self.thread.start()

    def close(self):
        self.stop()
        self.log_housekeeping.close()
        if self.thread:
            self.thread.join(timeout=10)
            if self.thread.is_alive():
                raise RuntimeError("web_shutdown_timeout")
        try:
            # The serving thread's bounded attempt may have retained a child
            # whose exit was not yet confirmed. Main remains its cleanup owner.
            self.jobs.close()
            self.benchmark.close()
        except BaseException as error:
            self.runtime_failed(error)
            raise
        finally:
            try:
                if not self.thread and self.live:
                    self.live.close()
                if not self.thread:
                    self._close_history()
            finally:
                # Preserve actual use queued since the last host-loop flush. The
                # finite drain fails soft on contention; never acquire source here.
                self.cache_housekeeping.lifecycle.flush_pending()
                if self.store:
                    self.observations.persist(self, final=True)
                    self.store.remove(self.nonce)
                    self.store.log(self.reason if self.reason in {"source_changed", "runtime_fault"} else "stopped")

    def _close_history(self):
        try:
            if self.history_reports:
                self.history_reports.close()
        finally:
            try:
                if self.history_accounts:
                    self.history_accounts.close()
            finally:
                if self.watch_history:
                    self.watch_history.close()

    def _tick_history_accounts(self, selection):
        accounts, source, observation, captured_at = self.live.account_observation
        available = captured_at is not None and self.live.driver.error is None
        catalog = self.live.catalog
        with catalog.lock:
            covered = (available and observation is not None and observation is catalog.last_observation
                       and catalog.state == 'observed')
            unavailable = catalog.unavailable_history()
            live_roots = frozenset(catalog.history_live_roots())
            progress_roots = frozenset(catalog.history_progress_live_roots()), frozenset(catalog.history_refresh_roots())
            pending = frozenset(catalog.history_pending)
        self.history_accounts.tick(source=source, observation=observation if available else None,
            accounts=accounts if available else (), periods=frozenset(PERIODS),
            zone=self.history_zone,
            catalog=None, prices=self.dependencies.prices, migration_gap=selection.migration_gap if selection else None,
            now_ms=int(time.time() * 1000), available=available, terminal=not available,
            foreground=self.dispatcher.account_timeline_foreground(),
            unavailable_history=unavailable, live_roots=live_roots, pending_history=pending,
            coverage_confirmed=covered, progress_roots=progress_roots)

    def _history_idle(self, jobs):
        driver = self.live.driver
        if not self.live.observed.is_set() or driver is None or driver.error or driver.frame is None or driver.frame.active_count:
            return False
        if (self.history_reports.job is not None or len(self.history_reports.published_keys) < 5
                or self.history_accounts.job is not None or self.history_accounts.initial_periods
                or len(self.history_accounts.results) < len(PERIODS) or self.watch_history.job is not None):
            return False
        coordinator = driver.coordinator
        if coordinator.daily_usage is None or coordinator.history_job is not None or coordinator.detail_job is not None:
            return False
        if any(item['status'] in {'queued', 'running'} for item in jobs):
            return False
        catalog = self.live.catalog
        with catalog.lock:
            return (catalog.archive.loaded and catalog.legacy_done and not catalog.history_pending
                    and not catalog.history_live_roots())

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
