"""Controlled-clock retention and lifecycle checks; never workstation logs or UI."""
import io
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch
from zipfile import ZipFile

from development.tools import collect_diagnostics as diagnostics
from development.tools.diagnostic_logs import create_bundle
from development.tools.validate_package import Results, check_required_layout, iter_package_files
from src import log_housekeeping as maintenance
from src.log_paths import file_lock, log_root
from src.runtime_errors import RuntimeErrors
from src.sources import connectivity_events
from src.watch import observation_diagnostics
from src.web.change_guard import SourceGuard
from src.web.host import WebHost

NOW = 1_800_000_000
CUTOFF = NOW - 30 * 86400


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        environment = patch.dict(os.environ, {"COST_GUARD_TEST_MODE": ""})
        environment.start()
        self.addCleanup(environment.stop)

    def file(self, relative, modified=CUTOFF - 60):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"owned fixture")
        os.utime(path, (modified, modified))
        return path

    def test_strict_30_day_mtime_boundary_in_all_roots_and_date_names_do_not_set_age(self):
        for base in ("logs/errors", "diagnostics", "development/logs/errors",
                     "development/logs/diagnostics"):
            with self.subTest(base=base):
                stem = "cost-guard-diagnostics-20000101-010101.zip" if base.endswith("diagnostics") else "cost-guard-errors-2000-01-01.log"
                old = self.file(f"{base}/{stem}")
                young = self.file(f"{base}/" + stem.replace("2000", "2001"), CUTOFF + 60)
                exact = self.file(f"{base}/" + stem.replace("2000", "2002"), CUTOFF)

                maintenance.prune_logs(self.root, now=NOW)

                self.assertFalse(old.exists())
                self.assertTrue(young.exists())
                self.assertTrue(exact.exists())

    def test_all_error_crash_recovery_event_layouts_and_empty_parents_are_removed(self):
        for base in ("logs", "diagnostics", "development/logs"):
            for folder, name in (("errors", "cost-guard-errors-2000-01-01.log"),
                                 ("crashes", "cost-guard-crash-20000101-010101-123.txt"),
                                 ("recovery", "cost-guard-metadata-2000-01-01.log")):
                self.file(f"{base}/{folder}/{name}")
        self.file("development/logs/diagnostics/cost-guard-diagnostics.zip")
        self.file("diagnostics/cost-guard-diagnostics.zip")

        maintenance.prune_logs(self.root, now=NOW)

        for name in ("logs", "diagnostics", "development/logs"):
            self.assertFalse((self.root / name).exists())
        self.assertTrue((self.root / "development").is_dir())

    def test_state_unknown_files_unexpected_children_custom_output_and_private_state_survive(self):
        paths = [self.file(name) for name in (
            "logs/recovery/model-metadata.json", "logs/recovery/watch-recovery.json",
            "development/logs/recovery/watch-observations.json",
            "development/logs/errors/my-notes.log",
            "development/logs/errors/unknown/cost-guard-errors-2000-01-01.log",
            "custom/cost-guard-diagnostics.zip", "private/logs/errors/cost-guard-errors-2000-01-01.log",
            "cache/state/model-metadata.json", "development/tools/keep.py",
            "development/logs/diagnostics/cost-guard-diagnostics.zip.123.456.incomplete")]

        maintenance.prune_logs(self.root, now=NOW)

        self.assertTrue(all(path.is_file() for path in paths))

    def test_directory_reparse_bit_and_nonregular_files_are_skipped(self):
        path = self.file("logs/errors/cost-guard-errors-2000-01-01.log")
        from src.log_paths import safe
        self.assertFalse(safe(type("Info", (), {"st_mode": 0o100644, "st_file_attributes": 0x400})()))
        directory = self.root / "diagnostics/cost-guard-diagnostics.zip"
        directory.mkdir(parents=True)
        maintenance.prune_logs(self.root, now=NOW)
        self.assertFalse(path.exists())
        self.assertTrue(directory.is_dir())

    def test_symlink_and_linked_ancestor_targets_survive(self):
        outside = self.file("outside/cost-guard-errors-2000-01-01.log")
        folder = self.root / "logs/errors"
        folder.mkdir(parents=True)
        link = folder / outside.name
        try:
            link.symlink_to(outside)
            (self.root / "development").symlink_to(self.root / "outside", target_is_directory=True)
        except OSError:
            self.skipTest("OS does not permit test symlink creation")

        maintenance.prune_logs(self.root, now=NOW)

        self.assertTrue(outside.is_file())
        self.assertTrue(link.is_symlink())

    @unittest.skipUnless(os.name == "nt", "Windows junction")
    def test_windows_junction_target_is_never_traversed(self):
        outside = self.file("outside/cost-guard-errors-2000-01-01.log")
        (self.root / "logs").mkdir()
        junction = self.root / "logs/errors"
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(outside.parent)],
                                capture_output=True, timeout=10)
        self.assertEqual(0, result.returncode)
        try:
            maintenance.prune_logs(self.root, now=NOW)
            self.assertTrue(outside.exists())
            self.assertTrue(junction.exists())
        finally:
            junction.rmdir()

    def test_replaced_or_changing_file_is_not_unlinked(self):
        path = self.file("logs/errors/cost-guard-errors-2000-01-01.log")
        original_open = maintenance.os.open
        def replace_before_open(name, *args, **kwargs):
            if str(name).endswith(path.name):
                path.unlink()
                path.write_text("replacement")
            return original_open(name, *args, **kwargs)
        with patch.object(maintenance.os, "open", side_effect=replace_before_open):
            maintenance.prune_logs(self.root, now=NOW)
        self.assertEqual("replacement", path.read_text())

    def test_writer_lock_and_permission_errors_are_quiet_and_not_retried(self):
        path = self.file("logs/errors/cost-guard-errors-2000-01-01.log")
        with path.open("r+b") as writer, file_lock(writer):
            maintenance.prune_logs(self.root, now=NOW)
        self.assertTrue(path.exists())
        with patch.object(maintenance, "_remove", side_effect=PermissionError) as remove:
            maintenance.prune_logs(self.root, now=NOW)
        self.assertEqual(1, remove.call_count)
        self.assertTrue(path.exists())
        maintenance.prune_logs(self.root, now=NOW)
        self.assertFalse(path.exists())

    def test_concurrent_pass_and_cancelled_pass_do_no_work(self):
        path = self.file("logs/errors/cost-guard-errors-2000-01-01.log")
        with maintenance._PASS_LOCK:
            maintenance.prune_logs(self.root, now=NOW)
        self.assertTrue(path.exists())
        stopping = threading.Event()
        stopping.set()
        maintenance.prune_logs(self.root, now=NOW, stopping=stopping)
        self.assertTrue(path.exists())

    def test_disabled_mode_and_bad_clock_never_touch_logs(self):
        path = self.file("logs/errors/cost-guard-errors-2000-01-01.log")
        with patch.dict(os.environ, {"COST_GUARD_TEST_MODE": "1"}):
            maintenance.prune_logs(self.root, now=NOW)
        maintenance.prune_logs(self.root, now=float("nan"))
        maintenance.prune_logs(self.root, now=NOW, budget_seconds=0)
        self.assertTrue(path.exists())

    def test_disappearing_file_is_quiet(self):
        self.file("logs/errors/cost-guard-errors-2000-01-01.log")
        with patch.object(maintenance, "_remove", side_effect=FileNotFoundError):
            maintenance.prune_logs(self.root, now=NOW)

    def test_current_day_log_is_protected_even_with_an_old_mtime(self):
        from datetime import datetime
        today = datetime.fromtimestamp(NOW).astimezone()
        path = self.file(f"development/logs/errors/cost-guard-errors-{today:%Y-%m-%d}.log")
        maintenance.prune_logs(self.root, now=NOW)
        self.assertTrue(path.exists())


