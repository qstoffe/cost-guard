"""Isolation, verification and safe pruning of owned Diagnostics logs."""
from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from development.tools.diagnostic_logs import create_bundle
from src.watch import recovery_events


class DiagnosticLogsTests(unittest.TestCase):
    def test_archive_and_prune_only_quiet_unchanged_owned_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "logs" / "errors"
            folder.mkdir(parents=True)
            old = folder / "cost-guard-errors-2026-10-08.log"
            old.write_text("Cost Guard: v80.16\n", encoding="utf-8")
            import os
            os.utime(old, (time.time() - 120, time.time() - 120))
            unowned = folder / "unrelated.log"
            unowned.write_text("do not touch", encoding="utf-8")
            bundle = root / "diagnostics" / "bundle.zip"
            report = create_bundle(bundle, root=root, json_bytes=b"{}", text_bytes=b"ok")
            self.assertEqual(1, report["archived_logs"])
            self.assertEqual(1, report["removed_logs"])
            self.assertFalse(old.exists())
            self.assertTrue(unowned.exists())
            with ZipFile(bundle) as archive:
                self.assertIn("logs/errors/cost-guard-errors-2026-10-08.log", archive.namelist())
                self.assertEqual(b"Cost Guard: v80.16\n", archive.read("logs/errors/cost-guard-errors-2026-10-08.log"))

    def test_recent_recovery_log_remains_after_archiving(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file = root / "logs" / "recovery" / "watch-recovery.json"
            file.parent.mkdir(parents=True)
            file.write_text("[]", encoding="utf-8")
            bundle = root / "diagnostics" / "bundle.zip"
            result = create_bundle(bundle, root=root, json_bytes=b"{}", text_bytes=b"ok")
            self.assertEqual(1, result["archived_logs"])
            self.assertEqual(0, result["removed_logs"])
            self.assertTrue(file.exists())

    def test_failed_zip_publishing_keeps_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file = root / "logs" / "errors" / "cost-guard-errors-2026-10-08.log"
            file.parent.mkdir(parents=True)
            file.write_text("important", encoding="utf-8")
            import os
            os.utime(file, (time.time() - 120, time.time() - 120))
            # Destination is a directory; atomic publish must fail.
            destination = root / "diagnostics" / "bundle.zip"
            destination.mkdir()
            with self.assertRaises(OSError):
                create_bundle(destination, root=root, json_bytes=b"{}", text_bytes=b"ok")
            self.assertTrue(file.exists())

    def test_single_latest_zip_replaces_old_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / "diagnostics" / "cost-guard-diagnostics.zip"
            destination.parent.mkdir()
            previous = destination.parent / "cost-guard-diagnostics-20261008-150806.zip"
            previous.write_bytes(b"previous")
            create_bundle(destination, root=root, json_bytes=b"{}", text_bytes=b"first")
            self.assertFalse(previous.exists())
            create_bundle(destination, root=root, json_bytes=b"{}", text_bytes=b"second")
            self.assertEqual([destination], list(destination.parent.glob("*.zip")))
            with ZipFile(destination) as archive:
                self.assertEqual(b"second", archive.read("summary.txt"))

    def test_test_mode_never_persists_recovery_events(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(recovery_events, "FILE", Path(tmp) / "record.json"), patch.dict("os.environ", {"COST_GUARD_TEST_MODE":"1"}):
            recovery_events.record("v2", "retrying", "unreadable")
            self.assertFalse((Path(tmp) / "record.json").exists())


if __name__ == "__main__":
    unittest.main()
