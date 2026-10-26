"""Opt-in real AppKit ABI/callback/HTTP-owner smoke; never part of Quick/Full.

Requires current approval for native UI. It shows/removes a menu item but does not
open a browser, change source, call a model/provider or touch a managed instance.
Finder/Gatekeeper/Terminal behavior remains a separate manual acceptance check.
"""
import argparse
import ctypes
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def probe():
    from src.web.host import WebHost
    from src.web.macos_status import StatusItem
    from src.web.native_macos import MacHost
    from src.web.objc_bridge import BOOL, INTEGER, PTR

    class ProbeItem(StatusItem):
        def __init__(self):
            super().__init__()
            self.polls = 0
            self.labels = []
            self.failed_browser = False

        def install(self):
            super().install()
            count = self.api.send(self.menu, "numberOfItems", INTEGER)
            for index in range(count):
                item = self.api.send(self.menu, "itemAtIndex:", PTR, (INTEGER, index))
                title = self.api.send(item, "title")
                self.labels.append(self.api.send(title, "UTF8String", ctypes.c_char_p).decode("utf-8"))
            assert self.labels == ["Open Cost Guard", "Exit Cost Guard"]

        def poll(self):
            self.polls += 1
            if self.polls == 2 or self.failed_browser:
                selector = "exitCostGuard:" if self.failed_browser else "openCostGuard:"
                delivered = self.api.send(self.app, "sendAction:to:from:", BOOL,
                                          (PTR, self.api.selector(selector)),
                                          (PTR, self.target), (PTR, self.item))
                assert delivered
            if self.polls > 100:
                raise RuntimeError("native_callback_timeout")
            return super().poll()

        def browser_failed(self):
            self.failed_browser = True
            super().browser_failed()

    tray = ProbeItem()
    adapter = MacHost(tray)
    owner = WebHost(ROOT)
    with patch.object(owner, "open_browser", return_value=False) as browser:
        owner.run_gui(adapter)
        assert owner.ready and owner.reason == "menu" and owner.stopped.is_set()
        assert tray.failed_browser and tray.item is None and tray.timer is None
        assert browser.call_count == 1
        assert not owner.thread.is_alive()
        assert adapter.open_thread is not None and not adapter.open_thread.is_alive()
    return {"native_macos_execution": True,
            "checks": ["AppKit typed ABI", "menu labels and Objective-C Open/Exit callbacks",
                       "HTTP owner readiness/shutdown", "browser-failure menu retention", "native cleanup"],
            "not_checked": ["Finder", "Gatekeeper/quarantine", "physical double click", "Terminal lifetime",
                            "system browser", "fresh clone/ZIP", "offline launch", "both CPU architectures"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-native-ui", action="store_true")
    args = parser.parse_args()
    if sys.platform != "darwin" or not args.allow_native_ui:
        parser.error("requires macOS and explicit --allow-native-ui approval")
    print(json.dumps(probe(), sort_keys=True))


if __name__ == "__main__":
    main()
