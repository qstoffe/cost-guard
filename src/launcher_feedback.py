"""Consume the launcher's single transient row only when Python can replace it."""
import os
import sys


def release_launcher_status() -> None:
    if os.environ.pop("COST_GUARD_LAUNCHER_STATUS", "") != "1":
        return
    if sys.stdout.isatty():
        # No ANSI dependency, and no control characters in redirected output.
        sys.stdout.write("\r" + " " * 40 + "\r")
        sys.stdout.flush()
