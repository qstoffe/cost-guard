"""Server-first Sessions scope, fixed-clock epochs and measured hydration economy."""
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import time
import unittest
from unittest.mock import patch

from development.tests.fixtures.compact_reports import report_service
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from src.application.session_catalog import SessionCatalog, SORTS
from src.analysis.timezones import local_date_range
from src.reports.models import SessionUsageRow
from src.watch.observers import observe_catalog
from src.web.session_catalog import catalog_page

DAY = 86_400_000


def timestamp(text):
    return int(datetime.fromisoformat(text).replace(tzinfo=timezone.utc).timestamp() * 1000)


class SessionPeriodTests(unittest.TestCase):
    def setUp(self):
        self.now = timestamp("2026-11-13T12:00:00")
        self.clock = 0

    def catalog(self, activities, *, zone="UTC"):
        source = SyntheticMonthSource(len(activities), 1, month_start_ms=self.now - 730 * DAY)
        for (key, snapshot), activity in zip(tuple(source.snapshots.items()), activities):
            root = replace(snapshot.root, created_at_ms=min(activity, snapshot.root.created_at_ms),
                           updated_at_ms=activity)
            source.snapshots[key] = replace(snapshot, root=root, sessions=(root,), complete=True)
        catalog = SessionCatalog(clock=lambda: self.clock, clock_ms=lambda: self.now, timezone_id=zone)
        catalog.observe(observe_catalog(source, include_archived_revisions=True))
        return source, catalog

    def qualify(self, catalog):
        for index, (key, root) in enumerate(catalog.roots.items()):
            catalog.rows[key] = SessionUsageRow(key, root.title, "Model", False, Decimal(index), index,
                context_tokens=index, effort="High", effort_key="high")
            catalog.valid[key] = catalog.revisions[key], self.clock

    def test_cold_5000_root_sorts_hydrate_only_thirty_today_then_reuse_and_revise(self):
        activities = ([self.now - 1000] * 30 + [self.now - 3 * DAY] * 40 +
                      [self.now - 20 * DAY] * 50 + [self.now - (31 + index % 699) * DAY for index in range(4880)])
        evidence = []
        for sort in ("ccost", "effort", "ctx"):
            source, catalog = self.catalog(activities)
            service = report_service(self, source, now_ms=self.now)
            page = catalog_page(catalog, {"sort": sort})
            self.assertEqual((page["period"], page["total"], page["available"]), ("today", 30, 30))
            self.assertEqual(page["progress"]["total"], 30)
            self.assertEqual(len(catalog._targets()), 30)
            started, cpu = time.perf_counter(), time.process_time()
            with patch.object(service, "_analyze", wraps=service._analyze) as analyze:
                for _ in range(8):
                    catalog.tick(service)
                ready = catalog.page(token=page["token"], sort=sort)
                cold_reads = analyze.call_count
                self.assertEqual(cold_reads, 30)
                self.assertEqual({call.args[0].session_id for call in analyze.call_args_list},
                                 {f"root-{index:04d}" for index in range(30)})
                self.assertFalse(ready["pending_sort"])
                self.assertEqual(ready["indexed"], 30)
                self.assertEqual(source.load_count, 30)
                cold_seconds, cold_cpu = time.perf_counter() - started, time.process_time() - cpu
                analyze.reset_mock()
                warm = time.perf_counter()
                with patch.object(catalog, "_rows", wraps=catalog._rows) as rows:
                    for _ in range(10):
                        catalog.page(token=page["token"], sort=sort)
                    self.assertTrue(all(len(call.args[0]) <= 30 for call in rows.call_args_list))
                catalog.tick(service)
                self.assertEqual(analyze.call_count, 0)
                warm_seconds = time.perf_counter() - warm
                snapshot = source.snapshots["root-0000"]
                source.snapshots["root-0000"] = replace(snapshot, source_revision="revised-today")
                catalog.observe(observe_catalog(source, include_archived_revisions=True))
                revised = catalog.page(token=page["token"], sort=sort)
                self.assertEqual(revised["indexed"], 29)
                self.clock += 6
                catalog.tick(service)
                self.assertEqual(analyze.call_count, 1)
            for period, expected in (("7-days", 70), ("30-days", 120), ("all", 5000)):
                scoped = catalog.page(token=page["token"], period=period, sort=sort)
                self.assertEqual(scoped["total"], expected)
                self.assertEqual(scoped["progress"]["total"], expected)
                self.assertEqual(len(catalog._targets()), expected)
            evidence.append(dict(sort=sort, catalog_roots=5000, today_roots=30, cold_hydrations=cold_reads,
                cold_seconds=round(cold_seconds, 4), cold_cpu_seconds=round(cold_cpu, 4),
                warm_ten_polls_seconds=round(warm_seconds, 4), warm_hydrations=0, revised_hydrations=1,
                seven_day_targets=70, thirty_day_targets=120, all_time_targets=5000))
        print({"period_scope_measurements": evidence})

    def test_every_scope_sort_and_boundary_count_uses_twenty_five_row_pages(self):
        for total in (0, 1, 24, 25, 26, 50, 51):
            _, catalog = self.catalog([self.now - 1000] * total)
            self.qualify(catalog)
            for period in ("today", "7-days", "30-days", "month", "all"):
                for sort in SORTS:
                    with self.subTest(total=total, period=period, sort=sort):
                        page = catalog_page(catalog, dict(period=period, sort=sort, direction=1))
                        self.assertEqual((page["size"], page["total"]), (25, total))
                        ids = [row["session_id"] for row in page["view"]["session_usage"]]
                        self.assertEqual(len(ids), min(total, 25))
                        for offset in range(25, total, 25):
                            following = catalog_page(catalog, dict(token=page["token"], period=period,
                                sort=sort, direction=1, epoch=page["epoch"], offset=offset))
                            self.assertEqual(len(following["view"]["session_usage"]), min(25, total - offset))
                            ids.extend(row["session_id"] for row in following["view"]["session_usage"])
                        self.assertEqual(len(set(ids)), total)
                        catalog.interest(page["token"], False)
                        # Leases are bounded; this test has finished this browser.
                        catalog.leases.pop(page["token"])

    def test_half_open_bounds_missing_future_activity_and_child_last_activity(self):
        midnight = timestamp("2026-11-13T00:00:00")
        source, catalog = self.catalog([midnight - 1, midnight, self.now, self.now + 1, 0, self.now - DAY])
        root = source.snapshots["root-0005"]
        child = replace(root.root, session_id="child", parent_session_id=root.root.session_id,
                        created_at_ms=self.now - 2000, updated_at_ms=self.now - 1000)
        source.snapshots["root-0005"] = replace(root, sessions=(root.root, child))
        catalog.observe(observe_catalog(source, include_archived_revisions=True))
        page = catalog.page()
        self.assertEqual({row["session_id"] for row in page["view"]["session_usage"]},
                         {"root-0001", "root-0002", "root-0005"})
        all_time = catalog.page(token=page["token"], period="all")
        rows = {row["session_id"]: row for row in all_time["view"]["session_usage"]}
        self.assertEqual(len(rows), 6)
        self.assertIsNone(rows["root-0004"]["last_activity_ms"])
        self.assertIsNone(rows["root-0003"]["last_activity_ms"])
        self.assertEqual(rows["root-0005"]["last_activity_ms"], self.now - 1000)

    def test_stockholm_dst_day_month_year_and_exact_rolling_boundaries(self):
        for date, hours in (("2026-03-29", 23), ("2026-10-25", 25)):
            day = local_date_range(date, "Europe/Stockholm")
            self.assertEqual(day.end_ms - day.start_ms, hours * 3_600_000)
            self.now = day.end_ms - 1
            _, catalog = self.catalog([day.start_ms - 1, day.start_ms, self.now], zone="Europe/Stockholm")
            page = catalog.page()
            self.assertEqual(page["total"], 2)
            self.assertEqual(page["window"]["start_ms"], day.start_ms)
        self.now = timestamp("2026-12-31T23:30:00")
        midnight = timestamp("2026-12-31T23:00:00")
        _, catalog = self.catalog([midnight - 1, midnight], zone="Europe/Stockholm")
        for period in ("today", "month"):
            page = catalog.page(period=period)
            self.assertEqual(page["total"], 1)
            self.assertEqual(page["window"]["start_ms"], midnight)
        for days, period in ((7, "7-days"), (30, "30-days")):
            cutoff = self.now - days * DAY
            _, catalog = self.catalog([cutoff - 1, cutoff, self.now])
            self.assertEqual(catalog.page(period=period)["total"], 2)
            self.assertEqual(catalog.page(period=period)["window"]["start_ms"], cutoff)

    def test_rollover_and_source_arrivals_preserve_pinned_window_not_new_first_page(self):
        self.now = timestamp("2026-11-13T23:59:59")
        source, catalog = self.catalog([self.now - 1000] * 51)
        self.qualify(catalog)
        page = catalog.page()
        older = catalog.page(token=page["token"], offset=25, epoch=page["epoch"])
        self.now += 2000
        latest = catalog.page(token=page["token"])
        self.assertEqual(latest["total"], 0)
        self.assertNotEqual(latest["epoch"], older["epoch"])
        pinned = catalog.page(token=page["token"], offset=25, epoch=older["epoch"])
        self.assertEqual(pinned["window"], older["window"])
        self.assertEqual(pinned["total"], 51)
        self.assertEqual((pinned["indexed"], pinned["available"]), (51, 51))
        self.assertEqual([row["session_id"] for row in pinned["view"]["session_usage"]],
                         [row["session_id"] for row in older["view"]["session_usage"]])
        snapshot = source.snapshots["root-0000"]
        source.snapshots["root-0000"] = replace(snapshot, root=replace(snapshot.root, updated_at_ms=self.now),
                                               source_revision="new-day")
        catalog.observe(observe_catalog(source, include_archived_revisions=True))
        self.assertEqual(catalog.page(token=page["token"])["total"], 1)

    def test_period_and_direction_qualified_epochs_and_independent_lease_union(self):
        _, catalog = self.catalog([self.now - 1000] * 30 + [self.now - 3 * DAY] * 40)
        first = catalog.page(sort="ccost")
        self.assertEqual(len(catalog._targets()), 30)
        second = catalog.page(period="7-days", sort="effort")
        self.assertEqual(len(catalog._targets()), 70)
        catalog.interest(second["token"], False)
        self.assertEqual(len(catalog._targets()), 30)
        for request in (dict(period="all", offset=25, epoch=first["epoch"]),
                        dict(direction=1, offset=25, epoch=first["epoch"])):
            with self.assertRaisesRegex(KeyError, "catalog_expired"):
                catalog.page(token=first["token"], **request)
        scoped = catalog.page(token=first["token"], period="7-days", sort="ccost")
        self.assertEqual(scoped["offset"], 0)
        self.assertEqual(scoped["progress"]["total"], 70)
        self.qualify(catalog)
        all_time = catalog.page(period="all", sort="ctx")
        self.assertFalse(all_time["pending_sort"])
        self.assertEqual(len(catalog._targets()), 70)
        catalog.interest(all_time["token"], False)

    def test_default_today_validation_empty_scope_and_rolling_reconciliation(self):
        _, catalog = self.catalog([self.now - 8 * DAY])
        catalog.enable_warm()
        page = catalog_page(catalog, {})
        self.assertEqual((page["period"], page["total"]), ("today", 0))
        self.assertEqual(catalog._targets(), set(), "empty Today must not warm historical roots")
        for period in (None, "", "ALL", "yesterday", [], {}):
            with self.subTest(period=period), self.assertRaises(ValueError):
                catalog_page(catalog, {"period": period})
        with self.assertRaises(ValueError):
            catalog_page(catalog, {"offset": 24})
        _, catalog = self.catalog([self.now - 7 * DAY, self.now - 1000])
        rolling = catalog.page(period="7-days")
        self.now += 1
        latest = catalog.page(token=rolling["token"], period="7-days")
        self.assertEqual((rolling["total"], latest["total"]), (2, 1))
        self.assertNotEqual(rolling["epoch"], latest["epoch"])


if __name__ == "__main__":
    unittest.main()
