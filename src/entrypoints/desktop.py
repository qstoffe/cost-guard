#!/usr/bin/env python3
"""Stable executable entry point for Cost Guard."""
import sys

if sys.version_info < (3, 11):
    print("Cost Guard requires Python 3.11 or newer.", file=sys.stderr)
    raise SystemExit(1)

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if __package__ in {None, ""}:
    sys.path.insert(0, str(ROOT))

def run(application=None):
    """Import initialization is inside the guard; intended exit is outside it."""
    try:
        from pathlib import Path
        from src.runtime_errors import RuntimeErrors
        errors = RuntimeErrors(ROOT)
        def start():
            if application is not None:
                return application()
            from src.product_entry import main
            return main()
        return errors.run(start, preserve_hooks=True)
    except KeyboardInterrupt:
        return 130
    except BaseException as exc:
        # Even a broken minimal boundary cannot expose an unowned traceback.
        try:
            sys.stderr.write(f"COST GUARD FAILED\nUnhandled {type(exc).__name__}\n"
                             "Crash report could not be written: runtime boundary unavailable\n")
            launcher = {"win32": "development/user-tools/diagnostics/windows/Cost-Guard-Diagnostics.cmd",
                        "darwin": "development/user-tools/diagnostics/macos/Cost-Guard-Diagnostics.command"}.get(
                sys.platform, "development/tools/collect_diagnostics.py")
            sys.stderr.write("\nNeed help? Run Cost Guard Diagnostics:\n"
                             + str(ROOT / launcher) + "\n")
        except BaseException:
            pass
        return 1

if __name__ == "__main__":
    raise SystemExit(run())
