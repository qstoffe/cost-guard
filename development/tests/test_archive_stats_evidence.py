"""AI Stats timeline and response populations use exact root acquisition."""
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from development.tests.fixtures.session_snapshots import make_snapshot, one_request
from src.analysis import analyze_snapshot
from src.analysis.input_identity import fingerprint, first_input
from src.application.request_archive_projection import request_roster
from src.cache.display_history import ACQUIRED_SCALAR_FIELDS, DisplayHistory, SessionChange, SessionFact
from src.cache.display_stats_evidence import (ResponseTiming, StatsInterval, response_timings, stats_interval_page,
                                              stats_revision)
from src.cache.display_usage_reader import USAGE_SLICE
from src.pricing.catalog import PricingCatalog


def capture(snapshot):
    return request_roster(snapshot, analyze_snapshot(snapshot, now_ms=10_000), PricingCatalog(()), config={})


class ArchiveStatsEvidenceTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.history = DisplayHistory(self.root)
        self.history.initialize()

    def commit(self, previous, number, roster=None, *, source="trusted"):
        self.history.commit_sessions(source, (SessionChange(SessionFact("root", f"r{number}", "Root"),
            previous, ACQUIRED_SCALAR_FIELDS, "dependency", number - 1, request_roster=roster),))

    def test_timing_and_compaction_are_not_whole_message_wait_or_prompt_display_duration(self):
        snapshot = make_snapshot()
        roster = capture(snapshot)
        parent = next(request for request in roster.requests if request.clock_ms == 1500)
        child = next(request for request in roster.requests if request.session_id == "child")
        self.commit(None, 1, roster)

        with self.history._connect(read=True) as db:
            timings = response_timings(db, "trusted", (parent.key, child.key))
            geometry = stats_interval_page(db, "trusted", "root")
            unbound = response_timings(db, "other", (parent.key, child.key))

        self.assertEqual({parent.key: ResponseTiming(1100, 50), child.key: ResponseTiming(1230, 170)}, timings)
        self.assertIn(StatsInterval("root", "u_comp", "compaction", 3000, 300, False), geometry.intervals)
        self.assertTrue(any(interval.event == "u_sub" and interval.kind == "prompt" for interval in geometry.intervals))
        self.assertFalse(unbound)

    def test_missing_timing_preserves_as_of_but_explicit_failure_invalidates_same_completion(self):
        snapshot = one_request(running=False)
        original = capture(snapshot)
        request, = original.requests
        self.commit(None, 1, original)

        # A roster with no new timing can contribute independent physical facts
        # but must not erase the last confirmed response interval.
        uncertain = replace(original, requests=(replace(request, response=None),))
        self.commit("r1", 2, uncertain)
        with self.history._connect(read=True) as db:
            retained = response_timings(db, "trusted", (request.key,))
            before = stats_revision(db, "trusted")

        failed_snapshot = replace(snapshot, invocations=(
            replace(snapshot.invocations[0], error_name="fixture-private-error"),))
        failed = capture(failed_snapshot)
        self.commit("r2", 3, failed)
        with self.history._connect(read=True) as db:
            corrected = response_timings(db, "trusted", (request.key,))
            after = stats_revision(db, "trusted")
        shifted = replace(uncertain, requests=(replace(uncertain.requests[0], clock_ms=2400),))
        self.commit("r3", 4, shifted)
        with self.history._connect(read=True) as db:
            mismatched = response_timings(db, "trusted", (request.key,))

        self.assertEqual({request.key: ResponseTiming(2100, 200)}, retained)
        self.assertEqual({request.key: ResponseTiming(excluded=True)}, corrected)
        self.assertGreater(after, before)
        self.assertFalse(mismatched)

    def test_paged_geometry_survives_disappearance_but_clear_and_scalar_only_proof_are_distinct(self):
        roster = capture(one_request(running=False))
        linear = tuple(StatsInterval("root", f"t{i:03}", "prompt", 1000 + i, 3, False)
                       for i in range(USAGE_SLICE + 2))
        self.commit(None, 1)
        scalar_history = self.history.completed_sessions("trusted", {"root": "r1"}, "dependency", with_history=True)
        self.commit("r1", 2, replace(roster, stats=replace(roster.stats, intervals=linear)))
        self.commit(None, 1, roster, source="foreign")
        full_history = self.history.completed_sessions("trusted", {"root": "r2"}, "dependency", with_history=True)
        checkpoint = self.history.session_checkpoints("trusted", ("root",))["root"]
        self.history.commit_sessions("trusted", missing=(("root", checkpoint),))

        reopened = DisplayHistory(self.root)
        reopened.initialize()
        with reopened._connect(read=True) as db:
            first = stats_interval_page(db, "trusted", "root")
            last = stats_interval_page(db, "trusted", "root", first.next_cursor)
        reopened.clear_confirmed_sessions("trusted", reopened.source_state("trusted"))
        with reopened._connect(read=True) as db:
            cleared = stats_interval_page(db, "trusted", "root")
            foreign = stats_interval_page(db, "foreign", "root")

        self.assertFalse(scalar_history)
        self.assertEqual({"root"}, full_history)
        self.assertEqual(linear, (*first.intervals, *last.intervals))
        self.assertIsNone(last.next_cursor)
        self.assertFalse(cleared.intervals)
        self.assertTrue(foreign.intervals)

    def test_first_input_uses_only_a_digest_and_does_not_promote_a_later_prompt_after_deletion(self):
        snapshot = one_request(running=False)
        first = capture(snapshot)
        self.commit(None, 1, first)
        candidate = replace(first.stats.first_input, event="later", fingerprint=b"\xff" * 32, start_ms=4000)
        self.commit("r1", 2, replace(first, stats=replace(first.stats, first_input=candidate)))
        with self.history._connect(read=True) as db:
            kept = db.execute("""
                SELECT event_id,fingerprint,start_ms,duration_ms,status FROM archive_stats_first_inputs
                WHERE source='trusted' AND root_id='root'
            """).fetchone()
        correction = replace(first.stats.first_input, status="failed", duration_ms=None)
        self.commit("r2", 3, replace(first, stats=replace(first.stats, first_input=correction)))
        with self.history._connect(read=True) as db:
            corrected = db.execute("SELECT status FROM archive_stats_first_inputs WHERE source='trusted'").fetchone()[0]

        self.assertEqual(("u_next", bytes.fromhex(fingerprint(first_input(snapshot))), 2000, 300, "complete"), kept)
        self.assertEqual("failed", corrected)
