"""Calendar consumer boundaries and source-counted immutable navigation."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import time
import unittest
from unittest.mock import patch

from development.tests.fixtures.compact_reports import report_service
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from src.analysis.ai_stats import windows
from src.analysis.timezones import local_date_range
from src.application.session_catalog import SessionCatalog
from src.reports import ReportKind, ReportRequest
from src.watch.observers import observe_catalog


class SessionsCalendarCacheTests(unittest.TestCase):
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
        self.assertFalse(first["pending_sort"])
        cold_ms = (time.perf_counter() - started) * 1000
        # Use real acquisition for the visited page, not all 5,000 histories.
        page = catalog.page(token=first["token"], offset=75, epoch=first["epoch"], period="7-days")
        for _ in range(7):
            catalog.tick(service)
        self.assertEqual(source.load_count, 25)
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
        self.assertEqual(source.load_count, 25)
        print(dict(roots=5000, cold_metadata_ms=round(cold_ms, 3), cold_metadata_hydrations=0,
                   page_four_hydrations=25, warm_unchanged_hydrations=0, elapsed_hours=4))

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
