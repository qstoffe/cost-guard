"""macOS-only preflight, optional local Finder wrapper and shared Web lifecycle."""
from pathlib import Path
import subprocess
import sys

from src.config import ConfigError, load_configuration
from .instance_state import InstanceStore
from .lifecycle import launch
from .launch_messages import messages, print_failure
from .macos_app import prepare_app
from .process_identity import InstanceConflict
from .startup import StartupProgress

MESSAGES = messages('macos')


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
        print("Cost Guard requires macOS and already-installed Python 3.11+. Legacy CLI: python cost-guard-cli.py")
        return 1
    store = None
    progress = StartupProgress()
    try:
        progress("config")
        store = InstanceStore(root)
        load_configuration(root)
        progress("preflight")
        native_preflight(root)
        # Finder wrapper failure must not disable the direct .command fallback.
        try:
            progress("helper")
            app = prepare_app(root, store)
            print(f"Cost Guard: Optional Finder app (native validation pending): {app}", flush=True)
        except (InstanceConflict, OSError, ValueError):
            store.log("app_preparation_failed")
            print("Cost Guard: Finder app preparation failed. Check /usr/bin/osacompile and "
                  "private app-data permissions; continuing with .command. No tools installed.", flush=True)
        from .native_macos import open_registered_browser
        result = launch(root, "src.web.native_macos", opener=open_registered_browser, progress=progress)
        if not result.browser_opened:
            store.log("browser_open_failed")
            print_failure("browser_open_failed", 'macos')
            return 4
        progress("handoff")
        print("Cost Guard: Running; use the CG menu to Open or Exit.")
        return 0
    except ConfigError:
        code = "configuration_unavailable"
    except InstanceConflict as error:
        code = str(error) if str(error) in MESSAGES else "instance_conflict"
    except Exception:
        code = "gui_or_server_start_failed"
    if store:
        try:
            store.log(code)
        except (OSError, InstanceConflict):
            print("Cost Guard: Private startup diagnostic could not be recorded.")
    print_failure(code, 'macos')
    return 1
