#!/usr/bin/env python3
"""Stable executable entry point for Cost Guard."""
import sys

if sys.version_info < (3, 11):
    print("Cost Guard requires Python 3.11 or newer.", file=sys.stderr)
    raise SystemExit(1)

from src.bootstrap import main

if __name__ == "__main__":
    raise SystemExit(main())
