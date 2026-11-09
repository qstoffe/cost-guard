"""Windows launch preflight and sanitized, actionable terminal results."""
from src.config import load_configuration, ConfigError
from .instance_state import InstanceStore
from .lifecycle import launch
from .process_identity import InstanceConflict
from .startup import StartupProgress

MESSAGES = {
    "tray_unavailable": "Windows notification-area API is unavailable. Check Explorer and retry.",
    "instance_start_timeout": "Web startup timed out. Run Diagnostics and retry.",
    "gui_or_server_start_failed": "Web host failed to start. Run Diagnostics.",
    "configuration_unavailable": "Check config/user-config.jsonc, then retry.",
    "instance_conflict": "Web ownership could not be verified. Preserve its state and run Diagnostics.",
    "process_identity_access_denied": "Windows denied process identity access; Web ownership is unresolved. Preserve state and run Diagnostics.",
    "process_identity_unavailable": "Native process identity is unavailable; Web ownership is unresolved. Preserve state and run Diagnostics.",
    "process_identity_changed": "Process identity changed during Web shutdown. Preserve state and retry; run Diagnostics if repeated.",
    "instance_lifetime_busy": "Web lifetime coordination is busy. Preserve state and retry; run Diagnostics if repeated.",
    "instance_lifetime_unavailable": "Web lifetime coordination could not be checked. Preserve state and run Diagnostics.",
    "instance_transition_busy": "Another Web launch transition is busy. Wait and retry; run Diagnostics if repeated.",
    "instance_transition_unavailable": "Web launch coordination is unavailable. Preserve state and run Diagnostics.",
    "corrupt_instance_state": "Web state is invalid. Do not delete it; run Diagnostics.",
    "unsafe_instance_path": "Web state path is unsafe. Do not change permissions; run Diagnostics.",
    "foreign_instance_path": "Web state ownership is unsafe. Do not change permissions; run Diagnostics.",
    "private_state_unavailable": "Private Web state is unavailable. Do not change permissions; run Diagnostics.",
    "instance_state_changed": "Web state changed during inspection. Preserve state and retry; run Diagnostics if repeated.",
    "instance_control_conflict": "Web control identity could not be verified. Preserve state and run Diagnostics.",
    "instance_control_unavailable": "Web control did not respond. Preserve state and run Diagnostics.",
    "instance_not_ready": "Web readiness could not be verified. Preserve state and run Diagnostics.",
    "instance_start_conflict": "New Web host identity could not be verified. Run Diagnostics.",
    "instance_stop_timeout": "Verified Web host did not stop in time. Preserve state and run Diagnostics.",
    "process_stop_unavailable": "Verified Web host could not be stopped safely. Preserve state and run Diagnostics.",
    "safe_force_stop_unavailable": "Safe Web host termination is unavailable. Preserve state and run Diagnostics.",
    "browser_open_failed": "Web is running. Browser could not open; use tray Open Cost Guard to retry.",
}


def launch_windows(root):
    store = None
    progress = StartupProgress()
    try:
        progress("config")
        store = InstanceStore(root)
        load_configuration(root)
        from .native_windows import open_registered_browser, preflight
        progress("preflight")
        preflight()
        result = launch(root, "src.web.native_windows", opener=open_registered_browser, progress=progress)
        if not result.browser_opened:
            store.log("browser_open_failed")
            print("Cost Guard: " + MESSAGES["browser_open_failed"])
            return 4
        progress("handoff")
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
    print("Cost Guard: " + MESSAGES[code])
    print("Legacy CLI: windows/Legacy/Cost-Guard.cmd or python cost-guard-cli.py")
    return 1
