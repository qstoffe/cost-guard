#!/usr/bin/env python3
"""Deterministic macOS-behavior checks, runnable on Windows without macOS."""
from __future__ import annotations

import json
from contextlib import closing
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.sources.opencode_v1 import OpenCodeV1Source, REQUIRED_COLUMNS
from src.sources.errors import SourceDataError
from src.sources.discovery import (
    default_opencode_data_dir, default_opencode_state_dir,
    discover_v1_database_candidate, discover_v2_registration_candidate,
    find_opencode_executable, has_opencode_installation_evidence,
    read_v2_service_registration, ServiceRegistrationCandidate,
)



def equivalent_path(path: Path) -> str:
    """Compare filesystem meaning rather than Windows display casing."""
    import os
    return os.path.normcase(os.path.realpath(os.fspath(path)))


class MacCompatibilityChecks(unittest.TestCase):
    def test_default_xdg_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self.assertEqual(equivalent_path(home / ".local/share/opencode"), equivalent_path(default_opencode_data_dir(environment={}, home=home)))
            self.assertEqual(equivalent_path(home / ".local/state/opencode"), equivalent_path(default_opencode_state_dir(environment={}, home=home)))

    def test_custom_xdg_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            env = {"XDG_DATA_HOME": str(home / "custom-data"), "XDG_STATE_HOME": str(home / "custom-state")}
            self.assertEqual(equivalent_path(home / "custom-data/opencode"), equivalent_path(default_opencode_data_dir(environment=env, home=home)))
            self.assertEqual(equivalent_path(home / "custom-state/opencode/service.json"),
                             equivalent_path(discover_v2_registration_candidate(environment=env, home=home).path))

    def test_v1_database_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            result = discover_v1_database_candidate(environment={"OPENCODE_DB": "~/custom/db.sqlite"}, home=home)
            self.assertEqual(equivalent_path(home / "custom/db.sqlite"), equivalent_path(result.path))
            self.assertEqual("OPENCODE_DB", result.origin)

    def test_cli_on_path_takes_priority(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual("/synthetic/bin/opencode", find_opencode_executable(
                environment={}, home=Path(tmp), which=lambda name: "/synthetic/bin/opencode"))

    def test_cli_outside_path_in_homebrew_style_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            folder = home / ".opencode/bin"
            folder.mkdir(parents=True)
            executable = folder / "opencode"
            executable.write_text("synthetic fixture", encoding="utf-8")
            with patch("src.sources.discovery.os.access", return_value=True):
                result = find_opencode_executable(environment={}, home=home, which=lambda name: None)
            self.assertEqual(str(executable), result)

    def test_cli_missing_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            with patch("src.sources.discovery.Path.is_file", return_value=False):
                self.assertIsNone(find_opencode_executable(environment={}, home=home, which=lambda name: None))

    def test_macos_app_counts_as_installation_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            app = home / "Applications/OpenCode.app"
            app.mkdir(parents=True)
            self.assertTrue(has_opencode_installation_evidence(environment={}, home=home, platform="darwin"))

    def test_service_registration_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            candidate = ServiceRegistrationCandidate(Path(tmp) / "state/service.json", "synthetic")
            with self.assertRaises((OSError, ValueError)):
                read_v2_service_registration(candidate)

    def test_v1_sqlite_readonly_valid_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "opencode.db"
            with closing(sqlite3.connect(path)) as connection:
                for table, columns in REQUIRED_COLUMNS.items():
                    connection.execute(
                        f'CREATE TABLE "{table}" (' +
                        ", ".join(f'"{name}" TEXT' for name in sorted(columns)) + ")"
                    )
            source = OpenCodeV1Source(path)
            self.assertTrue(source.probe().healthy)
            self.assertEqual((), tuple(source.list_sessions()))

    def test_v1_sqlite_missing_schema_is_unhealthy(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "opencode.db"
            with closing(sqlite3.connect(path)) as connection:
                connection.execute("CREATE TABLE unrelated (id TEXT)")
            self.assertFalse(OpenCodeV1Source(path).probe().healthy)

    def test_v1_sqlite_invalid_database_is_unhealthy(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "opencode.db"
            path.write_bytes(b"not a sqlite database")
            source = OpenCodeV1Source(path)
            self.assertFalse(source.probe().healthy)

    def test_v1_sqlite_concurrent_wal_writer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "opencode.db"
            with closing(sqlite3.connect(path)) as writer:
                writer.execute("PRAGMA journal_mode=WAL")
                for table, columns in REQUIRED_COLUMNS.items():
                    writer.execute(f'CREATE TABLE "{table}" (' +
                                   ", ".join(f'"{name}" TEXT' for name in sorted(columns)) + ")")
                writer.commit()
                writer.execute("BEGIN IMMEDIATE")
                writer.execute('INSERT INTO "session" ("id") VALUES (?)', ("synthetic",))
                source = OpenCodeV1Source(path)
                self.assertTrue(source.probe().healthy)
                self.assertEqual((), tuple(source.list_sessions()))
                writer.rollback()

    def test_v1_sqlite_error_is_sanitized(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "opencode.db"
            path.write_bytes(b"dummy")
            source = OpenCodeV1Source(path)
            # Opening succeeds in mock; SQL operation fails in the guarded read phase.
            class FailingConnection:
                def execute(self, *args, **kwargs):
                    raise sqlite3.InterfaceError("private-path-or-secret")
                def close(self):
                    pass
            with patch("src.sources.opencode_v1.sqlite3.connect", return_value=FailingConnection()):
                with self.assertRaises(SourceDataError) as caught:
                    source.inspect_schema()
            self.assertIn("InterfaceError", str(caught.exception))
            self.assertNotIn("private-path-or-secret", str(caught.exception))

    def test_mac_launcher_contracts(self):
        launchers = (
            ROOT / "macos/Cost Guard.command",
            ROOT / "macos/Cost Guard Watch.command",
            ROOT / "development/macos/Cost Guard Diagnostics.command",
        )
        for launcher in launchers:
            with self.subTest(launcher=launcher.name):
                content = launcher.read_text(encoding="utf-8")
                self.assertTrue(content.startswith("#!/bin/zsh"))
                self.assertIn("find_python()", content)
                self.assertIn("3.11", content)
                self.assertIn("CG_ROOT=", content)
        self.assertIn("--test-service-start", launchers[2].read_text(encoding="utf-8"))


class JsonResults(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.cases = []

    def startTest(self, test):
        super().startTest(test)
        self.cases.append({"id": test._testMethodName, "status": "PASS"})

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.cases[-1]["status"] = "FAIL"
        self.cases[-1]["error_type"] = err[0].__name__

    def addError(self, test, err):
        super().addError(test, err)
        self.cases[-1]["status"] = "ERROR"
        self.cases[-1]["error_type"] = err[0].__name__

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.cases[-1]["status"] = "SKIP"


def run_checks():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(MacCompatibilityChecks)
    result = JsonResults()
    suite.run(result)
    return {
        "mode": "simulated-macos-behavior",
        "native_macos_execution": False,
        "cases": result.cases,
        "passed": sum(x["status"] == "PASS" for x in result.cases),
        "failed": sum(x["status"] in ("FAIL", "ERROR") for x in result.cases),
        "skipped": sum(x["status"] == "SKIP" for x in result.cases),
        "ok": result.wasSuccessful(),
    }


if __name__ == "__main__":
    result = run_checks()
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result["ok"] else 1)
