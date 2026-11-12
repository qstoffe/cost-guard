"""Windows launch preflight and sanitized, actionable terminal results."""
from src.config import load_configuration, ConfigError
from .instance_state import InstanceStore
from .lifecycle import launch
from .launch_messages import messages, print_failure
from .process_identity import InstanceConflict
from .startup import StartupProgress

MESSAGES = messages('windows')


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
            print_failure("browser_open_failed", 'windows')
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
    print_failure(code, 'windows')
    return 1
