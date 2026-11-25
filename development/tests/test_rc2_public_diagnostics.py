from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from src.version import DISPLAY_VERSION, RELEASE_DATE
from development.tools.validate_package import Results, check_lowercase_directories, check_public_hygiene
from development.tests.fixtures.package_copy import copy_package

ROOT = Path(__file__).resolve().parents[2]
DIAG = ROOT / "development/tools/collect_diagnostics.py"


class PublicRepoLayoutTests(unittest.TestCase):
    def test_open_source_license_and_generic_public_hygiene(self) -> None:
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("Zero-Clause BSD", license_text)
        self.assertIn("Permission to use, copy, modify", license_text)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "LICENSE").write_text(license_text, encoding="utf-8")
            (root / "config").mkdir()
            (root / "config/default-config.jsonc").write_text(
                '{"' + "tenant" + 'Id": "example", "note": "' + "internal " + 'use only"}',
                encoding="utf-8",
            )
            results = Results()
            check_public_hygiene(root, results)
            self.assertGreaterEqual(len(results.failures), 2)
            self.assertTrue(all(label == "public repository hygiene" for label, _ in results.failures))

    def test_all_package_owned_directories_are_lowercase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = copy_package(Path(tmp))
            results = Results()
            check_lowercase_directories(root, results)
            self.assertEqual([], results.failures)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "BadDir").mkdir()
            bad = Results()
            check_lowercase_directories(root, bad)
            self.assertTrue(any(label == "lowercase directories" for label, _ in bad.failures))

    def test_config_lives_under_config_directory(self) -> None:
        self.assertTrue((ROOT / "config/default-config.jsonc").is_file())
        self.assertFalse((ROOT / "default-config.jsonc").exists())
        self.assertFalse((ROOT / "user-config.jsonc").exists())


class WindowsLauncherTests(unittest.TestCase):
    def test_diagnostics_launcher_is_double_clickable(self) -> None:
        text = (ROOT / "development/user-tools/diagnostics/windows/Cost-Guard-Diagnostics.cmd").read_text(encoding="utf-8")
        self.assertIn('%~dp0..\\..\\..\\..\\src\\windows_launcher.ps1', text)
        self.assertIn("-Mode diagnostics", text)
        driver = (ROOT / "src/windows_launcher.ps1").read_text(encoding="utf-8")
        self.assertIn("development\\tools\\collect_diagnostics.py", driver)
        self.assertIn("-NoExit", text)


class LauncherPlacementTests(unittest.TestCase):
    def test_public_folders_hold_only_everyday_launchers(self) -> None:
        self.assertEqual({"Cost-Guard-Web.cmd", "Legacy"},
                         {path.name for path in (ROOT / "windows").iterdir()})
        self.assertEqual({"Cost-Guard.cmd", "Cost-Guard-Watch.cmd"},
                         {path.name for path in (ROOT / "windows/Legacy").iterdir()})
        self.assertEqual({"Cost-Guard-Web.command", "launcher.applescript", "Legacy"},
                         {path.name for path in (ROOT / "macos").iterdir()})
        self.assertEqual({"Cost-Guard.command", "Cost-Guard-Watch.command"},
                         {path.name for path in (ROOT / "macos/Legacy").iterdir()})

    def test_validator_rejects_diagnostics_launcher_in_public_folder(self) -> None:
        from development.tools.validate_package import check_required_layout

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "windows").mkdir()
            (root / "windows/Cost-Guard-Diagnostics.cmd").write_text("@echo off\n", encoding="utf-8")
            results = Results()
            check_required_layout(root, results)
            self.assertIn(("public launchers", "unexpected entry in user-facing launcher folder: windows/Cost-Guard-Diagnostics.cmd"),
                          results.failures)


class MacOSLauncherTests(unittest.TestCase):
    def test_macos_launchers_exist_are_executable_and_relative(self) -> None:
        expected = {
            "development/user-tools/diagnostics/macos/Cost-Guard-Diagnostics.command": "/development/tools/collect_diagnostics.py",
        }
        for name, needle in expected.items():
            path = ROOT / name
            self.assertTrue(path.is_file(), name)
            # Source filesystem mode is intentionally not asserted here: Python
            # ZIP extraction and Windows worktrees do not reliably preserve Unix
            # executable bits. The package validator verifies that
            # every packaged macOS .command entry is normalized to executable.
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("#!/bin/zsh"), name)
            self.assertIn('dirname "$0"', text, name)
            self.assertIn('source "$CG_ROOT/src/python_discovery.sh"', text, name)
            self.assertIn('cg_find_python', text, name)
            self.assertIn(needle, text, name)
        diagnostics = (ROOT / "development/user-tools/diagnostics/macos/Cost-Guard-Diagnostics.command").read_text(encoding="utf-8")
        self.assertIn('CG_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"', diagnostics)


class DiagnosticBundleTests(unittest.TestCase):
    def test_standalone_web_bundle_does_not_require_a_source_or_host(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            env.update(OPENCODE_DB=str(Path(tmp) / "absent.sqlite"), XDG_STATE_HOME=tmp, XDG_DATA_HOME=tmp)
            env["PYTHONIOENCODING"] = "utf-8"  # independent of the outer console code page
            proc = subprocess.run(
                [sys.executable, str(DIAG), "--output-dir", tmp],
                cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
            )
            self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
            self.assertTrue(
                proc.stdout.startswith(f"Cost Guard {DISPLAY_VERSION} ({RELEASE_DATE}) — Diagnostics\n"),
                proc.stdout,
            )
            bundles = list(Path(tmp).glob("cost-guard-diagnostics.zip"))
            self.assertEqual(1, len(bundles))
            with zipfile.ZipFile(bundles[0]) as archive:
                self.assertTrue({"diagnostics.json", "summary.txt"}.issubset(set(archive.namelist())))
                payload = json.loads(archive.read("diagnostics.json"))
                raw = archive.read("diagnostics.json").decode("utf-8").lower()
            self.assertEqual(3, payload["schema_version"])
            self.assertEqual("Web", payload["cost_guard"]["product"])
            self.assertIn("sources", payload)
            self.assertIn("v2", payload["sources"])
            self.assertNotIn("fatal", payload)
            self.assertNotIn("refresh_token", raw)
            self.assertNotIn("access_token", raw)
            self.assertNotIn("prompt_text", raw)


if __name__ == "__main__":
    unittest.main()
