from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from src.presentation import StartupProgress
from src.version import DISPLAY_VERSION, VERSION
from development.tools import run_tests

ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINT = ROOT / "cost-guard.py"


def run_python(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, *args], cwd=ROOT, env=env,
        capture_output=True, text=True, timeout=10,
    )


class BootstrapQuickTests(unittest.TestCase):
    def test_http_product_identifiers_follow_authoritative_version(self) -> None:
        from src.accounts.github_copilot import _default_json_get
        from src.accounts.openai_subscription import _default_usage_get
        from src.pricing.github_copilot import _default_fetch_text
        calls = (
            (_default_json_get, ("https://example.invalid", "synthetic-token", False, 1), DISPLAY_VERSION),
            (_default_usage_get, ("https://example.invalid", "synthetic-token", "synthetic-account", 1), VERSION),
            (_default_fetch_text, ("https://example.invalid", 1), DISPLAY_VERSION),
        )
        for function, args, version in calls:
            with self.subTest(function=function.__name__), patch("urllib.request.urlopen") as opener:
                response = opener.return_value.__enter__.return_value
                response.status = 200
                response.read.return_value = b"{}"
                function(*args)
                self.assertEqual(f"CostGuard/{version}", opener.call_args.args[0].get_header("User-agent"))

    def test_suite_membership_is_complete_and_watch_activity_is_in_runtime(self) -> None:
        self.assertEqual([], run_tests.suite_membership_errors())
        self.assertIn("test_watch_tool_activity.py", run_tests.QUICK_PATTERNS)
        self.assertIn("test_watch_tool_activity.py", run_tests.PROFILES["runtime"])

    def test_runner_rejects_orphans_before_starting_even_a_focused_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tests = Path(directory)
            for name in run_tests.QUICK_PATTERNS + run_tests.FULL_ONLY_PATTERNS:
                (tests / name).touch()
            orphan = tests / "test_unassigned.py"
            orphan.touch()
            original = run_tests.suite_membership_errors
            with patch.object(run_tests, "suite_membership_errors", side_effect=lambda: original(tests)), \
                    patch.object(run_tests, "_run_pattern") as execute, \
                    patch("sys.stderr", new_callable=io.StringIO) as stderr:
                self.assertEqual(2, run_tests.main(["--pattern", "test_foundation_quick.py"]))
                self.assertIn("unassigned test module: test_unassigned.py", stderr.getvalue())
                execute.assert_not_called()
            with patch.object(run_tests, "EXCLUDED_TEST_MODULES", {orphan.name: "Manual-only fixture"}):
                self.assertEqual([], original(tests))
            with patch.object(run_tests, "EXCLUDED_TEST_MODULES", {orphan.name: ""}):
                self.assertIn("stale or undocumented test exclusion", "\n".join(original(tests)))
            orphan.unlink()
            with patch.object(run_tests, "EXCLUDED_TEST_MODULES", {orphan.name: "Manual-only fixture"}):
                self.assertIn("stale or undocumented test exclusion", "\n".join(original(tests)))
            (tests / run_tests.QUICK_PATTERNS[0]).unlink()
            self.assertIn("suite pattern matches no test module", "\n".join(original(tests)))
            with patch.object(run_tests, "FULL_ONLY_PATTERNS", run_tests.FULL_ONLY_PATTERNS + (run_tests.QUICK_PATTERNS[1],)):
                self.assertIn("overlapping suite/exclusion assignments", "\n".join(original(tests)))

    def test_version_is_available_without_loading_runtime_integrations(self) -> None:
        proc = run_python(str(ENTRYPOINT), "--version")
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual(f"Cost Guard {DISPLAY_VERSION}", proc.stdout.strip())

    def test_entrypoint_guards_minimum_python_before_bootstrap(self) -> None:
        text = ENTRYPOINT.read_text(encoding="utf-8")
        self.assertIn("sys.version_info < (3, 11)", text)
        self.assertLess(text.index("sys.version_info"), text.index("from src.bootstrap import main"))

    def test_help_documents_python_cli_shapes(self) -> None:
        proc = run_python(str(ENTRYPOINT), "--help")
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("python cost-guard.py <session-id> --watch", proc.stdout)
        self.assertIn("YYYY-MM-DD:YYYY-MM-DD", proc.stdout)

    def test_watch_runtime_is_wired_to_single_startup_dashboard(self) -> None:
        bootstrap = (ROOT / "src/bootstrap.py").read_text(encoding="utf-8")
        self.assertIn("render_initializing", bootstrap)
        self.assertIn("initial_cycle = coordinator.initialize()", bootstrap)
        self.assertIn("run_forever(watch_renderer, initial_cycle=initial_cycle)", bootstrap)

    def test_one_shot_header_is_rendered_once_with_selected_source(self) -> None:
        bootstrap = (ROOT / "src/bootstrap.py").read_text(encoding="utf-8")
        self.assertNotIn('print(f"{PRODUCT_NAME} {DISPLAY_VERSION} ({RELEASE_DATE})")', bootstrap)
        self.assertIn("ReportRenderer(config).render(projection)", bootstrap)

    def test_startup_progress_supports_runtime_and_explicit_percentages(self) -> None:
        stream = io.StringIO()
        progress = StartupProgress(stream, mode="normal", interactive=True, animate=False)
        progress.update("Selecting OpenCode source")
        progress.update("Diagnostics validation", 67)
        progress.stop()
        rendered = stream.getvalue()
        self.assertIn("67%", rendered)
        closed = stream.getvalue()
        progress.update("must stay closed", 99)
        self.assertEqual(closed, stream.getvalue())

    def test_watch_progress_can_render_into_dashboard_status_sink(self) -> None:
        lines: list[str] = []
        progress = StartupProgress(
            io.StringIO(), mode="watch", interactive=True, animate=False,
            line_sink=lines.append,
        )
        progress.update("Analyzing ses_fixture")
        progress.stop()
        self.assertTrue(lines)
        self.assertIn("Watch: ", lines[-1])
        self.assertIn("100%", lines[-1])

    def test_report_loading_heading_cleans_all_wrapped_rows_and_redirect_has_no_ui(self) -> None:
        for columns in (80, 12):
            stream = io.StringIO()
            with patch("src.presentation.progress.shutil.get_terminal_size", return_value=type("Size", (), {"columns": columns})()):
                progress = StartupProgress(stream, interactive=True, animate=False, heading="Cost Guard — Report")
                progress.update("Analyzing", 57)
                progress.stop()
            rendered = stream.getvalue()
            self.assertIn("57%", rendered)
            heading_rows = rendered.split("\r", 1)[0].count("\n")
            self.assertEqual(heading_rows, rendered.count("\x1b[1A\x1b[2K"))
            self.assertTrue(rendered.endswith("\x1b[1A\x1b[2K" * heading_rows))
        quiet = io.StringIO()
        progress = StartupProgress(quiet, interactive=False, heading="Cost Guard — Report")
        progress.update("Analyzing", 57)
        progress.stop()
        self.assertEqual("Cost Guard: Analyzing\n", quiet.getvalue())
        bootstrap = (ROOT / "src/bootstrap.py").read_text(encoding="utf-8")
        self.assertIn('StartupProgress(mode="normal", heading=mode_heading(startup_mode(command)))', bootstrap)


if __name__ == "__main__":
    unittest.main()
