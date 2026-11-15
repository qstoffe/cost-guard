#!/usr/bin/env python3
"""Managed Web runtime and explicit foreground developer entry."""
from pathlib import Path
import sys

if sys.version_info < (3, 11):
    print("Cost Guard requires Python 3.11 or newer.", file=sys.stderr)
    raise SystemExit(1)

ROOT = Path(__file__).resolve().parents[2]
if __package__ in {None, ""}:
    sys.path.insert(0, str(ROOT))


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
    return RuntimeErrors(ROOT, mode="Web").run(start)


if __name__ == "__main__":
    sys.exit(run())
