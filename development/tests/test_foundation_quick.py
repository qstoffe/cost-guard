from __future__ import annotations

import io
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import os
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from pathlib import Path

from src.presentation import StartupProgress
from src.version import DISPLAY_VERSION, RELEASE_DATE, VERSION

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
    def test_inventory_counts_nested_fixture_modules_once(self) -> None:
        from development.tools.code_inventory import inventory

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = root / "development/tests/fixtures/example.py"
            fixture.parent.mkdir(parents=True)
            fixture.write_text('"""Synthetic fixture."""\n', encoding="utf-8")

            data = inventory(root)

        self.assertEqual(["development.tests.fixtures.example"],
                         [module["module"] for module in data["modules"]])

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

    def test_version_is_available_without_loading_runtime_integrations(self) -> None:
        proc = run_python(str(ENTRYPOINT), "--version")
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual(f"Cost Guard {DISPLAY_VERSION}", proc.stdout.strip())

    def test_entrypoint_guards_minimum_python_before_bootstrap(self) -> None:
        import runpy

        # Execute the entry guard as an unsupported interpreter. A runtime import
        # would fail this test, even if its source spelling/placement changes.
        original_import = __import__
        def guarded_import(name, *args, **kwargs):
            if name.startswith("src"):
                self.fail("Unsupported Python reached a runtime integration")
            return original_import(name, *args, **kwargs)

        output = io.StringIO()
        with patch.object(sys, "version_info", (3, 10)), patch("builtins.__import__", guarded_import), \
                redirect_stderr(output), self.assertRaises(SystemExit) as exit:
            runpy.run_path(str(ENTRYPOINT), run_name="__main__")
        self.assertEqual(1, exit.exception.code)
        self.assertIn("Python 3.11", output.getvalue())

    def test_help_documents_python_cli_shapes(self) -> None:
        proc = run_python(str(ENTRYPOINT), "--help")
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("python cost-guard.py <session-id> --watch", proc.stdout)
        self.assertIn("YYYY-MM-DD:YYYY-MM-DD", proc.stdout)

    def test_watch_runtime_is_wired_to_single_startup_dashboard(self) -> None:
        from src import bootstrap

        runtime = self.bootstrap_runtime()
        renderer = runtime.WatchRenderer.return_value
        coordinator = runtime.WatchCoordinator.return_value
        with redirect_stdout(io.StringIO()):
            result = bootstrap.main(["--watch"])
        self.assertEqual(0, result)
        renderer.render_initializing.assert_called_once()
        coordinator.initialize_with_recovery.assert_called_once_with(
            renderer, before_recovery=runtime.StartupProgress.return_value.stop)
        coordinator.run_forever.assert_called_once_with(
            renderer, initial_cycle=coordinator.initialize_with_recovery.return_value)
        runtime.ReportRenderer.assert_not_called()

    def test_one_shot_header_is_rendered_once_with_selected_source(self) -> None:
        from src import bootstrap

        runtime = self.bootstrap_runtime()
        output = io.StringIO()
        with redirect_stdout(output):
            result = bootstrap.main([])
        self.assertEqual(0, result)
        self.assertEqual("", output.getvalue(), "Only the report renderer owns report output")
        runtime.ReportRenderer.return_value.render.assert_called_once_with(
            runtime.ReportService.return_value.build.return_value)
        self.assertIs(runtime._select_or_wait.return_value,
                      runtime.ReportService.call_args.kwargs["selection"])
        runtime.WatchRenderer.assert_not_called()
        self.assertEqual(f"Cost Guard {DISPLAY_VERSION} ({RELEASE_DATE}) — Report",
                         runtime.StartupProgress.call_args.kwargs["heading"])

    def bootstrap_runtime(self):
        """Replace I/O boundaries, not the composition path being exercised."""
        from src import bootstrap

        stack = ExitStack()
        self.addCleanup(stack.close)
        names = ("load_configuration", "_select_or_wait", "CacheDatabase", "CacheRepository",
                 "GitHubCopilotPricingProvider", "_account_providers", "_model_availability_source",
                 "ReportService", "WatchCoordinator", "WatchRenderer", "ReportRenderer", "StartupProgress")
        runtime = SimpleNamespace(**{name: stack.enter_context(patch.object(bootstrap, name)) for name in names})
        runtime.load_configuration.return_value.values = {"openCode": {"source": "auto"}}
        runtime._account_providers.return_value = ()
        runtime._select_or_wait.return_value = SimpleNamespace(selected="v2", source=Mock())
        return runtime

    def test_startup_progress_supports_runtime_and_explicit_percentages(self) -> None:
        stream = io.StringIO()
        progress = StartupProgress(stream, mode="normal", interactive=True, animate=False)
        progress.update("Selecting OpenCode source")
        progress.update("Diagnostics validation", 67)
        progress.stop(complete=True)
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
        progress.stop(complete=True)
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


if __name__ == "__main__":
    unittest.main()
