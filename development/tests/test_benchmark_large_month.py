"""The developer benchmark follows bounded Normal sampling, not all roots."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import unittest
from unittest.mock import patch

from development.tools.benchmark_large_month import main


class LargeMonthBenchmarkTests(unittest.TestCase):
    def test_warm_hydrations_follow_sampled_running_roots(self):
        for running_roots, expected_running in ((0, 0), (1, 0), (4, 2)):
            with self.subTest(running_roots=running_roots):
                output = io.StringIO()
                errors = io.StringIO()
                arguments = ["benchmark_large_month.py", "--roots", "4", "--prompts", "60",
                             "--running-roots", str(running_roots)]

                with patch("sys.argv", arguments), redirect_stdout(output), redirect_stderr(errors):
                    exit_code = main()

                result = json.loads(output.getvalue())
                self.assertEqual(0, exit_code, errors.getvalue())
                self.assertEqual(2, result["sampled_roots"])
                self.assertEqual(expected_running, result["sampled_running_roots"])
                self.assertEqual(expected_running, result["second_additional_hydrations"])
                self.assertEqual(100, result["sample_prompts_first"])
                self.assertEqual(100, result["sample_prompts_second"])


if __name__ == "__main__":
    unittest.main()