class SchedulingTests(unittest.TestCase):
    def test_delayed_once_daily_attempt_after_failure_and_one_thread_only(self):
        waits = []
        def wait(seconds):
            waits.append(seconds)
            return len(waits) == 3
        prune = Mock(side_effect=PermissionError)
        worker = maintenance.LogHousekeeping(Path.cwd(), prune=prune)
        worker.stopping = Mock(is_set=lambda: False, wait=wait)
        worker._run()
        self.assertEqual([60, 86400, 86400], waits)
        self.assertEqual(2, prune.call_count)
        with patch.dict(os.environ, {"COST_GUARD_TEST_MODE": ""}), patch.object(maintenance, "Thread") as thread:
            owner = maintenance.LogHousekeeping(Path.cwd())
            owner.start()
            owner.start()
            self.assertEqual(1, thread.call_count)

    def test_cold_warm_web_readiness_never_waits_for_slow_directory_scanning(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"COST_GUARD_TEST_MODE": ""}):
            root = Path(tmp)
            for warm in (False, True):
                with self.subTest(warm=warm):
                    directory = log_root(root) / "errors"
                    directory.mkdir(parents=True, exist_ok=True)
                    for number in range(256):
                        path = directory / f"cost-guard-errors-2000-{number // 28 + 1:02}-{number % 28 + 1:02}.log"
                        path.write_text("old")
                        os.utime(path, (CUTOFF - 60,) * 2)
                    entered, release = threading.Event(), threading.Event()
                    scandir = maintenance.os.scandir
                    def slow_scan(*args, **kwargs):
                        entered.set()
                        release.wait(5)
                        return scandir(*args, **kwargs)
                    host = WebHost(root, jobs=Mock())
                    def prune(root, **kwargs):
                        maintenance.prune_logs(root, now=NOW, **kwargs)
                    host.log_housekeeping = maintenance.LogHousekeeping(root, delay=0, prune=prune)
                    with patch.object(maintenance.os, "scandir", side_effect=slow_scan):
                        start = time.monotonic()
                        host.publish_ready()
                        self.assertTrue(host.ready)
                        self.assertLess(time.monotonic() - start, 0.5)
                        self.assertTrue(entered.wait(2))
                        start = time.monotonic()
                        host.log_housekeeping.close()
                        self.assertLess(time.monotonic() - start, 0.5)
                        release.set()
                        host.log_housekeeping.thread.join(2)
                    self.assertFalse(host.log_housekeeping.thread.is_alive())

    def test_close_during_initial_delay_and_disabled_mode_create_no_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            worker = maintenance.LogHousekeeping(Path(tmp))
            with patch.dict(os.environ, {"COST_GUARD_TEST_MODE": ""}):
                worker.start()
                worker.close()
            self.assertFalse(worker.thread.is_alive())
            self.assertEqual([], list(Path(tmp).iterdir()))
            with patch.dict(os.environ, {"COST_GUARD_TEST_MODE": "1"}):
                other = maintenance.LogHousekeeping(Path(tmp))
                other.start()
            self.assertIsNone(other.thread)

    def test_runtime_boundary_never_runs_synchronous_cleanup_and_private_paths_are_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reporter = RuntimeErrors(root, stream=io.StringIO())
            with patch.object(reporter, "cleanup", side_effect=AssertionError("startup scan")):
                self.assertEqual(0, reporter.run(lambda: 0))
            private = RuntimeErrors(root / "private", private=True, mode="Web", stream=io.StringIO())
            private.fatal(TypeError())
            self.assertTrue(list((root / "private/logs/crashes").glob("*.txt")))
            self.assertFalse((root / "private/development").exists())
            private.usable()
            self.assertIsNone(private.housekeeping)

    def test_package_copy_and_working_view_exclude_the_entire_generated_tree(self):
        from development.tests.fixtures import package_copy
        from development.tools import validate_package
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "source"
            generated = log_root(root) / "errors/private.txt"
            generated.parent.mkdir(parents=True)
            generated.write_text("private")
            with patch.object(package_copy, "ROOT", root):
                copied = package_copy.copy_package(Path(tmp) / "copy")
            self.assertFalse(log_root(copied).exists())
            def inspect(view):
                self.assertFalse(log_root(view).exists())
                return Results()
            with patch.object(validate_package, "validate", side_effect=inspect):
                self.assertEqual(0, validate_package.main(["--root", str(root), "--working-tree"]))


