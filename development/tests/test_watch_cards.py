"""Web-only one-row card membership, canonical capture and bounded work."""
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
from src.reports.watch_capture import capture_rows
from src.watch.card_workers import CardResult, CardWorkers
from src.watch.cards import WatchCards
from src.watch.models import WatchProjection
from src.watch.observers import CatalogObservation
from src.watch.web_coordinator import WebWatchCoordinator
from src.watch.models import ToolInvocation, ToolObservation
from src.web.events import MAX_EVENT_BYTES
from src.sources.errors import SourceUnavailableError, http_failure, transport_failure


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
        self.source.snapshots = {key: replace(value, complete=True) for key, value in self.source.snapshots.items()}
        _, _, self.service, _ = make_service(self.tmp.name, self.source, now_ms=100_000_000)
        self.roots = tuple(snapshot.root for snapshot in self.source.snapshots.values())
        self.capture, self.item = capture_rows(self.service, self.roots[0])

    def catalog(self, roots=None, active=(), revision="one"):
        roots = roots or self.roots
        return CatalogObservation(roots, roots, {root.session_id: root.session_id for root in roots},
            {root.session_id: revision for root in roots}, frozenset(active))

    def publish(self, cards, root, capture, now=1000):
        entry = cards.sessions[root.session_id]
        capture = replace(capture, session_id=root.session_id, title=root.title)
        cards.accept(CardResult(root.session_id, entry.generation, "rows", (capture, (), None)), now)

    def test_ten_thousand_prompt_history_keeps_one_latest_canonical_row_and_anchors(self):
        source = SyntheticMonthSource(1, 10000, month_start_ms=1000)
        source.snapshots = {key: replace(value, complete=True) for key, value in source.snapshots.items()}
        _, _, service, _ = make_service(str(Path(self.tmp.name) / "large"), source, now_ms=100_000_000)
        root = source.snapshots["root-0000"].root
        recent, item = capture_rows(service, root)
        self.assertEqual(6, len(recent.rows), "one extra context anchor, never all history")
        expected = service.build(ReportRequest(ReportKind.SESSION, root.session_id)).prompt_blocks[0]
        cards = WatchCards(ManualWorkers())
        cards.catalog(self.catalog((root,)))
        self.publish(cards, root, recent)
        active, history, state = cards.project(1000)
        self.assertEqual((), active)
        self.assertEqual(1, len(history[0].rows))
        actual = history[0].rows[0].prompt
        self.assertEqual(10000, actual.prompt_number)
        self.assertEqual((expected.rows[-1].ccost, expected.rows[-1].duration_ms), (actual.ccost, actual.duration_ms))

    def test_historical_ranking_ignores_metadata_and_excludes_before_limit(self):
        cards = WatchCards(ManualWorkers())
        active_ids = [self.roots[0].session_id, self.roots[1].session_id]
        cards.catalog(self.catalog(active=active_ids))
        for index, root in enumerate(self.roots):
            capture = replace(self.capture, latest_ms=9000 - index,
                rows=(replace(self.capture.rows[-1], at_ms=1000 + index, completed_at_ms=9000 - index),))
            if index < 2:
                capture = replace(capture, rows=(replace(capture.rows[-1], in_progress=True),))
            self.publish(cards, root, capture)
        _, history, state = cards.project(2000)
        self.assertEqual([root.session_id for root in reversed(self.roots[2:7])], [card.session_id for card in history])
        self.assertEqual("observed", state)
        self.assertTrue(all(len(card.rows) == 1 for card in history))

    def test_card_freshness_exports_capture_time_not_projection_or_cost_ticks(self):
        cards = WatchCards(ManualWorkers())
        cards.catalog(self.catalog((self.roots[0],)))
        self.publish(cards, self.roots[0], replace(self.capture, observed_at_ms=1234))

        first = cards.project(5000)[1][0]
        repeated = cards.project(9000)[1][0]
        wire = project_live(WatchProjection("Watch", "Synthetic", (), history_cards=(repeated,))).to_json()

        self.assertEqual(1234, first.observed_at_ms)
        self.assertEqual(1234, wire["history_cards"][0]["observed_at_ms"])
        self.publish(cards, self.roots[0], replace(self.capture, observed_at_ms=9999, retained=True))
        self.assertIsNone(cards.project(10000)[1][0].observed_at_ms)

    def test_history_supplies_five_after_running_and_terminal_grace_exclusions(self):
        cards = WatchCards(ManualWorkers())
        cards.catalog(self.catalog())
        for index, root in enumerate(self.roots):
            row = replace(self.capture.rows[-1], at_ms=1000 + index,
                completed_at_ms=9000 - index, in_progress=index < 3)
            self.publish(cards, root, replace(self.capture, rows=(row,), latest_ms=row.at_ms))
        terminal = replace(cards.sessions[self.roots[2].session_id].capture.rows[0],
            in_progress=False, completed_at_ms=10000)
        self.publish(cards, self.roots[2], replace(self.capture, rows=(terminal,), latest_ms=terminal.at_ms), now=2000)

        active, history, state = cards.project(2001)

        self.assertEqual("observed", state)
        self.assertEqual(3, len(active))
        self.assertEqual([root.session_id for root in reversed(self.roots[3:])], [card.session_id for card in history])
        self.assertTrue(set(card.session_id for card in active).isdisjoint(card.session_id for card in history))

    def test_history_reorders_selected_set_by_displayed_prompt_with_stable_ties(self):
        cards = WatchCards(ManualWorkers())
        cards.catalog(self.catalog())
        for index, root in enumerate(self.roots):
            row = replace(self.capture.rows[-1], at_ms=1000 + index, completed_at_ms=2000 + index // 2)
            self.publish(cards, root, replace(self.capture, rows=(row,), latest_ms=row.at_ms))
        expected = [root.session_id for root in self.roots[2:3] + self.roots[4:]]
        self.assertEqual(expected, [card.session_id for card in cards.project(2000)[1]])
        cards.catalog(self.catalog(tuple(reversed(self.roots))))
        self.assertEqual(expected, [card.session_id for card in cards.project(2001)[1]])
        root = self.roots[0]
        row = replace(self.capture.rows[-1], at_ms=2000, in_progress=True)
        self.publish(cards, root, replace(self.capture, rows=(row,), latest_ms=2000))
        self.assertNotIn(root.session_id, [card.session_id for card in cards.project(2002)[1]])
        self.publish(cards, root, replace(self.capture, rows=(replace(row, in_progress=False, completed_at_ms=3000),), latest_ms=2000), now=2003)
        self.assertEqual(root.session_id, cards.project(32003)[1][-1].session_id)

    def test_latest_finish_outside_recent_start_slice_keeps_its_exact_prompt(self):
        root = self.roots[0]
        snapshot = self.source.snapshots[root.session_id]
        first = snapshot.invocations[0]
        self.source.snapshots[root.session_id] = replace(snapshot,
            messages=tuple(replace(message, completed_at_ms=99000) if message.message_id == first.message_id else message
                for message in snapshot.messages),
            invocations=(replace(first, completed_at_ms=99000),) + snapshot.invocations[1:])

        capture, _ = capture_rows(self.service, root)
        cards = WatchCards(ManualWorkers())
        cards.catalog(self.catalog((root,)))
        self.publish(cards, root, capture)
        row = cards.project(100000)[1][0].rows[0].prompt

        self.assertEqual((1, first.initiating_event_id, 99000, 'prompt 0-0'),
            (row.prompt_number, row.event_id, row.completed_at_ms, row.preview))
        self.assertEqual(capture.rows[0].ccost, row.ccost)
        self.assertFalse(row.in_progress)

    def test_unknown_history_fills_spare_slots_without_displacing_known_finishes(self):
        cards = WatchCards(ManualWorkers())
        cards.catalog(self.catalog())
        for index, root in enumerate(self.roots):
            row = replace(self.capture.rows[-1], completed_at_ms=None if index < 4 else 10000 - index,
                completed_successfully=index >= 4, at_ms=9000 + index)
            self.publish(cards, root, replace(self.capture, rows=(row,), latest_ms=row.at_ms))

        history = cards.project(20000)[1]

        self.assertEqual([self.roots[index].session_id for index in (0, 7, 6, 5, 4)],
            [card.session_id for card in history])
        unknown = history[0].rows[0].prompt
        self.assertIsNone(unknown.completed_at_ms)
        self.assertFalse(unknown.completed_successfully)
        # Timestamp ties use event identity, never a different start-selected row.
        a = replace(unknown, event_id='a', completed_at_ms=20000, at_ms=15000)
        z = replace(unknown, event_id='z', completed_at_ms=20000, at_ms=1000)
        self.publish(cards, self.roots[1], replace(self.capture, rows=(z, a)))
        self.assertEqual('z', cards.project(20001)[1][-1].rows[0].prompt.event_id)

    def test_retryable_card_failure_retains_rows_confirms_once_and_requires_success(self):
        clock = [0.0]
        cards = WatchCards(ManualWorkers(), monotonic=lambda: clock[0])
        root = self.roots[0]
        cards.catalog(self.catalog((root,)))
        capture = replace(self.capture, rows=(replace(self.capture.rows[-1], in_progress=True),))
        self.publish(cards, root, capture)
        entry = cards.sessions[root.session_id]
        failure = CardResult(root.session_id, entry.generation, 'unavailable', transport_failure(TimeoutError(), phase='capture'))

        cards.accept(failure, 1001)
        first = cards.project(1002)[0][0]
        self.assertEqual('retrying', first.state)
        self.assertEqual(capture.rows[-1].ccost, first.rows[-1].prompt.ccost)
        clock[0] = 4.9
        cards.accept(failure, 1003)
        self.assertEqual('retrying', cards.project(1004)[0][0].state)
        clock[0] = 5.0
        self.assertEqual('unavailable', cards.project(1005)[0][0].state)
        self.assertEqual(first.rows, cards.project(1005)[0][0].rows, 'retained running duration is not freshened')
        self.publish(cards, root, replace(capture, retained=True), now=1006)
        self.assertEqual('unavailable', cards.project(1007)[0][0].state, 'retained publication is not recovery')
        self.publish(cards, root, capture, now=1008)
        self.assertEqual('observed', cards.project(1009)[0][0].state)
        cards.accept(CardResult(root.session_id, entry.generation, 'unavailable', http_failure(401, phase='capture')), 1010)
        self.assertEqual('unavailable', cards.project(1011)[0][0].state, 'authentication has no grace')

    def test_invocation_clears_during_source_revision_reverification(self):
        root = self.roots[0]
        row = replace(self.capture.rows[-1], in_progress=True, background_kinds=('shell', 'shell'))
        capture = replace(self.capture, rows=(row,), observed_ids=frozenset({row.event_id}), observed_at_ms=1000)
        cards = WatchCards(ManualWorkers())
        cards.catalog(self.catalog((root,), active=(root.session_id,)))
        self.publish(cards, root, capture)
        entry = cards.sessions[root.session_id]
        detail = ToolInvocation("physical", "revision", 'command:\npython tokenizer.py --mode=fast\n\ntimeout:\n120000 ms (2 min)', '')
        entry.tools[row.event_id] = ToolObservation(running_tool="shell", running_ms=30_000,
            running_invocation=detail, background_invocation=detail,
            running_invocations=(detail,), background_invocations=(detail, replace(detail, identity='second')))

        first = cards.project(2000)[0][0].rows[0].tool
        self.assertEqual(detail, cards.project(2001)[0][0].rows[0].tool.running_invocation)
        cards.catalog(self.catalog((root,), active=(root.session_id,), revision="changed"))
        verifying = cards.project(2001)[0][0].rows[0].tool

        self.assertEqual(detail, first.running_invocation)
        self.assertIsNone(verifying.running_invocation)
        self.assertIsNone(verifying.background_invocation)
        self.assertEqual(2, len(first.background_invocations))
        self.assertEqual((), verifying.running_invocations)
        self.assertEqual((), verifying.background_invocations)
        self.assertEqual(first.tool_count, verifying.tool_count)

    def test_one_hundred_concurrent_cards_each_have_only_their_focal_row(self):
        root = self.roots[0]
        base = self.capture.rows[-1]
        rows = tuple(replace(base, event_id=f"p-{index:03}", at_ms=1000 + index,
            prompt_number=index + 1, in_progress=True) for index in range(100))
        capture = replace(self.capture, rows=rows, observed_at_ms=5000,
            observed_ids=frozenset(row.event_id for row in rows))
        cards = WatchCards(ManualWorkers())
        cards.catalog(self.catalog((root,), active=(root.session_id,)))
        self.publish(cards, root, capture)
        active, history, _ = cards.project(6000)
        self.assertEqual(100, len(active))
        self.assertEqual((), history)
        self.assertEqual(list(range(1, 101)), [card.rows[-1].prompt.prompt_number for card in active])
        self.assertTrue(all(len(card.rows) == 1 for card in active))
        wire = project_live(WatchProjection("Watch", "fixture", (), now_ms=6000,
            active_cards=active, cards_state="observed")).to_json()
        self.assertEqual(100, len(wire["active_cards"]))
        self.assertNotIn("totals", wire["active_cards"][0])
        self.assertNotIn("provisional", wire["active_cards"][0])
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
        self.assertTrue(set(workers.submissions) & {root.session_id for root in self.roots[6:]})
        cards = WatchCards(ManualWorkers())
        cards.catalog(self.catalog())
        for root in self.roots:
            self.publish(cards, root, self.capture)
        self.assertFalse(cards.project(1001)[0])
        self.assertTrue(all(not row.marker for card in cards.project(1001)[1] for row in card.rows))

    def test_fixed_catalog_delayed_newer_roots_never_publish_provisional_winners(self):
        # One source/catalog revision, no new activity across the virtual minute.
        roots = tuple(replace(self.roots[0], session_id=f"fixed-{index:02}", updated_at_ms=1)
            for index in range(12))
        cards = WatchCards(ManualWorkers())
        observation = self.catalog(roots, revision="fixed-source-revision")
        cards.catalog(observation)
        for index, root in enumerate(roots):
            row = replace(self.capture.rows[-1], at_ms=100 + index, completed_at_ms=1000 + index)
            self.publish(cards, root, replace(self.capture, rows=(row,), latest_ms=row.at_ms), now=2000)
            if index < 11:
                self.assertEqual((), cards.historical_ids(2000), "partial top-k is not authoritative")
                self.assertEqual((), cards.project(2000)[1])
        before = cards.project(62000)[1]
        self.assertEqual([root.session_id for root in roots[-5:]], [card.session_id for card in before])
        cards.catalog(observation)
        self.assertEqual(before, cards.project(63000)[1], "unchanged catalog never replaces winners")

    def test_history_refresh_is_an_atomic_publication_not_mixed_card_versions(self):
        cards = WatchCards(ManualWorkers())
        cards.catalog(self.catalog())
        for root in self.roots:
            self.publish(cards, root, self.capture)
        before = cards.project(2000)[1]
        cards.catalog(self.catalog(revision="two"))
        changed = replace(self.capture, rows=(replace(self.capture.rows[-1], ccost=Decimal("42")),))
        for root in self.roots[:-1]:
            self.publish(cards, root, changed)
            self.assertEqual(before, cards.project(3000)[1], "retain one coherent verified epoch")
        self.publish(cards, self.roots[-1], changed)
        after = cards.project(3001)[1]
        self.assertTrue(all(card.rows[0].prompt.ccost == Decimal("42") for card in after))

    def test_history_failure_partial_revision_recovery_and_terminal_invalidation(self):
        clock = [0.0]
        cards = WatchCards(ManualWorkers(), monotonic=lambda: clock[0])
        cards.catalog(self.catalog())
        for root in self.roots:
            self.publish(cards, root, self.capture)
        verified = cards.project(2000)[1]
        epoch, stamp = cards.history.epoch, cards.history.verified_at_ms
        root = self.roots[-1]
        entry = cards.sessions[root.session_id]
        cards.accept(CardResult(root.session_id, entry.generation, 'unavailable',
            transport_failure(TimeoutError(), phase='capture')), 2001)
        self.assertEqual(verified, cards.project(2002)[1])
        self.assertEqual('refreshing', cards.history.state)
        clock[0] = 5
        self.assertEqual(verified, cards.project(2003)[1])
        self.assertEqual(('unavailable', epoch, stamp),
            (cards.history.state, cards.history.epoch, cards.history.verified_at_ms))
        self.publish(cards, root, replace(self.capture, authoritative=False), now=2004)
        cards.project(2004)
        self.assertEqual('unavailable', cards.history.state, 'incomplete trees cannot certify membership')
        self.publish(cards, root, self.capture, now=2005)
        cards.project(2005)
        self.assertEqual('observed', cards.history.state)
        cards.catalog(self.catalog(self.roots[:-1]))
        self.assertNotIn(root.session_id, cards.historical_ids(2006))

    def test_status_only_resumption_invalidates_history_and_cost_ticks_do_not_renew_proof(self):
        cards = WatchCards(ManualWorkers())
        cards.catalog(self.catalog())
        for root in self.roots:
            self.publish(cards, root, self.capture)
        history = cards.project(2000)[1]
        epoch, stamp = cards.history.epoch, cards.history.verified_at_ms
        entry = cards.sessions[history[0].session_id]
        entry.cost.failed = True
        cards.project(9000)
        self.assertEqual((epoch, stamp), (cards.history.epoch, cards.history.verified_at_ms))
        cards.catalog(self.catalog(active=(entry.root.session_id,)))
        active, retained, _ = cards.project(9001)
        self.assertEqual(entry.root.session_id, active[0].session_id)
        self.assertEqual((), active[0].rows, 'loading a resumed prompt never displays the old representative as active')
        self.assertNotIn(entry.root.session_id, [card.session_id for card in retained])
        self.assertEqual('refreshing', cards.history.state)

    def test_actual_workers_delay_newer_capture_without_blocking_live_publication(self):
        release, started = Event(), Event()
        source = SyntheticMonthSource(12, 1, month_start_ms=1000)
        source.snapshots = {key: replace(value, complete=True) for key, value in source.snapshots.items()}
        roots = tuple(value.root for value in source.snapshots.values())
        def factory(now):
            return make_service(str(Path(self.tmp.name) / uuid4().hex), source, now_ms=now)[2]
        original = capture_rows
        def delayed(service, root, previous, focal_ids):
            if root.session_id == roots[-1].session_id:
                started.set()
                if not release.wait(10):
                    raise RuntimeError('test_release_missing')
            return original(service, root, previous, focal_ids)
        workers = CardWorkers(factory)
        self.addCleanup(workers.close)
        self.addCleanup(release.set)
        cards = WatchCards(workers)
        cards.catalog(self.catalog(roots, revision='fixed-worker-catalog'))
        # The fixture's revision map must match each canonical source snapshot.
        for key, entry in cards.sessions.items():
            entry.revision = source.snapshots[key].source_revision
        def consume(now):
            for result in workers.drain():
                if result.phase != 'timing':
                    cards.accept(result, now)
        with patch('src.watch.card_workers.capture_rows', side_effect=delayed):
            for root in roots:
                entry = cards.sessions[root.session_id]
                while len(workers.jobs) >= workers.limit:
                    for future in tuple(workers.jobs.values()):
                        future.result(timeout=3)
                    consume(100_000_000)
                workers.submit(root, entry.generation, 100_000_000)
            self.assertTrue(started.wait(3))
            for key, future in tuple(workers.jobs.items()):
                if key != roots[-1].session_id:
                    future.result(timeout=3)
            consume(100_000_000)
            self.assertEqual((), cards.project(100_060_000)[1])
            self.assertEqual('loading', cards.history.state)
            release.set()
            for future in tuple(workers.jobs.values()):
                future.result(timeout=3)
            consume(100_060_000)
            self.assertEqual(5, len(cards.project(100_060_000)[1]))
            self.assertEqual('observed', cards.history.state)

    def test_history_revision_refresh_retains_visible_metrics_without_expansion_signal(self):
        workers = ManualWorkers()
        cards = WatchCards(workers)
        cards.catalog(self.catalog())
        for root in self.roots:
            self.publish(cards, root, self.capture)
        before = cards.project(1001)[1]
        cards.catalog(self.catalog(revision="changed"))
        cards.tick(1002)
        self.assertEqual(before, cards.project(1002)[1])
        self.assertEqual(4, len(workers.jobs), "history refresh needs no browser disclosure event")
        root = self.roots[0]
        row = replace(self.capture.rows[-1], ccost=Decimal("42"))
        self.publish(cards, root, replace(self.capture, rows=(row,)), now=1003)
        self.assertEqual(before, cards.project(1003)[1], "one refreshed root cannot replace a verified epoch")
        for root in self.roots[1:]:
            self.publish(cards, root, replace(self.capture, rows=(row,)), now=1003)
        self.assertEqual(Decimal("42"), cards.project(1003)[1][0].rows[0].prompt.ccost)

    def test_revision_churn_cannot_starve_a_retained_running_card(self):
        workers = ManualWorkers()
        cards = WatchCards(workers)
        roots = self.roots[:6]
        cards.catalog(self.catalog(roots))
        running = replace(self.capture, rows=(replace(self.capture.rows[-1], in_progress=True),))
        for root in roots:
            self.publish(cards, root, running)
        for revision in range(3):
            cards.catalog(self.catalog(roots, revision=str(revision)))
            cards.tick(2000 + revision)
            for key in tuple(workers.jobs):
                self.publish(cards, cards.sessions[key].root, running, now=2000 + revision)
            workers.jobs.clear()
        self.assertEqual({root.session_id for root in roots}, set(workers.submissions))

    def test_rejected_generation_keeps_its_admission_turn(self):
        workers = ManualWorkers()
        cards = WatchCards(workers)
        roots = self.roots[:6]
        cards.catalog(self.catalog(roots, active=[root.session_id for root in roots]))
        cards.tick(1000)
        stale = tuple(workers.jobs.items())
        cards.catalog(self.catalog(roots, active=[root.session_id for root in roots], revision="new"))
        for key, generation in stale:
            cards.accept(CardResult(key, generation, "rows", (self.capture, (), None)), 2000)
        workers.jobs.clear()
        cards.tick(2000)
        self.assertEqual({root.session_id for root in roots}, set(workers.submissions))
        self.assertTrue(all(entry.capture is None for entry in cards.sessions.values()))

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

    def test_slow_capture_is_bounded_and_never_acquires_full_session_totals(self):
        slow_started, release = Event(), Event()
        original = capture_rows
        def capture(service, root, previous, focal_ids):
            if root.session_id == self.roots[0].session_id:
                slow_started.set()
                if not release.wait(10):
                    raise RuntimeError("test_release_missing")
            return original(service, root, previous, focal_ids)
        def factory(now_ms):
            service = make_service(str(Path(self.tmp.name) / uuid4().hex), self.source, now_ms=now_ms)[2]
            service._prompt_block = lambda *args, **kwargs: self.fail("Watch must not project session aggregates")
            return service
        workers = CardWorkers(factory, workers=2)
        self.addCleanup(workers.close)
        self.addCleanup(release.set)
        with patch("src.watch.card_workers.capture_rows", side_effect=capture):
            workers.submit(self.roots[0], 1, self.service.now_ms)
            self.assertTrue(slow_started.wait(3))
            workers.submit(self.roots[1], 2, self.service.now_ms)
            results = []
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                results.extend(workers.drain())
                if any(result.generation == 2 and result.phase == "timing" for result in results):
                    break
                Event().wait(.01)
            self.assertFalse(any(result.generation == 1 and result.phase == "rows" for result in results))
            self.assertEqual(["rows", "timing"], [result.phase for result in results if result.generation == 2])
            self.assertLessEqual(len(workers.jobs), 2)
            release.set()

    def test_focal_tool_threshold_elapsed_and_terminal_clearing_are_server_owned(self):
        root = self.roots[0]
        base = replace(self.capture.rows[-1], in_progress=True, event_id="focal", at_ms=1000,
            background_kinds=("subagent",), background_started_ms=1000)
        capture = replace(self.capture, rows=(base,), observed_at_ms=2000, observed_ids=frozenset({"focal"}))
        cards = WatchCards(ManualWorkers())
        cards.catalog(self.catalog((root,)))
        entry = cards.sessions[root.session_id]
        tool = ToolObservation(tool_counts=(("shell", 1),), running_tool="shell", running_ms=11000)
        cards.accept(CardResult(root.session_id, entry.generation, "rows", (capture, (("focal", tool),), None)), 2000)
        self.assertEqual("", cards.project(10999)[0][0].rows[-1].tool.running_tool)
        self.assertEqual("shell", cards.project(11000)[0][0].rows[-1].tool.running_tool)
        self.assertEqual(10000, cards.project(11000)[0][0].rows[-1].tool.running_ms)
        wire = project_live(WatchProjection("Watch", "fixture", (), now_ms=11000,
            active_cards=cards.project(11000)[0])).to_json()
        activity = wire["active_cards"][0]["rows"][0]["tool"]
        self.assertEqual(["subagent"], activity["background_kinds"])
        self.assertEqual(10000, activity["background_ms"])
        terminal = replace(capture, rows=(replace(base, in_progress=False),))
        cards.accept(CardResult(root.session_id, entry.generation, "rows", (terminal, (("focal", tool),), None)), 12000)
        self.assertEqual("", cards.project(12001)[0][0].rows[-1].tool.running_tool)
        self.assertEqual((), cards.project(12001)[0][0].rows[-1].tool.background_kinds)
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
        self.assertIsInstance(results[0].value, SourceUnavailableError)

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
