"""Calendar consumer boundaries and source-counted immutable navigation."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import time
import unittest
from unittest.mock import patch

from development.tests.fixtures.compact_reports import report_service
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from src.analysis.ai_stats import windows
from src.analysis.timezones import local_date_range
from src.application.session_catalog import SessionCatalog, ordered, sort_value
from src.reports.models import SessionUsageRow
from src.reports import ReportKind, ReportRequest
from src.watch.observers import observe_catalog


class SessionsCalendarCacheTests(unittest.TestCase):
    def test_running_cohort_scale_churn_and_verified_page_four_avoidance(self):
        now = 1_800_000_000_000
        for count in (1000, 5000):
            for live_count in (0, 10, 26):
                with self.subTest(roots=count, running=live_count):
                    source = SyntheticMonthSource(count, 1, month_start_ms=now - count * 60_000 - 1000,
                                                  running_roots=live_count)
                    source.snapshots = {key: replace(value, complete=True) for key, value in source.snapshots.items()}
                    clock = [0]
                    catalog = SessionCatalog(clock=lambda: clock[0], clock_ms=lambda: now)
                    catalog.observe(observe_catalog(source, include_archived_revisions=True))
                    service = report_service(self, source, now_ms=now)
                    catalog.tick(service)  # Dependencies only, before seeding/admission.
                    # Existing unchanged scalar cache: exact fixture event endpoints,
                    # not metadata guesses. Only running roots need fresh acquisition.
                    for index, (key, root) in enumerate(catalog.roots.items()):
                        if index < live_count:
                            continue
                        catalog.rows[key] = SessionUsageRow(key, root.title, "GPT Test", False, Decimal(0), 1,
                            last_activity_ms=source.snapshots[key].events[0].created_at_ms + 300)
                        catalog.valid[key] = catalog.revisions[key], clock[0]
                    first = catalog.page(period="all", sort="name", direction=-1)
                    for _ in range((live_count + 3) // 4):
                        catalog.tick(service)
                    ready = catalog.page(token=first["token"], period="all", sort="name", direction=-1)
                    self.assertFalse(ready["pending_sort"])
                    self.assertEqual(source.load_count, live_count)
                    expected = [f"root-{index:04d}" for index in range(live_count - 1, -1, -1)]
                    epoch = catalog.leases[first["token"]]["epochs"][ready["epoch"]]
                    self.assertEqual([row.session_id for row in epoch.rows[:live_count]], expected)
                    reads = source.load_count
                    started = time.perf_counter()
                    for _ in range(5):
                        catalog.page(token=first["token"], period="all", sort="name", direction=-1)
                        catalog.tick(service)
                    warm_ms = (time.perf_counter() - started) * 1000
                    self.assertEqual(source.load_count, reads)
                    for sequence in range(3):
                        for key in expected:
                            snapshot = source.snapshots[key]
                            source.snapshots[key] = replace(snapshot, source_revision=f"stream-{sequence}",
                                root=replace(snapshot.root, updated_at_ms=now - sequence))
                        clock[0] += 6
                        catalog.observe(observe_catalog(source, include_archived_revisions=True))
                        for _ in range((live_count + 3) // 4):
                            catalog.tick(service)
                        current = catalog.page(token=first["token"], period="all", sort="name", direction=-1)
                        current_epoch = catalog.leases[first["token"]]["epochs"][current["epoch"]]
                        self.assertEqual([row.session_id for row in current_epoch.rows[:live_count]], expected)
                        self.assertEqual(current["epoch"], ready["epoch"], "unchanged cohort does not drift")
                    churn_reads = source.load_count - reads
                    self.assertEqual(churn_reads, live_count * 3)
                    older = catalog.page(token=first["token"], offset=75, epoch=ready["epoch"],
                                         period="all", sort="name", direction=-1)
                    clock[0] += 6
                    before = source.load_count
                    catalog.tick(service)
                    revisit = catalog.page(token=first["token"], offset=75, epoch=ready["epoch"],
                                           period="all", sort="name", direction=-1)
                    self.assertEqual(older["view"]["session_usage"], revisit["view"]["session_usage"])
                    self.assertEqual(source.load_count, before, "verified finished-only pinned page excludes live cohort")
                    print(dict(roots=count, running=live_count, initial_running_reads=live_count,
                        warm_five_pages_ms=round(warm_ms, 3), warm_reads=0,
                        three_revision_waves_reads=churn_reads, warm_page_four_reads=0))

    def test_sort_values_are_extracted_once_with_stable_ties_and_unknowns_last(self):
        zero = SessionUsageRow("b", "Alpha", "Alpha", False, Decimal(0), 0,
            last_activity_ms=0, duration_ms=0, context_tokens=0, effort_key="none")
        high = replace(zero, session_id="c", title="Zulu", model="Zulu", ccost=Decimal("1.25"),
            prompt_count=9, last_activity_ms=99, duration_ms=999, context_tokens=99, effort_key="max")
        unknown = replace(high, session_id="e", model="N/A", complete=False, prompt_count=None,
            last_activity_ms=None, duration_ms=None, context_qualified=False, effort_key=None)
        rows = (unknown, zero, high, replace(unknown, session_id="d"), replace(zero, session_id="a"))
        for key in ("activity", "model", "ccost", "prompts", "duration", "ctx", "effort", "name"):
            for direction in (-1, 1):
                with self.subTest(key=key, direction=direction):
                    if key == "name":
                        expected = ["c", "d", "e", "a", "b"] if direction == -1 else ["a", "b", "c", "d", "e"]
                    else:
                        expected = ["c", "a", "b", "d", "e"] if direction == -1 else ["a", "b", "c", "d", "e"]
                    with patch("src.application.session_catalog.sort_value", wraps=sort_value) as extract:
                        result = ordered(rows, key, direction)
                    self.assertEqual([row.session_id for row in result], expected)
                    self.assertEqual(extract.call_count, len(rows))

    def test_shared_boundaries_across_dst_leap_month_year_and_timezone(self):
        for zone in ("Europe/Stockholm", "UTC"):
            for day in ("2026-03-29", "2026-10-25", "2024-02-29", "2027-01-01"):
                with self.subTest(zone=zone, day=day):
                    span = local_date_range(day, zone)
                    expected = {}
                    date = datetime.fromisoformat(day).date()
                    for period, ago in (("today", 0), ("7-days", 6), ("30-days", 29)):
                        expected[period] = local_date_range((date - timedelta(days=ago)).isoformat(), zone).start_ms
                    expected.update(month=local_date_range(date.replace(day=1).isoformat(), zone).start_ms, all=None)
                    for now in (span.start_ms, span.end_ms - 1):
                        self.assertEqual(dict(windows(zone, now)), expected)
                        source = SyntheticMonthSource(0, 1, month_start_ms=now)
                        service = report_service(self, source, now_ms=now, timezone_id=zone)
                        catalog = SessionCatalog(clock_ms=lambda: now, timezone_id=zone)
                        for period, start in expected.items():
                            self.assertEqual(catalog.page(period=period)["window"]["start_ms"], start)
                            report = service.build_token_mix_history(scope=period)
                            self.assertEqual(report.token_mix_period["start_ms"], start)
                        stats = service.build(ReportRequest(ReportKind.AI_STATS, stats_scope="30-days"))
                        self.assertEqual({item.period: item.start_ms for item in stats.ai_stats}, expected)
                    tomorrow = dict(windows(zone, span.end_ms))
                    self.assertEqual(tomorrow["today"], span.end_ms)
                    self.assertNotEqual(tomorrow["7-days"], expected["7-days"])

    def test_5000_root_metadata_and_warm_page_four_ignore_offscreen_running_age(self):
        now = int(datetime(2026, 11, 15, 12, tzinfo=timezone.utc).timestamp() * 1000)
        source = SyntheticMonthSource(5000, 1, month_start_ms=now - 5 * 86_400_000, running_roots=1)
        source.snapshots = {key: replace(value, complete=True) for key, value in source.snapshots.items()}
        clock = [0]
        catalog = SessionCatalog(clock=lambda: clock[0], clock_ms=lambda: now)
        catalog.observe(observe_catalog(source, include_archived_revisions=True))
        service = report_service(self, source, now_ms=now)
        started = time.perf_counter()
        first = catalog.page(period="7-days")
        self.assertEqual(source.load_count, 0)
        self.assertEqual(len(first["view"]["session_usage"]), 25)
        self.assertTrue(first["pending_sort"])
        self.assertTrue(first["membership_pending"])
        cold_ms = (time.perf_counter() - started) * 1000
        # Use real acquisition for the visited page, not all 5,000 histories.
        page = catalog.page(token=first["token"], offset=75, epoch=first["epoch"], period="7-days")
        self.assertEqual(page["order_state"], "provisional")
        for _ in range(7):
            catalog.tick(service)
        self.assertEqual(source.load_count, 26, "provisional pages must validate offscreen live hints")
        # Seed unchanged finished scalar facts to establish complete coverage.
        # Only the actual running root needed extra source acquisition.
        for key, root in catalog.roots.items():
            if key not in catalog.rows:
                catalog.rows[key] = SessionUsageRow(key, root.title, "GPT Test", False, Decimal(0), 1,
                    last_activity_ms=source.snapshots[key].events[0].created_at_ms + 300)
                catalog.valid[key] = catalog.revisions[key], clock[0]
        verified = catalog.page(token=first["token"], period="7-days")
        self.assertEqual(verified["order_state"], "verified")
        first = verified
        page = catalog.page(token=first["token"], offset=75, epoch=first["epoch"], period="7-days")
        original = [row["session_id"] for row in page["view"]["session_usage"]]
        running = "root-0000"
        for sequence in range(4):
            for _ in range(15):
                clock[0] += 240
                catalog.page(token=first["token"], offset=75, epoch=first["epoch"], period="7-days")
            clock[0] += 1
            snapshot = source.snapshots[running]
            source.snapshots[running] = replace(snapshot, source_revision=f"live-{sequence}",
                root=replace(snapshot.root, updated_at_ms=now - sequence))
            catalog.observe(observe_catalog(source, include_archived_revisions=True))
            # Renew the existing pinned epoch rather than pretending first-page arrivals never happened.
            warm = catalog.page(token=first["token"], offset=75, epoch=first["epoch"], period="7-days")
            self.assertEqual([row["session_id"] for row in warm["view"]["session_usage"]], original)
            self.assertEqual(warm["progress"]["completed"], 25)
            with patch.object(source, "load_session_snapshot", side_effect=AssertionError("unchanged warm history")):
                catalog.tick(service)
                for offset in (75, 100, 75):
                    catalog.page(token=first["token"], offset=offset, epoch=first["epoch"], period="7-days")
        self.assertEqual(source.load_count, 26)
        print(dict(roots=5000, cold_metadata_ms=round(cold_ms, 3), cold_metadata_hydrations=0,
                   page_four_hydrations=25, offscreen_running_validation=1,
                   warm_unchanged_hydrations=0, elapsed_hours=4))

    def test_cached_order_is_reused_and_changed_source_key_is_repaired_alone(self):
        now = int(datetime(2026, 11, 15, 12, tzinfo=timezone.utc).timestamp() * 1000)
        source = SyntheticMonthSource(100, 1, month_start_ms=now - 6_001_000)
        source.snapshots = {key: replace(value, complete=True) for key, value in source.snapshots.items()}
        clock = [0]
        catalog = SessionCatalog(clock=lambda: clock[0], clock_ms=lambda: now)
        service = report_service(self, source, now_ms=now)
        catalog.observe(observe_catalog(source, include_archived_revisions=True))
        first = catalog.page(sort="ccost", period="30-days")
        for _ in range(25):
            catalog.tick(service)
        ready = catalog.page(token=first["token"], sort="ccost", period="30-days")
        self.assertFalse(ready["pending_sort"])
        reads = source.load_count
        started = time.perf_counter()
        with patch("src.application.session_catalog.ordered", side_effect=AssertionError("warm re-sort")):
            for _ in range(5):
                catalog.page(token=first["token"], sort="ccost", period="30-days")
                catalog.page(token=first["token"], sort="ccost", period="30-days", offset=75, epoch=ready["epoch"])
                catalog.tick(service)
        self.assertEqual(source.load_count, reads)
        snapshot = source.snapshots["root-0000"]
        source.snapshots["root-0000"] = replace(snapshot, source_revision="changed")
        catalog.observe(observe_catalog(source, include_archived_revisions=True))
        clock[0] += 6
        pending = catalog.page(token=first["token"], sort="ccost", period="30-days")
        self.assertEqual(pending["progress"]["completed"], 99)
        catalog.tick(service)
        self.assertEqual(source.load_count, reads + 1)
        print(dict(warm_ten_pages_ms=round((time.perf_counter() - started) * 1000, 3),
                   unchanged_hydrations=0, changed_hydrations=1))
