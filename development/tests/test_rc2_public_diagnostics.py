from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace

from src.domain import TokenUsage
from src.analysis.token_mix import token_mix
from src.reports import ReportKind, ReportProjection
from src.version import DISPLAY_VERSION, RELEASE_DATE
from development.tools.collect_diagnostics import _projection_summary, _session_stats
from development.tools.validate_package import Results, check_lowercase_directories, check_public_hygiene

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
        results = Results()
        check_lowercase_directories(ROOT, results)
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
    def test_normal_launcher_keeps_powershell_open(self) -> None:
        text = (ROOT / "windows/Cost Guard.cmd").read_text(encoding="utf-8")
        self.assertIn("powershell.exe", text.lower())
        self.assertIn("-NoExit", text)
        self.assertIn("/b powershell.exe", text)
        self.assertIn("-Mode report", text)
        driver = (ROOT / "src/windows_launcher.ps1").read_text(encoding="utf-8")
        self.assertIn("cost-guard.py", driver)
        self.assertIn("sys.version_info >= (3,11)", driver)

    def test_watch_launcher_exits_batch_before_ctrl_c_path(self) -> None:
        text = (ROOT / "windows/Cost Guard Watch.cmd").read_text(encoding="utf-8")
        self.assertIn("powershell.exe", text.lower())
        self.assertIn("-Mode watch", text)
        self.assertIn("-NoExit", text)
        self.assertIn("/b powershell.exe", text)
        self.assertNotIn("Read-Host", text)
        self.assertLess(text.index('start "Cost Guard Watch"'), text.index("exit /b 0"))

    def test_diagnostics_launcher_is_double_clickable(self) -> None:
        text = (ROOT / "development/windows/Cost Guard Diagnostics.cmd").read_text(encoding="utf-8")
        self.assertIn('%~dp0..\\..\\src\\windows_launcher.ps1', text)
        self.assertIn("-Mode diagnostics", text)
        driver = (ROOT / "src/windows_launcher.ps1").read_text(encoding="utf-8")
        self.assertIn("development\\tools\\collect_diagnostics.py", driver)
        self.assertIn("--test-service-start", driver)
        self.assertIn("-NoExit", text)


class LauncherPlacementTests(unittest.TestCase):
    def test_public_folders_hold_only_everyday_launchers(self) -> None:
        self.assertEqual({"Cost Guard.cmd", "Cost Guard Watch.cmd"},
                         {path.name for path in (ROOT / "windows").iterdir()})
        self.assertEqual({"Cost Guard.command", "Cost Guard Watch.command"},
                         {path.name for path in (ROOT / "macos").iterdir()})

    def test_validator_rejects_diagnostics_launcher_in_public_folder(self) -> None:
        from development.tools.validate_package import check_required_layout

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "windows").mkdir()
            (root / "windows/Cost Guard Diagnostics.cmd").write_text("@echo off\n", encoding="utf-8")
            results = Results()
            check_required_layout(root, results)
            self.assertIn(("public launchers", "unexpected entry in user-facing launcher folder: windows/Cost Guard Diagnostics.cmd"),
                          results.failures)


class MacOSLauncherTests(unittest.TestCase):
    def test_macos_launchers_exist_are_executable_and_relative(self) -> None:
        expected = {
            "macos/Cost Guard.command": "cost-guard.py",
            "macos/Cost Guard Watch.command": "--watch",
            "development/macos/Cost Guard Diagnostics.command": "/development/tools/collect_diagnostics.py",
        }
        for name, needle in expected.items():
            path = ROOT / name
            self.assertTrue(path.is_file(), name)
            # Source filesystem mode is intentionally not asserted here: Python
            # ZIP extraction and Windows worktrees do not reliably preserve Unix
            # executable bits. The release-builder regression test verifies that
            # every packaged macOS .command entry is normalized to executable.
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("#!/bin/zsh"), name)
            self.assertIn('dirname "$0"', text, name)
            self.assertIn("sys.version_info >= (3,11)", text, name)
            self.assertIn(needle, text, name)
        watch = (ROOT / "macos/Cost Guard Watch.command").read_text(encoding="utf-8")
        self.assertIn('exec "$PYTHON"', watch)
        diagnostics = (ROOT / "development/macos/Cost Guard Diagnostics.command").read_text(encoding="utf-8")
        self.assertIn('CG_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"', diagnostics)


