"""Full-catalog keys, cold indexing, retained epochs and scalar-cache boundaries."""
from dataclasses import replace
from decimal import Decimal
from threading import Event, Lock
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from development.tests.fixtures.compact_reports import report_service
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from development.tests.fixtures.watch_runtime import make_service
from src.application.session_catalog import SessionCatalog, SORTS
from src.reports.models import SessionUsageRow
from src.reports.session_summary import ALGORITHM, NAMESPACE, session_summary, summary_key
from src.watch.observers import observe_catalog
from src.web.session_catalog import catalog_page
from src.watch.web_coordinator import WebWatchCoordinator


class SessionCatalogTests(unittest.TestCase):
    def setUp(self):
        self.clock = 0
        self.source = SyntheticMonthSource(120, 1, month_start_ms=1000)
        self.service = report_service(self, self.source, now_ms=100_000_000)
        self.catalog = SessionCatalog(clock=lambda: self.clock)
        self.observe()

    def observe(self):
        self.catalog.observe(observe_catalog(self.source, include_archived_revisions=True))

    def index(self):
        for number, (key, root) in enumerate(self.catalog.roots.items()):
            self.catalog.rows[key] = SessionUsageRow(key, root.title, f"Model {number:03}", False,
                Decimal(number) / 1000, number, duration_ms=number * 1000,
                last_activity_ms=self.catalog.activity[key])
            self.catalog.valid[key] = self.catalog.revisions[key], self.clock

    def test_every_sort_orders_full_catalog_with_numeric_keys_and_stable_ties(self):
        self.index()
        for sort in SORTS:
            with self.subTest(sort=sort):
                page = self.catalog.page(sort=sort, direction=-1)
                self.assertFalse(page["pending_sort"])
                self.assertEqual(page["total"], 120)
                rows = page["view"]["session_usage"]
                self.assertEqual(len(rows), 50)
                self.assertEqual(rows[0]["session_id"], "root-0119")
                following = self.catalog.page(token=page["token"], offset=50, epoch=page["epoch"], sort=sort)
                ids = [row["session_id"] for row in rows + following["view"]["session_usage"]]
                self.assertEqual(len(set(ids)), 100)
                self.assertEqual(ids[50], "root-0069")

    def test_new_arrivals_keep_older_epoch_stable_and_page_one_live(self):
        self.index()
        page = self.catalog.page()
        second = self.catalog.page(token=page["token"], offset=50, epoch=page["epoch"])
        original = [row["session_id"] for row in second["view"]["session_usage"]]
        newer = SyntheticMonthSource(121, 1, month_start_ms=1000)
        self.catalog.observe(observe_catalog(newer, include_archived_revisions=True))
        retained = self.catalog.page(token=page["token"], offset=50, epoch=page["epoch"])
        self.assertEqual([row["session_id"] for row in retained["view"]["session_usage"]], original)
        self.assertEqual(retained["total"], 120)
        latest = self.catalog.page(token=page["token"])
        self.assertEqual(latest["total"], 121)
        self.assertEqual(latest["view"]["session_usage"][0]["session_id"], "root-0120")
        self.catalog.observe(None, unavailable=True)
        failed = self.catalog.page(token=page["token"])
        self.assertEqual(failed["total"], 121)
        self.assertEqual(failed["state"], "source_unavailable")

    def test_cold_pending_sort_warms_in_bounded_slices_and_revalidates(self):
        page = self.catalog.page(sort="ccost")
        self.assertTrue(page["pending_sort"])
        self.assertEqual(page["sort"], "activity")
        self.assertIsNone(page["view"]["session_usage"][0]["prompt_count"])
        for _ in range(30):
            before = self.source.load_count
            self.clock += 6
            self.catalog.tick(self.service)
            self.assertLessEqual(self.source.load_count - before, 4)
        ready = self.catalog.page(token=page["token"], sort="ccost")
        self.assertFalse(ready["pending_sort"])
        self.assertEqual(ready["indexed"], 120)
        snapshot = self.source.snapshots["root-0000"]
        self.source.snapshots["root-0000"] = replace(snapshot, source_revision="changed")
        self.observe()
        stale = self.catalog.page(token=page["token"], sort="ccost")
        self.assertTrue(stale["pending_sort"])
        self.assertEqual(stale["indexed"], 119)
        self.clock += 6
        self.catalog.tick(self.service)
        self.assertEqual(self.catalog.page(token=page["token"], sort="ccost")["indexed"], 120)

    def test_scalar_cache_reuse_without_history_hydration_and_active_bypass(self):
        root = next(iter(self.catalog.roots.values()))
        revision = self.catalog.revisions[root.session_id]
        row, actual = session_summary(self.service, root, revision)
        self.assertEqual(actual, revision)
        self.assertFalse(row.complete, "the fixture lacks complete-source proof, even with fully priced requests")
        with patch.object(self.service, "_analyze", side_effect=AssertionError("unexpected hydration")):
            cached, _ = session_summary(self.service, root, revision)
        self.assertEqual(cached, row)
        with patch.object(self.service, "_analyze", wraps=self.service._analyze) as acquire:
            session_summary(self.service, root, revision, active=True)
        self.assertTrue(acquire.call_args.kwargs["force_fresh"])

    def test_partial_unknown_metrics_are_indexed_but_sort_last_both_directions(self):
        self.index()
        key = "root-0119"
        self.catalog.rows[key] = replace(self.catalog.rows[key], complete=False, duration_ms=None)
        for sort in ("ccost", "duration"):
            for direction in (-1, 1):
                page = self.catalog.page(sort=sort, direction=direction)
                final = self.catalog.page(token=page["token"], offset=100, epoch=page["epoch"], sort=sort)
                self.assertEqual(final["view"]["session_usage"][-1]["session_id"], key)
                self.assertFalse(page["pending_sort"])

    def test_restart_reuses_scalar_cache_but_corruption_and_dependencies_miss(self):
        root = self.catalog.roots["root-0000"]
        revision = self.catalog.revisions[root.session_id]
        row, _ = session_summary(self.service, root, revision)
        restarted = report_service(self, self.source)
        restarted.cache_repository = self.service.cache_repository
        with patch.object(restarted, "_analyze", side_effect=AssertionError("unexpected history read")):
            self.assertEqual(session_summary(restarted, root, revision)[0], row)
        key = summary_key(restarted, root)
        for payload in ({}, {"ccost": "NaN"}, [], {"ccost": "0", "prompt_count": False}):
            restarted.cache_repository.put(NAMESPACE, key, payload,
                source_revision=revision, algorithm_version=ALGORITHM)
            with patch.object(restarted, "_analyze", wraps=restarted._analyze) as acquire:
                session_summary(restarted, root, revision)
            self.assertEqual(acquire.call_count, 1)
        with patch.object(restarted, "_dependencies", return_value=("changed-analysis-config",)):
            with patch.object(restarted, "_analyze", side_effect=RuntimeError("cache_miss")):
                with self.assertRaisesRegex(RuntimeError, "cache_miss"):
                    session_summary(restarted, root, revision)

    def test_idle_catalog_reuses_epoch_and_slice_stops_after_slow_root(self):
        first = self.catalog.page()
        self.assertEqual(self.catalog.page(token=first["token"])["epoch"], first["epoch"])
        def slow(service, root, revision, **kwargs):
            self.clock += 3
            return SessionUsageRow(root.session_id, root.title, "N/A", False, Decimal(0), 0), revision
        with patch("src.application.session_catalog.session_summary", side_effect=slow) as acquire:
            self.catalog.tick(self.service)
        self.assertEqual(acquire.call_count, 1)
        self.index()
        self.assertFalse(self.catalog.needed())
        self.clock += 61
        self.assertTrue(self.catalog.needed(), "dependencies must be revalidated even without changed roots")

    def test_source_identity_change_invalidates_keys_even_with_same_revision(self):
        self.index()
        snapshot = self.source.snapshots["root-0000"]
        moved = replace(snapshot.root, provenance=replace(snapshot.root.provenance, source_instance="new-source"))
        self.source.snapshots[moved.session_id] = replace(snapshot, root=moved, sessions=(moved,))
        self.observe()
        page = self.catalog.page(sort="ccost")
        self.assertTrue(page["pending_sort"])
        self.assertEqual(page["indexed"], 119)

    def test_blocked_catalog_worker_does_not_occupy_detail_or_http_lane(self):
        entered, released, captured = Event(), Event(), Event()
        with tempfile.TemporaryDirectory() as tmp:
            config, selection, service, _ = make_service(tmp, self.source)
            owner = WebWatchCoordinator(selection=selection, report_service=service, config=config,
                service_factory=lambda now: make_service(tmp, self.source, now_ms=now)[2])
            owner.catalog_observation = observe_catalog(self.source, include_archived_revisions=True)
            self.catalog.page()
            details = SimpleNamespace(lock=Lock(), leases={"owned": {}}, tick=lambda *args, **kwargs: captured.set())
            def blocked(service):
                entered.set()
                if not released.wait(3):
                    raise AssertionError("catalog test release missing")
            try:
                with patch.object(self.catalog, "tick", side_effect=blocked):
                    owner.tick_catalog(self.catalog)
                    self.assertTrue(entered.wait(1))
                    self.assertEqual(self.catalog.page()["total"], 120)
                    owner.tick_details(details)
                    self.assertTrue(captured.wait(1), "detail lane blocked behind catalog")
                    owner.detail_job.result(timeout=1)
                    self.assertFalse(owner.catalog_job.done())
                    released.set()
                    owner.catalog_job.result(timeout=1)
            finally:
                released.set()
                owner.close()

    def test_expired_epochs_invalid_requests_and_archived_membership(self):
        snapshot = self.source.snapshots["root-0000"]
        archived = replace(snapshot.root, archived_at_ms=2000)
        self.source.snapshots["root-0000"] = replace(snapshot, root=archived,
            sessions=(archived, *snapshot.sessions[1:]))
        self.observe()
        self.assertIn("root-0000", self.catalog.revisions)
        self.assertEqual(len(self.catalog.roots), 120)
        page = self.catalog.page()
        self.clock = 301
        with self.assertRaises(KeyError):
            self.catalog.page(token=page["token"], offset=50, epoch=page["epoch"])
        for request in ({"offset": True}, {"offset": 1}, {"direction": True}, {"sort": "raw"}, {"action": "scan"}):
            with self.subTest(request=request), self.assertRaises(ValueError):
                catalog_page(self.catalog, request)


if __name__ == "__main__":
    unittest.main()
