"""Source-shaped post-start completion proof, independent of cold global history."""
from dataclasses import replace
import tempfile
import unittest

from development.tests.fixtures.history_acquisition import CaptureWorkers
from development.tests.fixtures.synthetic_month import SyntheticMonthSource, make_root_snapshot
from development.tests.fixtures.watch_runtime import make_service
from development.tests.fixtures.opencode_v2_service import source_with_current_service
from src.application.live_projection import project_live
from src.reports.watch_capture import capture_rows
from src.watch.card_workers import CardResult
from src.watch.cards import WatchCards
from src.watch.models import WatchProjection
from src.watch.observers import observe_catalog
from src.sources.errors import SourceConcurrentChangeError


START = 1_000_000_000


def finished_snapshot(index, at, *, revision="new"):
    value = make_root_snapshot(index, 1, month_start_ms=at - index * 60_000)
    return replace(value, complete=True, source_revision=revision)


class RecentFinishedTests(unittest.TestCase):
    def test_v2_saved_fast_prompt_in_old_root_qualifies_without_running_sighting(self):
        with source_with_current_service() as (source, server, _), tempfile.TemporaryDirectory() as tmp:
            server.sessions.append(dict(id="ses_cold", projectID="prj_current", title="old",
                time=dict(created=100, updated=100), location=dict(directory="/private/repo")))
            server.messages["ses_cold"] = []
            cards = WatchCards(None, started_at_ms=5000)
            cards.catalog(observe_catalog(source))
            server.messages["ses_current"][0]["time"] = dict(created=6000)
            server.messages["ses_current"][1]["time"] = dict(created=6100, completed=6300)
            server.sessions[0]["time"]["updated"] = 6400
            source.refresh_connection()
            cards.catalog(observe_catalog(source))
            service = make_service(tmp, source, now_ms=7000)[2]
            entry = cards.sessions["ses_current"]
            capture, item = capture_rows(service, entry.root)

            cards.accept(CardResult("ses_current", entry.generation, "rows",
                (capture, (), item.snapshot)), 7000)
            active, history, _ = cards.project(7000)
            recent = cards.recent.project(cards, 7000)

            self.assertEqual(((), ()), (active, history))
            self.assertEqual(("loading", 0), (cards.history.state, cards.history.epoch))
            self.assertEqual([("ses_current", "msg_current_user", 6300)],
                [(card.session_id, card.rows[0].prompt.event_id, card.rows[0].prompt.completed_at_ms) for card in recent])

    def test_fast_prompt_bypasses_5000_unread_roots_without_certifying_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = SyntheticMonthSource(5000, 1, month_start_ms=1000)
            source.snapshots = {key: replace(value, complete=True) for key, value in source.snapshots.items()}
            service = make_service(tmp, source, now_ms=START + 1000)[2]
            workers = CaptureWorkers(service)
            cards = WatchCards(workers, started_at_ms=START)
            cards.catalog(observe_catalog(source))
            cards.tick(START)
            cold_jobs = set(workers.jobs)
            # A canonical 300ms prompt first appears already finished, never Running.
            fresh = finished_snapshot(6000, START + 200)
            source.snapshots[fresh.root.session_id] = fresh
            cards.catalog(observe_catalog(source))

            cards.tick(START + 1000)

            self.assertIn(fresh.root.session_id, workers.jobs)
            self.assertTrue(cold_jobs.isdisjoint(workers.jobs), "older work also progresses")
            cards.tick(START + 1100)
            active, history, _ = cards.project(START + 1100)
            recent = cards.recent.project(cards, START + 1100)
            self.assertEqual((), active)
            self.assertEqual((), history)
            self.assertEqual(("loading", 0), (cards.history.state, cards.history.epoch))
            self.assertLess(cards.history.checked, cards.history.total)
            self.assertEqual([fresh.root.session_id], [card.session_id for card in recent])
            prompt = recent[0].rows[0].prompt
            self.assertEqual((fresh.events[0].event_id, START + 500),
                (prompt.event_id, prompt.completed_at_ms))
            self.assertTrue(prompt.completed_successfully)
            # Ordinary eviction and terminal-grace expiry cannot erase this evidence.
            cards.tick(START + 60_000)
            self.assertEqual([fresh.root.session_id],
                [card.session_id for card in cards.recent.project(cards, START + 60_000)])
            wire = project_live(WatchProjection("Watch", "fixture", (),
                recent_finished_cards=recent)).to_json()
            self.assertEqual(START + 500, wire["recent_finished_cards"][0]["rows"][0]["prompt"]["completed_at_ms"])

    def test_old_root_new_finish_replaces_representative_and_converges_atomically(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = SyntheticMonthSource(2, 1, month_start_ms=1000)
            service = make_service(tmp, source, now_ms=START + 5000)[2]
            cards = WatchCards(None, started_at_ms=START)
            cards.catalog(observe_catalog(source))
            root_id = "root-0000"
            for number, at in enumerate((START + 200, START + 1200)):
                fresh = finished_snapshot(0, at, revision=str(number))
                source.snapshots[root_id] = fresh
                cards.catalog(observe_catalog(source))
                capture, item = capture_rows(service, fresh.root)
                entry = cards.sessions[root_id]
                cards.accept(CardResult(root_id, entry.generation, "rows",
                    (capture, (), item.snapshot)), START + 5000)
                cards.project(START + 5000)
                recent = cards.recent.project(cards, START + 5000)
                self.assertEqual([at + 300], [c.rows[0].prompt.completed_at_ms for c in recent])
            old = source.snapshots["root-0001"]
            source.snapshots["root-0001"] = replace(old, complete=True)
            capture, item = capture_rows(service, old.root)
            entry = cards.sessions["root-0001"]
            cards.accept(CardResult("root-0001", entry.generation, "rows",
                (capture, (), item.snapshot)), START + 5000)
            history = cards.project(START + 5000)[1]
            self.assertEqual("observed", cards.history.state)
            self.assertEqual(root_id, history[-1].session_id)
            self.assertEqual((), cards.recent.project(cards, START + 5000))

    def test_reused_changed_root_is_foreground_even_after_prior_archive_admission(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = SyntheticMonthSource(5000, 1, month_start_ms=1000)
            service = make_service(tmp, source, now_ms=START + 1000)[2]
            workers = CaptureWorkers(service)
            cards = WatchCards(workers, started_at_ms=START)
            cards.catalog(observe_catalog(source))
            entry = cards.sessions["root-0000"]
            entry.admission_order = 1000  # Hundreds of unread old roots precede it.
            source.snapshots["root-0000"] = finished_snapshot(0, START + 100)
            cards.catalog(observe_catalog(source))

            cards.tick(START + 1000)

            self.assertEqual("root-0000", next(iter(workers.jobs)))
            self.assertLessEqual(len(workers.jobs), 4)

    def test_metadata_touch_and_late_old_capture_do_not_prove_a_new_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = SyntheticMonthSource(2, 1, month_start_ms=1000)
            cards = WatchCards(None, started_at_ms=START)
            cards.catalog(observe_catalog(source))
            old = source.snapshots["root-0000"]
            touched = replace(old, complete=True, source_revision="metadata-touch",
                root=replace(old.root, updated_at_ms=START + 1000))
            source.snapshots["root-0000"] = touched
            cards.catalog(observe_catalog(source))
            service = make_service(tmp, source, now_ms=START + 60_000)[2]
            capture, item = capture_rows(service, touched.root)
            entry = cards.sessions["root-0000"]

            cards.accept(CardResult("root-0000", entry.generation, "rows",
                (capture, (), item.snapshot)), START + 60_000)
            cards.project(START + 60_000)

            self.assertEqual((), cards.recent.project(cards, START + 60_000))
            self.assertEqual(("loading", 0), (cards.history.state, cards.history.epoch))
            source.snapshots["root-0000"] = replace(touched,
                root=replace(touched.root, archived_at_ms=START + 2000))
            cards.catalog(observe_catalog(source))
            self.assertNotIn("root-0000", cards.sessions)

    def test_ranking_bounds_and_unsupported_evidence_never_becomes_recent(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = SyntheticMonthSource(8, 1, month_start_ms=1000)
            cards = WatchCards(None, started_at_ms=START)
            cards.catalog(observe_catalog(source))
            service = make_service(tmp, source, now_ms=START + 10_000)[2]
            # Deliberately reverse acquisition order: actual finish wins.
            for index in reversed(range(7)):
                fresh = finished_snapshot(index, START + index * 1000)
                source.snapshots[fresh.root.session_id] = fresh
                cards.catalog(observe_catalog(source))
                capture, item = capture_rows(service, fresh.root)
                entry = cards.sessions[fresh.root.session_id]
                cards.accept(CardResult(fresh.root.session_id, entry.generation, "rows",
                    (capture, (), item.snapshot)), START + 10_000)
            cards.project(START + 10_000)
            self.assertEqual([f"root-{i:04d}" for i in range(2, 7)],
                [c.session_id for c in cards.recent.project(cards, START + 10_000)])
            self.assertEqual(5, len(cards.recent.entries))
            key = "root-0007"
            fresh = finished_snapshot(7, START + 7000)
            source.snapshots[key] = fresh
            cards.catalog(observe_catalog(source))
            capture, item = capture_rows(service, fresh.root)
            entry = cards.sessions[key]
            row = capture.rows[0]
            for invalid in (replace(row, completed_at_ms=None),
                    replace(row, completed_at_ms=START - 1),
                    replace(row, completed_at_ms=START + 99_000),
                    replace(row, execution_unverified=True),
                    replace(row, completed_successfully=False),
                    replace(row, is_compaction=True)):
                cards.accept(CardResult(key, entry.generation, "rows",
                    (replace(capture, rows=(invalid,)), (), item.snapshot)), START + 10_000)
                self.assertNotIn(key, cards.recent.entries)
            for incomplete in (replace(capture, authoritative=False), replace(capture, retained=True)):
                cards.accept(CardResult(key, entry.generation, "rows",
                    (incomplete, (), item.snapshot)), START + 10_000)
                self.assertNotIn(key, cards.recent.entries)

    def test_retained_revision_rejects_stale_wrong_root_and_resets_source_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = SyntheticMonthSource(2, 1, month_start_ms=1000)
            cards = WatchCards(None, started_at_ms=START)
            cards.catalog(observe_catalog(source))
            fresh = finished_snapshot(0, START + 100)
            source.snapshots[fresh.root.session_id] = fresh
            cards.catalog(observe_catalog(source))
            service = make_service(tmp, source, now_ms=START + 1000)[2]
            capture, item = capture_rows(service, fresh.root)
            entry = cards.sessions[fresh.root.session_id]
            result = CardResult(fresh.root.session_id, entry.generation, "rows", (capture, (), item.snapshot))
            cards.accept(result, START + 1000)
            cards.project(START + 1000)
            unsupported = replace(capture, retained=True, authoritative=False,
                rows=(replace(capture.rows[0], completed_at_ms=START + 999),))
            cards.accept(replace(result, value=(unsupported, (), replace(item.snapshot, complete=False))), START + 1000)
            self.assertEqual(START + 400,
                cards.recent.project(cards, START + 2000)[0].rows[0].prompt.completed_at_ms)
            source.snapshots[fresh.root.session_id] = replace(fresh, source_revision="changed")
            cards.catalog(observe_catalog(source))
            cards.accept(result, START + 2000)
            cards.accept(CardResult(fresh.root.session_id, entry.generation, "unavailable",
                SourceConcurrentChangeError("synthetic churn")), START + 2000)
            retained = cards.recent.project(cards, START + 60_000)
            self.assertEqual(START + 400, retained[0].rows[0].prompt.completed_at_ms)
            self.assertEqual("refreshing", retained[0].state)
            cards.active_candidates = frozenset({fresh.root.session_id})
            self.assertEqual((), cards.recent.project(cards, START + 60_000),
                "a pending active root cannot also be an Earlier filler")
            cards.active_candidates = frozenset()
            wrong = replace(item.snapshot, root=source.snapshots["root-0001"].root)
            cards.accept(CardResult(fresh.root.session_id, entry.generation, "rows",
                (capture, (), wrong)), START + 2000)
            self.assertNotEqual(entry.generation, entry.verified_generation)
            # Successful complete source reclassification is actual invalidation.
            cards.accept(CardResult(fresh.root.session_id, entry.generation, "rows",
                (replace(capture, rows=()), (), replace(item.snapshot, source_revision="changed"))), START + 2000)
            self.assertEqual((), cards.recent.project(cards, START + 2000))
            source.snapshots = {key: replace(value, root=replace(value.root,
                provenance=replace(value.root.provenance, source_instance="other")))
                for key, value in source.snapshots.items()}
            cards.catalog(observe_catalog(source))
            cards.accept(result, START + 3000)
            self.assertTrue(all(entry.capture is None for entry in cards.sessions.values()))
            self.assertEqual({}, cards.recent.entries)
            del source.snapshots[fresh.root.session_id]
            cards.catalog(observe_catalog(source))
            self.assertNotIn(fresh.root.session_id, cards.sessions)

    def test_real_running_transition_survives_grace_and_prestart_prompt_uses_finish(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = SyntheticMonthSource(2, 1, month_start_ms=START - 1000, running_roots=1)
            source.snapshots = {key: replace(value, complete=True) for key, value in source.snapshots.items()}
            cards = WatchCards(None, started_at_ms=START)
            cards.catalog(observe_catalog(source))
            service = make_service(tmp, source, now_ms=START + 1000)[2]
            entry = cards.sessions["root-0000"]
            capture, item = capture_rows(service, entry.root)
            cards.accept(CardResult("root-0000", entry.generation, "rows",
                (capture, (), item.snapshot)), START + 1000)
            self.assertTrue(cards.project(START + 1000)[0][0].rows[0].prompt.in_progress)
            running = source.snapshots["root-0000"]
            ended = replace(running, source_revision="ended",
                root=replace(running.root, active=False),
                messages=tuple(replace(message, completed_at_ms=START + 2000, finish_reason="stop")
                    if message.role.value == "assistant" else message for message in running.messages),
                invocations=tuple(replace(request, completed_at_ms=START + 2000, finish_reason="stop")
                    for request in running.invocations))
            source.snapshots["root-0000"] = ended
            cards.catalog(observe_catalog(source))
            capture, item = capture_rows(service, ended.root)
            cards.accept(CardResult("root-0000", entry.generation, "rows",
                (capture, (), item.snapshot)), START + 2500)
            self.assertEqual(1, len(cards.project(START + 2500)[0]))
            self.assertEqual((), cards.recent.project(cards, START + 2500))
            self.assertEqual((), cards.project(START + 40_000)[0])
            recent = cards.recent.project(cards, START + 40_000)
            self.assertEqual((START - 1000, START + 2000),
                (recent[0].rows[0].prompt.at_ms, recent[0].rows[0].prompt.completed_at_ms))


if __name__ == "__main__":
    unittest.main()
