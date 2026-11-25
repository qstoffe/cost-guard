"""Deterministic startup work/time principles and terminal ownership handoff."""
import unittest

from src.domain.progress import WorkProgress


class WorkProgressMetadataTests(unittest.TestCase):
    def test_web_stage_does_not_change_cli_string_or_phase_counts(self):
        value = WorkProgress("Analyzing sessions", "history", 3, 8, stage="account-analysis")
        self.assertEqual("Analyzing sessions", str(value))
        self.assertEqual(("history", 3, 8), (value.phase, value.completed, value.total))


if __name__ == "__main__":
    unittest.main()
