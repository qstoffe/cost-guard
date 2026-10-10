"""Full-tier release builder regressions on disposable package copies (never a checkout ZIP)."""
from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from development.fixtures.package_copy import ROOT, copy_package, run_python
from src.version import DISPLAY_VERSION

BUILDER = ROOT / "development/tools/build_release.py"


class ReleaseBuilderTests(unittest.TestCase):
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
            proc = run_python(str(copy / "development/tools/build_release.py"), cwd=copy, release_nested=True)
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
            proc = run_python(str(copy / "development/tools/build_release.py"), "--output", str(output),
                              cwd=copy, release_nested=True)
            self.assertEqual(3, proc.returncode, proc.stdout + proc.stderr)
            self.assertFalse(output.exists())
            self.assertIn("Release build refused", proc.stderr)


if __name__ == "__main__":
    unittest.main()
