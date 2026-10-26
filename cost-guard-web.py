#!/usr/bin/env python3
"""Optional Web entry; preserve the CLI's independent startup/import graph."""
from pathlib import Path
import sys


def start():
    from src.web.main import main
    return main()


def run():
    from src.runtime_errors import RuntimeErrors
    return RuntimeErrors(Path(__file__).resolve().parent, mode="Web Beta").run(start)


if __name__ == "__main__":
    sys.exit(run())
