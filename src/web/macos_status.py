"""Main-thread NSStatusItem and bounded Cocoa event pump; no helper process."""
from queue import Empty, SimpleQueue

from .objc_bridge import BOOL, DOUBLE, INTEGER, MASK, PTR, ObjC, require_main_thread
from .process_identity import InstanceConflict


class StatusItem:
    def __init__(self, api=None):
        self.api = api
        self.pool = self.app = self.bar = self.item = self.menu = self.target = None
        self.timer = self.owner = None
        self.failure = None
        self.events = SimpleQueue()

    def watch(self, owner):
        self.owner = owner

    def _failed(self, error):
        self.failure = error
        if self.owner:
            self.owner.failure = error
            self.owner.stop("runtime_fault")

    def _tick(self):
        # Cocoa menu tracking is nested. A timer in tracking mode dismisses an open
        # menu on host loss, allowing the outer pump to remove the status item.
        if self.owner and (self.owner.stopping.is_set() or self.owner.stopped.is_set()):
            self.api.send(self.menu, "cancelTracking", None)

    def install(self):
        require_main_thread()
        if self.item:
            raise InstanceConflict("tray_unavailable")
        self.api = self.api or ObjC()
        api = self.api
        self.pool = api.send(api.send(api.cls("NSAutoreleasePool"), "alloc"), "init")
        self.app = api.send(api.cls("NSApplication"), "sharedApplication")
        if not self.app or not api.send(self.app, "setActivationPolicy:", BOOL, (INTEGER, 1)):
            raise InstanceConflict("tray_unavailable")
        api.send(self.app, "finishLaunching", None)
        self.target = api.target(self.events.put, self._tick, self._failed)
        self.menu = api.send(api.send(api.cls("NSMenu"), "alloc"), "initWithTitle:", PTR,
                             (PTR, api.string("Cost Guard")))
        if not self.target or not self.menu:
            raise InstanceConflict("tray_unavailable")
        for title, selector in (("Open Cost Guard", "openCostGuard:"),
                                ("Exit Cost Guard", "exitCostGuard:")):
            item = api.send(api.send(api.cls("NSMenuItem"), "alloc"),
                            "initWithTitle:action:keyEquivalent:", PTR,
                            (PTR, api.string(title)), (PTR, api.selector(selector)),
                            (PTR, api.string("")))
            if not item:
                raise InstanceConflict("tray_unavailable")
            try:
                api.send(item, "setTarget:", None, (PTR, self.target))
                api.send(self.menu, "addItem:", None, (PTR, item))
            finally:
                api.send(item, "release", None)
        self.bar = api.send(api.cls("NSStatusBar"), "systemStatusBar")
        self.item = api.send(self.bar, "statusItemWithLength:", PTR, (DOUBLE, -1.0))
        if not self.item:
            raise InstanceConflict("tray_unavailable")
        api.send(self.item, "retain")
        button = api.send(self.item, "button")
        if not button:
            raise InstanceConflict("tray_unavailable")
        api.send(button, "setTitle:", None, (PTR, api.string("CG")))
        api.send(button, "setToolTip:", None, (PTR, api.string("Cost Guard Web Beta")))
        api.send(self.item, "setMenu:", None, (PTR, self.menu))
        self.timer = api.send(api.cls("NSTimer"), "timerWithTimeInterval:target:selector:userInfo:repeats:",
                              PTR, (DOUBLE, 0.1), (PTR, self.target),
                              (PTR, api.selector("pollOwner:")), (PTR, None), (BOOL, True))
        if not self.timer:
            raise InstanceConflict("tray_unavailable")
        api.send(self.timer, "retain")
        loop = api.send(api.cls("NSRunLoop"), "mainRunLoop")
        for mode in ("NSDefaultRunLoopMode", "NSEventTrackingRunLoopMode"):
            api.send(loop, "addTimer:forMode:", None, (PTR, self.timer), (PTR, api.string(mode)))

    def poll(self):
        require_main_thread()
        api = self.api
        pool = api.send(api.send(api.cls("NSAutoreleasePool"), "alloc"), "init")
        try:
            # One finite wait, then return to the shared stop owner. Cocoa itself
            # dispatches menu tracking/callbacks; no blocking analysis is done here.
            until = api.send(api.cls("NSDate"), "dateWithTimeIntervalSinceNow:", PTR, (DOUBLE, 0.05))
            event = api.send(self.app, "nextEventMatchingMask:untilDate:inMode:dequeue:", PTR,
                             (MASK, 0xffffffffffffffff), (PTR, until),
                             (PTR, api.string("NSDefaultRunLoopMode")), (BOOL, True))
            if event:
                api.send(self.app, "sendEvent:", None, (PTR, event))
            api.send(self.app, "updateWindows", None)
            if self.failure:
                raise self.failure
            events = []
            while True:
                try:
                    events.append(self.events.get_nowait())
                except Empty:
                    return events
        finally:
            api.send(pool, "drain", None)

    def browser_failed(self):
        # Nonmodal truthful feedback: menu stays usable, no Automation permission.
        button = self.api.send(self.item, "button")
        self.api.send(button, "setToolTip:", None,
                      (PTR, self.api.string("Browser could not open; use Open Cost Guard to retry.")))

    def close(self):
        require_main_thread()
        if self.timer:
            self.api.send(self.timer, "invalidate", None)
            self.api.send(self.timer, "release", None)
            self.timer = None
        if self.item:
            self.api.send(self.bar, "removeStatusItem:", None, (PTR, self.item))
            self.api.send(self.item, "release", None)
            self.item = None
        for name in ("menu", "target"):
            value = getattr(self, name)
            if value:
                self.api.send(value, "release", None)
                setattr(self, name, None)
        if self.pool:
            self.api.send(self.pool, "drain", None)
            self.pool = None
        self.owner = None
