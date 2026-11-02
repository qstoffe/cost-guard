"""Web-only card membership, canonical two-phase capture and bounded work."""
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import json
import tempfile
from threading import Event
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from development.tests.fixtures.watch_runtime import make_service
from src.application.live_projection import project_live
from src.reports import ReportKind, ReportRequest
from src.reports.watch_capture import WatchCapture, capture_rows, capture_totals
from src.watch.card_workers import CardResult, CardWorkers
from src.watch.cards import WatchCards
from src.watch.models import WatchProjection
from src.watch.observers import CatalogObservation
from src.watch.web_coordinator import WebWatchCoordinator
from src.watch.models import ToolObservation
from src.web.events import MAX_EVENT_BYTES
from src.sources.errors import SourceUnavailableError


class ManualWorkers:
    limit = 4

    def __init__(self):
        self.jobs = {}
        self.submissions = []

    def drain(self):
        return ()

    def submit(self, root, generation, now_ms, previous, focal_ids=()):
        self.jobs[root.session_id] = generation
        self.submissions.append(root.session_id)
        return True


class WatchCardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = SyntheticMonthSource(8, 8, month_start_ms=1000)
        _, _, self.service, _ = make_service(self.tmp.name, self.source, now_ms=100_000_000)
        self.roots = tuple(snapshot.root for snapshot in self.source.snapshots.values())
        self.capture, self.item = capture_rows(self.service, self.roots[0])

    def catalog(self, roots=None, active=(), revision="one"):
        roots = roots or self.roots
        return CatalogObservation(roots, roots, {root.session_id: root.session_id for root in roots},
            {root.session_id: revision for root in roots}, frozenset(active))

    def publish(self, cards, root, capture, now=1000, totals=None):
        entry = cards.sessions[root.session_id]
        capture = replace(capture, session_id=root.session_id, title=root.title)
        cards.accept(CardResult(root.session_id, entry.generation, "rows", (capture, (), None)), now)
        if totals is not None:
            cards.accept(CardResult(root.session_id, entry.generation, "totals", totals), now)

    def test_full_ten_thousand_prompt_totals_and_five_row_window_match_canonical(self):
        source = SyntheticMonthSource(1, 10000, month_start_ms=1000)
        _, _, service, _ = make_service(str(Path(self.tmp.name) / "large"), source, now_ms=100_000_000)
        root = source.snapshots["root-0000"].root
        recent, item = capture_rows(service, root)
        self.assertEqual(6, len(recent.rows), "one extra context anchor, never all history")
        total = capture_totals(service, item)
        expected = service.build(ReportRequest(ReportKind.SESSION, root.session_id)).prompt_blocks[0]
        self.assertEqual(expected.total_ccost, total.total_ccost)
        self.assertEqual(expected.duration_ms, total.duration_ms)
        self.assertEqual(10000, total.total_calls)
        self.assertEqual((), total.rows)
        cards = WatchCards(ManualWorkers())
        cards.catalog(self.catalog((root,)))
        self.publish(cards, root, recent, totals=total)
        active, history, state = cards.project(1000)
        self.assertEqual((), active)
        self.assertEqual(5, len(history[0].rows))
        self.assertEqual(9996, history[0].rows[0].prompt.prompt_number)
        self.assertGreater(history[0].totals.total_ccost, sum(row.prompt.ccost for row in history[0].rows))

    def test_historical_ranking_ignores_metadata_and_excludes_before_limit(self):
        cards = WatchCards(ManualWorkers())
        active_ids = [self.roots[0].session_id, self.roots[1].session_id]
        cards.catalog(self.catalog(active=active_ids))
        for index, root in enumerate(self.roots):
            capture = replace(self.capture, latest_ms=9000 - index)
            if index < 2:
                capture = replace(capture, rows=(replace(capture.rows[-1], in_progress=True),))
            self.publish(cards, root, capture)
        _, history, state = cards.project(2000)
        self.assertEqual([root.session_id for root in self.roots[2:7]], [card.session_id for card in history])
        self.assertEqual("observed", state)
        self.assertTrue(all(len(card.rows) == 5 for card in history))

    def test_one_hundred_concurrent_cards_focal_slices_order_and_shared_totals(self):
        root = self.roots[0]
        base = self.capture.rows[-1]
        rows = tuple(replace(base, event_id=f"p-{index:03}", at_ms=1000 + index,
            prompt_number=index + 1, in_progress=True) for index in range(100))
        capture = replace(self.capture, rows=rows, observed_at_ms=5000,
            observed_ids=frozenset(row.event_id for row in rows))
        total = replace(capture_totals(self.service, self.item), rate_provisional=True, duration_ms=4000)
        cards = WatchCards(ManualWorkers())
        cards.catalog(self.catalog((root,), active=(root.session_id,)))
        self.publish(cards, root, capture, totals=total)
        active, history, _ = cards.project(6000)
        self.assertEqual(100, len(active))
        self.assertEqual((), history)
        self.assertEqual(list(range(1, 101)), [card.rows[-1].prompt.prompt_number for card in active])
        self.assertTrue(all(len(card.rows) <= 5 for card in active))
        self.assertTrue(all(card.totals.duration_ms == 5000 for card in active), "overlap extends once, not 100 times")
        wire = project_live(WatchProjection("Watch", "fixture", (), now_ms=6000,
            active_cards=active, cards_state="observed")).to_json()
        self.assertEqual(100, len(wire["active_cards"]))
        self.assertLess(len(json.dumps(wire).encode()), MAX_EVENT_BYTES)
        self.assertRegex(wire["active_cards"][0]["rows"][0]["prompt"]["display"]["date_time"], r"^\d{4}-\d\d-\d\d \d\d:\d\d$")

    def test_observed_terminal_grace_restart_stale_results_and_removal(self):
        root = self.roots[0]
        base = replace(self.capture.rows[-1], event_id="p1", at_ms=100, in_progress=True)
        cards = WatchCards(ManualWorkers(), recent_seconds=30)
        cards.catalog(self.catalog((root,)))
        first = replace(self.capture, rows=(base,), latest_ms=100)
        self.publish(cards, root, first)
        terminal = replace(first, rows=(replace(base, in_progress=False, completed_successfully=True),))
        self.publish(cards, root, terminal, now=2000)
        self.assertEqual("✓", cards.project(31999)[0][0].rows[-1].marker)
        self.assertEqual((), cards.project(32000)[0])
        self.assertEqual(root.session_id, cards.project(32000)[1][0].session_id)
        new = replace(base, event_id="p2", at_ms=31000)
        self.publish(cards, root, replace(first, rows=(terminal.rows[0], new)), now=31000)
        self.assertEqual("p2", cards.project(99000)[0][0].focal_id)
        generation = cards.sessions[root.session_id].generation
        cards.catalog(self.catalog((root,), revision="changed"))
        cards.accept(CardResult(root.session_id, generation, "rows", (terminal, (), None)), 100000)
        self.assertEqual("p2", cards.project(100000)[0][0].focal_id)
        cards.catalog(self.catalog((self.roots[1],)))
        cards.accept(CardResult(root.session_id, generation, "rows", (first, (), None)), 100001)
        self.assertNotIn(root.session_id, cards.sessions)

    def test_startup_history_does_not_flash_and_scheduler_is_bounded_and_fair(self):
        workers = ManualWorkers()
        cards = WatchCards(workers)
        cards.catalog(self.catalog(active=[root.session_id for root in self.roots[:6]]))
        cards.tick(1000)
        self.assertEqual(4, len(workers.jobs))
        self.assertIn(self.roots[6].session_id, workers.submissions)
        cards = WatchCards(ManualWorkers())
        cards.catalog(self.catalog())
        for root in self.roots:
            self.publish(cards, root, self.capture)
        self.assertFalse(cards.project(1001)[0])
        self.assertTrue(all(not row.marker for card in cards.project(1001)[1] for row in card.rows))

    def test_concurrent_completion_keeps_its_own_grace_and_focal_acquisition_anchor(self):
        root = self.roots[0]
        rows = tuple(replace(self.capture.rows[-1], event_id=f"p-{index}", at_ms=1000 + index,
            in_progress=True) for index in range(10))
        capture = replace(self.capture, rows=rows)
        workers = ManualWorkers()
        cards = WatchCards(workers)
        cards.catalog(self.catalog((root,), active=(root.session_id,)))
        self.publish(cards, root, capture)
        terminal = replace(rows[0], in_progress=False, aborted=True)
        self.publish(cards, root, replace(capture, rows=(terminal,) + rows[1:]), now=2000)
        active = cards.project(2001)[0]
        self.assertEqual(10, len(active))
        self.assertEqual("!", active[0].rows[-1].marker)
        self.assertEqual(9, len(cards.project(32000)[0]))
        # The capture phase retains a focal older than the latest six prompts,
        # including its own four preceding context rows.
        recent, _ = capture_rows(self.service, root, focal_ids=(self.item.bundle.prompts[0].prompt_id,))
        self.assertIn(self.item.bundle.prompts[0].prompt_id, [row.event_id for row in recent.rows])

    def test_slow_full_aggregate_does_not_hold_rows_other_sessions_or_presentation(self):
        slow_started, release = Event(), Event()
        original = capture_totals
        def totals(service, item):
            if item.session.session_id == self.roots[0].session_id:
                slow_started.set()
                if not release.wait(10):
                    raise RuntimeError("test_release_missing")
            return original(service, item)
        def factory(now_ms):
            return make_service(str(Path(self.tmp.name) / uuid4().hex), self.source, now_ms=now_ms)[2]
        workers = CardWorkers(factory, workers=2)
        self.addCleanup(workers.close)
        self.addCleanup(release.set)
        with patch("src.watch.card_workers.capture_totals", side_effect=totals):
            workers.submit(self.roots[0], 1, self.service.now_ms)
            self.assertTrue(slow_started.wait(3))
            workers.submit(self.roots[1], 2, self.service.now_ms)
            results = []
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                results.extend(workers.drain())
                if any(result.session_id == self.roots[1].session_id and result.phase == "totals" for result in results):
                    break
                Event().wait(.01)
            self.assertTrue(any(result.generation == 1 and result.phase == "rows" for result in results))
            self.assertFalse(any(result.generation == 1 and result.phase == "totals" for result in results))
            self.assertTrue(any(result.generation == 2 and result.phase == "totals" for result in results))
            self.assertLessEqual(len(workers.jobs), 2)
            release.set()

    def test_focal_tool_threshold_elapsed_and_terminal_clearing_are_server_owned(self):
        root = self.roots[0]
        base = replace(self.capture.rows[-1], in_progress=True, event_id="focal", at_ms=1000)
        capture = replace(self.capture, rows=(base,), observed_at_ms=2000, observed_ids=frozenset({"focal"}))
        cards = WatchCards(ManualWorkers())
        cards.catalog(self.catalog((root,)))
        entry = cards.sessions[root.session_id]
        tool = ToolObservation(tool_counts=(("shell", 1),), running_tool="shell", running_ms=11000)
        cards.accept(CardResult(root.session_id, entry.generation, "rows", (capture, (("focal", tool),), None)), 2000)
        self.assertEqual("", cards.project(10999)[0][0].rows[-1].tool.running_tool)
        self.assertEqual("shell", cards.project(11000)[0][0].rows[-1].tool.running_tool)
        self.assertEqual(10000, cards.project(11000)[0][0].rows[-1].tool.running_ms)
        terminal = replace(capture, rows=(replace(base, in_progress=False),))
        cards.accept(CardResult(root.session_id, entry.generation, "rows", (terminal, (("focal", tool),), None)), 12000)
        self.assertEqual("", cards.project(12001)[0][0].rows[-1].tool.running_tool)
        self.assertEqual((("shell", 1),), cards.project(12001)[0][0].rows[-1].tool.tool_counts)

    def test_web_coordinator_hydration_does_not_borrow_live_service(self):
        config, selection, service, _ = make_service(str(Path(self.tmp.name) / "owner"), self.source)
        def factory(now_ms):
            return make_service(str(Path(self.tmp.name) / uuid4().hex), self.source, now_ms=now_ms)[2]
        owner = WebWatchCoordinator(selection=selection, report_service=service, config=config,
            service_factory=factory, clock_ms=lambda: 100_000_000)
        self.addCleanup(owner.close)
        with patch.object(service, "build_watch_root", side_effect=AssertionError("blocking hydration")):
            frame = owner.initialize(defer_history=True).projection
            self.assertEqual((), frame.rows)
            self.assertLessEqual(len(owner.card_workers.jobs), 4)
            self.assertFalse(owner.blocks)
            self.assertIsNotNone(owner.history_job)

    def test_isolated_factory_source_failure_is_local_not_a_host_fault(self):
        def unavailable(now_ms):
            raise SourceUnavailableError("private source details")
        workers = CardWorkers(unavailable, workers=1)
        self.addCleanup(workers.close)
        workers.submit(self.roots[0], 1, 1000)
        workers.jobs[self.roots[0].session_id].result(timeout=3)
        results = workers.drain()
        self.assertEqual(["unavailable", "timing"], [result.phase for result in results])
        self.assertFalse(workers.jobs)
        self.assertIsNone(results[0].value)

    def test_web_cadence_ema_measures_actual_capture_not_fast_catalog_admission(self):
        config, selection, service, _ = make_service(str(Path(self.tmp.name) / "cadence"), self.source)
        owner = WebWatchCoordinator(selection=selection, report_service=service,
            config=dict(config, sessionWatchIntervalSeconds="auto"), service_factory=lambda now: service)
        self.addCleanup(owner.close)
        owner._record_refresh_duration(1)
        owner._record_card_duration(3)
        self.assertAlmostEqual(2.2, owner._refresh_ema_seconds)
        owner._record_refresh_duration(.001)
        self.assertAlmostEqual(2.2, owner._refresh_ema_seconds)
        owner._record_card_duration(1)
        self.assertAlmostEqual(1.96, owner._refresh_ema_seconds)
        self.assertEqual(12, owner._delay_seconds(1))


if __name__ == "__main__":
    unittest.main()
