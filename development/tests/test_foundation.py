from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from src.version import DISPLAY_VERSION

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "development/tools/validate_package.py"
BUILDER = ROOT / "development/tools/build_release.py"
ENTRYPOINT = ROOT / "cost-guard.py"


def run_python(
    *args: str, cwd: Path = ROOT, release_nested: bool = False
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if release_nested:
        env["COST_GUARD_RELEASE_GATE_ACTIVE"] = "1"
    return subprocess.run(
        [sys.executable, *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def copy_package(destination: Path) -> Path:
    root = destination / "package"

    def ignore(directory: str, names: list[str]) -> set[str]:
        ignored = {name for name in names if name in {".git", "__pycache__"} or name.endswith((".pyc", ".zip"))}
        current = Path(directory).resolve()
        if current == ROOT.resolve():
            ignored.update(name for name in ("cache", "diagnostics", "logs", "releases") if name in names)
        if current == (ROOT / "config").resolve() and "user-config.jsonc" in names:
            ignored.add("user-config.jsonc")
        return ignored

    shutil.copytree(ROOT, root, ignore=ignore)
    return root


class ValidationTests(unittest.TestCase):
    def test_documentation_images_use_existing_binary_cap_not_text_cap(self) -> None:
        from development.tools.validate_package import Results, check_budgets, file_kind

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "development").mkdir()
            shutil.copyfile(ROOT / "development/file-budgets.json", root / "development/file-budgets.json")
            image = root / "docs/images/example.png"
            image.parent.mkdir(parents=True)
            self.assertEqual("universalFile", file_kind(root, image))
            self.assertEqual("otherText", file_kind(root, root / "docs/example.md"))
            image.write_bytes(b"\0" * 65537)
            results = Results()
            check_budgets(root, results)
            self.assertEqual([], results.failures)
            image.write_bytes(b"\0" * 2097153)
            results = Results()
            check_budgets(root, results)
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

    def test_validator_rejects_runtime_cache_in_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copy = copy_package(Path(tmp))
            cache = copy / "cache"
            cache.mkdir()
            (cache / "should-not-ship.txt").write_text("runtime only", encoding="utf-8")
            proc = run_python(str(copy / "development/tools/validate_package.py"), "--root", str(copy), cwd=copy)
            self.assertNotEqual(0, proc.returncode)
            self.assertIn("forbidden packaged top-level path: cache", proc.stdout)

    def test_runtime_logs_are_excluded_only_from_distributable_view(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copy = copy_package(Path(tmp))
            runtime_log = copy / "logs/errors/synthetic.log"
            nested_log = copy / "src/cache/logs/synthetic.txt"
            for path in (runtime_log, nested_log):
                path.parent.mkdir(parents=True)
                path.write_text("synthetic evidence", encoding="utf-8")
            validator = str(copy / "development/tools/validate_package.py")
            proc = run_python(validator, "--working-tree", cwd=copy)
            self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
            proc = run_python(validator, cwd=copy)
            self.assertNotEqual(0, proc.returncode)
            self.assertIn("forbidden packaged top-level path: logs", proc.stdout)
            output = Path(tmp) / "release.zip"
            proc = run_python(
                str(copy / "development/tools/build_release.py"),
                "--output", str(output), cwd=copy, release_nested=True,
            )
            self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())
            self.assertFalse(any(name.startswith("logs/") for name in names))
            self.assertIn("src/cache/logs/synthetic.txt", names)
            self.assertEqual("synthetic evidence", runtime_log.read_text(encoding="utf-8"))

    def test_validator_rejects_report_layer_import_of_concrete_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copy = copy_package(Path(tmp))
            target = copy / "src/reports/service.py"
            target.write_text(
                target.read_text(encoding="utf-8") + "\nimport src.pricing.github_copilot\n",
                encoding="utf-8",
            )
            proc = run_python(str(copy / "development/tools/validate_package.py"), "--root", str(copy), cwd=copy)
            self.assertNotEqual(0, proc.returncode)
            self.assertIn("report architecture", proc.stdout)

    def test_validator_rejects_watch_layer_import_of_concrete_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copy = copy_package(Path(tmp))
            target = copy / "src/watch/coordinator.py"
            target.write_text(
                target.read_text(encoding="utf-8") + "\nimport src.sources.opencode_v1\n",
                encoding="utf-8",
            )
            proc = run_python(str(copy / "development/tools/validate_package.py"), "--root", str(copy), cwd=copy)
            self.assertNotEqual(0, proc.returncode)
            self.assertIn("watch architecture", proc.stdout)

    def test_validator_rejects_syntax_newer_than_python_311(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copy = copy_package(Path(tmp))
            target = copy / "src/py312_only.py"
            target.write_text("type Alias = int\n", encoding="utf-8")
            proc = run_python(str(copy / "development/tools/validate_package.py"), "--root", str(copy), cwd=copy)
            self.assertNotEqual(0, proc.returncode)
            self.assertIn("Python 3.11 syntax", proc.stdout)

    def test_release_builder_runs_behavior_and_clean_extract_gates(self) -> None:
        text = BUILDER.read_text(encoding="utf-8")
        self.assertIn("development/tools/run_tests.py", text)
        self.assertIn("clean-extracted release {suite} test suite failed", text)
        self.assertIn("verify_archive_bytes", text)

    def test_release_builder_includes_source_cache_package_but_not_runtime_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "release.zip"
            proc = run_python(str(BUILDER), "--output", str(output), release_nested=True)
            self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())
                for name in (
                    "macos/Cost Guard.command",
                    "macos/Cost Guard Watch.command",
                    "development/macos/Cost Guard Diagnostics.command",
                ):
                    mode = (archive.getinfo(name).external_attr >> 16) & 0o777
                    self.assertTrue(mode & 0o100, f"{name} not executable in archive metadata: {oct(mode)}")
            self.assertIn("development/windows/Cost Guard Diagnostics.cmd", names)
            self.assertFalse(any(name.startswith(("windows/", "macos/")) and "Diagnostics" in name for name in names))
            self.assertIn("src/cache/database.py", names)
            self.assertIn("src/cache/repository.py", names)
            for name in ("watch", "report", "token-mix"):
                self.assertIn(f"docs/images/cost-guard-{name}.png", names)
            self.assertIn("docs/usage-and-cost.md", names)
            self.assertFalse(any(name == "cache" or name.startswith("cache/") for name in names))

    def test_release_builder_default_output_is_gitignored_releases_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copy = copy_package(Path(tmp))
            proc = run_python(
                str(copy / "development/tools/build_release.py"),
                cwd=copy,
                release_nested=True,
            )
            self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
            output = copy / f"releases/cost-guard-{DISPLAY_VERSION}.zip"
            self.assertTrue(output.is_file())
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())
            self.assertIn("AGENTS.md", names)
            self.assertFalse(any(name == "releases" or name.startswith("releases/") for name in names))
            self.assertIn("/releases/", (copy / ".gitignore").read_text(encoding="utf-8"))

    def test_release_builder_refuses_invalid_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copy = copy_package(Path(tmp))
            bad = copy / "src" / "BadDir"
            bad.mkdir()
            (bad / "bad.py").write_text("VALUE = 1\n", encoding="utf-8")
            output = Path(tmp) / "should-not-exist.zip"
            proc = run_python(str(copy / "development/tools/build_release.py"), "--output", str(output), cwd=copy, release_nested=True)
            self.assertEqual(3, proc.returncode, proc.stdout + proc.stderr)
            self.assertFalse(output.exists())
            self.assertIn("Release build refused", proc.stderr)


if __name__ == "__main__":
    unittest.main()
