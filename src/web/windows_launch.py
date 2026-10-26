"""Windows Beta launch preflight and sanitized, actionable terminal results."""
from src.config import load_configuration, ConfigError
from .instance_state import InstanceStore
from .lifecycle import launch
from .process_identity import InstanceConflict

MESSAGES = {
    "tray_unavailable": "Windows notification-area API is unavailable. Check Explorer and retry.",
    "instance_start_timeout": "Web startup timed out. Run Diagnostics and retry.",
    "gui_or_server_start_failed": "Web host failed to start. Run Diagnostics.",
    "configuration_unavailable": "Check config/user-config.jsonc, then retry.",
    "instance_conflict": "Existing Web instance could not be verified. Do not delete its state; run Diagnostics.",
    "browser_open_failed": "Web is running. Browser could not open; use tray Open Cost Guard to retry.",
}


def launch_windows(root):
    store = None
    try:
        store = InstanceStore(root)
        load_configuration(root)
        from .native_windows import open_registered_browser, preflight
        preflight()
        result = launch(root, "src.web.native_windows", opener=open_registered_browser)
        if not result.browser_opened:
            store.log("browser_open_failed")
            print("Cost Guard Web Beta: " + MESSAGES["browser_open_failed"])
            return 4
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
    return 1
