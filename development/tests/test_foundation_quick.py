from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout
import os
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

from src.version import DISPLAY_VERSION, VERSION

ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINT = ROOT / "src/entrypoints/desktop.py"


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

    def test_product_help_and_version_do_not_import_cli_or_web(self) -> None:
        from src import product_entry
        original = __import__

        def guarded(name, *args, **kwargs):
            if name in {"bootstrap", "src.bootstrap"} or "web" in name:
                self.fail("Information-only entry imported a runtime")
            return original(name, *args, **kwargs)

        for argument in ("--help", "-h", "--version"):
            with self.subTest(argument=argument), patch.object(sys, "argv", [str(ENTRYPOINT), argument]), \
                    patch("builtins.__import__", guarded), redirect_stdout(io.StringIO()) as output:
                self.assertEqual(0, product_entry.main())
                self.assertIn(DISPLAY_VERSION, output.getvalue())

    def test_product_does_not_launch_native_ui_for_explicit_arguments(self) -> None:
        from src import bootstrap, product_entry
        with patch.object(sys, "argv", [str(ENTRYPOINT), "--sessions"]), \
             patch.object(bootstrap, "main", return_value=17), \
             patch.object(product_entry.subprocess, "run") as native:
            self.assertEqual(17, product_entry.main())
            native.assert_not_called()

    def test_product_windows_default_uses_existing_powershell_handoff(self) -> None:
        from src import product_entry
        with patch.object(sys, "argv", [str(ENTRYPOINT)]), patch.object(sys, "platform", "win32"), \
                patch.dict(os.environ, SystemRoot="C:/Windows"), \
                patch.object(product_entry.subprocess, "run", return_value=SimpleNamespace(returncode=4)) as native:
            self.assertEqual(4, product_entry.main())
        self.assertEqual([str(Path("C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")),
                          "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                          str(ROOT / "src/web/windows_launch.ps1")], native.call_args.args[0])
        self.assertNotIn("shell", native.call_args.kwargs)

    def test_product_macos_default_uses_existing_managed_launcher(self) -> None:
        from src import product_entry
        with patch.object(sys, "argv", [str(ENTRYPOINT)]), patch.object(sys, "platform", "darwin"), \
                patch("src.web.macos_launch.launch_macos", return_value=4) as native:
            self.assertEqual(4, product_entry.main())
        native.assert_called_once_with(ROOT)

    def test_product_unsupported_default_never_attempts_a_native_launch(self) -> None:
        from src import product_entry
        with patch.object(sys, "argv", [str(ENTRYPOINT)]), patch.object(sys, "platform", "linux"), \
                patch.object(product_entry.subprocess, "run") as native, redirect_stderr(io.StringIO()) as output:
            self.assertEqual(2, product_entry.main())
        native.assert_not_called()
        self.assertIn("src/entrypoints/cli.py", output.getvalue())
        self.assertIn("--foreground", output.getvalue())

    def test_desktop_entry_rejects_unknown_flags_without_starting_web(self) -> None:
        result = run_python(str(ENTRYPOINT), "--not-a-cost-guard-option")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("Unknown option", result.stdout + result.stderr)

    def test_promoted_source_guard_tracks_each_actual_entry(self) -> None:
        from src.web.change_guard import SourceGuard
        entries = ("src/entrypoints/desktop.py", "src/entrypoints/cli.py", "src/entrypoints/web.py",
                   "windows/Cost-Guard-Web.cmd", "macos/Cost-Guard-Web.command",
                   "macos/launcher.applescript", "windows/Legacy/Cost-Guard.cmd")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative in entries:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("original", encoding="utf-8")
            for relative in entries:
                with self.subTest(relative=relative):
                    guard = SourceGuard(root, interval=0)
                    with (root / relative).open("a", encoding="utf-8") as stream:
                        stream.write("changed")
                    self.assertEqual("source_changed", guard.check())


if __name__ == "__main__":
    unittest.main()
