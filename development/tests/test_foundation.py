"""Full-tier package validator gates on real and deliberately broken package copies."""
from __future__ import annotations

import shutil
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
            for relative, threshold in (("README.md", 32768), ("VERSION_HISTORY.md", 32768),
                                        ("docs/web-beta.md", 65536)):
                path = copy / relative
                with path.open("a", encoding="utf-8") as stream:
                    stream.write("\n" + "x" * (threshold + 1))
            validation = run_python(str(VALIDATOR), "--root", str(copy), "--working-tree")
            self.assertEqual(0, validation.returncode, validation.stdout + validation.stderr)
            for kind in ("rootReadme", "versionHistory", "webUserGuide"):
                self.assertIn(f"WARN  {kind} prose budget", validation.stdout)

            # Neither Markdown nor operational-context names inherit the prose exception.
            for relative in ("AGENTS.md", "skills/example/SKILL.md", "commands/example.md",
                             "docs/agent-reference.md", "docs/example/README.md", "docs/example.md"):
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
                             "docs/agent-reference.md", "docs/example/README.md", "docs/example.md",
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

            malformed = copy / "docs/Unexpected/oversize.txt"
            malformed.parent.mkdir(parents=True)
            malformed.write_text("x" * 65537, encoding="utf-8")
            validation = run_python(str(VALIDATOR), "--root", str(copy), "--working-tree")
            self.assertNotEqual(0, validation.returncode)
            self.assertIn("lowercase directories", validation.stdout)
            self.assertIn("otherText hard cap", validation.stdout)

    def test_nested_visual_studio_directory_is_not_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copy = copy_package(Path(tmp))
            nested = copy / "docs/.vs/Unexpected/index.vsidx"
            nested.parent.mkdir(parents=True)
            nested.write_bytes(b"\0" * 65537)
            validation = run_python(str(VALIDATOR), "--root", str(copy), "--working-tree")
            self.assertNotEqual(0, validation.returncode)
            self.assertIn("docs/.vs/Unexpected", validation.stdout)

    def test_documentation_images_use_existing_binary_cap_not_text_cap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "development/architecture/governance/policies").mkdir(parents=True)
            shutil.copyfile(ROOT / "development/architecture/governance/policies/file-budgets.json", root / "development/architecture/governance/policies/file-budgets.json")
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
