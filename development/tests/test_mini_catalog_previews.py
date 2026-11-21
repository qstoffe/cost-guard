"""Catalog-first Mini publication without rich history, browser leases or IO."""
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from development.tests.fixtures.synthetic_month import SyntheticMonthSource, make_root_snapshot
from development.tests.fixtures.catalog_previews import CatalogPreviewFixture
from development.tests.fixtures.watch_runtime import make_service
from development.tests.test_watch_cards import ManualWorkers
from src.application.live_projection import project_live
from src.application.session_catalog import SessionCatalog
from src.reports.models import SessionUsageRow
from src.reports.watch_capture import capture_rows
from src.sources.errors import http_failure, transport_failure
from src.watch.card_workers import CardResult
from src.watch.cards import WatchCards
from src.watch.models import WatchProjection
from src.watch.observers import observe_catalog
from src.watch.web_coordinator import WebWatchCoordinator

NOW = 1_000_000_000


def observed_catalog(count, *, indexed=False):
    source = SyntheticMonthSource(count, 0, month_start_ms=1000)
    source.snapshots = {key: replace(value, root=replace(value.root, active=False))
        for key, value in source.snapshots.items()}
    observation = observe_catalog(source, include_archived_revisions=True)
    catalog = SessionCatalog(clock_ms=lambda: NOW)
    catalog.observe(observation)
    if indexed:
        for index, key in enumerate(catalog.roots):
            catalog.rows[key] = SessionUsageRow(key, catalog.roots[key].title, "N/A", False,
                Decimal(index), 1, last_activity_ms=catalog.activity[key], context_tokens=999999)
            catalog.valid[key] = catalog.revisions[key], catalog.clock()
            catalog.activity_valid[key] = catalog.revisions[key]
    return source, catalog, observation


