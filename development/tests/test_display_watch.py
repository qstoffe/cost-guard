"""Watch and Mini read one committed source-scoped observation."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from threading import Event
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from development.tests.fixtures.display_watch import running_frame
from src.analysis.daily_usage import DailyUsage
from src.analysis.timezones import local_date_range
from src.analysis.token_mix import TokenMix
from src.analysis.valuation import ComparisonCost
from src.application.watch_archive_projection import archive_watch_observation, cached_watch_view
from src.cache.display_history import BATCH_LIMIT, DisplayHistory, RunningSession, SessionChange, SessionFact
from src.cache.display_watch import WATCH_LIVE_MS, WATCH_ROW_LIMIT, publish_watch
from src.sources.opencode_v1 import OpenCodeV1Source
from src.web.display_archive import DisplayArchive
from src.watch.models import SessionPreview


class DisplayWatchTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.history = DisplayHistory(self.root)
        self.history.initialize()

    def test_common_values_have_independent_costs_and_retained_running_is_never_current_after_restart(self):
        at = 100_000
        observed = archive_watch_observation(running_frame(at), at)
        self.history.replace_watch("bound", "first-host", observed, archive_epoch=0)

        full = self.history.watch("bound", "first-host", at + 500, live_eligible=True)
        mini = self.history.watch("bound", "first-host", at + 500, live_eligible=True)
        restarted = DisplayHistory(self.root).watch("bound", "new-host", at + 500, live_eligible=True)
        expired = self.history.watch("bound", "first-host", at + WATCH_LIVE_MS, live_eligible=True)
        interrupted = self.history.watch("bound", "first-host", at + 500, live_eligible=False)
        foreign = self.history.watch("different", "first-host", at + 500, live_eligible=True)

        self.assertEqual(full, mini)
        self.assertEqual(("current", 1, at), (full["freshness"], full["generation"], full["observed_ms"]))
        fact, = full["cards"]
        self.assertEqual(("root", "prompt-1", "running", at - 2_000, None), tuple(
            fact[key] for key in ("session_id", "event_id", "outcome", "start_ms", "finish_ms")))
        self.assertEqual(("0.125", "1.25000001", 773), tuple(
            fact[key] for key in ("prompt_cost", "session_cost", "context_tokens")))
        self.assertNotIn(b"private transcript sample", self.history.path.read_bytes())
        for value in (restarted, expired, interrupted):
            self.assertEqual(("as-of", "unverified"), (value["freshness"], value["cards"][0]["outcome"]))
        self.assertEqual(("empty", []), (foreign["freshness"], foreign["cards"]))

    def test_open_reader_does_not_wait_for_a_new_snapshot_and_sees_only_complete_revisions(self):
        at = 100_000
        frame = running_frame(at)
        earlier = archive_watch_observation(frame, at)
        changed = replace(earlier.facts[0], title="After commit", prompt_cost=Decimal("0.15"), context_tokens=774)
        expected = replace(earlier, observed_ms=at + 1, projected_ms=at + 1, facts=(changed,))
        self.history.replace_watch("bound", "host", earlier, archive_epoch=0)
        # Hold a real concurrent write transaction, not a fake result cache.
        with self.history._connect() as writer:
            writer.execute("BEGIN IMMEDIATE")
            publish_watch(writer, "bound", "host", expected)
            held = self.history.watch("bound", "host", at + 1, live_eligible=True)
            writer.commit()
        committed = self.history.watch("bound", "host", at + 1, live_eligible=True)
        stale = self.history.replace_watch("bound", "host", earlier, archive_epoch=0)

        self.assertEqual((1, "Observed title", "0.125", 773), (
            held["generation"], held["cards"][0]["title"], held["cards"][0]["prompt_cost"], held["cards"][0]["context_tokens"]))
        self.assertEqual((2, "After commit", "0.15", 774), (committed["generation"], committed["cards"][0]["title"],
                         committed["cards"][0]["prompt_cost"], committed["cards"][0]["context_tokens"]))
        self.assertIsNone(stale)

    def test_missing_running_proof_does_not_claim_complete_empty_running_membership(self):
        at = 100_000
        observed = archive_watch_observation(running_frame(at), at)
        stale = replace(observed.facts[0], qualified_ms=at - WATCH_LIVE_MS)
        self.history.replace_watch("bound", "host", replace(observed, facts=(stale,)), archive_epoch=0)

        snapshot = self.history.watch("bound", "host", at, live_eligible=True)
        view = cached_watch_view(dict(binding="host", **snapshot), "UTC")

        self.assertEqual("current", snapshot["freshness"])
        self.assertEqual("partial", view["cards_state"])
        self.assertEqual([], view["active_cards"])
        card, = view["earlier_cards"]
        row, = card["rows"]
        self.assertEqual("Observed title", card["title"])
        self.assertTrue(row["prompt"]["execution_unverified"])
        self.assertIsNone(row["prompt"]["completed_at_ms"])

    def test_new_version_preserves_previous_partition_and_purge_prevents_late_writes(self):
        at = 100_000
        observed = archive_watch_observation(running_frame(at), at)
        with self.history._connect() as db:
            db.executescript("""
                DROP TRIGGER archive_usage_correction;
                DROP INDEX archive_requests_revision;
                ALTER TABLE archive_requests DROP COLUMN first_revision;
                DROP TABLE archive_usage_revisions;
                DROP TABLE archive_watch_daily;
                DROP TABLE archive_watch_cards;
                DROP TABLE archive_watch_state;
                INSERT INTO sources(source,generation,session_count) VALUES('bound',4,0);
                PRAGMA user_version=10;
            """)
        upgraded = DisplayHistory(self.root)
        upgraded.initialize()

        generation = upgraded.replace_watch("bound", "host", observed, archive_epoch=0)
        previous = upgraded.source_state("bound")
        cleared = upgraded.clear_confirmed_sessions("bound", previous)
        late = upgraded.replace_watch("bound", "host", observed, archive_epoch=0)
        snapshot = upgraded.watch("bound", "host", at, live_eligible=True)

        self.assertEqual(4, previous.generation)
        self.assertEqual(1, generation)
        self.assertEqual(1, cleared.archive_epoch)
        self.assertIsNone(late)
        self.assertEqual((1, "empty", []), (snapshot["archive_epoch"], snapshot["freshness"], snapshot["cards"]))

    def test_v11_watch_upgrade_keeps_old_snapshot_and_leaves_added_fields_unknown(self):
        with self.history._connect() as db:
            db.executescript("""
                DROP TRIGGER archive_usage_correction;
                DROP INDEX archive_requests_revision;
                ALTER TABLE archive_requests DROP COLUMN first_revision;
                DROP TABLE archive_usage_revisions;
                DROP TABLE archive_watch_daily;
                DROP TABLE archive_watch_cards;
                CREATE TABLE archive_watch_cards (
                    source TEXT NOT NULL REFERENCES archive_watch_state(source) ON DELETE CASCADE,
                    position INTEGER NOT NULL, session_id TEXT NOT NULL, event_id TEXT NOT NULL, title TEXT NOT NULL,
                    card_group TEXT NOT NULL, start_ms INTEGER, finish_ms INTEGER, outcome TEXT,
                    prompt_cost TEXT, prompt_cost_complete INTEGER NOT NULL,
                    session_cost TEXT, session_cost_complete INTEGER NOT NULL,
                    context_tokens INTEGER, model TEXT, effort TEXT, calls INTEGER, duration_ms INTEGER, qualified_ms INTEGER,
                    PRIMARY KEY(source, position)
                ) WITHOUT ROWID;
                INSERT INTO sources(source) VALUES('bound');
                INSERT INTO archive_watch_state VALUES('bound','first-host',7,100000,100000,'observed',0);
                INSERT INTO archive_watch_cards VALUES(
                    'bound',0,'root','prompt-1','Saved v11','active',98000,NULL,'running',
                    '0.125',1,'1.25',1,773,'Model','medium',2,NULL,100000);
                PRAGMA user_version=11;
            """)
        migrated = DisplayHistory(self.root)

        migrated.initialize()
        retained = migrated.watch("bound", "restarted", 101_000, live_eligible=True)

        self.assertEqual(("as-of", 7), (retained["freshness"], retained["generation"]))
        fact, = retained["cards"]
        self.assertEqual(("Saved v11", "0.125", "1.25", 773, "unverified"), (
            fact["title"], fact["prompt_cost"], fact["session_cost"], fact["context_tokens"], fact["outcome"]))
        self.assertEqual((None, None, None, None), (
            fact["prompt_number"], fact["is_compaction"], fact["mix_input"], fact["catalog_activity_ms"]))

    def test_prompt_metrics_and_catalog_preview_keep_distinct_clocks_and_lifetime(self):
        at = 100_000
        frame = running_frame(at)
        active, = frame.active_cards
        running_row, = active.rows
        compacted = replace(running_row.prompt, in_progress=False, event_id="compact", prompt_number=3,
                            duration_ms=1337, completed_successfully=True, completed_at_ms=at - 400,
                            is_compaction=True, watch_delta_context_tokens=None)
        finished = replace(active, session_id="compaction-root", focal_id="compact",
                           rows=(replace(running_row, session_id="compaction-root", prompt=compacted),))
        frame = replace(frame, recent_finished_cards=(finished,), earlier_previews=(
            SessionPreview("metadata-root", "Catalog only", activity_ms=at - 800, total_ccost=Decimal(0)),))
        observed = archive_watch_observation(frame, at)
        self.history.replace_watch("bound", "host", observed, archive_epoch=0)

        current = cached_watch_view(dict(binding="host", **self.history.watch("bound", "host", at, live_eligible=True)), "UTC")
        retained = cached_watch_view(dict(binding="next", **self.history.watch("bound", "next", at, live_eligible=True)), "UTC")

        row, = current["active_cards"][0]["rows"]
        self.assertEqual((1, 817, [12, 34, 5, 49]), (
            row["prompt"]["prompt_number"], row["prompt"]["incoming_context_tokens"], row["prompt"]["token_mix_percent"]))
        self.assertEqual(-44, row["live_context"]["watch_delta_context_tokens"])
        unverified, = retained["earlier_cards"][0]["rows"]
        self.assertTrue(unverified["prompt"]["execution_unverified"])
        self.assertIsNone(unverified["live_context"]["watch_delta_context_tokens"])
        self.assertIsNone(unverified["prompt"]["completed_at_ms"])
        compaction, = retained["recent_finished_cards"][0]["rows"]
        self.assertTrue(compaction["prompt"]["is_compaction"])
        self.assertEqual(at - 400, compaction["prompt"]["completed_at_ms"])
        self.assertEqual("Compaction", compaction["prompt"]["label"])
        preview, = retained["earlier_previews"]
        self.assertEqual(("catalog", at - 800, "0", "retained"), (
            preview["activity_origin"], preview["activity_ms"], preview["total_ccost"], preview["total_state"]))

    def test_daily_only_observation_is_independent_of_running_and_expires_at_dst_boundary(self):
        zone = "Europe/Stockholm"
        local = local_date_range("2026-10-25", zone)
        at = local.start_ms + 3_600_000
        running = archive_watch_observation(running_frame(at), at, zone)
        self.history.replace_watch("bound", "host", running, archive_epoch=0)
        day_at = at + WATCH_LIVE_MS
        total = ComparisonCost(Decimal("3.0000014"), observed_requests=3, priced_requests=2)
        value = DailyUsage(local.start_ms, day_at, total, TokenMix(), 2, False)
        daily_frame = replace(running_frame(day_at), active_cards=(), cards_state="loading", daily_usage=value)
        daily_only = archive_watch_observation(daily_frame, day_at, zone)

        self.history.replace_watch("bound", "host", daily_only, archive_epoch=0)
        latest = self.history.watch("bound", "host", day_at, live_eligible=True, timezone_id=zone)
        restart = DisplayHistory(self.root).watch("bound", "next", local.end_ms - 1,
                                                  live_eligible=False, timezone_id=zone)
        rollover = self.history.watch("bound", "next", local.end_ms, live_eligible=False, timezone_id=zone)
        wrong_zone = self.history.watch("bound", "host", day_at, live_eligible=True)
        view = cached_watch_view(dict(binding="host", **restart), zone)

        self.assertIsNone(daily_only.facts)
        self.assertEqual((2, at, "unverified"), (latest["generation"], latest["observed_ms"], latest["cards"][0]["outcome"]))
        self.assertEqual(25 * 3_600_000, local.end_ms - local.start_ms)
        self.assertEqual(("3.0000014", False, 2, False, day_at), tuple(restart["daily"][key] for key in
                         ("known_ccost", "cost_complete", "prompt_count", "prompt_count_complete", "observed_at_ms")))
        self.assertEqual("retained", view["daily_state"])
        self.assertEqual(2, view["daily_usage"]["prompt_count"])
        self.assertIsNone(rollover["daily"])
        self.assertIsNone(wrong_zone["daily"])

    def test_bounded_projection_never_promotes_placeholder_only_turn_or_truncation_to_complete(self):
        frame = running_frame(100_000)
        card = frame.active_cards[0]
        loading = replace(frame, cards_state="loading", active_cards=(replace(card, rows=(), session_cost=None),))
        large = replace(frame, active_cards=tuple(replace(card, session_id=f"r-{i}") for i in range(WATCH_ROW_LIMIT + 5)))

        placeholder = archive_watch_observation(loading, frame.now_ms)
        oversized = archive_watch_observation(large, frame.now_ms)

        self.assertIsNone(placeholder)
        self.assertTrue(oversized.truncated)
        self.assertEqual(WATCH_ROW_LIMIT, len(oversized.facts))

    def test_live_publication_progresses_while_five_thousand_root_catalog_work_is_held(self):
        path = self.root / "catalog"
        path.write_bytes(b"fixture identity")
        selection = SimpleNamespace(selected="v1", source=OpenCodeV1Source(path))
        service = SimpleNamespace(timezone_id="UTC", selection=selection)
        driver = SimpleNamespace(error=None, terminal=False,
            coordinator=SimpleNamespace(catalog_observation=None, report_service=service))
        archive = DisplayArchive(self.root, lambda *_: None, watch_enabled=True)
        self.addCleanup(archive.close)
        archive.observe(driver, before_tick=True)
        source = archive.views.source
        ready, release = Event(), Event()

        def historical_turn():
            for start in range(0, 5_000, BATCH_LIMIT):
                archive.history.commit_sessions(source, tuple(
                    SessionChange(SessionFact(f"old-{i}", "r1", "Older session"), None)
                    for i in range(start, min(start + BATCH_LIMIT, 5_000))))
            ready.set()
            if not release.wait(5):
                raise AssertionError("fixture did not release history")

        with ThreadPoolExecutor(max_workers=1) as catalog_lane:
            history = catalog_lane.submit(historical_turn)
            try:
                self.assertTrue(ready.wait(10))
                base = int(time.time() * 1000) - 1000
                for step, count in enumerate((0, 1, 5, 26)):
                    now = base + step
                    frame = running_frame(now)
                    card, = frame.active_cards
                    roots = tuple(replace(card, session_id=f"active-{index}") for index in range(count))
                    frame = replace(frame, active_cards=roots)
                    running = tuple(RunningSession(card.session_id, card.title, now - 2000, now) for card in roots)
                    archive.publish_live(running, frame, now)
                    self.assertTrue(archive._live_write.result(timeout=3))

                    full = archive.watch_snapshot(live_eligible=lambda: True, presentation=True)
                    mini = archive.watch_snapshot(live_eligible=lambda: True, presentation=True)
                    page = archive.views.page(period="all")
                    self.assertEqual(full, mini)
                    self.assertEqual(count, len(full["view"]["active_cards"]))
                    self.assertEqual(5_000 + count, page["cached_total"])
                    self.assertEqual(min(count, page["size"]), sum(row["running"] for row in page["rows"]))
                    self.assertFalse(history.done())
                    if count:
                        fact = full["cards"][-1]
                        self.assertEqual(("0.125", "1.25000001", 773),
                                         (fact["prompt_cost"], fact["session_cost"], fact["context_tokens"]))

                now = base + 4
                row, = card.rows
                finished = replace(row.prompt, in_progress=False, completed_successfully=True, completed_at_ms=now)
                recent = tuple(replace(card, session_id=f"finished-{i}", rows=(replace(row, prompt=finished),))
                               for i in range(250))
                archive.publish_live((), replace(frame, now_ms=now, active_cards=(), recent_finished_cards=recent), now)
                self.assertTrue(archive._live_write.result(timeout=3))
                latest = archive.watch_snapshot(live_eligible=lambda: True, presentation=True)
                self.assertFalse(history.done())
                self.assertEqual(250, len(latest["view"]["recent_finished_cards"]))
                self.assertEqual({now}, {item["finish_ms"] for item in latest["cards"] if item["outcome"] == "finished"})
            finally:
                release.set()
            history.result(timeout=3)
        self.assertEqual(5_000, archive.views.page(period="all")["cached_total"])

    def test_readers_and_notifications_see_both_slices_only_after_one_commit(self):
        notifications = []

        def observe_hint(kind, hint):
            if "generation" in hint:
                notifications.append((kind, hint, snapshot()))

        def snapshot():
            watch = archive.watch_snapshot(live_eligible=lambda: True)
            page = archive.views.page(period="all")
            return ([row["title"] for row in page["rows"] if row["running"]],
                    [row["title"] for row in watch["cards"]])

        archive, _ = self.bound_archive(observe_hint)
        at = int(time.time() * 1000) - 100
        publish_cycle(archive, at, "previous")
        self.assertTrue(archive._live_write.result(timeout=5))
        notifications.clear()
        staged, release = Event(), Event()

        def held_watch(db, source, binding, observation):
            # Running has already changed in this transaction, but the
            # other connections must not see the uncommitted replacement.
            staged.set()
            if not release.wait(5):
                raise AssertionError("fixture did not release SQLite writer")
            return publish_watch(db, source, binding, observation)

        with patch("src.cache.display_history.publish_watch", side_effect=held_watch) as write_watch:
            try:
                publish_cycle(archive, at + 1, "next")
                turn = archive._live_write
                self.assertTrue(staged.wait(5))
                publish_cycle(archive, at + 2, "not queued")
                self.assertIs(turn, archive._live_write)
                self.assertEqual((["previous"], ["previous"]), snapshot())
                self.assertEqual([], notifications)
            finally:
                release.set()
            self.assertTrue(turn.result(timeout=5))

        self.assertEqual(1, write_watch.call_count)
        self.assertEqual((["next"], ["next"]), snapshot())
        self.assertEqual([("cache", 2, (["next"], ["next"])), ("watch-cache", 2, (["next"], ["next"]))],
                         [(kind, hint["generation"], committed) for kind, hint, committed in notifications])
        self.assertEqual([], notifications[0][1]["detail_roots"])

    def test_failed_second_slice_rolls_back_running_and_both_hints(self):
        events = []
        archive, _ = self.bound_archive(lambda kind, hint: events.append((kind, hint)))
        now = int(time.time() * 1000) - 100
        publish_cycle(archive, now, "before")
        self.assertTrue(archive._live_write.result(timeout=5))
        before = list(events)

        def fail_after_watch(*args):
            publish_watch(*args)
            raise sqlite3.OperationalError("injected second-slice failure after SQL mutations")

        with patch("src.cache.display_history.publish_watch", side_effect=fail_after_watch):
            publish_cycle(archive, now + 1, "failed")
            self.assertFalse(archive._live_write.result(timeout=5))

        page = archive.views.page(period="all")
        watch = archive.watch_snapshot(live_eligible=lambda: True)
        self.assertEqual((1, ["before"]), (page["generation"], [row["title"] for row in page["rows"]]))
        self.assertEqual((1, ["before"]), (watch["generation"], [row["title"] for row in watch["cards"]]))
        self.assertEqual(before, events)

    def test_rebind_during_transaction_rejects_both_slices_even_for_same_source(self):
        events = []
        archive, driver = self.bound_archive(lambda kind, hint: events.append((kind, hint)))
        views = archive.views
        now = int(time.time() * 1000) - 100
        publish_cycle(archive, now, "retained")
        self.assertTrue(archive._live_write.result(timeout=5))
        events.clear()
        staged, release = Event(), Event()

        def held_watch(*args):
            generation = publish_watch(*args)
            staged.set()
            if not release.wait(5):
                raise AssertionError("fixture did not release SQLite writer")
            return generation

        with patch("src.cache.display_history.publish_watch", side_effect=held_watch):
            try:
                publish_cycle(archive, now + 1, "stale")
                turn = archive._live_write
                self.assertTrue(staged.wait(5))
                archive.unbind()
                archive.observe(driver, before_tick=True)
            finally:
                release.set()
            self.assertFalse(turn.result(timeout=5))

        self.assertEqual(views.source, archive.views.source)
        self.assertNotEqual(views.binding, archive.views.binding)
        self.assertEqual([], [hint for _, hint in events if "generation" in hint])
        self.assertEqual(0, archive.views.page(period="all")["cached_total"])
        watch = archive.watch_snapshot(live_eligible=lambda: True)
        self.assertEqual(("as-of", "retained", 1), (watch["freshness"], watch["cards"][0]["title"], watch["generation"]))

    def test_outage_withdraws_running_without_overwriting_the_watch_snapshot(self):
        archive, _ = self.bound_archive(lambda *_: None)
        at = int(time.time() * 1000)
        publish_cycle(archive, at, "known")
        self.assertTrue(archive._live_write.result(timeout=5))
        archive.publish_live((), source_unavailable=True)
        self.assertTrue(archive._live_write.result(timeout=5))

        self.assertEqual(0, archive.views.page(period="all")["cached_total"])
        # Even recovery of the driver's health does not re-qualify old cards.
        watch = archive.watch_snapshot(live_eligible=lambda: True)
        self.assertEqual(("as-of", at, 2), (watch["freshness"], watch["observed_ms"], watch["generation"]))
        self.assertEqual([("known", "unverified")], [(card["title"], card["outcome"]) for card in watch["cards"]])

    def test_source_loss_and_recovery_invalidates_a_turn_held_inside_sqlite(self):
        archive, _ = self.bound_archive(lambda *_: None)
        now = int(time.time() * 1000) - 100
        staged, release = Event(), Event()

        def held_watch(*args):
            generation = publish_watch(*args)
            staged.set()
            if not release.wait(5):
                raise AssertionError("fixture did not release SQLite writer")
            return generation

        with patch("src.cache.display_history.publish_watch", side_effect=held_watch):
            try:
                publish_cycle(archive, now, "stale")
                pending = archive._live_write
                self.assertTrue(staged.wait(5))
                archive.publish_live((), source_unavailable=True)
                publish_cycle(archive, now + 1, "first recovery offer")
            finally:
                release.set()
            self.assertFalse(pending.result(timeout=5))
        empty = archive.watch_snapshot(live_eligible=lambda: True)
        self.assertEqual(("empty", 0), (empty["freshness"], archive.views.page(period="all")["cached_total"]))

        publish_cycle(archive, now + 2, "fresh")
        self.assertTrue(archive._live_write.result(timeout=5))
        watch = archive.watch_snapshot(live_eligible=lambda: True)
        self.assertEqual("fresh", watch["cards"][0]["title"])
        self.assertEqual(1, archive.views.page(period="all")["cached_total"])

    def test_clear_rejects_an_old_offer_and_does_not_promote_a_preclear_card_capture(self):
        archive, _ = self.bound_archive(lambda *_: None)
        source, binding = archive.views.source, archive.views.binding
        now = int(time.time() * 1000)
        at = now - 10
        frame = running_frame(at)
        observed = archive_watch_observation(frame, at)
        running = (RunningSession("root", "Observed title", at - 2000, at),)
        publish_cycle(archive, at, "before clear")
        self.assertTrue(archive._live_write.result(timeout=5))

        before = archive.history.source_state(source)
        with patch("src.application.session_archive_owner.time.time", return_value=now / 1000):
            cleared = archive.sessions.clear(source, binding, before, eligible=lambda: True,
                                             current_observation=lambda: 1)
            rejected = archive.sessions.commit_live(source, binding, running=running, watch=observed, clear_fence=0)
            empty = archive.watch_snapshot(live_eligible=lambda: True)
            # A fresh outer tick does not make the card's retained capture fresh.
            after_clear = replace(observed, observed_ms=now + 1, projected_ms=now + 1)
            accepted = archive.sessions.commit_live(source, binding, running=running, watch=after_clear, clear_fence=1)

        self.assertEqual(1, cleared.archive_epoch)
        self.assertFalse(rejected)
        self.assertEqual(("empty", []), (empty["freshness"], empty["cards"]))
        self.assertTrue(accepted)
        self.assertEqual(0, archive.views.page(period="all")["cached_total"])
        watch = archive.watch_snapshot(live_eligible=lambda: True)
        self.assertEqual("unverified", watch["cards"][0]["outcome"])

    def bound_archive(self, publish):
        path = self.root / "fixture.db"
        path.write_bytes(b"fixture identity")
        source = OpenCodeV1Source(path)
        driver = SimpleNamespace(error=None, terminal=False, coordinator=SimpleNamespace(catalog_observation=None,
            report_service=SimpleNamespace(timezone_id="UTC", selection=SimpleNamespace(selected="v1", source=source))))
        archive = DisplayArchive(self.root, publish, watch_enabled=True)
        self.addCleanup(archive.close)
        archive.observe(driver, before_tick=True)
        return archive, driver

    def test_health_lost_during_watch_read_withdraws_running_without_rereading_sqlite(self):
        path = self.root / "fixture.db"
        path.write_bytes(b"fixture identity")
        driver = SimpleNamespace(error=None, terminal=False, coordinator=SimpleNamespace(catalog_observation=None,
            report_service=SimpleNamespace(timezone_id="UTC",
                selection=SimpleNamespace(selected="v1", source=OpenCodeV1Source(path)))))
        archive = DisplayArchive(self.root, lambda *_: None, watch_enabled=True)
        self.addCleanup(archive.close)
        archive.observe(driver, before_tick=True)
        at = int(time.time() * 1000)
        archive.publish_live(None, running_frame(at), at)
        archive._live_write.result(timeout=5)
        eligible = iter((True, False))

        with patch.object(archive.history, "watch", wraps=archive.history.watch) as read:
            result = archive.watch_snapshot(live_eligible=lambda: next(eligible), presentation=True)

        read.assert_called_once()
        self.assertEqual("as-of", result["freshness"])
        self.assertEqual("unverified", result["cards"][0]["outcome"])
        self.assertEqual([], result["view"]["active_cards"])
        self.assertEqual("Observed title", result["view"]["earlier_cards"][0]["title"])


def publish_cycle(archive, at, title):
    frame = running_frame(at)
    card = replace(frame.active_cards[0], title=title)
    running = (RunningSession(card.session_id, title, at - 2000, at),)
    archive.publish_live(running, replace(frame, active_cards=(card,)), at)
