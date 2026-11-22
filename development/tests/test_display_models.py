"""Models retains qualified catalog facts; reads never use a finite job result."""
from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from development.tests.fixtures.compact_reports import Availability, NOW, report_service
from development.tests.test_web_dispatch import RecordingJobs
from src.application import ReportApplication
from src.cache.display_history import SessionChange, SessionFact
from src.cache.display_models import ModelPage
from src.reports import ReportRequest
from src.web.dispatch import DataDispatcher
from src.web.display_archive import DisplayArchive
from src.web.display_binding import DisplayBinding
from src.web.models_http import model_page


def model(name, costs, *, publisher="Publisher", release=None, selectable=True, superseded=False,
          superseded_selectable=False, promotion=None):
    return dict(publisher=publisher, model=name, category="Category", release_date=release, relative_cost=costs[0],
                relative_levels=[dict(relative_cost=value) for value in costs],
                selectable=selectable, superseded=superseded, superseded_selectable=superseded_selectable,
                promotional=promotion is not None, promotion=promotion, price_help="Published reference rates",
                display=dict(relative_cost="Exact reference ratio"))


def capture(rows, *, scope="source", observed=1000, boundary=None, stale=False):
    return dict(error=None, source=dict(status="acquired", model_scope=scope, observed_at_ms=observed,
                   model_price_boundary_ms=boundary, model_price_stale=stale),
                view=dict(kind="normal", model_catalog=dict(rows=rows), model_availability_empty=False,
                   model_availability_unverified=False, pricing_retrieved_at_ms=800,
                   display=dict(pricing_retrieved_at_ms="Last published")))


class DisplayModelsTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.events = []
        self.archive = DisplayArchive(Path(tmp.name), lambda kind, data: self.events.append((kind, data)),
                                      models_enabled=True)
        self.addCleanup(self.archive.close)
        self.assertTrue(self.archive.initialize())
        self.archive._set_binding(DisplayBinding("source", "selected-epoch"))
        self.models = self.archive.models

    def publish(self, rows, **observation):
        result = capture(rows, **observation)
        self.assertTrue(self.models.offer(self.models.binding(), result, eligible=lambda: True))
        action = self.archive.next_projection(lambda: None)
        action(result["source"]["observed_at_ms"], active=lambda: True)

    def names(self, request=None, *, now=2000):
        return [row["model"] for row in self.models.snapshot(request or ModelPage(), now)["rows"]]

    def test_exact_tier_vectors_use_null_last_per_tier_in_both_directions(self):
        self.publish([
            model("unknown", [None]), model("a", ["1.0000000000000000000000000001", "2"]),
            model("b", ["1.0000000000000000000000000002", "1"]),
            model("c", ["1.0000000000000000000000000001"]),
            model("d", ["1.0000000000000000000000000001", "3"]),
            model("e", ["1.0000000000000000000000000001", "2", None]),
            model("negative", ["-100"]), model("zero", ["0"]), model("also unknown", [None, None]),
        ])

        self.assertEqual(["negative", "zero", "a", "e", "d", "c", "b", "unknown", "also unknown"],
                         self.names(ModelPage(orders=(("cost", "asc"),))))
        self.assertEqual(["b", "d", "a", "e", "c", "zero", "negative", "unknown", "also unknown"], self.names())

    def test_typed_filters_multi_sort_and_bounded_paging(self):
        self.publish([
            model("A-old", ["2"], publisher="Á", superseded=True),
            model("A-hidden", ["2"], publisher="a", selectable=False),
            model("B-old", ["4"], publisher="b", superseded=True, superseded_selectable=True),
            model("B-new", ["3"], publisher="B"),
            model("Unknown publisher", ["3"], publisher=None),
            *(model(f"Extra {index:03d}", [None], publisher='Z') for index in range(50)),
        ])
        default = ModelPage(orders=(("publisher", "asc"), ("cost", "desc")))
        first = self.models.snapshot(default, 2000)
        last = self.models.snapshot(ModelPage(orders=default.orders, offset=50), 2000)
        everyone = self.names(ModelPage(show_all=True, latest=False, orders=default.orders))
        latest = self.names(ModelPage(show_all=True, orders=default.orders))

        self.assertEqual(53, first["count"])
        self.assertEqual(50, len(first["rows"]))
        self.assertEqual(["A-old", "B-new", "Extra 000"], [row["model"] for row in first["rows"][:3]])
        self.assertEqual(["Extra 048", "Extra 049", "Unknown publisher"], [row["model"] for row in last["rows"]])
        self.assertEqual(["A-old", "A-hidden", "B-old", "B-new"], everyone[:4])
        self.assertEqual(["A-hidden", "B-new", "Extra 000"], latest[:3])

    def test_promotion_expiry_masks_every_ratio_and_recent_marker_has_utc_boundary(self):
        day = 86_400_000
        offer = dict(through="1970-01-07", resumes="1970-01-08", description="Verified promotion")
        self.publish([model("regular", ["1"], release="1970-01-01"),
                      model("offer", ["4"], promotion=offer)], boundary=7 * day)
        fresh = self.models.snapshot(ModelPage(), 7 * day - 1)
        expired = self.models.snapshot(ModelPage(), 7 * day)

        self.assertTrue(fresh["rows"][0]["promotional"])
        self.assertTrue(fresh["rows"][1]["recent"])
        self.assertEqual(["regular", "offer"], [row["model"] for row in expired["rows"]])
        self.assertFalse(any(row["promotional"] or row["recent"] for row in expired["rows"]))
        self.assertTrue(all(row["display"]["relative_cost"] == "N/A" for row in expired["rows"]))

    def test_uncertain_work_cannot_replace_published_rows_after_rebind_or_clear(self):
        self.publish([model("saved", ["1"])])
        binding = self.models.binding()
        self.assertTrue(self.models.offer(binding, capture([model("old worker", ["2"])], observed=1001),
                                         eligible=lambda: True))
        self.archive._set_binding(DisplayBinding("foreign", "another"))
        self.assertIsNone(self.models.snapshot(ModelPage(), 2000)["count"])
        self.archive._set_binding(DisplayBinding("source", "reconnected"))
        self.assertEqual(["saved"], self.names())
        self.assertFalse(self.models.offer(binding, capture([], observed=1002), eligible=lambda: True))
        current = self.models.binding()
        self.assertTrue(self.models.offer(current, capture([], observed=1002), eligible=lambda: True))
        views = self.archive.views
        expected = self.archive.history.source_state(views.source)

        cleared = self.archive.sessions.clear(views.source, views.binding, expected, eligible=lambda: True,
                                              current_observation=lambda: 0)
        self.archive.next_projection(lambda: None)(2000, active=lambda: True)
        after = self.models.snapshot(ModelPage(), 2000)

        self.assertEqual(1, cleared.archive_epoch)
        self.assertEqual(1, after["archive_epoch"])
        self.assertIsNone(after["count"])

    def test_old_and_invalid_results_never_certify_empty_or_overwrite_same_scope(self):
        self.publish([model("current", ["1"])], observed=1010)
        events = tuple(self.events)
        self.publish([model("old", ["42"])], observed=1005)
        self.publish([model("duplicate", ["2"]), model("duplicate", ["3"])], observed=1020)

        self.assertEqual(events, tuple(self.events))
        self.assertEqual(["current"], self.names())
        self.models.invalidate_prices(1030)
        self.assertFalse(self.models.snapshot(ModelPage(), 2000)["prices_valid"])

    def test_legacy_v26_upgrade_keeps_prior_session_rows(self):
        history = self.archive.history
        history.commit_sessions("source", (SessionChange(SessionFact("prior", "r1", "Prior"), None),))
        with closing(sqlite3.connect(history.path, isolation_level=None)) as db:
            db.execute("DROP TABLE display_models")
            db.execute("DROP TABLE display_model_state")
            db.execute("PRAGMA user_version=26")

        self.assertTrue(self.archive.initialize())
        self.publish([model("new", ["1"])])

        self.assertEqual(1, history.session_page("source").total)
        self.assertEqual(["new"], self.names())

    def test_actual_models_worker_projection_is_a_complete_cache_input_without_history(self):
        availability = Availability()
        service = report_service(self, availability=availability)
        selected_scopes = []

        def qualify(selection):
            selected_scopes.append(selection)
            return "source"

        app = ReportApplication(lambda now, progress: service, clock=lambda: NOW, models_only=True,
                                models_binding=qualify)
        with patch.object(service, "session_catalog", side_effect=AssertionError("Models enumerated history")):
            produced = app.execute(ReportRequest()).to_json()

        self.assertIsNone(produced["error"])
        self.assertEqual(1, availability.calls)
        self.assertEqual([service.selection], selected_scopes)
        self.assertTrue(self.models.offer(self.models.binding(), produced, eligible=lambda: True))
        self.archive.next_projection(lambda: None)(NOW, active=lambda: True)

        expected = [row["model"] for row in produced["view"]["model_catalog"]["rows"]]
        actual = self.names(ModelPage(show_all=True, latest=False), now=NOW)
        self.assertGreater(len(actual), 0)
        self.assertCountEqual(expected, actual)

    def test_hidden_background_capture_and_read_path_are_separate(self):
        jobs = RecordingJobs()
        now = 1000
        dispatcher = DataDispatcher(jobs, clock=lambda: now, wall_clock=lambda: now, models=self.models,
                                    cache_only_mix=True, cache_only_stats=True)
        dispatcher.tick(identity="runtime")
        self.assertIsNone(self.models.snapshot(ModelPage(), now * 1000)["count"])
        self.assertEqual({}, jobs.values)
        now += 15
        dispatcher.tick()
        queued = jobs.values["0"]
        self.assertEqual("source", queued["request"].models_scope)
        self.assertEqual({"0": 2}, jobs.priorities)
        result = capture([model("cached", ["1"])], observed=now * 1000)
        queued.update(status="running", result=result)
        dispatcher.tick()
        self.assertFalse(self.models.pending())
        queued.update(status="complete")
        dispatcher.tick()
        self.assertTrue(self.models.pending())
        self.assertIsNone(dispatcher.entries[ReportRequest()]["result"])
        self.assertIsNone(self.models.snapshot(ModelPage(), now * 1000)["count"])

        self.archive.next_projection(lambda: None)(now * 1000, active=lambda: True)

        self.assertEqual(["cached"], self.names(now=now * 1000))
        self.assertEqual(1, len(jobs.values))

    def test_cached_models_route_reprioritizes_one_managed_job_without_a_report_request(self):
        jobs = RecordingJobs()
        dispatcher = DataDispatcher(jobs, clock=lambda: 1000, models=self.models,
                                    cache_only_mix=True, cache_only_stats=True)
        dispatcher.tick(identity="runtime")
        dispatcher.interest("tab", "models", True)
        self.assertEqual({}, jobs.values)  # HTTP lease cannot admit source work.

        dispatcher.tick()
        self.assertEqual({"0": 0}, jobs.priorities)
        dispatcher.interest("tab", "sessions", True)
        dispatcher.tick()
        self.assertEqual({"0": 2}, jobs.priorities)
        dispatcher.interest("tab", "models", True)
        dispatcher.tick()

        self.assertEqual({"0": 0}, jobs.priorities)
        self.assertEqual("source", jobs.values["0"]["request"].models_scope)
        self.assertEqual(1, len(jobs.values))

    def test_page_parser_rejects_unrecognized_columns_duplicate_orders_and_offsets(self):
        valid = dict(show_all=False, latest=True, orders=[["cost", "desc"]], offset=0)
        self.assertEqual(ModelPage(), model_page(valid))
        for change in (dict(orders=[["cost DESC", "desc"]]), dict(orders=[["model", "ASC"]]),
                       dict(orders=[["cost", "desc"], ["cost", "asc"]]), dict(offset=51), dict(offset=True),
                       dict(show_all=0), dict(source="foreign")):
            with self.subTest(change=change), self.assertRaises(ValueError):
                model_page({**valid, **change})
