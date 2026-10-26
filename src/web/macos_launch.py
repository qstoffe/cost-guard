"""macOS-only preflight, optional local Finder wrapper and shared Web lifecycle."""
from pathlib import Path
import subprocess
import sys

from src.config import ConfigError, load_configuration
from .instance_state import InstanceStore
from .lifecycle import launch
from .macos_app import prepare_app
from .process_identity import InstanceConflict

MESSAGES = {
    "tray_unavailable": "The native macOS menu could not start. Use a logged-in desktop and retry; CLI remains available.",
    "instance_start_timeout": "Web startup timed out. Run Diagnostics and retry.",
    "gui_or_server_start_failed": "Web host failed to start. Run Diagnostics; CLI remains available.",
    "configuration_unavailable": "Check config/user-config.jsonc, then retry.",
    "instance_conflict": "Existing Web instance could not be verified/stopped. Do not delete its state; run Diagnostics.",
    "browser_open_failed": "Web is running. Use menu-bar Open Cost Guard to retry the default browser.",
}


def native_preflight(root):
    # Contain a native ABI/Objective-C crash or stalled WindowServer before restart.
    try:
        result = subprocess.run([sys.executable, str(Path(root) / "cost-guard-web.py"),
                                 "--preflight-macos"], stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise InstanceConflict("tray_unavailable") from None
    if result.returncode:
        raise InstanceConflict("tray_unavailable")


def launch_macos(root):
    if sys.platform != "darwin" or sys.version_info < (3, 11):
        print("Cost Guard Web Beta requires macOS and already-installed Python 3.11+.")
        return 1
    store = None
    try:
        store = InstanceStore(root)
        load_configuration(root)
        native_preflight(root)
        # Finder wrapper failure must not disable the direct .command fallback.
        try:
            app = prepare_app(root, store)
            print(f"Cost Guard: Optional Finder app (native validation pending): {app}", flush=True)
        except (InstanceConflict, OSError, ValueError):
            store.log("app_preparation_failed")
            print("Cost Guard: Finder app preparation failed. Check /usr/bin/osacompile and "
                  "private app-data permissions; continuing with .command. No tools installed.", flush=True)
        from .native_macos import open_registered_browser
        result = launch(root, "src.web.native_macos", opener=open_registered_browser)
        if not result.browser_opened:
            store.log("browser_open_failed")
            print("Cost Guard Web Beta: " + MESSAGES["browser_open_failed"])
            return 4
        print("Cost Guard Web Beta: Running; use the CG menu to Open or Exit.")
        return 0
    except ConfigError:
        code = "configuration_unavailable"
    except InstanceConflict as error:
        code = str(error) if str(error) in MESSAGES else "instance_conflict"
    except Exception:
        code = "gui_or_server_start_failed"
    if store:
        store.log(code)
    print("Cost Guard Web Beta: " + MESSAGES[code])
    print("Diagnostics: development/user-tools/diagnostics/macos/Cost Guard Diagnostics.command")
    return 1
