"""Shared help interaction regression without a browser/package dependency."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


class WebHelpTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node is optional VM tooling")
    def test_shared_help_handles_focus_pointer_escape_touch_updates_and_documents(self):
        result = subprocess.run(
            [shutil.which("node"), "development/tests/integration/web_help.cjs"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=15,
        )

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
