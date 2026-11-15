"""Catalog-first Mini publication without rich history, browser leases or IO."""
from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace
import tempfile
import unittest

from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from development.tests.fixtures.watch_runtime import make_service
from development.tests.test_watch_cards import ManualWorkers
from src.application.live_projection import project_live
from src.application.session_catalog import SessionCatalog
from src.reports.models import SessionUsageRow
from src.reports.watch_capture import capture_rows
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
        self.assertEqual(first, catalog.previews()[0], "temporary gaps retain qualified same-source values")
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
        self.assertEqual((), cards.preview_cards(NOW))

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


if __name__ == "__main__":
    unittest.main()
