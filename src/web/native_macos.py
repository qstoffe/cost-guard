"""macOS native adapter; AppKit on main thread, bounded browser handoff off it."""
from queue import Empty, Queue
import subprocess
from threading import Thread

from .macos_status import StatusItem
from .objc_bridge import require_main_thread


def open_registered_browser(url):
    # The system association, not $BROWSER or a shell command; URL is one argument.
    return subprocess.run(["/usr/bin/open", url], stdin=subprocess.DEVNULL,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                          timeout=5, check=False).returncode == 0


class MacHost:
    def __init__(self, tray=None):
        self.tray = tray if tray is not None else StatusItem()
        self.open_thread = None
        self.results = Queue(maxsize=1)

    def _open(self, owner):
        try:
            self.results.put(owner.open_browser(opener=open_registered_browser))
        except BaseException as error:
            owner.failure = error
            owner.stop("runtime_fault")

    def dispatch(self, owner, events):
        if "exit" in events:
            owner.stop("menu")
        elif "open" in events and not owner.stopping.is_set():
            if self.open_thread is None or not self.open_thread.is_alive():
                self.open_thread = Thread(target=self._open, args=(owner,), daemon=True,
                                          name="cost-guard-browser")
                self.open_thread.start()

    def run(self, owner):
        require_main_thread()
        self.tray.watch(owner)
        self.tray.install()
        events = self.tray.poll()  # Exercise the native pump before advertising readiness.
        self.dispatch(owner, events)
        if not owner.stopping.is_set() and not owner.stopped.is_set():
            owner.publish_ready()
        while not owner.stopping.is_set() and not owner.stopped.is_set():
            self.dispatch(owner, self.tray.poll())
            try:
                if not self.results.get_nowait():
                    self.tray.browser_failed()
                    if owner.store:
                        owner.store.log("browser_open_failed")
            except Empty:
                pass

    def close(self):
        self.tray.close()
        if self.open_thread:
            self.open_thread.join(timeout=6)  # /usr/bin/open has its own five-second deadline.


def preflight():
    tray = StatusItem()
    try:
        tray.install()
        tray.poll()
    finally:
        tray.close()


def create_host():
    return MacHost()
