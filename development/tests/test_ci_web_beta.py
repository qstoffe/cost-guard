"""CI evidence accounting and fail-closed workstation UI boundary; no UI invocation."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from development.tools import ci_web_beta, run_tests


class CiEvidenceTests(unittest.TestCase):
    def test_workstation_cannot_enter_hosted_probe(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(SystemExit, "not authorized on a workstation"):
                ci_web_beta.hosted_only()

    def test_provisioning_blocked_is_not_relabelled_as_test_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            results = Path(temporary)
            (results / "browser.json").write_text(json.dumps(dict(outcome="BLOCKED", reason="tool unavailable")))
            with patch.object(ci_web_beta, "RESULTS", results), patch.object(ci_web_beta, "hosted_only"), \
                    patch.object(ci_web_beta, "facts", return_value={}), patch.object(ci_web_beta, "save"), \
                    patch.object(ci_web_beta, "run", return_value=1), patch("sys.argv", ["ci", "browser"]), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                result = ci_web_beta.main()
        self.assertEqual(1, result)
        self.assertEqual("BLOCKED", json.loads(output.getvalue())["outcome"])

    def test_report_preserves_named_skips_failures_and_missing_counts(self):
        outputs = [
            ("test_a.py", 0, 0.1, "test_a (example.Tests.test_a) ... ok\ntest_b (example.Tests.test_b) ... skipped 'Windows only'\nRan 2 tests in 0.1s\n\nOK (skipped=1)"),
            ("test_b.py", 1, 0.1, "Ran 3 tests in 0.1s\n\nFAILED (failures=1, errors=1, skipped=1)"),
            ("test_c.py", 124, 1, "TIMEOUT after 1s"),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "report.json"
            with patch.object(run_tests, "QUICK_PATTERNS", tuple(row[0] for row in outputs)), \
                    patch.object(run_tests, "_run_pattern", side_effect=outputs), contextlib.redirect_stdout(io.StringIO()):
                result = run_tests.main(["--jobs", "1", "--json-report", str(path)])
            report = json.loads(path.read_text())["files"]
        self.assertEqual(1, result)
        self.assertEqual(1, report[0]["skipped"])
        self.assertEqual("'Windows only'", report[0]["skips"][0]["reason"])
        self.assertEqual(1, report[1]["failures"])
        self.assertEqual(1, report[1]["errors"])
        self.assertIsNone(report[2]["tests"])
        self.assertEqual("FAIL", report[2]["outcome"])


if __name__ == "__main__":
    unittest.main()
