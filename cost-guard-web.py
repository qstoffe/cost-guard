#!/usr/bin/env python3
"""Optional Web entry; preserve the CLI's independent startup/import graph."""
from pathlib import Path
import sys


def start():
    from src.web.main import main
    return main()


def run():
    if sys.argv[1:2] == ["--managed"]:
        # Managed diagnostics are bounded/allowlisted in private app data, not checkout.
        try:
            return start()
        except Exception:
            return 1
    from src.runtime_errors import RuntimeErrors
    return RuntimeErrors(Path(__file__).resolve().parent, mode="Web Beta").run(start)


if __name__ == "__main__":
    sys.exit(run())
