"""Offline synthetic report/Live replay input; no source access or inference."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from development.tests.fixtures.default_effort import capture


if __name__ == "__main__":
    test = unittest.TestCase()
    try:
        value = capture(test)
        Path(sys.argv[1]).write_text(json.dumps(value, indent=2), encoding="utf-8")
        print(json.dumps({"rows": len(value["browser_rows"]), "views": list(value["synthetic_views"])}))
    finally:
        test.doCleanups()
