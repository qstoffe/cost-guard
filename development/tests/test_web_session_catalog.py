"""Full-catalog keys, cold indexing, retained epochs and scalar-cache boundaries."""
from dataclasses import replace
from decimal import Decimal
from threading import Event, Lock
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from development.tests.fixtures.compact_reports import report_service
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from development.tests.fixtures.watch_runtime import make_service
from src.application.session_catalog import SessionCatalog, SORTS
from src.domain import ModelRef
from src.reports.models import SessionUsageRow
from src.reports.session_summary import ALGORITHM, NAMESPACE, session_summary, summary_key
from src.reports.watch_capture import capture_rows
from src.sources.errors import SourceUnavailableError, SourceSchemaError
from src.watch.observers import observe_catalog
from src.web.session_catalog import catalog_page
from src.watch.web_coordinator import WebWatchCoordinator


class SessionCatalogTests(unittest.TestCase):
    def setUp(self):
        self.clock = 0
        self.source = SyntheticMonthSource(120, 1, month_start_ms=1000)
        self.service = report_service(self, self.source, now_ms=100_000_000)
        self.catalog = SessionCatalog(clock=lambda: self.clock)
        self.observe()

    def observe(self):
        self.catalog.observe(observe_catalog(self.source, include_archived_revisions=True))

    def index(self):
        for number, (key, root) in enumerate(self.catalog.roots.items()):
            self.catalog.rows[key] = SessionUsageRow(key, root.title, f"Model {number:03}", False,
                Decimal(number) / 1000, number, duration_ms=number * 1000,
                last_activity_ms=self.catalog.activity[key])
            self.catalog.valid[key] = self.catalog.revisions[key], self.clock

    def test_every_sort_orders_full_catalog_with_numeric_keys_and_stable_ties(self):
        self.index()
        for sort in SORTS:
            with self.subTest(sort=sort):
                page = self.catalog.page(sort=sort, direction=-1)
                self.assertFalse(page["pending_sort"])
                self.assertEqual(page["total"], 120)
                rows = page["view"]["session_usage"]
                self.assertEqual(len(rows), 50)
                self.assertEqual(rows[0]["session_id"], "root-0119")
                following = self.catalog.page(token=page["token"], offset=50, epoch=page["epoch"], sort=sort)
                ids = [row["session_id"] for row in rows + following["view"]["session_usage"]]
                self.assertEqual(len(set(ids)), 100)
                self.assertEqual(ids[50], "root-0069")

    def test_new_arrivals_keep_older_epoch_stable_and_page_one_live(self):
        self.index()
        page = self.catalog.page()
        second = self.catalog.page(token=page["token"], offset=50, epoch=page["epoch"])
        original = [row["session_id"] for row in second["view"]["session_usage"]]
        newer = SyntheticMonthSource(121, 1, month_start_ms=1000)
        self.catalog.observe(observe_catalog(newer, include_archived_revisions=True))
        retained = self.catalog.page(token=page["token"], offset=50, epoch=page["epoch"])
        self.assertEqual([row["session_id"] for row in retained["view"]["session_usage"]], original)
        self.assertEqual(retained["total"], 120)
        latest = self.catalog.page(token=page["token"])
        self.assertEqual(latest["total"], 121)
        self.assertEqual(latest["view"]["session_usage"][0]["session_id"], "root-0120")
        self.catalog.observe(None, unavailable=True)
        failed = self.catalog.page(token=page["token"])
        self.assertEqual(failed["total"], 121)
        self.assertEqual(failed["state"], "source_unavailable")

    def test_cold_pending_sort_warms_in_bounded_slices_and_revalidates(self):
        page = self.catalog.page(sort="ccost")
        self.assertTrue(page["pending_sort"])
        self.assertEqual(page["sort"], "activity")
        self.assertIsNone(page["view"]["session_usage"][0]["prompt_count"])
        for _ in range(30):
            before = self.source.load_count
            self.clock += 6
            self.catalog.tick(self.service)
            self.assertLessEqual(self.source.load_count - before, 4)
        ready = self.catalog.page(token=page["token"], sort="ccost")
        self.assertFalse(ready["pending_sort"])
        self.assertEqual(ready["indexed"], 120)
        snapshot = self.source.snapshots["root-0000"]
        self.source.snapshots["root-0000"] = replace(snapshot, source_revision="changed")
        self.observe()
        stale = self.catalog.page(token=page["token"], sort="ccost")
        self.assertTrue(stale["pending_sort"])
        self.assertEqual(stale["indexed"], 119)
        self.clock += 6
        self.catalog.tick(self.service)
        self.assertEqual(self.catalog.page(token=page["token"], sort="ccost")["indexed"], 120)

    def test_hidden_metric_sort_drops_global_work_without_expiring_page_epoch(self):
        page = self.catalog.page(sort='ccost')
        self.catalog.enable_warm()
        catalog_page(self.catalog, {'action': 'interest', 'token': page['token'], 'visible': True})
        self.assertEqual(120, len(self.catalog._targets()))
        catalog_page(self.catalog, {'action': 'interest', 'token': page['token'], 'visible': False})
        self.assertEqual(50, len(self.catalog._targets()))
        self.assertIn(page['epoch'], self.catalog.leases[page['token']]['epochs'])
        self.catalog.interest(page['token'], True)
        self.clock += 91
        self.assertEqual(50, len(self.catalog._targets()), 'expired visibility cannot retain a global sort scan')

    def test_scalar_cache_reuse_without_history_hydration_and_active_bypass(self):
        root = next(iter(self.catalog.roots.values()))
        revision = self.catalog.revisions[root.session_id]
        row, actual = session_summary(self.service, root, revision)
        self.assertEqual(actual, revision)
        self.assertFalse(row.complete, "the fixture lacks complete-source proof, even with fully priced requests")
        with patch.object(self.service, "_analyze", side_effect=AssertionError("unexpected hydration")):
            cached, _ = session_summary(self.service, root, revision)
        self.assertEqual(cached, row)
        with patch.object(self.service, "_analyze", wraps=self.service._analyze) as acquire:
            session_summary(self.service, root, revision, active=True)
        self.assertTrue(acquire.call_args.kwargs["force_fresh"])

    def test_only_viewed_pages_warm_until_a_global_metric_sort_requires_more_keys(self):
        first = self.catalog.page()
        visible = {row["session_id"] for row in first["view"]["session_usage"]}
        acquired = []
        def summary(service, root, revision, **kwargs):
            acquired.append(root.session_id)
            return SessionUsageRow(root.session_id, root.title, "N/A", False, Decimal(0), 0), revision
        with patch("src.application.session_catalog.session_summary", side_effect=summary):
            self.catalog.tick(self.service)
            self.assertTrue(set(acquired).issubset(visible))
            self.clock += 6
            second = self.catalog.page(token=first["token"], offset=50, epoch=first["epoch"])
            current = {row["session_id"] for row in second["view"]["session_usage"]}
            self.catalog.tick(self.service)
            self.assertTrue(set(acquired[4:7]).issubset(current))
            self.assertTrue(set(acquired[4:]).issubset(current))
            for _ in range(30):
                self.clock += 6
                self.catalog.tick(self.service)
            self.assertLessEqual(len(acquired), 54, 'no speculative hydration of unvisited pages')
            pending = self.catalog.page(token=first['token'], sort='prompts')
            self.assertTrue(pending['pending_sort'])
            for _ in range(30):
                self.clock += 6
                self.catalog.tick(self.service)
        self.assertEqual(len(acquired), 120)
        self.assertEqual(len(set(acquired)), 120, 'global sort acquires missing keys exactly once')
        ready = self.catalog.page(token=first['token'], sort='prompts')
        self.assertFalse(ready["pending_sort"])

    def test_repeated_catalog_publication_and_page_navigation_do_not_renew_age(self):
        observation = self.catalog.last_observation
        first = self.catalog.page()
        self.clock = 3601
        self.catalog.observe(observation)
        old = self.catalog.page()
        self.assertEqual(3_601_000, old['age_ms'])
        self.observe()
        self.assertEqual(0, self.catalog.page()['age_ms'])

    def test_unvisited_warming_is_bounded_to_first_fifty_rows(self):
        self.catalog.enable_warm()
        acquired = []
        def summary(service, root, revision, **kwargs):
            acquired.append(root.session_id)
            return SessionUsageRow(root.session_id, root.title, 'N/A', False, Decimal(0), 0), revision
        with patch('src.application.session_catalog.session_summary', side_effect=summary):
            for _ in range(20):
                if self.catalog.needed():
                    self.catalog.tick(self.service)
                self.clock += 15
        self.assertEqual(50, len(acquired))
        self.assertEqual(50, len(set(acquired)))

    def test_visible_second_page_finishes_during_quiet_background_delay_without_retry(self):
        self.catalog.enable_warm()
        first = self.catalog.page()
        self.catalog.interest(first['token'], True)
        for _ in range(13):
            self.catalog.tick(self.service)
        self.assertEqual(50, self.catalog.page(token=first['token'])['page_ready'])
        self.catalog.interest(first['token'], False)
        self.catalog.tick(self.service)
        quiet_due = self.catalog.background_due
        self.assertEqual(900, quiet_due)

        # A quick visit followed by navigation away is not completed warming.
        second = self.catalog.page(token=first['token'], offset=50, epoch=first['epoch'])
        self.catalog.interest(first['token'], False)
        self.clock = 240
        self.assertEqual(0, second['page_ready'])
        self.assertFalse(self.catalog.needed())
        self.assertEqual(quiet_due, self.catalog.background_due)
        before = self.source.load_count

        self.catalog.interest(first['token'], True)
        for _ in range(13):
            self.assertTrue(self.catalog.needed())
            self.catalog.tick(self.service)
        ready = self.catalog.page(token=first['token'], offset=50, epoch=first['epoch'])

        self.assertEqual(50, ready['page_ready'])
        self.assertTrue(all(row['metric_state'] == 'ready' for row in ready['view']['session_usage']))
        self.assertEqual([row['session_id'] for row in second['view']['session_usage']],
                         [row['session_id'] for row in ready['view']['session_usage']])
        self.assertEqual(first['epoch'], ready['epoch'])
        self.assertEqual(50, self.source.load_count - before)
        self.assertEqual(100, len(self.catalog.valid), 'unvisited third page is not hydrated')
        self.assertLess(self.clock, self.catalog.background_due, 'visible work bypasses the quiet delay')

    def test_failed_rows_are_unavailable_or_retained_not_endlessly_pending(self):
        first = self.catalog.page()
        self.assertTrue(all(row["metric_state"] == "pending" for row in first["view"]["session_usage"]))
        with patch("src.application.session_catalog.session_summary", side_effect=SourceUnavailableError("safe")):
            self.catalog.tick(self.service)
        failed = self.catalog.page(token=first["token"])["view"]["session_usage"][:4]
        self.assertTrue(all(row["metric_state"] == "unavailable" for row in failed))
        self.index()
        key = "root-0119"
        self.catalog.rows[key] = replace(self.catalog.rows[key], running=True, prompt_count=0)
        self.catalog.failures[key] = self.catalog.revisions[key], False
        row = self.catalog.page(token=first["token"])["view"]["session_usage"][0]
        self.assertEqual(row["metric_state"], "retained")
        self.assertEqual(row["prompt_count"], 0)
        self.assertFalse(row["running"], "failed evidence cannot confirm currently running work")
        self.catalog.failures.clear()
        self.assertTrue(self.catalog.page(token=first["token"])["view"]["session_usage"][0]["running"])
        self.clock += 16
        self.assertFalse(self.catalog.page(token=first["token"])["view"]["session_usage"][0]["running"])
        self.catalog.observe(None, unavailable=True)
        self.assertEqual(self.catalog.page(token=first["token"])["view"]["session_usage"][0]["metric_state"], "retained")

    def test_slow_failed_root_respects_slice_budget_and_terminal_revision_boundary(self):
        self.catalog.page()
        def fail(service, root, revision, **kwargs):
            self.clock += 3
            raise SourceSchemaError("safe")
        with patch("src.application.session_catalog.session_summary", side_effect=fail) as acquire:
            self.catalog.tick(self.service)
        self.assertEqual(acquire.call_count, 1)
        key = acquire.call_args.args[1].session_id
        self.clock += 60
        self.assertFalse(self.catalog._eligible(key))
        snapshot = self.source.snapshots[key]
        self.source.snapshots[key] = replace(snapshot, source_revision="recovered")
        self.observe()
        self.assertTrue(self.catalog._eligible(key))

    def test_index_lane_failure_keeps_values_truthful_and_backs_off_without_rehydration(self):
        page = self.catalog.page()
        self.catalog.index_failed()
        unavailable = self.catalog.page(token=page["token"])
        self.assertTrue(all(row["metric_state"] == "unavailable" for row in unavailable["view"]["session_usage"]))
        self.assertFalse(self.catalog.needed())
        self.clock += 31
        self.assertTrue(self.catalog.needed())
        self.catalog.tick(self.service)
        self.assertFalse(self.catalog.index_unavailable)
        self.index()
        self.catalog.index_failed()
        retained = self.catalog.page(token=page["token"], sort="prompts")
        self.assertTrue(retained["pending_sort"])
        self.assertEqual(retained["view"]["session_usage"][0]["metric_state"], "retained")

    def test_partial_unknown_metrics_are_indexed_but_sort_last_both_directions(self):
        self.index()
        key = "root-0119"
        self.catalog.rows[key] = replace(self.catalog.rows[key], complete=False, duration_ms=None)
        for sort in ("ccost", "duration"):
            for direction in (-1, 1):
                page = self.catalog.page(sort=sort, direction=direction)
                final = self.catalog.page(token=page["token"], offset=100, epoch=page["epoch"], sort=sort)
                self.assertEqual(final["view"]["session_usage"][-1]["session_id"], key)
                self.assertFalse(page["pending_sort"])

    def test_restart_reuses_scalar_cache_but_corruption_and_dependencies_miss(self):
        root = self.catalog.roots["root-0000"]
        revision = self.catalog.revisions[root.session_id]
        row, _ = session_summary(self.service, root, revision)
        restarted = report_service(self, self.source)
        restarted.cache_repository = self.service.cache_repository
        with patch.object(restarted, "_analyze", side_effect=AssertionError("unexpected history read")):
            self.assertEqual(session_summary(restarted, root, revision)[0], row)
        key = summary_key(restarted, root)
        for payload in ({}, {"ccost": "NaN"}, [], {"ccost": "0", "prompt_count": False}):
            restarted.cache_repository.put(NAMESPACE, key, payload,
                source_revision=revision, algorithm_version=ALGORITHM)
            with patch.object(restarted, "_analyze", wraps=restarted._analyze) as acquire:
                session_summary(restarted, root, revision)
            self.assertEqual(acquire.call_count, 1)
        with patch.object(restarted, "_dependencies", return_value=("changed-analysis-config",)):
            with patch.object(restarted, "_analyze", side_effect=RuntimeError("cache_miss")):
                with self.assertRaisesRegex(RuntimeError, "cache_miss"):
                    session_summary(restarted, root, revision)

    def test_idle_catalog_reuses_epoch_and_slice_stops_after_slow_root(self):
        first = self.catalog.page()
        self.assertEqual(self.catalog.page(token=first["token"])["epoch"], first["epoch"])
        def slow(service, root, revision, **kwargs):
            self.clock += 3
            return SessionUsageRow(root.session_id, root.title, "N/A", False, Decimal(0), 0), revision
        with patch("src.application.session_catalog.session_summary", side_effect=slow) as acquire:
            self.catalog.tick(self.service)
        self.assertEqual(acquire.call_count, 1)
        self.index()
        self.assertFalse(self.catalog.needed())
        self.clock += 61
        self.assertTrue(self.catalog.needed(), "dependencies must be revalidated even without changed roots")

    def test_source_identity_change_invalidates_keys_even_with_same_revision(self):
        self.index()
        original = self.catalog.page()
        self.catalog.page(token=original['token'], epoch=original['epoch'], offset=100)
        snapshot = self.source.snapshots["root-0000"]
        moved = replace(snapshot.root, provenance=replace(snapshot.root.provenance, source_instance="new-source"))
        self.source.snapshots[moved.session_id] = replace(snapshot, root=moved, sessions=(moved,))
        self.observe()
        with self.assertRaisesRegex(KeyError, 'catalog_expired'):
            self.catalog.page(token=original['token'], epoch=original['epoch'], offset=100)
        page = self.catalog.page(sort="ccost")
        self.assertTrue(page["pending_sort"])
        self.assertEqual(page["indexed"], 119)

    def test_out_of_range_retained_page_requires_explicit_recovery(self):
        original = self.catalog.page()
        with self.assertRaisesRegex(KeyError, 'catalog_expired'):
            self.catalog.page(token=original['token'], epoch=original['epoch'], offset=150)
        latest = self.catalog.page(token=original['token'])
        self.assertEqual(latest['offset'], 0)
        self.assertEqual(len(latest['view']['session_usage']), 50)

    def test_blocked_catalog_worker_does_not_occupy_detail_or_http_lane(self):
        entered, released, captured = Event(), Event(), Event()
        with tempfile.TemporaryDirectory() as tmp:
            config, selection, service, _ = make_service(tmp, self.source)
            owner = WebWatchCoordinator(selection=selection, report_service=service, config=config,
                service_factory=lambda now: make_service(tmp, self.source, now_ms=now)[2])
            owner.catalog_observation = observe_catalog(self.source, include_archived_revisions=True)
            self.catalog.page()
            details = SimpleNamespace(lock=Lock(), leases={"owned": {}}, tick=lambda *args, **kwargs: captured.set())
            def blocked(service):
                entered.set()
                if not released.wait(3):
                    raise AssertionError("catalog test release missing")
            try:
                with patch.object(self.catalog, "tick", side_effect=blocked):
                    owner.tick_catalog(self.catalog)
                    self.assertTrue(entered.wait(1))
                    self.assertEqual(self.catalog.page()["total"], 120)
                    owner.tick_details(details)
                    self.assertTrue(captured.wait(1), "detail lane blocked behind catalog")
                    owner.detail_job.result(timeout=1)
                    self.assertFalse(owner.catalog_job.done())
                    released.set()
                    owner.catalog_job.result(timeout=1)
            finally:
                released.set()
                owner.close()

    def test_expired_epochs_invalid_requests_and_archived_membership(self):
        snapshot = self.source.snapshots["root-0000"]
        archived = replace(snapshot.root, archived_at_ms=2000)
        self.source.snapshots["root-0000"] = replace(snapshot, root=archived,
            sessions=(archived, *snapshot.sessions[1:]))
        self.observe()
        self.assertIn("root-0000", self.catalog.revisions)
        self.assertEqual(len(self.catalog.roots), 120)
        page = self.catalog.page()
        self.clock = 301
        with self.assertRaises(KeyError):
            self.catalog.page(token=page["token"], offset=50, epoch=page["epoch"])
        for request in ({"offset": True}, {"offset": 1}, {"direction": True}, {"sort": "raw"}, {"action": "scan"}):
            with self.subTest(request=request), self.assertRaises(ValueError):
                catalog_page(self.catalog, request)

    def test_cold_running_proof_survives_scalar_churn_but_not_age_outage_or_newer_finish(self):
        root = self.catalog.roots["root-0119"]
        self.catalog.active = frozenset((root.session_id,))
        first = self.catalog.page()
        self.assertFalse(first["view"]["session_usage"][0]["running"], "a candidate alone is not proof")
        self.catalog.observe_prompts(((root, True, 0),))
        cold = self.catalog.page(token=first["token"])["view"]["session_usage"][0]
        self.assertTrue(cold["running"])
        self.assertEqual(cold["title"], root.title)
        self.assertEqual(cold["metric_state"], "pending")
        self.assertFalse(cold["has_summary"])
        self.index()
        snapshot = self.source.snapshots[root.session_id]
        self.source.snapshots[root.session_id] = replace(snapshot, source_revision="streaming")
        self.clock = 5
        self.observe()
        self.catalog.observe_prompts(((root, True, 5),))
        retained = self.catalog.page(token=first["token"])["view"]["session_usage"][0]
        self.assertTrue(retained["running"])
        self.assertEqual(retained["metric_state"], "retained")
        self.catalog.index_failed()
        self.assertTrue(self.catalog.page(token=first["token"])["view"]["session_usage"][0]["running"],
                        "pricing/index failure cannot erase independent prompt proof")
        self.catalog.observe(None, unavailable=True)
        self.assertFalse(self.catalog.page(token=first["token"])["view"]["session_usage"][0]["running"])
        self.observe()
        self.clock = 16
        self.catalog.observe_prompts(((root, True, 16),))
        self.assertFalse(self.catalog.page(token=first["token"])["view"]["session_usage"][0]["running"],
                         "repeated publication must not renew stale proof")
        self.catalog.prompt_activity[root.session_id] = (15, True)
        self.catalog.observe_prompts(((root, False, 0),))
        self.assertFalse(self.catalog.page(token=first["token"])["view"]["session_usage"][0]["running"])
        self.clock = 17
        self.catalog.observe_prompts(((root, True, 0),))
        self.assertTrue(self.catalog.page(token=first["token"])["view"]["session_usage"][0]["running"])
        foreign = replace(root, provenance=replace(root.provenance, source_instance="foreign"))
        self.catalog.prompt_activity.clear()
        self.catalog.observe_prompts(((foreign, True, 0),))
        self.assertFalse(self.catalog.page(token=first["token"])["view"]["session_usage"][0]["running"])

    def test_live_summary_fields_advance_independently_and_unknowns_are_not_zero(self):
        source = SyntheticMonthSource(1, 1, month_start_ms=1000, running_roots=1)
        service = report_service(self, source, now_ms=100_000)
        catalog = SessionCatalog(clock=lambda: self.clock)
        catalog.observe(observe_catalog(source, include_archived_revisions=True))
        page = catalog.page()
        catalog.tick(service)
        initial = catalog.page(token=page["token"])["view"]["session_usage"][0]
        self.assertTrue(initial["running"])
        self.assertEqual(initial["prompt_count"], 1)
        self.assertNotEqual(initial["model"], "N/A")
        for count in (2, 3):
            newer = SyntheticMonthSource(1, count, month_start_ms=1000, running_roots=1)
            snapshot = newer.snapshots["root-0000"]
            source.snapshots["root-0000"] = replace(snapshot, source_revision=f"usage-{count}")
            self.clock += 6
            catalog.observe(observe_catalog(source, include_archived_revisions=True))
            catalog.tick(service)
            current = catalog.page(token=page["token"])["view"]["session_usage"][0]
            self.assertEqual(current["prompt_count"], count)
            self.assertGreater(Decimal(current["ccost"]), Decimal(initial["ccost"]))
        row = catalog.rows["root-0000"]
        catalog.rows["root-0000"] = replace(row, model="N/A", ccost=Decimal("1.25"), complete=False,
                                           prompt_count=0, duration_ms=None, model_pending=True)
        unknown = catalog.page(token=page["token"])["view"]["session_usage"][0]
        self.assertEqual(unknown["metric_states"]["model"], "pending")
        self.assertEqual(unknown["metric_states"]["duration"], "ready")
        self.assertEqual(unknown["prompt_count"], 0)
        self.assertIsNone(unknown["duration_ms"])
        self.assertIn("?", unknown["display"]["ccost"])
        source.snapshots["root-0000"] = replace(SyntheticMonthSource(1, 3, month_start_ms=1000)
            .snapshots["root-0000"], source_revision="finished")
        self.clock += 6
        catalog.observe(observe_catalog(source, include_archived_revisions=True))
        catalog.tick(service)
        ended = catalog.page(token=page["token"])["view"]["session_usage"][0]
        self.assertFalse(ended["running"])
        self.clock += 60
        idle = catalog.page(token=page["token"])["view"]["session_usage"][0]
        self.assertEqual((idle["ccost"], idle["duration_ms"]), (ended["ccost"], ended["duration_ms"]))

    def test_contributors_are_distinct_provider_qualified_bounded_and_allowlisted(self):
        root = self.catalog.roots["root-0000"]
        item = self.service._analyze(root, detail=True)
        entry = item.bundle.trace_entries[0]
        entries = (entry, entry, replace(entry, session_id="attributed-child", model=ModelRef("other", "gpt-test")))
        item = replace(item, bundle=replace(item.bundle, trace_entries=entries),
                       snapshot=replace(item.snapshot, complete=True))
        row = self.service._session_rows((item,))[0]
        self.assertTrue(row.multiple_models)
        self.assertEqual(row.contributor_models, ("github-copilot/gpt-test", "other/gpt-test"))
        self.assertTrue(row.contributor_models_complete)
        self.catalog.rows[root.session_id] = row
        self.catalog.valid[root.session_id] = self.catalog.revisions[root.session_id], self.clock
        exported = next(value for value in self.catalog.page(sort="name", direction=1)["view"]["session_usage"]
                        if value["session_id"] == root.session_id)
        self.assertEqual(exported["contributor_models"], list(row.contributor_models))
        self.assertNotIn("trace_entries", exported)
        many = tuple(replace(entry, model=ModelRef("provider", f"model-{index:03}")) for index in range(70))
        bounded = self.service._session_rows((replace(item, bundle=replace(item.bundle, trace_entries=many)),))[0]
        self.assertEqual(len(bounded.contributor_models), 64)
        self.assertFalse(bounded.contributor_models_complete)

    def test_old_and_malformed_contributor_cache_payloads_are_not_authoritative(self):
        root = self.catalog.roots["root-0000"]
        revision = self.catalog.revisions[root.session_id]
        session_summary(self.service, root, revision)
        key = summary_key(self.service, root)
        cached = self.service.cache_repository.get(NAMESPACE, key)
        for models in (["not-qualified"], ["z/model", "a/model"], ["a/model"] * 65):
            payload = dict(cached.payload, contributor_models=models)
            self.service.cache_repository.put(NAMESPACE, key, payload, source_revision=revision, algorithm_version=ALGORITHM)
            with patch.object(self.service, "_analyze", wraps=self.service._analyze) as acquire:
                session_summary(self.service, root, revision)
            self.assertEqual(acquire.call_count, 1)
        self.service.cache_repository.put(NAMESPACE, key, cached.payload, source_revision=revision,
                                           algorithm_version="session-summary-1")
        with patch.object(self.service, "_analyze", wraps=self.service._analyze) as acquire:
            session_summary(self.service, root, revision)
        self.assertEqual(acquire.call_count, 1)

    def test_web_adapter_shares_fresh_canonical_watch_proof_without_new_acquisition(self):
        source = SyntheticMonthSource(1, 1, month_start_ms=1000, running_roots=1)
        source.snapshots["root-0000"] = replace(source.snapshots["root-0000"], complete=True)
        service = report_service(self, source, now_ms=5000)
        root = source.snapshots["root-0000"].root
        capture, item = capture_rows(service, root)
        self.assertTrue(any(row.in_progress for row in capture.rows))
        entry = SimpleNamespace(capture=capture, snapshot=item.snapshot, source_status=SimpleNamespace(failed_at=None))
        owner = SimpleNamespace(catalog_observation=observe_catalog(source, include_archived_revisions=True),
            cards=SimpleNamespace(sessions={root.session_id: entry}), clock_ms=lambda: 6000,
            catalog_job=None, _closed=True)
        catalog = SessionCatalog(clock=lambda: self.clock)
        loads = source.load_count
        WebWatchCoordinator.tick_catalog(owner, catalog)
        cold = catalog.page()["view"]["session_usage"][0]
        self.assertTrue(cold["running"])
        self.assertFalse(cold["has_summary"])
        self.assertEqual(source.load_count, loads)
        entry.source_status.failed_at = 0
        WebWatchCoordinator.tick_catalog(owner, catalog)
        self.assertFalse(catalog.page()["view"]["session_usage"][0]["running"])
        entry.source_status.failed_at = None
        entry.capture = replace(capture, retained=True)
        WebWatchCoordinator.tick_catalog(owner, catalog)
        self.assertFalse(catalog.page()["view"]["session_usage"][0]["running"])

    def test_pending_model_requires_pre_request_execution_not_an_unknown_physical_model(self):
        root = self.catalog.roots["root-0000"]
        item = self.service._analyze(root, detail=True)
        prompt = replace(item.bundle.prompts[0], main_model_id="", in_progress=True)
        waiting = replace(item, bundle=replace(item.bundle, trace_entries=(), prompts=(prompt,)))
        row = self.service._session_rows((waiting,))[0]
        self.assertTrue(row.model_pending)
        self.assertEqual(row.prompt_count, 1)
        self.assertFalse(row.contributor_models_complete)
        selected = replace(prompt, main_model_id="source-selected-model")
        row = self.service._session_rows((replace(waiting, bundle=replace(waiting.bundle, prompts=(selected,))),))[0]
        self.assertEqual(row.model, "source-selected-model")
        self.assertFalse(row.model_pending)
        entry = replace(item.bundle.trace_entries[0], model=ModelRef("unknown", "N/A"))
        unknown = replace(item, bundle=replace(item.bundle, trace_entries=(entry,), prompts=(prompt,)))
        self.assertFalse(self.service._session_rows((unknown,))[0].model_pending)


if __name__ == "__main__":
    unittest.main()