class MiniCatalogPreviewTests(unittest.TestCase):
    def test_browser_fixture_warms_only_today_slice_even_at_utc_midnight(self):
        midnight = int(datetime(2026, 11, 16, tzinfo=timezone.utc).timestamp() * 1000)
        for elapsed in (0, 13, 259, 260, 15 * 60_000, 12 * 3_600_000):
            now = midnight + elapsed
            with self.subTest(elapsed=elapsed), tempfile.TemporaryDirectory() as directory:
                fixture = CatalogPreviewFixture(Path(directory), now)
                self.addCleanup(fixture.close)
                cold = fixture.catalog.page(period="today")
                previews = fixture.catalog.previews()
                self.assertEqual(25, cold["total"])
                self.assertEqual(0, fixture.source.load_count)
                self.assertTrue(all(item.total_ccost is None for item in previews))

                warm = fixture.warm()

                self.assertEqual((25, 25), (warm["total"], warm["indexed"]))
                self.assertEqual(25, fixture.source.load_count)
                qualified = fixture.catalog.previews()
                self.assertEqual([item.session_id for item in previews],
                                 [item.session_id for item in qualified])
                self.assertEqual([Decimal("0.014200")] * 5,
                                 [item.total_ccost for item in qualified])
                self.assertTrue(all(item.activity_ms is not None for item in qualified))
                for index in range(3192, 3217):
                    snapshot = fixture.source.snapshots[f"root-{index:04d}"]
                    root = snapshot.root
                    self.assertEqual((root,), snapshot.sessions)
                    times = [root.created_at_ms, root.updated_at_ms]
                    for message in snapshot.messages:
                        times.append(message.created_at_ms)
                        if message.completed_at_ms is not None:
                            self.assertLessEqual(message.created_at_ms, message.completed_at_ms)
                            times.append(message.completed_at_ms)
                        for part in message.parts:
                            self.assertIn(part, snapshot.parts)
                    for part in snapshot.parts:
                        self.assertLessEqual(part.created_at_ms, part.updated_at_ms)
                        times.extend((part.created_at_ms, part.updated_at_ms))
                    times.extend(event.created_at_ms for event in snapshot.events)
                    for invocation in snapshot.invocations:
                        self.assertLessEqual(invocation.created_at_ms, invocation.completed_at_ms)
                        self.assertGreaterEqual(invocation.completed_at_ms, midnight)
                        times.extend((invocation.created_at_ms, invocation.completed_at_ms))
                    self.assertTrue(all(midnight - 3 <= at <= now for at in times))
                    self.assertTrue(all(root.created_at_ms <= at <= root.updated_at_ms for at in times))

    def test_qualified_sessions_first_page_reaches_next_publication_with_history_blocked(self):
        source, catalog, observation = observed_catalog(3217, indexed=True)
        page = catalog.page(period="all", sort="activity")
        self.assertEqual(25, len(page["view"]["session_usage"]))
        self.assertFalse(page["pending_sort"])
        cards = WatchCards(ManualWorkers())
        cards.catalog(observation)
        cards.history.checked, cards.history.total = 20, 3217
        owner = SimpleNamespace(cards=cards)
        frame = WatchProjection("Watch", "Synthetic", (), now_ms=NOW)
        counts = source.load_count, source.catalog_count, source.batch_count

        published = WebWatchCoordinator.catalog_frame(owner, catalog, frame)
        wire = project_live(published).to_json()

        expected = [f"root-{index:04}" for index in range(3216, 3211, -1)]
        self.assertEqual(expected, [item["session_id"] for item in wire["earlier_previews"]])
        self.assertEqual(expected, [row["session_id"] for row in page["view"]["session_usage"][:5]])
        self.assertEqual("3216", wire["earlier_previews"][0]["total_ccost"])
        self.assertEqual((), published.history_cards)
        self.assertEqual((20, 3217), (cards.history.checked, cards.history.total))
        self.assertEqual(counts, (source.load_count, source.catalog_count, source.batch_count))
        self.assertEqual(1, len(catalog.leases), "Mini never creates another browser lease")
        preview = wire["earlier_previews"][0]
        self.assertFalse({"prompt", "rows", "event_id", "context_tokens", "watch_next_context_tokens"} & preview.keys())

    def test_never_opened_sessions_publishes_metadata_and_loading_metrics_without_reads(self):
        source, catalog, observation = observed_catalog(2793)
        cards = WatchCards(ManualWorkers())
        cards.catalog(observation)
        counts = source.load_count, source.catalog_count, source.batch_count
        frame = WatchProjection("Watch", "Synthetic", (), now_ms=NOW)

        published = WebWatchCoordinator.catalog_frame(SimpleNamespace(cards=cards), catalog, frame)
        previews = project_live(published).to_json()["earlier_previews"]

        self.assertEqual(5, len(previews))
        self.assertEqual("Synthetic 2792", previews[0]["title"])
        self.assertEqual("catalog", previews[0]["activity_origin"])
        self.assertIsNone(previews[0]["total_ccost"])
        self.assertNotEqual("Loading…", previews[0]["display"]["activity_clock"])
        self.assertEqual({}, catalog.leases)
        self.assertEqual(counts, (source.load_count, source.catalog_count, source.batch_count))

    def test_invalidations_and_unknowns_do_not_revive_old_scalar_facts(self):
        _, catalog, observation = observed_catalog(3, indexed=True)
        first = catalog.previews()[0]
        key = first.session_id
        catalog.rows[key] = replace(catalog.rows[key], complete=False, ccost=Decimal(0))
        self.assertEqual(first.total_ccost, catalog.previews()[0].total_ccost,
            "an incomplete scalar refresh cannot replace qualified Total with a fabricated zero")
        catalog.observe(None, unavailable=True)
        catalog.index_failed()
        retained = catalog.previews()[0]
        self.assertEqual(first, replace(retained, total_state="ready"),
            "temporary gaps retain qualified same-source values")
        self.assertEqual("retained", retained.total_state)
        changed = replace(observation, revisions={**observation.revisions, key: "changed"})
        catalog.observe(changed)
        self.assertIsNone(catalog.previews()[0].total_ccost)
        catalog.observe(replace(changed, live_candidates=frozenset((key,))))
        self.assertNotIn(key, [item.session_id for item in catalog.previews()])
        catalog.observe(replace(changed, source_epoch="other"))
        self.assertTrue(all(item.total_ccost is None for item in catalog.previews()))
        catalog.observe(replace(changed, sessions=(), roots=()))
        self.assertEqual((), catalog.previews())

    def test_unqualified_zero_is_loading_and_dependency_changes_drop_last_good_total(self):
        _, catalog, _ = observed_catalog(1, indexed=True)
        key = "root-0000"
        catalog.rows[key] = replace(catalog.rows[key], complete=False, ccost=Decimal(0))
        self.assertIsNone(catalog.previews()[0].total_ccost)
        catalog.rows[key] = replace(catalog.rows[key], complete=True)
        self.assertEqual(Decimal(0), catalog.previews()[0].total_ccost, "qualified zero is real data")
        catalog.valid.clear()
        catalog.dependencies = "new-prices"
        self.assertIsNone(catalog.previews()[0].total_ccost)

    def test_event_activity_correction_and_ties_use_shared_current_index(self):
        _, catalog, observation = observed_catalog(3, indexed=True)
        key = "root-0002"
        catalog.rows[key] = replace(catalog.rows[key], last_activity_ms=1)

        previews = catalog.previews()

        self.assertEqual(["root-0001", "root-0000", key], [item.session_id for item in previews])
        self.assertEqual((1, "events"), (previews[-1].activity_ms, previews[-1].activity_origin))
        for key in catalog.rows:
            catalog.rows[key] = replace(catalog.rows[key], last_activity_ms=2)
        self.assertEqual(["root-0000", "root-0001", "root-0002"],
            [item.session_id for item in catalog.previews()])
        catalog.observe(replace(observation, source_epoch="new", sessions=tuple(
            replace(root, updated_at_ms=NOW + 1) for root in observation.sessions)))
        self.assertTrue(all(item.activity_ms is None for item in catalog.previews()))

    def test_real_representative_upgrades_without_global_certification_and_revisions_withdraw_it(self):
        source = SyntheticMonthSource(25, 1, month_start_ms=1000)
        source.snapshots = {key: replace(value, complete=True, root=replace(value.root, active=False))
            for key, value in source.snapshots.items()}
        observation = observe_catalog(source)
        catalog = SessionCatalog(clock_ms=lambda: NOW)
        catalog.observe(observation)
        workers = ManualWorkers()
        cards = WatchCards(workers)
        cards.catalog(observation)
        owner = SimpleNamespace(cards=cards)
        frame = WatchProjection("Watch", "Synthetic", (), now_ms=NOW)
        WebWatchCoordinator.catalog_frame(owner, catalog, frame)
        with tempfile.TemporaryDirectory() as directory:
            service = make_service(directory, source, now_ms=NOW)[2]
            root = catalog.roots[cards.preview_ids[0]]
            capture, item = capture_rows(service, root)
            entry = cards.sessions[root.session_id]
            cards.accept(CardResult(root.session_id, entry.generation, "rows",
                (capture, (), item.snapshot)), NOW)

        published = WebWatchCoordinator.catalog_frame(owner, catalog, frame)

        self.assertEqual([root.session_id], [card.session_id for card in published.earlier_cards])
        self.assertEqual(capture.history_row, published.earlier_cards[0].rows[0].prompt)
        self.assertEqual((), cards.project(NOW)[1], "true global proof still requires every root")
        self.assertEqual(0, cards.history.epoch)
        cards.catalog(replace(observation, revisions={**observation.revisions, root.session_id: "new"}))
        retained = cards.preview_cards(NOW)[0]
        self.assertEqual("refreshing", retained.state)
        self.assertIsNone(retained.observed_at_ms)

    def test_shortlist_bounds_speculative_history_and_keeps_running_capacity(self):
        _, catalog, observation = observed_catalog(324)
        workers = ManualWorkers()
        cards = WatchCards(workers)
        cards.catalog(observation)
        WebWatchCoordinator.catalog_frame(SimpleNamespace(cards=cards), catalog,
            WatchProjection("Watch", "Synthetic", (), now_ms=NOW))

        cards.tick(NOW)

        self.assertEqual(4, len(workers.jobs))
        self.assertTrue(set(workers.jobs).issubset(cards.preview_ids))
        self.assertEqual(("root-0323", "root-0322", "root-0321", "root-0320"),
            tuple(workers.submissions))
        self.assertEqual(3, len(catalog.previews(("root-0323", "root-0322"), limit=3)))
        self.assertEqual((), catalog.previews(limit=0))

    def test_metadata_only_preview_settles_after_a_complete_empty_capture(self):
        source, catalog, observation = observed_catalog(1)
        cards = WatchCards(ManualWorkers())
        cards.catalog(observation)
        owner = SimpleNamespace(cards=cards)
        frame = WatchProjection("Watch", "Synthetic", (), now_ms=NOW)
        WebWatchCoordinator.catalog_frame(owner, catalog, frame)
        cards.tick(NOW)
        root = next(iter(catalog.roots.values()))
        with tempfile.TemporaryDirectory() as directory:
            service = make_service(directory, source, now_ms=NOW)[2]
            capture, item = capture_rows(service, root)
            capture = replace(capture, rows=(), authoritative=True, retained=False)
            del cards.workers.jobs[root.session_id]
            cards.accept(CardResult(root.session_id, cards.sessions[root.session_id].generation,
                "rows", (capture, (), item.snapshot)), NOW)

        result = WebWatchCoordinator.catalog_frame(owner, catalog, frame)

        self.assertEqual((), result.earlier_cards)
        self.assertEqual("unknown", result.earlier_previews[0].hydration_state)

    def test_visible_preview_recovers_after_long_read_revision_churn_and_retry(self):
        now = NOW
        source = SyntheticMonthSource(5, 1, month_start_ms=1000)
        source.snapshots = {key: replace(value, complete=True) for key, value in source.snapshots.items()}
        catalog = SessionCatalog(clock_ms=lambda: now)
        workers = ManualWorkers()
        cards = WatchCards(workers, monotonic=lambda: now / 1000)
        owner = SimpleNamespace(cards=cards)
        target = "root-0004"

        def publish():
            frame = WatchProjection("Watch", "Synthetic", (), now_ms=now)
            result = WebWatchCoordinator.catalog_frame(owner, catalog, frame)
            return next(item for item in result.earlier_previews if item.session_id == target), result.earlier_cards

        def observe():
            observation = observe_catalog(source, include_archived_revisions=True)
            catalog.observe(observation)
            cards.catalog(observation)

        observe()
        self.assertEqual("queued", publish()[0].hydration_state)
        cards.tick(now)
        initial = workers.jobs[target]
        self.assertEqual("reading", publish()[0].hydration_state)
        with tempfile.TemporaryDirectory() as directory:
            service = make_service(directory, source, now_ms=now)[2]
            for minutes, indexes in ((7, (5, 6)), (12, (7, 8, 9)), (30, (10, 11))):
                now = NOW + minutes * 60_000
                for key in tuple(source.snapshots):
                    if key > target:
                        # Previously arrived short-lived sessions were removed.
                        del source.snapshots[key]
                        workers.jobs.pop(key, None)
                for index in indexes:
                    raw = make_root_snapshot(index, 1, month_start_ms=1000)
                    source.snapshots[raw.root.session_id] = replace(raw, complete=True)
                observe()
                for sibling, generation in tuple(workers.jobs.items()):
                    if sibling != target:
                        capture, item = capture_rows(service, source.snapshots[sibling].root)
                        del workers.jobs[sibling]
                        cards.accept(CardResult(sibling, generation, "rows", (capture, (), item.snapshot)), now)
                self.assertEqual("waiting", publish()[0].hydration_state)
                cards.tick(now)
                self.assertEqual(initial, workers.jobs[target])
                self.assertLessEqual(len(workers.jobs), workers.limit)
            old_capture, old_item = capture_rows(service, source.snapshots[target].root)
            source.snapshots[target] = replace(source.snapshots[target], source_revision="new")
            observe()
            del workers.jobs[target]
            cards.accept(CardResult(target, initial, "rows", (old_capture, (), old_item.snapshot)), now)
            cards.tick(now)
            current = workers.jobs.pop(target)
            self.assertNotEqual(initial, current)
            cards.accept(CardResult(target, current, "unavailable", transport_failure(TimeoutError(), phase="capture")), now)
            self.assertEqual("retrying", publish()[0].hydration_state)
            cards.tick(now + 1000)
            self.assertNotIn(target, workers.jobs)
            now += 5000
            cards.tick(now)
            current = workers.jobs.pop(target)
            cards.accept(CardResult(target, current, "unavailable", http_failure(401, phase="capture")), now)
            now += 300_000
            cards.tick(now)
            self.assertNotIn(target, workers.jobs)
            self.assertEqual(("unavailable", "http_auth_failure"),
                (publish()[0].hydration_state, publish()[0].hydration_reason))
            source.snapshots[target] = replace(source.snapshots[target], source_revision="recovered")
            observe()
            cards.tick(now)
            capture, item = capture_rows(service, source.snapshots[target].root)
            cards.accept(CardResult(target, workers.jobs.pop(target), "rows", (capture, (), item.snapshot)), now)

        preview, rich = publish()
        self.assertEqual("ready", preview.hydration_state)
        self.assertIsNone(preview.total_ccost, "card success alone is not scalar total proof")
        self.assertEqual(capture.history_row, next(card.rows[0].prompt for card in rich if card.session_id == target))
        self.assertTrue({"root-0005", "root-0006"} & set(workers.submissions))


if __name__ == "__main__":
    unittest.main()
