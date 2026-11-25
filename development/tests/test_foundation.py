"""Full-tier package validator gates on real and deliberately broken package copies."""
from __future__ import annotations

import shutil
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from development.tests.fixtures.package_copy import ROOT, copy_package, run_python
from development.tools import validate_package
from src.version import DISPLAY_VERSION

VALIDATOR = ROOT / "development/tools/validate_package.py"


class ValidationTests(unittest.TestCase):
    def test_only_named_product_prose_can_cross_former_caps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copy = copy_package(Path(tmp))
            for relative, threshold in (("README.md", 32768),):
                path = copy / relative
                with path.open("a", encoding="utf-8") as stream:
                    stream.write("\n" + "x" * (threshold + 1))
            validation = run_python(str(VALIDATOR), "--root", str(copy), "--working-tree")
            self.assertEqual(0, validation.returncode, validation.stdout + validation.stderr)
            for kind in ("rootReadme",):
                self.assertIn(f"WARN  {kind} prose budget", validation.stdout)

            # Neither Markdown nor operational-context names inherit the prose exception.
            for relative in ("AGENTS.md", "skills/example/SKILL.md", "commands/example.md",
                             "manual/agent-reference.md", "manual/example/README.md", "manual/example.md"):
                path = copy / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"x" * 65537)
            config = copy / "config/default-config.jsonc"
            config.write_bytes(b"x" * 32769)
            module = copy / "src/oversize.py"
            module.write_bytes(b"x" * 65537)
            results = validate_package.Results()
            validate_package.check_budgets(copy, results)
            details = "\n".join(detail for _, detail in results.failures)
            for relative in ("AGENTS.md", "skills/example/SKILL.md", "commands/example.md",
                             "manual/agent-reference.md", "manual/example/README.md", "manual/example.md",
                             "config/default-config.jsonc", "src/oversize.py"):
                self.assertIn(relative + ":", details)
            (copy / "README.md").write_bytes(b"x" * 2097153)
            results = validate_package.Results()
            validate_package.check_budgets(copy, results)
            self.assertIn(("universal file cap", "README.md: 2097153 > 2097152 bytes"), results.failures)

    def test_root_visual_studio_cache_is_local_not_distributable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copy = copy_package(Path(tmp))
            index = copy / ".vs/CostGuard/FileContentIndex/cache.vsidx"
            index.parent.mkdir(parents=True)
            index.write_bytes(b"\0" * 65537)
            database = copy / ".vs/slnx.sqlite"
            database.write_bytes(b"\0" * 65537)

            validation = run_python(str(VALIDATOR), "--root", str(copy), "--working-tree")
            self.assertEqual(0, validation.returncode, validation.stdout + validation.stderr)
            self.assertEqual(65537, index.stat().st_size)
            self.assertEqual(65537, database.stat().st_size)

            observed = []

            def inspect_view(view: Path) -> validate_package.Results:
                observed.append((view / ".vs").exists())
                return validate_package.Results()

            with patch.object(validate_package, "validate", side_effect=inspect_view):
                self.assertEqual(0, validate_package.main(["--root", str(copy), "--working-tree"]))
            self.assertEqual([False], observed)
            with patch("development.tests.fixtures.package_copy.ROOT", copy):
                fixture = copy_package(Path(tmp) / "fixture")
            self.assertFalse((fixture / ".vs").exists())

            explicit = run_python(str(VALIDATOR), "--root", str(copy))
            self.assertNotEqual(0, explicit.returncode)
            self.assertIn("forbidden packaged top-level path: .vs", explicit.stdout)

            malformed = copy / "src/Unexpected/oversize.txt"
            malformed.parent.mkdir(parents=True)
            malformed.write_text("x" * 65537, encoding="utf-8")
            validation = run_python(str(VALIDATOR), "--root", str(copy), "--working-tree")
            self.assertNotEqual(0, validation.returncode)
            self.assertIn("lowercase directories", validation.stdout)
            self.assertIn("otherText hard cap", validation.stdout)

    def test_nested_visual_studio_directory_is_not_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copy = copy_package(Path(tmp))
            nested = copy / "src/.vs/Unexpected/index.vsidx"
            nested.parent.mkdir(parents=True)
            nested.write_bytes(b"\0" * 65537)
            validation = run_python(str(VALIDATOR), "--root", str(copy), "--working-tree")
            self.assertNotEqual(0, validation.returncode)
            self.assertIn("src/.vs/Unexpected", validation.stdout)

    def test_runtime_images_use_existing_binary_cap_not_text_cap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "development/tests/policies").mkdir(parents=True)
            shutil.copyfile(ROOT / "development/tests/policies/file-budgets.json", root / "development/tests/policies/file-budgets.json")
            image = root / "src/web/assets/example.png"
            image.parent.mkdir(parents=True)
            self.assertEqual("universalFile", validate_package.file_kind(root, image))
            self.assertEqual("otherText", validate_package.file_kind(root, root / "example.md"))
            image.write_bytes(b"\0" * 65537)
            results = validate_package.Results()
            validate_package.check_budgets(root, results)
            self.assertEqual([], results.failures)
            image.write_bytes(b"\0" * 2097153)
            results = validate_package.Results()
            validate_package.check_budgets(root, results)
            self.assertIn("universal file cap", [label for label, _ in results.failures])

    def test_current_skeleton_passes_validator(self) -> None:
        proc = run_python(str(VALIDATOR), "--working-tree")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("SUMMARY failures=0", proc.stdout)

    def test_product_version_and_validation_need_no_archive_and_create_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copy = copy_package(Path(tmp))
            self.assertFalse((copy / "releases").exists())
            version = run_python(str(copy / "src/entrypoints/desktop.py"), "--version", cwd=copy)
            self.assertEqual(0, version.returncode, version.stdout + version.stderr)
            self.assertEqual(f"Cost Guard {DISPLAY_VERSION}", version.stdout.strip())
            validation = run_python(str(copy / "development/tools/validate_package.py"), "--working-tree", cwd=copy)
            self.assertEqual(0, validation.returncode, validation.stdout + validation.stderr)
            self.assertFalse((copy / "releases").exists())
            self.assertEqual([], list(copy.rglob("*.zip")))

    def test_tiny_readme_is_web_first_with_real_launchers(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(readme.split()), 100)
        self.assertLessEqual(len(readme.splitlines()), 25)
        self.assertLess(readme.index("## Requirements"), readme.index("## Windows"))
        self.assertLess(readme.index("## Windows"), readme.index("## macOS"))
        shared = readme.split("## Requirements\n", 1)[1].split("## Windows", 1)[0]
        self.assertIn("Requires Python 3.11+ and OpenCode on Windows and macOS.", shared)
        self.assertIn("Use the tray/menu **Exit Cost Guard** action to stop the application.", shared)
        for platform, following, path in (
            ("Windows", "macOS", "windows/Cost-Guard-Web.cmd"),
            ("macOS", "Legacy", "macos/Cost-Guard-Web.command"),
        ):
            section = readme.split(f"## {platform}\n", 1)[1].split(f"## {following}", 1)[0]
            self.assertEqual(f"Start [{path}]({path}).", section.strip())
        self.assertIn("local Web server", readme)
        for path in ("windows/Cost-Guard-Web.cmd", "macos/Cost-Guard-Web.command"):
            self.assertIn(f"]({path})", readme)
            self.assertTrue((ROOT / path).is_file())
        for retired in ("docs/", "VERSION_HISTORY", "python ", "## Current version"):
            self.assertNotIn(retired, readme)

    def test_installed_entries_bootstrap_from_unrelated_unicode_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "Install space å 日本"
            base.mkdir()
            copy = copy_package(base)
            outside = Path(tmp) / "unrelated"
            outside.mkdir()
            self.assertEqual([], list(copy.glob("*.py")))
            self.assertFalse((copy / "docs").exists())
            self.assertFalse((copy / "VERSION_HISTORY.md").exists())
            for entry in ("desktop", "web"):
                with self.subTest(entry=entry):
                    result = run_python(str(copy / f"src/entrypoints/{entry}.py"), "--help", cwd=outside)
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertNotIn("Traceback", result.stdout + result.stderr)
                    # Standard module dispatch needs the installation on the import path.
                    environment = {**os.environ, "PYTHONPATH": str(copy), "PYTHONDONTWRITEBYTECODE": "1"}
                    module = subprocess.run([sys.executable, "-m", f"src.entrypoints.{entry}", "--help"],
                                            cwd=outside, env=environment, capture_output=True, text=True, timeout=20)
                    self.assertEqual(result.stdout, module.stdout, module.stderr)
                    self.assertEqual(0, module.returncode)
            result = run_python(str(copy / "src/entrypoints/desktop.py"), "--version", cwd=outside)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(f"Cost Guard {DISPLAY_VERSION}", result.stdout.strip())


