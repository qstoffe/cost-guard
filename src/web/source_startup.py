"""One host-lifetime source wake, executed on Live's worker, never HTTP callers."""
from threading import Event, Lock

from src.config import load_configuration
from src.opencode_service import wake_cli_service
from src.sources.discovery import find_opencode_executable
from src.sources.errors import FailureCode, SourceError, SourceUnavailableError
from src.sources.read_recovery import ReadRecovery
from src.sources.selection import SourceSelector

WAKE_TIMEOUT_SECONDS = 5
WAKE_CODES = frozenset({FailureCode.REGISTRATION_MISSING, FailureCode.REFUSED,
    FailureCode.RESET, FailureCode.DISCONNECTED, FailureCode.TIMEOUT,
    FailureCode.ENDPOINT_UNRESPONSIVE})


class SourceStartup:
    def __init__(self, root, publish, stopping):
        self.root = root
        self.publish = publish
        self.stopping = stopping
        self.finished = Event()
        self._lock = Lock()
        self._report_status = {"ready": False, "error": "source_starting", "retryable": True}

    def report_status(self):
        """Detached admission proof; HTTP never selects/wakes the source."""
        return dict(self._report_status)

    def _selected(self, selection):
        self._report_status = {"ready": True, "error": None, "retryable": False}
        return selection

    def _unavailable(self, error):
        permission = error.exception_type == "PermissionError"
        self._report_status = {"ready": False,
            "error": "source_permission_denied" if permission else error.code.value,
            "retryable": error.readiness_retryable and not permission}

    def prepare(self):
        """Coalesce entry paths; later recovery performs ordinary selection only."""
        with self._lock:
            if self.finished.is_set():
                return None
            waking = False
            try:
                config = load_configuration(self.root).values
                requested = str(config["openCode"]["source"])
                selector = SourceSelector(inspect_migration_gap=False)
                try:
                    return self._selected(selector.select(requested))
                except SourceUnavailableError as error:
                    if (requested not in {"auto", "v2"} or error.generation != "v2"
                            or error.code not in WAKE_CODES
                            or error.exception_type == "PermissionError"
                            or self.stopping.is_set()):
                        raise
                    executable = find_opencode_executable()
                    if executable is None:
                        raise
                    waking = True
                    self.publish("live", {"state": "starting_opencode", "view": None})
                    try:
                        wake_cli_service(executable, timeout=WAKE_TIMEOUT_SECONDS)
                    except SourceUnavailableError:
                        # A timed-out/failed CLI may nevertheless have woken the
                        # service. Only fresh registration/API proof can decide.
                        pass

                    def wait(seconds):
                        if self.stopping.wait(seconds):
                            raise error

                    return self._selected(ReadRecovery(sleep=wait).run(
                        lambda: selector.select(requested), initial_error=error))
            except SourceError as error:
                self._unavailable(error)
                raise
            except Exception:
                self._report_status = {"ready": False, "error": "report_unavailable", "retryable": False}
                raise
            finally:
                if waking:
                    self.publish("live", {"state": "starting", "view": None})
                self.finished.set()

    def acquire(self):
        from .composition import live_acquisition

        try:
            selection = self.prepare()
            driver = live_acquisition(selection=selection)
            self._selected(None)
            return driver
        except SourceError as error:
            self._unavailable(error)
            raise