class DiagnosticBundleTests(unittest.TestCase):
    def test_service_start_diagnostic_records_existing_service_without_stopping_it(self) -> None:
        from unittest import mock
        from development.tools import collect_diagnostics as diag

        healthy = SimpleNamespace(available=True, healthy=True, detail="ok")
        source = SimpleNamespace(probe=lambda: healthy, diagnostic_metadata=lambda: {}, database_path="db", registration_path="service.json")
        selected = SimpleNamespace(selected="v2", warnings=(), selected_health=healthy, migration_gap=None)
        with mock.patch.object(diag, "OpenCodeV1Source", return_value=source), \
             mock.patch.object(diag, "OpenCodeV2Source", return_value=source), \
             mock.patch.object(diag, "_safe_source_stats", return_value={"probe": {"healthy": True}}), \
             mock.patch.object(diag, "SourceSelector") as selector, \
             mock.patch.object(diag, "_select_source") as wake:
            selector.return_value.select.return_value = selected
            result = diag.collect(network=False, snapshots=0, test_service_start=True)
        wake.assert_not_called()
        self.assertEqual("already_running", result["service_start_test"]["outcome"])
        self.assertEqual("v2", result["service_start_test"]["selected"])

    def test_service_start_diagnostic_exercises_cold_path_and_redacts_errors(self) -> None:
        from unittest import mock
        from development.tools import collect_diagnostics as diag

        unhealthy = SimpleNamespace(available=False, healthy=False, detail="missing")
        source = SimpleNamespace(probe=lambda: unhealthy, diagnostic_metadata=lambda: {}, database_path="db", registration_path="service.json")
        with mock.patch.object(diag, "OpenCodeV1Source", return_value=source), \
             mock.patch.object(diag, "OpenCodeV2Source", return_value=source), \
             mock.patch.object(diag, "_safe_source_stats", return_value={"probe": {"healthy": False}}), \
             mock.patch.object(diag, "SourceSelector") as selector, \
             mock.patch.object(diag, "_select_source", side_effect=RuntimeError("secret output")) as wake:
            selector.return_value.select.side_effect = RuntimeError("not ready")
            result = diag.collect(network=False, snapshots=0, test_service_start=True)
        wake.assert_called_once()
        self.assertEqual("failed", result["service_start_test"]["outcome"])
        self.assertEqual("RuntimeError", result["service_start_test"]["error_type"])
        self.assertNotIn("secret output", str(result["service_start_test"]))

    def test_projection_summary_uses_current_warning_fields(self) -> None:
        projection = ReportProjection(ReportKind.NORMAL, "Report", "V2",
            source_warnings=("source warning",), notes=("report note",), recent_model_notice=None, accounts_quotas=None,
            pricing_diagnostics={"current_price_fallback_requests": 1000},
            token_mix=token_mix((TokenUsage(input=10, cache_read=80, output=10),), sample_size=37),
        )
        summary = _projection_summary(projection)
        self.assertEqual(["source warning", "report note"], summary["warnings"])
        self.assertEqual("all-canonical-providers", summary["local_usage_provider_scope"])
        self.assertEqual(1000, summary["pricing"]["current_price_fallback_requests"])
        self.assertEqual({"sample_prompts": 37, "totals": (10, 80, 0, 10),
                          "percentages": (10, 80, 0, 10)}, summary["token_mix"])

    def test_session_stats_uses_canonical_tokens_and_never_requires_complete_flag(self) -> None:
        health = SimpleNamespace(available=True, healthy=True, detail="healthy")
        session = SimpleNamespace(
            session_id="session", parent_session_id=None, archived_at_ms=None,
            created_at_ms=1, updated_at_ms=2,
        )
        invocation = SimpleNamespace(
            model=SimpleNamespace(provider="openai", model="gpt-test"),
            tokens=TokenUsage(input=10, cache_read=20, cache_write=30, output=40, reasoning=0),
            completed_at_ms=3,
        )
        snapshot = SimpleNamespace(
            sessions=(session,), messages=(object(),), events=(object(),), invocations=(invocation,),
        )
        source = SimpleNamespace(
            probe=lambda: health,
            list_sessions=lambda: (session,),
            load_session_snapshot=lambda _session_id: snapshot,
        )
        stats = _session_stats(source, snapshots=1)
        sample = stats["snapshot_sample"][0]
        self.assertEqual(100, sample["token_total"])
        self.assertEqual(0, sample["reported_cost_observations"])
        self.assertEqual(0, sample["positive_reported_cost_observations"])
        self.assertEqual("0", sample["reported_cost_total"])
        self.assertEqual({"openai": 1}, sample["providers"])
        self.assertEqual(0, sample["running_invocations"])

    def test_no_network_bundle_is_zip_fail_soft_and_excludes_raw_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            proc = subprocess.run(
                [sys.executable, str(DIAG), "--no-network", "--snapshots", "0", "--skip-validation", "--output-dir", tmp],
                cwd=ROOT, env=env, capture_output=True, text=True, timeout=30,
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
            self.assertEqual(2, payload["schema_version"])
            self.assertIn("sources", payload)
            self.assertIn("v2", payload["sources"])
            self.assertNotIn("fatal", payload)
            self.assertNotIn("refresh_token", raw)
            self.assertNotIn("access_token", raw)
            self.assertNotIn("prompt_text", raw)


if __name__ == "__main__":
    unittest.main()
