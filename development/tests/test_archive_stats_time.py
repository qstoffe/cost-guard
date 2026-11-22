"""Bounded Stats measured-time projection from local committed facts only."""
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from development.tests.fixtures.session_snapshots import one_request
from development.tests.test_archive_stats_evidence import capture
from src.analysis.ai_stats import windows
from src.application.archive_stats_time import ArchiveStatsTime
from src.cache.display_history import DisplayHistory, SessionChange, SessionFact
from src.cache.display_stats_evidence import StatsInterval
from src.cache.display_stats_time import StatsTimeRow
from src.cache.display_usage_reader import USAGE_SLICE


def utc(value):
    return int(datetime.fromisoformat(value + "+00:00").timestamp() * 1000)


class ArchiveStatsTimeTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.history = DisplayHistory(self.root)
        self.history.initialize()
        self.base = capture(one_request(running=False))

    def commit(self, intervals, *, source="bound", root="root", sequence=1):
        previous = f"r{sequence - 1}" if sequence > 1 else None
        roster = replace(self.base, stats=replace(self.base.stats, intervals=intervals))
        self.history.commit_sessions(source, (SessionChange(SessionFact(root, f"r{sequence}", root), previous,
            previous_progress=sequence - 1, request_roster=roster),))

    def reduce(self, now, *, source="bound", zone="UTC"):
        build = ArchiveStatsTime(source, zone, now)
        self.addCleanup(build.close)
        for turn in range(16):
            if not build.step(self.history, eligible=lambda: True):
                self.assertIsNotNone(build.publication)
                return build.publication, turn + 1
        self.fail("Measured geometry did not finish in its expected bounded turns")

    def test_bounded_union_includes_retained_geometry_after_source_disappearance_and_restart(self):
        intervals = tuple(StatsInterval("root", f"p{i}", "prompt", 1000 + 5 * i, 3, False)
                          for i in range(USAGE_SLICE + 2))
        intervals += (StatsInterval("child", "overlap", "prompt", 999, 9, False),
                      StatsInterval("root", "unmeasured", "prompt", 10, None, False),
                      StatsInterval("root", "running", "prompt", 10, 900, True))
        self.commit(intervals)
        self.commit((StatsInterval("root", "foreign", "prompt", 2, 900, False),), source="foreign")
        checkpoint = self.history.session_checkpoints("bound", ("root",))["root"]
        self.history.commit_sessions("bound", missing=(("root", checkpoint),))
        first = self.history.stats_geometry("bound")
        tail = self.history.stats_geometry("bound", expected=first.version, after=first.next_cursor)

        publication, turns = self.reduce(2000)
        reopened = DisplayHistory(self.root)
        reopened.initialize()
        cached = reopened.stats_time("bound", "UTC", "all", None, 2001)

        self.assertEqual(USAGE_SLICE, len(first.intervals))
        self.assertEqual(5, len(tail.intervals))
        self.assertIsNone(tail.next_cursor)
        self.assertEqual(5, turns)  # Two input and two sorted output slices, then one publish.
        self.assertEqual(StatsTimeRow("all", None, 393), cached.row)
        self.assertEqual(publication.stamp, cached.stamp)
        self.assertTrue(cached.current)
        self.assertIsNone(reopened.stats_time("foreign", "UTC", "all", None, 2001))

    def test_future_completion_and_dst_rollover_only_affect_eligible_scopes(self):
        zone = "Europe/Stockholm"
        midnight = utc("2026-10-24T22:00:00")
        next_midnight = utc("2026-10-25T23:00:00")  # Stockholm's 25-hour fall-back day.
        self.commit((StatsInterval("root", "measured", "prompt", midnight - 1000, 2000, False),
                     StatsInterval("root", "future", "compaction", next_midnight - 1000, 3000, False)))
        publication, _ = self.reduce(next_midnight - 1, zone=zone)
        today = self.history.stats_time("bound", zone, "today", midnight, next_midnight - 1)
        rolled = self.history.stats_time("bound", zone, "today", next_midnight, next_midnight)
        all_time = self.history.stats_time("bound", zone, "all", None, next_midnight)
        due_at_rollover = self.history.stats_time_due("bound", zone, windows(zone, next_midnight), next_midnight)
        second, _ = self.reduce(next_midnight, zone=zone)
        unknown = self.history.stats_time("bound", zone, "today", next_midnight, next_midnight)
        eligible = next_midnight + 2000
        due_for_end = self.history.stats_time_due("bound", zone, windows(zone, eligible), eligible)
        third, _ = self.reduce(eligible, zone=zone)
        final = self.history.stats_time("bound", zone, "today", next_midnight, eligible)

        self.assertEqual(1000, today.row.working_ms)
        self.assertEqual(eligible, publication.stamp.next_end)
        self.assertIsNone(rolled)
        self.assertEqual(2000, all_time.row.working_ms)
        self.assertTrue(due_at_rollover)
        self.assertEqual(("today", "7-days", "30-days"), second.changed_periods)
        self.assertIsNone(unknown.row.working_ms)
        self.assertTrue(due_for_end)
        self.assertIn("all", third.changed_periods)
        self.assertIsNone(third.stamp.next_end)
        self.assertEqual(2000, final.row.working_ms)

    def test_obsolete_correction_binding_and_clear_cannot_replace_a_committed_snapshot(self):
        old = StatsInterval("root", "measured", "prompt", 1000, 400, False)
        self.commit((old,))
        first, _ = self.reduce(2000)
        old_rows = tuple(StatsTimeRow(period, start, 400) for period, start in windows("UTC", 2000))
        self.commit((replace(old, duration_ms=600),), sequence=2)
        stale = self.history.stats_time("bound", "UTC", "all", None, 2000)
        obsolete = self.history.publish_stats_time("bound", first.stamp, old_rows, eligible=lambda: True)
        current = self.history.stats_geometry("bound").version
        changed_rows = tuple(replace(row, working_ms=600) for row in old_rows)
        allowed = iter((True, False))
        revoked = self.history.publish_stats_time("bound", replace(first.stamp, version=current),
                                                  changed_rows, eligible=lambda: next(allowed))
        retained = self.history.stats_time("bound", "UTC", "all", None, 2000)
        fresh, _ = self.reduce(2100)
        self.commit((old,), source="other")
        self.reduce(2100, source="other")
        self.history.clear_confirmed_sessions("bound", self.history.source_state("bound"))
        old_epoch = self.history.publish_stats_time("bound", fresh.stamp, changed_rows, eligible=lambda: True)

        self.assertFalse(stale.current)
        self.assertIsNone(obsolete)
        self.assertIsNone(revoked)
        self.assertEqual(stale, retained)
        self.assertIsNone(old_epoch)
        self.assertIsNone(self.history.stats_time("bound", "UTC", "all", None, 2100))
        self.assertEqual(400, self.history.stats_time("other", "UTC", "all", None, 2100).row.working_ms)

    def test_v19_upgrade_adds_projection_without_discarding_existing_geometry_or_pins(self):
        self.commit((StatsInterval("root", "old", "prompt", 1000, 250, False),))
        pin = self.history.stats_geometry("bound").version
        with self.history._connect() as db:
            db.execute("DROP INDEX archive_stats_geometry_cohort")
            db.execute("DROP TABLE archive_stats_time")
            db.execute("DROP TABLE archive_stats_time_state")
            db.execute("PRAGMA user_version=19")

        self.history = DisplayHistory(self.root)
        self.history.initialize()
        geometry = self.history.stats_geometry("bound", expected=pin)
        self.reduce(2000)

        self.assertEqual(pin, geometry.version)
        self.assertEqual(250, self.history.stats_time("bound", "UTC", "all", None, 2000).row.working_ms)
