"""Full-tier package validator gates on real and deliberately broken package copies."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from development.fixtures.package_copy import ROOT, copy_package, run_python
from development.tools import validate_package
from src.version import DISPLAY_VERSION

VALIDATOR = ROOT / "development/tools/validate_package.py"


class ValidationTests(unittest.TestCase):
    def test_documentation_images_use_existing_binary_cap_not_text_cap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "development").mkdir()
            shutil.copyfile(ROOT / "development/file-budgets.json", root / "development/file-budgets.json")
            image = root / "docs/images/example.png"
            image.parent.mkdir(parents=True)
            self.assertEqual("universalFile", validate_package.file_kind(root, image))
            self.assertEqual("otherText", validate_package.file_kind(root, root / "docs/example.md"))
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
            version = run_python(str(copy / "cost-guard.py"), "--version", cwd=copy)
            self.assertEqual(0, version.returncode, version.stdout + version.stderr)
            self.assertEqual(f"Cost Guard {DISPLAY_VERSION}", version.stdout.strip())
            validation = run_python(str(copy / "development/tools/validate_package.py"), "--working-tree", cwd=copy)
            self.assertEqual(0, validation.returncode, validation.stdout + validation.stderr)
            self.assertFalse((copy / "releases").exists())
            self.assertEqual([], list(copy.rglob("*.zip")))


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
