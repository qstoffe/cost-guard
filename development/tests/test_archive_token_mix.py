"""Archive Token Mix covers physical usage, not causal or account totals."""
from contextlib import closing
from dataclasses import replace
from decimal import Decimal, localcontext
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from development.tests.fixtures.session_snapshots import make_snapshot
from src.analysis import analyze_snapshot
from src.analysis.timezones import local_day_start_ms
from src.analysis.token_mix import priced_token_mix
from src.application.archive_mix_build import ArchiveMixBuild, MixBuildState
from src.application.archive_mix_refresh import ArchiveMixRefresh
from src.application.archive_token_mix import ArchiveMixRollup
from src.application.request_archive_projection import request_roster
from src.cache.display_history import DisplayHistory, SessionChange, SessionFact
from src.cache.display_usage_reader import USAGE_SLICE
from src.domain import ModelRef, TokenUsage


class ArchiveTokenMixTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.history = DisplayHistory(self.root)
        self.history.initialize()

    def test_archive_rollup_matches_canonical_mix_and_keeps_independent_window_evidence(self):
        bundle = analyze_snapshot(make_snapshot(), now_ms=10_000)
        costs = (Decimal("0.01"), Decimal("0.02"), Decimal("0.03"), Decimal("0.04"))
        reference = SimpleNamespace(analysis_signature="previous-pricing",
                                    reference_category_valuation=lambda _model, _tokens: costs)
        roster = request_roster(make_snapshot(), bundle, reference)
        child = next(request for request in roster.requests if request.session_id == "child")
        today = local_day_start_ms("Europe/Stockholm", now_ms=1792899000000)
        now = today + 3_600_000
        # Two physical calls of one executing prompt, an independent undated
        # root, a fork replica, an unqualified legacy row, and a future clock.
        first = replace(child, key=b"1-child", clock_ms=today, tokens=(7, 3, 0, 5, 2), known=0b11111)
        second = replace(first, key=b"2-child", clock_ms=today + 1, known=0b11011,
                         tokens=(11, 5, 0, 4, 3), category_costs=None)
        undated = replace(first, key=b"3-undated", clock_ms=None, fork_key=None,
                          session_id="different-executor", tokens=(2, 0, 0, 1, 0), logical_prompt_id="cu")
        future = replace(first, key=b"4-future", clock_ms=now + 1, fork_key=None)
        unqualified = replace(first, key=b"5-legacy", clock_ms=today + 2, dedup_tree=None)
        fork = replace(first, key=b"6-fork", clock_ms=today - 1, dedup_tree="fork")
        self.history.commit_sessions("bound", (SessionChange(SessionFact("root", "r1", "Root"), None,
            previous_progress=0, request_roster=replace(roster, requests=(first, second, undated, future, unqualified),
                                                       attribution=())),))
        self.history.commit_sessions("bound", (SessionChange(SessionFact("fork", "r1", "Fork"), None,
            previous_progress=0, request_roster=replace(roster, requests=(fork,), attribution=())),))
        expected = priced_token_mix(((ModelRef("route", "model"), TokenUsage(7, 3, 0, 5, 2)),
            (ModelRef("route", "model"), TokenUsage(11, 5, 0, 4, 3, ("input", "cache_read", "output")))),
            lambda _model, tokens: costs if tokens.input == 7 else None, sample_size=1)
        reducer = ArchiveMixRollup("Europe/Stockholm", now, pricing="current-pricing")

        keys = reducer.add_slice(self.history.usage_inputs("bound"))
        with closing(sqlite3.connect(":memory:")) as db:
            db.execute("CREATE TABLE prompts(period, session, id, PRIMARY KEY(period, session, id)) WITHOUT ROWID")
            db.executemany("INSERT OR IGNORE INTO prompts VALUES(?,?,?)", (*keys, *keys))
            counts = dict(db.execute("SELECT period,count(*) FROM prompts GROUP BY period"))
        totals = {value.period: value for value in reducer.result(counts)}

        current, all_time = totals["today"], totals["all"]
        self.assertEqual(expected, current.mix)
        self.assertEqual((18, 8, 0, 14), current.observed)
        self.assertEqual((1, 1, 1), (current.unqualified_forks, current.undated_calls, current.stale_prices))
        self.assertEqual(2, all_time.mix.sample_size)  # Same prompt ID from another executing session.
        self.assertEqual(3, all_time.mix.request_count)
        self.assertEqual((20, 8, 0, 15), all_time.observed)
        self.assertIsNone(current.mix.total_tokens)  # One unknown cache-write makes every share unknown.

    def test_archive_value_is_exact_even_when_runtime_decimal_context_is_small(self):
        bundle = analyze_snapshot(make_snapshot(), now_ms=10_000)
        tiny = Decimal("0.00000000000000000000000000000000000017")
        reference = SimpleNamespace(analysis_signature="p1",
            reference_category_valuation=lambda _model, _tokens: (Decimal("123.45000017"), Decimal(0), Decimal(0), tiny))
        roster = request_roster(make_snapshot(), bundle, reference)
        child = next(request for request in roster.requests if request.session_id == "child")
        peer = replace(child, key=b"distinct", fork_key=None, category_costs=(tiny, Decimal(0), Decimal(0), tiny))
        self.history.commit_sessions("bound", (SessionChange(SessionFact("root", "r1", "Root"), None,
            previous_progress=0, request_roster=replace(roster, requests=(child, peer), attribution=())),))
        reducer = ArchiveMixRollup("UTC", 10_000)

        with localcontext() as context:
            context.prec = 6
            reducer.add_slice(self.history.usage_inputs("bound"))
            all_time = next(total for total in reducer.result({"all": 1}) if total.period == "all")

        self.assertEqual((Decimal("123.45000017000000000000000000000000000017"),
                          Decimal(0), Decimal(0), Decimal("0.00000000000000000000000000000000000034")),
                         all_time.mix.costs)

    def test_only_exact_reduction_commits_and_scoped_reads_use_previous_rows_during_correction(self):
        bundle = analyze_snapshot(make_snapshot(), now_ms=10_000)
        prices = (Decimal("0.12500000000000000004"), Decimal(0), Decimal(0), Decimal("0.5"))
        reference = SimpleNamespace(analysis_signature="p1", reference_category_valuation=lambda _m, _u: prices)
        roster = request_roster(make_snapshot(), bundle, reference)
        selected = next(request for request in roster.requests if request.session_id == "child")
        roster = replace(roster, requests=(selected,), attribution=())
        now = 10_000
        self.history.commit_sessions("bound", (SessionChange(SessionFact("root", "r1", "Root"), None,
            previous_progress=0, request_roster=roster),))
        original = self.history.usage_inputs("bound")
        reducer = ArchiveMixRollup("UTC", now)
        reducer.add_slice(original)
        rows = tuple(total.row() for total in reducer.result({"all": 1}))

        published = self.history.replace_mix_totals("bound", original.version, "UTC", rows)
        later = replace(selected, category_costs=(Decimal("0.5"), *prices[1:]))
        self.history.commit_sessions("bound", (SessionChange(SessionFact("root", "r2", "Root"), "r1",
            previous_progress=1, request_roster=replace(roster, requests=(later,))),))
        stale = self.history.replace_mix_totals("bound", original.version, "UTC", rows)
        saved = DisplayHistory(self.root).mix_total("bound", "UTC", "all", None, now)
        wrong_timezone = self.history.mix_total("bound", "Europe/Stockholm", "all", None, now)
        wrong_period_start = self.history.mix_total("bound", "UTC", "today", 1, now)
        future = self.history.mix_total("bound", "UTC", "all", None, now - 1)
        self.history.clear_confirmed_sessions("bound", self.history.source_state("bound"))
        purged = self.history.mix_total("bound", "UTC", "all", None, now)

        self.assertTrue(published)
        self.assertFalse(stale)
        self.assertEqual((1, prices, now), (saved[0].calls, saved[0].costs, saved[0].end_ms))
        self.assertFalse(saved[1])
        self.assertIsNone(wrong_timezone)
        self.assertIsNone(wrong_period_start)
        self.assertIsNone(future)
        self.assertIsNone(purged)

    def test_background_steps_deduplicate_prompt_keys_across_chunks_and_discard_a_mixed_revision(self):
        now = 10_000
        snapshot = make_snapshot()
        reference = SimpleNamespace(analysis_signature="p1",
                                    reference_category_valuation=lambda _model, _tokens: (Decimal("0.1"),) * 4)
        roster = request_roster(snapshot, analyze_snapshot(snapshot, now_ms=now), reference)
        child = next(request for request in roster.requests if request.session_id == "child")
        requests = tuple(replace(child, key=index.to_bytes(4, "big"), fork_key=None)
                         for index in range(USAGE_SLICE + 5))
        roster = replace(roster, requests=requests, attribution=())
        self.history.commit_sessions("bound", (SessionChange(SessionFact("root", "r1", "Root"), None,
            previous_progress=0, request_roster=roster),))

        with ArchiveMixBuild("bound", "UTC", now) as interrupted:
            first = interrupted.step(self.history)
            row = self.history.mix_total("bound", "UTC", "all", None, now)
            updated = replace(requests[-1], clock_ms=now + 10)
            self.history.commit_sessions("bound", (SessionChange(SessionFact("root", "r2", "Root"), "r1",
                previous_progress=1, request_roster=replace(roster, requests=(updated,))),))
            rejected = interrupted.step(self.history)
        with ArchiveMixBuild("bound", "UTC", now) as complete:
            resumed, finished = complete.step(self.history), complete.step(self.history)
        saved, current = self.history.mix_total("bound", "UTC", "all", None, now)

        self.assertEqual((MixBuildState.MORE, MixBuildState.STALE), (first, rejected))
        self.assertIsNone(row)
        self.assertEqual((MixBuildState.MORE, MixBuildState.PUBLISHED), (resumed, finished))
        self.assertEqual((1, USAGE_SLICE + 4), (saved.prompts, saved.calls))
        self.assertEqual((Decimal("13.2"),) * 4, saved.costs)
        self.assertTrue(current)

    def test_refresh_skips_writes_without_changes_and_detects_a_future_clock_becoming_eligible(self):
        now = 1_750_000_000_000
        snapshot = make_snapshot()
        price = SimpleNamespace(analysis_signature="p1", reference_category_valuation=lambda *_: None)
        roster = request_roster(snapshot, analyze_snapshot(snapshot, now_ms=10_000), price)
        request = replace(roster.requests[0], clock_ms=now + 90_000, fork_key=None)
        self.history.commit_sessions("bound", (SessionChange(SessionFact("root", "r1", "Root"), None,
            previous_progress=0, request_roster=replace(roster, requests=(request,), attribution=())),))
        clock = [0]
        refresh = ArchiveMixRefresh(clock=lambda: clock[0])

        self.assertFalse(refresh.due(None))
        original = refresh.advance(self.history, "bound", "UTC", "first", now, eligible=lambda: True)
        self.assertFalse(refresh.due("first"))
        clock[0] = 6
        no_change = refresh.advance(self.history, "bound", "UTC", "first", now + 6_000, eligible=lambda: True)
        clock[0] = 91
        available = refresh.advance(self.history, "bound", "UTC", "first", now + 91_000, eligible=lambda: True)
        saved, current = self.history.mix_total("bound", "UTC", "all", None, now + 91_000)
        refresh.withdraw()

        self.assertEqual({"today", "7-days", "30-days", "month", "all"}, set(original.changed_periods))
        self.assertIsNone(no_change)
        self.assertEqual(original.changed_periods, available.changed_periods)
        self.assertEqual(original.version, available.version)
        self.assertEqual((now + 91_000, 1, True), (saved.end_ms, saved.calls, current))
        self.assertFalse(refresh.due(None))

    def test_refresh_scopes_old_correction_and_recomputes_local_calendar_without_new_usage(self):
        now = local_day_start_ms("Europe/Stockholm", now_ms=1792899000000) + 1000
        snapshot = make_snapshot()
        price = SimpleNamespace(analysis_signature="p1", reference_category_valuation=lambda *_: None)
        roster = request_roster(snapshot, analyze_snapshot(snapshot, now_ms=10_000), price)
        request = replace(roster.requests[0], clock_ms=now - 40 * 86_400_000, fork_key=None)
        self.history.commit_sessions("bound", (SessionChange(SessionFact("root", "r1", "Root"), None,
            previous_progress=0, request_roster=replace(roster, requests=(request,), attribution=())),))
        refresh = ArchiveMixRefresh()
        initial = refresh.advance(self.history, "bound", "Europe/Stockholm", "one", now, eligible=lambda: True)
        self.history.commit_sessions("bound", (SessionChange(SessionFact("root", "r2", "Root"), "r1",
            previous_progress=1, request_roster=replace(roster, requests=(
                replace(request, tokens=(2, 0, 0, 3, 0), known=0b1111),), attribution=())),))

        corrected = refresh.advance(self.history, "bound", "Europe/Stockholm", "one", now + 6000, eligible=lambda: True)
        next_day = local_day_start_ms("Europe/Stockholm", now_ms=now, days_ago=-1)
        rolled = refresh.advance(self.history, "bound", "Europe/Stockholm", "one", next_day, eligible=lambda: True)
        refresh.withdraw()

        self.assertGreater(corrected.version.revision, initial.version.revision)
        self.assertEqual(("all",), corrected.changed_periods)
        self.assertEqual(corrected.version, rolled.version)
        self.assertEqual({"today", "7-days", "30-days"}, set(rolled.changed_periods))

    def test_mix_publication_rolls_back_if_eligibility_changes_inside_the_transaction(self):
        version = self.history.usage_inputs("bound").version
        reducer = ArchiveMixRollup("UTC", 10_000)
        rows = tuple(total.row() for total in reducer.result({}))
        decisions = iter((True, False))

        rejected = self.history.replace_mix_totals("bound", version, "UTC", rows,
                                                   eligible=lambda: next(decisions))
        saved = self.history.mix_total("bound", "UTC", "all", None, 10_000)

        self.assertIsNone(rejected)
        self.assertIsNone(saved)

    def test_pinned_summary_publishes_under_continuous_independent_appends(self):
        now = 10_000
        snapshot = make_snapshot()
        reference = SimpleNamespace(analysis_signature="p1", reference_category_valuation=lambda *_: None)
        roster = request_roster(snapshot, analyze_snapshot(snapshot, now_ms=now), reference)
        request = next(request for request in roster.requests if request.session_id == "child")
        original = tuple(replace(request, key=f"old-{i:04}".encode(), fork_key=None, dedup_tree=None)
                         for i in range(USAGE_SLICE * 2 + 1))

        def append(root, requests):
            self.history.commit_sessions("bound", (SessionChange(SessionFact(root, "r1", root), None,
                previous_progress=0, request_roster=replace(roster, requests=requests, attribution=())),))

        append("original", original)
        with ArchiveMixBuild("bound", "UTC", now) as build:
            first = build.step(self.history)
            append("next", (replace(original[0], key=b"z-after-key"),))
            second = build.step(self.history)
            append("another", (replace(original[0], key=b"a-before-key"),))
            finished = build.step(self.history)
        saved, current = self.history.mix_total("bound", "UTC", "all", None, now)
        with ArchiveMixBuild("bound", "UTC", now + 1) as next_build:
            followup = tuple(next_build.step(self.history) for _ in range(3))
        new, new_current = self.history.mix_total("bound", "UTC", "all", None, now + 1)

        self.assertEqual((MixBuildState.MORE, MixBuildState.MORE, MixBuildState.PUBLISHED),
                         (first, second, finished))
        self.assertEqual((1, len(original), False), (saved.prompts, saved.calls, current))
        self.assertEqual((MixBuildState.MORE, MixBuildState.MORE, MixBuildState.PUBLISHED), followup)
        self.assertEqual((1, len(original) + 2, True), (new.prompts, new.calls, new_current))