class RoutingTests(unittest.TestCase):
    def test_legacy_watch_reads_then_writes_new_location_without_old_state_overriding_new(self):
        for module in (connectivity_events, observation_diagnostics):
            with self.subTest(module=module.__name__), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                name = module.FILE.name
                old = root / "logs/recovery" / name
                old.parent.mkdir(parents=True)
                old.write_text("[]")
                new = log_root(root) / "recovery" / name
                with patch.object(module, "FILE", new), patch.dict(os.environ, {"COST_GUARD_TEST_MODE": ""}):
                    self.assertEqual([], module.recent_events())
                    if module is connectivity_events:
                        module.record("v2", "recovered", "available")
                    else:
                        module.record_source_error("v2", "unavailable", object())
                    self.assertTrue(new.is_file())
                    self.assertEqual("[]", old.read_text())
                    new.write_text("[]")
                    self.assertEqual([], module.recent_events())

    def test_new_and_legacy_logs_are_exported_once_without_early_pruning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for base in (root / "logs", log_root(root)):
                path = base / "errors/cost-guard-errors-2000-01-01.log"
                path.parent.mkdir(parents=True)
                path.write_text("same")
            old_only = root / "logs/crashes/cost-guard-crash-20000101-010101-123.txt"
            old_only.parent.mkdir()
            old_only.write_text("legacy")
            target = log_root(root) / "diagnostics/cost-guard-diagnostics.zip"

            result = create_bundle(target, root=root, json_bytes=b"{}", text_bytes=b"ok")

            self.assertEqual(2, result["archived_logs"])
            self.assertEqual(0, result["removed_logs"])
            with ZipFile(target) as archive:
                self.assertEqual(1, list(archive.read(name) for name in archive.namelist()).count(b"same"))
                self.assertIn("logs/crashes/legacy-root/" + old_only.name, archive.namelist())
            self.assertTrue(old_only.exists())

    def test_default_diagnostics_path_and_explicit_override(self):
        from development.tests.test_diagnostics_ux import minimal_data
        for custom in (False, True):
            with tempfile.TemporaryDirectory() as tmp, patch.object(diagnostics, "ROOT", Path(tmp)), \
                    patch.object(diagnostics, "collect", return_value=minimal_data()), \
                    patch.object(diagnostics, "_support_email", return_value="support@example.invalid"), \
                    patch("sys.stdout", io.StringIO()):
                root = Path(tmp)
                args = []
                if custom:
                    args += ["--output-dir", str(root / "custom")]
                self.assertEqual(0, diagnostics.main(args))
                target = (root / "custom" if custom else log_root(root) / "diagnostics") / "cost-guard-diagnostics.zip"
                self.assertTrue(target.is_file())
                self.assertFalse((root / "logs").exists())
                self.assertFalse((root / "diagnostics").exists())

    def test_generated_tree_is_gitignored_not_source_and_rejected_in_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            guard = SourceGuard(root, interval=0)
            target = log_root(root) / "diagnostics/cost-guard-diagnostics.zip"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"private")
            results = Results()
            check_required_layout(root, results)
            self.assertIn(("runtime artifact", "generated development/logs must not ship"), results.failures)
            self.assertNotIn(target, list(iter_package_files(root)))
            self.assertEqual("unchanged", guard.check())
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run(["git", "check-ignore", "development/logs/diagnostics/cost-guard-diagnostics.zip"],
                                cwd=root, capture_output=True, text=True, timeout=10)
        self.assertEqual(0, result.returncode)


if __name__ == "__main__":
    unittest.main()