class BrokenPackageTests(unittest.TestCase):
    """Each defect is detected by its owning check on an otherwise real package copy."""

    def broken_copy(self, relative: str, text: str, *, append: bool = True) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        copy = copy_package(Path(tmp.name))
        target = copy / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        prefix = target.read_text(encoding="utf-8") if append and target.exists() else ""
        target.write_text(prefix + text, encoding="utf-8")
        return copy

    def failures(self, check, root: Path) -> list[tuple[str, str]]:
        results = validate_package.Results()
        check(root, results)
        return results.failures

    def test_validator_rejects_runtime_cache_in_package(self) -> None:
        copy = self.broken_copy("cache/should-not-ship.txt", "runtime only", append=False)
        failures = self.failures(validate_package.check_required_layout, copy)
        self.assertIn(("runtime artifact", "forbidden packaged top-level path: cache"), failures)

    def test_validator_rejects_retired_documentation_and_root_shims(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = copy_package(Path(temporary))
            for name in ("docs", "VERSION_HISTORY.md", "cost-guard.py", "cost-guard-web.py", "cost-guard-cli.py"):
                with self.subTest(name=name):
                    path = root / name
                    if name == "docs":
                        path.mkdir()
                    else:
                        path.write_text("retired", encoding="utf-8")
                    failures = self.failures(validate_package.check_required_layout, root)
                    self.assertIn(("retired layout", f"retired top-level path must not ship: {name}"), failures)

    def test_validator_checks_literal_runtime_version_and_release_date_without_prose(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = copy_package(Path(temporary))
            metadata = root / "src/version.py"
            original = metadata.read_text(encoding="utf-8")
            for source, expected in (
                (original.replace('DISPLAY_VERSION = f"v{VERSION}"', 'DISPLAY_VERSION = "v0.0"'),
                 "runtime/UI display metadata"),
                (original.replace('RELEASE_DATE = "', 'RELEASE_DATE = "invalid-'),
                 "valid YYYY-MM-DD"),
                (original.replace('VERSION = "', 'VERSION = "bad-', 1), "MAJOR.MINOR"),
            ):
                with self.subTest(expected=expected):
                    metadata.write_text(source, encoding="utf-8")
                    failures = self.failures(validate_package.check_version_consistency, root)
                    self.assertTrue(any(expected in detail for _, detail in failures), failures)

    def test_validator_requires_web_and_legacy_and_rejects_old_distribution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = copy_package(Path(temporary))
            for relative in ("windows/Cost-Guard-Web.cmd", "macos/Legacy/Cost-Guard.command"):
                path = root / relative
                original = path.read_bytes()
                path.unlink()
                failures = self.failures(validate_package.check_required_layout, root)
                self.assertIn(("required layout", "missing required file: " + relative), failures)
                path.write_bytes(original)
            for relative in ("windows/Beta/Cost-Guard-Web.cmd", "macos/Cost-Guard.command"):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("stale launcher", encoding="utf-8")
            failures = self.failures(validate_package.check_required_layout, root)
            self.assertTrue(any("windows/Beta" in detail for _, detail in failures))
            self.assertTrue(any("macos/Cost-Guard.command" in detail for _, detail in failures))

    def test_validator_rejects_report_layer_import_of_concrete_provider(self) -> None:
        copy = self.broken_copy("src/reports/service.py", "\nimport src.pricing.github_copilot\n")
        failures = self.failures(validate_package.check_architecture_imports, copy)
        self.assertIn("report architecture", [label for label, _ in failures])

    def test_validator_rejects_watch_layer_import_of_concrete_source(self) -> None:
        copy = self.broken_copy("src/watch/coordinator.py", "\nimport src.sources.opencode_v1\n")
        failures = self.failures(validate_package.check_architecture_imports, copy)
        self.assertIn("watch architecture", [label for label, _ in failures])

    def test_validator_rejects_syntax_newer_than_python_311(self) -> None:
        copy = self.broken_copy("src/py312_only.py", "type Alias = int\n", append=False)
        failures = self.failures(validate_package.compile_python, copy)
        self.assertIn("Python 3.11 syntax", [label for label, _ in failures])


if __name__ == "__main__":
    unittest.main()
