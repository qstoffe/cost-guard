"""Same-process Windows tray adapter; no second server or GUI process manager."""
import os
from queue import Empty, Queue
from threading import Thread

from .win32_tray import EXIT, OPEN, Tray


def open_registered_browser(url):
    # Use the Windows URL association, not a BROWSER environment command override.
    os.startfile(url)
    return True


class WindowsHost:
    def __init__(self, tray=None):
        self.tray = tray if tray is not None else Tray()
        self.open_thread = None
        self.results = Queue(maxsize=1)

    def _open(self, owner):
        # Browser shell handoff can block; never perform it in a menu callback.
        try:
            self.results.put(owner.open_browser(opener=open_registered_browser))
        except BaseException as error:
            owner.failure = error
            owner.stop("runtime_fault")

    def dispatch(self, owner, events):
        if EXIT in events:
            owner.stop("menu")
            return
        if OPEN in events and not owner.stopping.is_set():
            if self.open_thread is None or not self.open_thread.is_alive():
                self.open_thread = Thread(target=self._open, args=(owner,), daemon=True,
                                          name="cost-guard-browser")
                self.open_thread.start()

    def run(self, owner):
        self.tray.install()
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
            owner.stopping.wait(0.05)

    def close(self):
        self.tray.close()


def preflight():
    """Exercise native resources before the lifecycle may stop a healthy instance."""
    tray = Tray()
    try:
        tray.install()
        tray.poll()
    finally:
        tray.close()


def create_host():
    return WindowsHost()
