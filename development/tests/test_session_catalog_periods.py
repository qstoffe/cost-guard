"""Server-first Sessions scope, fixed-clock epochs and measured hydration economy."""
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import time
import unittest
from unittest.mock import patch

from development.tests.fixtures.compact_reports import report_service
from development.tests.fixtures.synthetic_month import SyntheticMonthSource, make_root_snapshot
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
        for index, ((key, snapshot), activity) in enumerate(zip(tuple(source.snapshots.items()), activities)):
            snapshot = make_root_snapshot(index, 1, month_start_ms=activity - 300 - index * 60_000)
            root = replace(snapshot.root, created_at_ms=min(activity, snapshot.root.created_at_ms),
                           updated_at_ms=activity)
            source.snapshots[key] = replace(snapshot, root=root, sessions=(root,), complete=True)
        catalog = SessionCatalog(clock=lambda: self.clock, clock_ms=lambda: self.now, timezone_id=zone)
        catalog.observe(observe_catalog(source, include_archived_revisions=True))
        return source, catalog

    def qualify(self, catalog):
        for index, (key, root) in enumerate(catalog.roots.items()):
            catalog.rows[key] = SessionUsageRow(key, root.title, "Model", False, Decimal(index), index,
                context_tokens=index, effort="High", effort_key="high",
                last_activity_ms=catalog.activity[key])
            catalog.valid[key] = catalog.revisions[key], self.clock
            catalog.activity_valid[key] = catalog.revisions[key]

    def test_cold_5000_root_sorts_hydrate_only_thirty_today_then_reuse_and_revise(self):
        activities = ([self.now - 1000] * 30 + [self.now - 3 * DAY] * 40 +
                      [self.now - 20 * DAY] * 50 + [self.now - (31 + index % 699) * DAY for index in range(4880)])
        evidence = []
        for sort in ("ccost", "prompts", "ctx"):
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

    def test_metadata_candidates_are_provisional_until_event_bounds_are_known(self):
        midnight = timestamp("2026-11-13T00:00:00")
        source, catalog = self.catalog([midnight - 1, midnight, self.now, self.now + 1, 0, self.now - DAY])
        root = source.snapshots["root-0005"]
        child = replace(root.root, session_id="child", parent_session_id=root.root.session_id,
                        created_at_ms=self.now - 2000, updated_at_ms=self.now - 1000)
        source.snapshots["root-0005"] = replace(root, sessions=(root.root, child))
        catalog.observe(observe_catalog(source, include_archived_revisions=True))
        page = catalog.page()
        self.assertEqual({row["session_id"] for row in page["view"]["session_usage"]},
                         {"root-0001", "root-0002", "root-0003", "root-0004", "root-0005"})
        self.assertTrue(page["membership_pending"])
        self.assertTrue(all(row["last_activity_ms"] is None for row in page["view"]["session_usage"]))
        self.qualify(catalog)
        # A child's metadata qualifies discovery only, not the displayed event.
        catalog.rows["root-0005"] = replace(catalog.rows["root-0005"], last_activity_ms=self.now - DAY)
        confirmed = catalog.page(token=page["token"])
        self.assertEqual({row["session_id"] for row in confirmed["view"]["session_usage"]},
                         {"root-0001", "root-0002"})
        all_time = catalog.page(token=page["token"], period="all")
        rows = {row["session_id"]: row for row in all_time["view"]["session_usage"]}
        self.assertEqual(len(rows), 6)
        self.assertIsNone(rows["root-0004"]["last_activity_ms"])
        self.assertIsNone(rows["root-0003"]["last_activity_ms"])
        self.assertEqual(rows["root-0005"]["last_activity_ms"], self.now - DAY)

    def test_passive_arrivals_keep_requested_order_and_qualified_running_priority(self):
        source, catalog = self.catalog([self.now - 1000] * 26)
        self.qualify(catalog)
        first = catalog.page(sort="ccost", direction=1)
        snapshot = make_root_snapshot(26, 1, month_start_ms=self.now - 26 * 60_000 - 1000)
        source.snapshots[snapshot.root.session_id] = snapshot
        catalog.observe(observe_catalog(source, include_archived_revisions=True))
        running = source.snapshots["root-0025"].root
        catalog.observe_prompts(((running, True, 0, "real-prompt", self.now - 100),))

        latest = catalog_page(catalog, dict(token=first["token"], passive=True))
        self.assertTrue(latest["pending_sort"])
        self.assertEqual(latest["view"]["session_usage"][0]["session_id"], "root-0025")
        arrival = latest["view"]["session_usage"][1]
        self.assertEqual((arrival["session_id"], arrival["title"], arrival["metric_state"]),
                         ("root-0026", snapshot.root.title, "pending"))
        self.assertIsNone(arrival["last_activity_ms"])
        frozen = catalog.page(token=first["token"], sort="ccost", direction=1,
                              offset=25, epoch=first["epoch"])
        self.assertEqual(frozen["total"], 26)
        self.assertEqual(frozen["view"]["session_usage"][0]["session_id"], "root-0025")
        for sort in SORTS:
            for direction in (-1, 1):
                page = catalog.page(token=first["token"], sort=sort, direction=direction, passive=True)
                self.assertEqual((page["sort"], page["direction"], page["offset"]), (sort, direction, 0))
                ids = [row["session_id"] for row in page["view"]["session_usage"]]
                self.assertEqual(ids[0], "root-0025")
                self.assertEqual(len(ids), 25)
                if (sort, direction) != ("activity", -1):
                    self.assertNotIn("root-0026", ids)
        self.assertEqual(source.load_count, 0, "passive pages and hints never acquire source history")

    def test_live_hint_deduplicates_publications_not_source_or_prompt_changes(self):
        source, catalog = self.catalog([self.now - 1000])
        hint = catalog.live_hint()
        for _ in range(10):
            catalog.observe(observe_catalog(source, include_archived_revisions=True))
        self.assertEqual(catalog.live_hint(), hint)
        root = source.snapshots["root-0000"].root
        catalog.observe_prompts(((root, True, 0, "", None),))
        self.assertEqual(catalog.live_hint(), hint, "active without a prompt is not running proof")
        catalog.observe_prompts(((root, True, 0, "prompt", self.now - 100),))
        running_hint = catalog.live_hint()
        self.assertNotEqual(running_hint, hint)
        self.clock += 1
        catalog.observe_prompts(((root, True, 0, "prompt", self.now - 100),))
        self.assertEqual(catalog.live_hint(), running_hint, "capture age is not a new prompt")
        catalog.observe_prompts(())
        self.assertNotEqual(catalog.live_hint(), running_hint)
        hint = catalog.live_hint()
        self.qualify(catalog)
        catalog.generation += 1  # Pricing/scalar work is deliberately not a wake source.
        self.assertEqual(catalog.live_hint(), hint)
        source.snapshots["root-0000"] = replace(source.snapshots["root-0000"], source_revision="changed")
        catalog.observe(observe_catalog(source, include_archived_revisions=True))
        self.assertNotEqual(catalog.live_hint(), hint)
        hint = catalog.live_hint()
        source.observation_epoch = "replacement-native-epoch"
        catalog.observe(observe_catalog(source, include_archived_revisions=True))
        self.assertNotEqual(catalog.live_hint(), hint)
        self.assertNotEqual(SessionCatalog().live_hint(), catalog.live_hint(), "owner replacement cannot alias hints")

    def test_passive_request_cannot_bypass_navigation_or_request_validation(self):
        _, catalog = self.catalog([self.now - 1000] * 26)
        for value in (dict(passive=1), dict(passive=True, navigation=1), dict(passive=True, offset=25)):
            with self.assertRaisesRegex(ValueError, "invalid_request"):
                catalog_page(catalog, value)
        first = catalog.page(sort="ccost", navigation=1)
        held = catalog.page(token=first["token"], sort="ccost", passive=True)
        self.assertFalse(held["passive"], "unacknowledged navigation still owns the lease")
        self.assertTrue(held["pending_sort"])

    def test_unresolved_issued_position_is_provisional_not_sort_or_membership_proof(self):
        source, catalog = self.catalog([self.now - 1000] * 26)
        self.qualify(catalog)
        first = catalog.page(sort="ccost", direction=1)
        original = [row["session_id"] for row in first["view"]["session_usage"]]
        source.snapshots["root-0000"] = replace(source.snapshots["root-0000"], source_revision="hot")
        catalog.observe(observe_catalog(source, include_archived_revisions=True))

        held = catalog.page(token=first["token"], sort="ccost", direction=1, passive=True)

        self.assertEqual([row["session_id"] for row in held["view"]["session_usage"]], original)
        self.assertEqual((held["indexed"], held["total"], held["order_state"]), (25, 26, "provisional"))
        self.assertEqual(held["view"]["session_usage"][0]["metric_states"]["ccost"], "retained")
        self.assertNotIn("snapshot_revision", held["view"]["session_usage"][0])
        catalog.rows["root-0000"] = replace(catalog.rows["root-0000"], ccost=Decimal(99))
        catalog.valid["root-0000"] = catalog.revisions["root-0000"], self.clock
        catalog.activity_valid["root-0000"] = catalog.revisions["root-0000"]
        ready = catalog.page(token=first["token"], sort="ccost", direction=1, passive=True)
        self.assertFalse(ready["pending_sort"])
        self.assertNotIn("root-0000", [row["session_id"] for row in ready["view"]["session_usage"]])
        self.assertEqual(source.load_count, 0)

    def test_old_position_never_overrides_retraction_exclusion_or_source_authority(self):
        for change in ("retraction", "period", "source", "provenance"):
            with self.subTest(change=change):
                source, catalog = self.catalog([self.now - 1000] * 26)
                self.qualify(catalog)
                first = catalog.page(sort="ccost", direction=1)
                snapshot = source.snapshots["root-0000"]
                if change == "retraction":
                    del source.snapshots["root-0000"]
                else:
                    if change == "source":
                        source.observation_epoch = "new-source"
                    if change == "provenance":
                        root = replace(snapshot.root, provenance=replace(snapshot.root.provenance, source_instance="new"))
                        snapshot = replace(snapshot, root=root, sessions=(root,))
                    source.snapshots["root-0000"] = replace(snapshot, source_revision="changed")
                catalog.observe(observe_catalog(source, include_archived_revisions=True))
                if change == "period":
                    catalog.rows["root-0000"] = replace(catalog.rows["root-0000"], last_activity_ms=self.now - 10 * DAY)
                    catalog.activity_valid["root-0000"] = catalog.revisions["root-0000"]
                page = catalog.page(token=first["token"], sort="ccost", direction=1, passive=True)
                self.assertNotIn("root-0000", [row["session_id"] for row in page["view"]["session_usage"]])

    def test_stockholm_dst_day_month_year_and_exact_calendar_boundaries(self):
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
            cutoff = timestamp("2026-12-31T00:00:00") - (days - 1) * DAY
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

    def test_default_today_validation_empty_scope_and_same_day_stability(self):
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
        cutoff = timestamp("2026-11-07T00:00:00")
        _, catalog = self.catalog([cutoff, self.now - 1000])
        rolling = catalog.page(period="7-days")
        self.now += 1
        latest = catalog.page(token=rolling["token"], period="7-days")
        self.assertEqual((rolling["total"], latest["total"]), (2, 2))
        self.assertEqual(rolling["epoch"], latest["epoch"])
        self.now = timestamp("2026-11-14T00:00:00")
        tomorrow = catalog.page(token=rolling["token"], period="7-days")
        self.assertEqual(tomorrow["total"], 1)
        self.assertNotEqual(rolling["epoch"], tomorrow["epoch"])


if __name__ == "__main__":
    unittest.main()
