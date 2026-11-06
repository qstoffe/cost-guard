"""Shared finite progress and bounded waiting; no real source/model calls."""
from pathlib import Path
import shutil
import subprocess
import unittest


class WebLoadingTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'optional JS VM unavailable')
    def test_navigation_preserves_pending_and_admitted_report_intent(self):
        result = subprocess.run(['node', 'development/tests/integration/web_report_lifetime.cjs'],
            cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=10)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'optional JS VM unavailable')
    def test_observed_progress_and_cancelable_bounded_admission(self):
        result = subprocess.run(['node', 'development/tests/integration/web_report_loading.cjs'],
            cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=10)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'optional JS VM unavailable')
    def test_ai_stats_scope_progress_and_serialized_priority(self):
        result = subprocess.run(['node', 'development/tests/integration/ai_stats_progress.cjs'],
            cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=10)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
