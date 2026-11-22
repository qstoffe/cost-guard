"""The archive projection shares the existing background history lane."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from development.tests.fixtures.session_snapshots import make_snapshot
from src.analysis import analyze_snapshot
from src.application.request_archive_projection import request_roster
from src.cache.display_history import SessionChange, SessionFact
from src.cache.display_stats_evidence import StatsInterval
from src.cache.display_usage_reader import USAGE_SLICE
from src.pricing.catalog import PricingCatalog
from src.sources.opencode_v1 import OpenCodeV1Source
from src.watch.web_coordinator import WebWatchCoordinator
from src.web.display_archive import DisplayArchive


class WebMixRefreshTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node unavailable")
    def test_browser_coalesces_scoped_hints_and_withdraws_old_binding(self):
        completed = subprocess.run([shutil.which("node"), "development/tests/integration/cached_mix.cjs"],
            cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=10)
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)

    @unittest.skipUnless(shutil.which("node"), "node unavailable")
    def test_stats_browser_withdraws_pending_reads_at_period_binding_clear_or_auth_fences(self):
        completed = subprocess.run([shutil.which("node"), "development/tests/integration/cached_stats.cjs"],
            cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=10)
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)

    def test_existing_lane_interleaves_scalar_with_bounded_mix_and_notifies_after_commit(self):
        now = 1_750_000_000_000
        ready, release = Event(), Event()
        events = []
        with TemporaryDirectory() as tmp, ThreadPoolExecutor(max_workers=1) as lane:
            root = Path(tmp)
            identity = root / "synthetic-source.db"
            identity.write_bytes(b"not queryable source")
            selection = SimpleNamespace(selected="v1", source=OpenCodeV1Source(identity))
            service = SimpleNamespace(timezone_id="UTC", selection=selection)

            def publish(kind, hint):
                if kind == "token-mix-cache" and "periods" in hint:
                    events.append((hint, archive.history.mix_total(archive.views.source, "UTC", "all", None, now)))

            archive = DisplayArchive(root, publish, mix_enabled=True)
            archive.initialize()
            driver = SimpleNamespace(error=None, terminal=False, coordinator=SimpleNamespace(
                report_service=service, catalog_observation=None))
            archive.observe(driver, before_tick=True)
            snapshot = make_snapshot()
            prices = SimpleNamespace(analysis_signature="p1", reference_category_valuation=lambda *_: None)
            roster = request_roster(snapshot, analyze_snapshot(snapshot, now_ms=10_000), prices)
            request = roster.requests[0]
            requests = tuple(replace(request, key=i.to_bytes(4, "big"), fork_key=None)
                             for i in range(USAGE_SLICE + 1))
            archive.history.commit_sessions(archive.views.source, (SessionChange(SessionFact("root", "r1", "Root"),
                None, previous_progress=0, request_roster=replace(roster, requests=requests, attribution=())),))
            catalog = Mock(display_archive=archive)
            catalog.needed.return_value = True
            catalog.archive_running.return_value = ()
            order = []

            def scalar(*_):
                order.append("scalar")

            owner = SimpleNamespace(report_service=service, catalog_observation=None, cards=SimpleNamespace(sessions={}),
                catalog_job=None, clock_ms=lambda: now, _closed=False, catalog_pool=lane,
                catalog_turn=0, _catalog_history_turns=3, _catalog_capture=scalar)
            read = archive.history.usage_inputs

            def hold_first_slice(*args, **kwargs):
                order.append("mix")
                if not ready.is_set():
                    ready.set()
                    if not release.wait(5):
                        raise AssertionError("test failed to release the catalog lane")
                return read(*args, **kwargs)

            try:
                with patch.object(archive, "catalog_pending", return_value=False), \
                     patch.object(archive, "summary_pending", return_value=False), \
                     patch.object(archive, "coverage_pending", return_value=False), \
                     patch.object(archive, "publish_running"), \
                     patch.object(archive.history, "usage_inputs", side_effect=hold_first_slice):
                    WebWatchCoordinator.tick_catalog(owner, catalog)
                    self.assertTrue(ready.wait(3))
                    first = owner.catalog_job
                    WebWatchCoordinator.tick_catalog(owner, catalog)
                    self.assertIs(first, owner.catalog_job)
                    self.assertIsNone(archive.history.mix_total(archive.views.source, "UTC", "all", None, now))
                    release.set()
                    first.result(timeout=3)
                    for _ in range(4):
                        WebWatchCoordinator.tick_catalog(owner, catalog)
                        owner.catalog_job.result(timeout=3)
            finally:
                release.set()
                lane.submit(archive.close_catalog_work).result(timeout=5)
                archive.close()

        self.assertEqual(["mix", "scalar", "scalar", "scalar", "mix"], order)
        self.assertEqual(3, owner.catalog_turn)
        self.assertEqual(1, len(events))
        hint, (row, current) = events[0]
        self.assertEqual({"today", "7-days", "30-days", "month", "all"}, set(hint["periods"]))
        self.assertEqual((USAGE_SLICE + 1, True), (row.calls, current))

    def test_stats_and_mix_share_projection_turns_without_starving_catalog_acquisition(self):
        now = 1_750_000_000_000
        events, order = [], []
        with TemporaryDirectory() as tmp, ThreadPoolExecutor(max_workers=1) as lane:
            def publish(kind, hint):
                if kind == "ai-stats-cache" and "periods" in hint:
                    events.append((hint, archive.stats.snapshot("all", now)["measured_working_ms"]))

            archive = DisplayArchive(Path(tmp), publish, mix_enabled=True, stats_enabled=True)
            archive.initialize()
            archive._set_binding(SimpleNamespace(scope="local-fixture"))
            snapshot = make_snapshot()
            roster = request_roster(snapshot, analyze_snapshot(snapshot, now_ms=10_000), PricingCatalog(()), config={})
            request = roster.requests[0]
            requests = tuple(replace(request, key=i.to_bytes(4, "big"), fork_key=None)
                             for i in range(USAGE_SLICE + 1))
            intervals = tuple(StatsInterval("root", str(i), "prompt", now - 20_000 + 300 * i, 250, False)
                              for i in range(26))
            roster = replace(roster, requests=requests, attribution=(), stats=replace(roster.stats, intervals=intervals))
            archive.history.commit_sessions("local-fixture", (SessionChange(SessionFact("root", "r1", "Root"),
                None, previous_progress=0, request_roster=roster),))
            catalog = Mock(display_archive=archive)
            catalog.needed.return_value = True
            service = SimpleNamespace(timezone_id="UTC")
            owner = SimpleNamespace(report_service=service, catalog_observation=None, cards=SimpleNamespace(sessions={}),
                catalog_job=None, clock_ms=lambda: now, _closed=False, catalog_pool=lane,
                catalog_turn=0, _catalog_history_turns=3, _catalog_capture=lambda *_: order.append("scalar"))
            mix, stats = archive.advance_mix, archive.stats.advance

            def track(kind, action):
                def advance(*args, **kwargs):
                    order.append(kind)
                    action(*args, **kwargs)
                return advance

            try:
                with patch.object(archive, "catalog_pending", return_value=False), \
                     patch.object(archive, "summary_pending", return_value=False), \
                     patch.object(archive, "coverage_pending", return_value=False), \
                     patch.object(archive, "publish_running"), \
                     patch.object(archive, "advance_mix", side_effect=track("mix", mix)), \
                     patch.object(archive.stats, "advance", side_effect=track("stats", stats)):
                    for _ in range(17):
                        WebWatchCoordinator.tick_catalog(owner, catalog)
                        owner.catalog_job.result(timeout=3)
            finally:
                lane.submit(archive.close_catalog_work).result(timeout=5)
                archive.close()

        self.assertEqual(["mix", "stats", "mix", "stats", "stats"], order[::4])
        self.assertTrue(all(order[i:i + 3] == ["scalar"] * 3 for i in (1, 5, 9, 13)))
        self.assertEqual(1, len(events))
        hint, measured = events[0]
        self.assertEqual({"today", "7-days", "30-days", "month", "all"}, set(hint["marks"]))
        self.assertEqual(6500, measured)
