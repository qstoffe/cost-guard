"""Mode scopes, staged daily Watch accounting and deterministic acquisition counts."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from development.tests.fixtures.synthetic_month import SyntheticMonthSource, make_root_snapshot
from development.tests.fixtures.watch_runtime import make_service
from src.analysis import analyze_snapshot
from src.analysis.valuation import comparison_cost, unique_usage
from src.domain import ModelRef
from src.presentation import WatchRenderer
from src.reports import ReportRequest
from src.reports.models import ReportKind
from src.watch import WatchCoordinator

DAY = 1_790_467_200_000  # 2026-09-27 UTC
NOW = DAY + 12 * 3_600_000
MONTH = DAY - 20 * 86_400_000


def watch_for(directory, source, *, now=NOW, session_id=None, rows=12):
    config, selection, service, _ = make_service(directory, source, now_ms=now)
    service.account_providers = ()
    config.update(watchDashboardMaxRows=rows)
    watch = WatchCoordinator(selection=selection, report_service=service, config=config,
                             clock_ms=lambda: now, session_id=session_id, record_observations=False)
    return watch


def finish_history(watch):
    cycle = None
    while watch.today_ccost.history_pending:
        cycle = watch.enrich_once()
    return cycle.projection if cycle else watch.status_projection()


class WatchHistoryLoadingTests(unittest.TestCase):
    def test_thousands_of_old_roots_do_not_hydrate_for_daily_accounting_and_warm_start_reuses_analysis(self):
        source = SyntheticMonthSource(2000, 1, month_start_ms=MONTH)
        with tempfile.TemporaryDirectory() as directory:
            cold = watch_for(directory, source)
            self.addCleanup(cold.close)
            initial = cold.initialize(defer_history=True)
            self.assertEqual(20, source.load_count)
            self.assertTrue(initial.projection.today_pending)
            complete = finish_history(cold)
            self.assertEqual(0, cold.report_service.metrics.counts["history_candidate_roots"])
            self.assertFalse(complete.today_pending)
            self.assertEqual(0, complete.today_total.observed_requests)
            warm = watch_for(directory, source)
            self.addCleanup(warm.close)
            before = source.load_count
            warm.initialize(defer_history=True)
            finish_history(warm)
            self.assertEqual(2, source.load_count - before)
            before = source.load_count
            analyzed = warm.report_service.metrics.counts.get("analyzed_prompts", 0)
            for _ in range(3):
                self.assertEqual((), warm.poll_once().hydrated_roots)
            self.assertEqual(before, source.load_count)
            self.assertEqual(analyzed, warm.report_service.metrics.counts.get("analyzed_prompts", 0))

    def test_sparse_today_scope_has_exact_exhaustive_accounting_and_pending_initial_output(self):
        source = SyntheticMonthSource(300, 2, month_start_ms=MONTH, today_roots=3, children_per_root=1, now_ms=NOW)
        last = source.snapshots["root-0299"]
        source.snapshots["root-0299"] = replace(last, invocations=(
            replace(last.invocations[0], model=ModelRef("unknown", "unpriced")), *last.invocations[1:]))
        with tempfile.TemporaryDirectory() as directory:
            watch = watch_for(directory, source)
            self.addCleanup(watch.close)
            initial = watch.initialize(defer_history=True).projection
            self.assertTrue(initial.today_pending)
            output = io.StringIO()
            WatchRenderer(watch.config, stream=output, interactive=False).render(initial)
            self.assertIn("Total today: Pending", output.getvalue())
            result = finish_history(watch)
            service = watch.report_service
            traces = [entry for snapshot in source.snapshots.values()
                      for entry in analyze_snapshot(snapshot, estimator=service._load_catalog().estimate, now_ms=NOW).trace_entries]
            expected = comparison_cost((entry for entry in unique_usage(traces) if DAY <= entry.completed_at_ms <= NOW),
                                       service.token_reference_valuation())
            self.assertEqual(expected, result.today_total)
            self.assertFalse(result.today_total.complete)
            self.assertFalse(result.today_pending)
            self.assertEqual(3, service.metrics.counts["history_candidate_roots"])
            self.assertEqual(20, source.load_count, "accounting reuses required startup roots, never the other 280")

    def test_all_old_running_roots_survive_startup_and_row_caps(self):
        source = SyntheticMonthSource(50, 1, month_start_ms=MONTH, running_roots=4)
        with tempfile.TemporaryDirectory() as directory:
            watch = watch_for(directory, source, rows=1)
            self.addCleanup(watch.close)
            cycle = watch.initialize(defer_history=True)
            self.assertEqual(4, cycle.projection.active_count)
            self.assertTrue({"root-0000", "root-0001", "root-0002", "root-0003"}.issubset(cycle.hydrated_roots))
            before = source.load_count
            watch.poll_once()
            self.assertEqual(4, source.load_count - before, "unchanged live revisions do not gate authoritative running work")

    def test_child_today_activity_selects_an_old_root_and_archived_history_is_accounted(self):
        source = SyntheticMonthSource(40, 1, month_start_ms=MONTH)
        old = source.snapshots["root-0000"]
        child = make_root_snapshot(9999, 1, month_start_ms=NOW - 60_000 - 9999 * 60_000)
        source.snapshots["root-0000"] = replace(old,
            sessions=(old.root, replace(child.root, parent_session_id=old.root.session_id)),
            messages=(*old.messages, *child.messages), parts=(*old.parts, *child.parts),
            events=(*old.events, *child.events), invocations=(*old.invocations, *child.invocations))
        archived = make_root_snapshot(1, 1, month_start_ms=NOW - 180_000)
        archived = replace(archived, root=replace(archived.root, archived_at_ms=NOW))
        source.snapshots["root-0001"] = replace(archived, sessions=(archived.root,))
        with tempfile.TemporaryDirectory() as directory:
            watch = watch_for(directory, source)
            self.addCleanup(watch.close)
            initial = watch.initialize(defer_history=True)
            self.assertNotIn("root-0001", initial.hydrated_roots)
            result = finish_history(watch)
            self.assertEqual(2, result.today_total.observed_requests)
            self.assertEqual(2, watch.report_service.metrics.counts["history_candidate_roots"])
            self.assertLess(old.root.created_at_ms, DAY)

    def test_unrelated_old_revision_change_does_not_hydrate_dashboard_or_accounting(self):
        source = SyntheticMonthSource(40, 1, month_start_ms=MONTH)
        with tempfile.TemporaryDirectory() as directory:
            watch = watch_for(directory, source)
            self.addCleanup(watch.close)
            watch.initialize(defer_history=True)
            old = source.snapshots["root-0000"]
            source.snapshots["root-0000"] = replace(old, source_revision="historical-edit")
            before = source.load_count
            changed = watch.poll_once(force_resync=True)
            self.assertIn("root-0000", changed.changed_roots)
            self.assertNotIn("root-0000", changed.hydrated_roots)
            self.assertEqual(20, source.load_count - before, "resync rereads observed roots, not all history")

    def test_scoped_watch_hydrates_only_requested_tree_but_keeps_independent_today_metric(self):
        source = SyntheticMonthSource(40, 1, month_start_ms=MONTH, today_roots=2, now_ms=NOW)
        with tempfile.TemporaryDirectory() as directory:
            watch = watch_for(directory, source, session_id="root-0000")
            self.addCleanup(watch.close)
            initial = watch.initialize(defer_history=True)
            self.assertEqual(("root-0000",), initial.hydrated_roots)
            self.assertEqual(1, source.load_count)
            result = finish_history(watch)
            self.assertEqual(2, result.today_total.observed_requests)
            self.assertEqual(3, source.load_count)

    def test_restart_after_history_deletion_does_not_invent_persistent_usage(self):
        source = SyntheticMonthSource(1, 1, month_start_ms=MONTH, today_roots=1, now_ms=NOW)
        with tempfile.TemporaryDirectory() as directory:
            first = watch_for(directory, source)
            self.addCleanup(first.close)
            before = first.initialize().projection
            self.assertEqual(1, before.today_total.observed_requests)
            source.snapshots.clear()
            self.assertEqual(before.today_total, first.poll_once().projection.today_total)
            second = watch_for(directory, source)
            self.addCleanup(second.close)
            after = second.initialize().projection
            self.assertEqual(0, after.today_total.observed_requests)
            self.assertFalse(after.today_pending)

    def test_old_session_reactivates_after_watch_start_without_event_hints(self):
        source = SyntheticMonthSource(50, 1, month_start_ms=MONTH)
        with tempfile.TemporaryDirectory() as directory:
            watch = watch_for(directory, source, rows=1)
            self.addCleanup(watch.close)
            watch.initialize(defer_history=True)
            fresh = SyntheticMonthSource(1, 1, month_start_ms=NOW, running_roots=1).snapshots["root-0000"]
            source.snapshots["root-0000"] = replace(fresh, source_revision="new-activity")
            cycle = watch.poll_once(force_resync=True)
            self.assertIn("root-0000", cycle.hydrated_roots)
            self.assertEqual(1, cycle.projection.active_count)

    def test_account_publication_and_unchanged_history_reuse_daily_projection(self):
        source = SyntheticMonthSource(1, 1, month_start_ms=MONTH, today_roots=1, now_ms=NOW)
        with tempfile.TemporaryDirectory() as directory:
            watch = watch_for(directory, source)
            self.addCleanup(watch.close)
            expected = watch.initialize().projection.today_total
            with patch("src.reports.accounts.accounts_quota_projection_with_today_entries", side_effect=AssertionError("daily rebuild")):
                for _ in range(3):
                    self.assertEqual(expected, watch.status_projection().today_total)
                service = watch.report_service
                service.watch_history_batch(service.watch_history_candidates(source.list_sessions()))
                service.publish_watch_history()
                self.assertEqual(1, service.project_watch_accounts(())[0].comparison_today.observed_requests)

    def test_new_liveness_without_a_revision_change_and_cached_startup_both_hydrate_authoritatively(self):
        source = SyntheticMonthSource(40, 1, month_start_ms=MONTH)
        with tempfile.TemporaryDirectory() as directory:
            watch = watch_for(directory, source)
            self.addCleanup(watch.close)
            watch.initialize(defer_history=True)
            old = source.snapshots["root-0000"]
            root = replace(old.root, active=True)
            source.snapshots["root-0000"] = replace(old, root=root, sessions=(root,))
            changed = watch.poll_once()
            self.assertIn("root-0000", changed.hydrated_roots)
            self.assertEqual(1, changed.projection.active_count)
            source.snapshots["root-0000"] = old
            service = watch_for(directory, source).report_service
            service.build(ReportRequest(ReportKind.SESSION, session_id="root-0000"))
            source.snapshots["root-0000"] = replace(old, root=root, sessions=(root,))
            fresh = watch_for(directory, source)
            self.addCleanup(fresh.close)
            self.assertEqual(1, fresh.initialize(defer_history=True).projection.active_count)

    def test_scoped_today_authoritatively_refreshes_unrelated_live_roots_even_with_unchanged_revision(self):
        source = SyntheticMonthSource(2, 1, month_start_ms=MONTH, today_roots=1, now_ms=NOW)
        with tempfile.TemporaryDirectory() as directory:
            watch = watch_for(directory, source, session_id="root-0000")
            self.addCleanup(watch.close)
            before = watch.initialize().projection.today_total
            old = source.snapshots["root-0001"]
            root = replace(old.root, active=True)
            source.snapshots["root-0001"] = replace(old, root=root, sessions=(root,),
                invocations=tuple(replace(request, tokens=replace(request.tokens, input=1000)) for request in old.invocations))
            loads = source.load_count
            after = watch.poll_once().projection.today_total
            self.assertGreater(after.known_ccost, before.known_ccost)
            self.assertEqual(1, source.load_count - loads, "independent Today only rehydrates the unrelated live root")

    def test_slow_history_plan_makes_progress_across_active_polls_and_prunes_deleted_candidates(self):
        source = SyntheticMonthSource(30, 1, month_start_ms=MONTH, today_roots=25, running_roots=4, now_ms=NOW)
        with tempfile.TemporaryDirectory() as directory:
            watch = watch_for(directory, source)
            self.addCleanup(watch.close)
            clock = [NOW]
            watch.clock_ms = lambda: clock[0]
            watch.initialize(defer_history=True)
            steps = 0
            while watch.today_ccost.history_pending and steps < 12:
                watch.enrich_once()
                steps += 1
                if watch.today_ccost.history_pending:
                    if steps == 1:
                        del source.snapshots["root-0029"]
                    clock[0] += 6000
                    watch.poll_once()
            self.assertFalse(watch.today_ccost.history_pending, "active refreshes must not starve enrichment")
            self.assertLessEqual(steps, 8)
            self.assertEqual(25, watch.status_projection().today_total.observed_requests,
                             "the deleted root was observed at startup and remains retained")

    def test_running_session_crosses_midnight_and_pending_plan_publishes_new_local_day_only(self):
        source = SyntheticMonthSource(1, 1, month_start_ms=DAY - 1000, running_roots=1)
        with tempfile.TemporaryDirectory() as directory:
            watch = watch_for(directory, source, now=DAY - 500)
            self.addCleanup(watch.close)
            clock = [DAY - 500]
            watch.clock_ms = lambda: clock[0]
            watch.initialize(defer_history=True)
            snapshot = source.snapshots["root-0000"]
            root = replace(snapshot.root, updated_at_ms=DAY + 900, active=False)
            source.snapshots["root-0000"] = replace(snapshot, root=root, sessions=(root,),
                messages=tuple(replace(message, completed_at_ms=DAY + 700, finish_reason="stop")
                               if message.role.value == "assistant" else message for message in snapshot.messages),
                invocations=tuple(replace(request, completed_at_ms=DAY + 700, finish_reason="stop") for request in snapshot.invocations))
            clock[0] = DAY + 1000
            watch.poll_once(force_resync=True)
            result = finish_history(watch)
            self.assertFalse(result.today_pending)
            self.assertEqual(1, result.today_total.observed_requests)
            self.assertEqual({"2026-09-27"}, set(result.today_total.by_day_utc))

    def test_staged_acquisition_uses_stockholm_midnight_on_both_dst_transition_days(self):
        for date, start in (("2026-03-29T12:00:00", "2026-03-28T23:00:00"),
                            ("2026-10-25T12:00:00", "2026-10-24T22:00:00")):
            now = int(datetime.fromisoformat(date).replace(tzinfo=timezone.utc).timestamp() * 1000)
            midnight = int(datetime.fromisoformat(start).replace(tzinfo=timezone.utc).timestamp() * 1000)
            source = SyntheticMonthSource(2, 1, month_start_ms=midnight - 60_000)
            # Root 0 finishes before midnight; root 1 starts exactly at it.
            with self.subTest(date=date), tempfile.TemporaryDirectory() as directory:
                config, selection, service, _ = make_service(directory, source, now_ms=now)
                config["timezone"] = "Europe/Stockholm"
                service.account_providers = ()
                watch = WatchCoordinator(selection=selection, report_service=service, config=config,
                                         clock_ms=lambda: now, record_observations=False)
                self.addCleanup(watch.close)
                watch.initialize(defer_history=True)
                result = finish_history(watch)
                self.assertEqual(1, result.today_total.observed_requests)
                self.assertEqual(1, service.metrics.counts["history_candidate_roots"])


class ReportHistoryLoadingTests(unittest.TestCase):
    def test_detail_snapshot_revision_cannot_mix_with_an_older_cached_bundle(self):
        source = SyntheticMonthSource(1, 1, month_start_ms=MONTH)
        with tempfile.TemporaryDirectory() as directory:
            first = watch_for(directory, source).report_service
            first.build(ReportRequest(ReportKind.SESSIONS, session_limit=1))
            fresh = watch_for(directory, source).report_service
            original = source.load_session_snapshot
            def changed_on_hydration(root_id):
                old = source.snapshots[root_id]
                source.snapshots[root_id] = replace(old, source_revision="changed-during-detail")
                return original(root_id)
            with patch.object(source, "load_session_snapshot", side_effect=changed_on_hydration):
                fresh.build(ReportRequest(ReportKind.SESSION, session_id="root-0000"))
            self.assertEqual("changed-during-detail", fresh._analyzed["root-0000"].bundle.source_revision)
            self.assertEqual(2, source.load_count)

    def test_retrieval_metadata_does_not_invalidate_analysis_but_semantic_rates_do(self):
        source = SyntheticMonthSource(6, 20, month_start_ms=MONTH)
        with tempfile.TemporaryDirectory() as directory:
            first = watch_for(directory, source).report_service
            expected = first.build(ReportRequest())
            before = source.load_count
            warm = watch_for(directory, source).report_service
            warm.pricing_provider.catalog = replace(first.pricing_provider.catalog, retrieved_at_ms=999, source_revision="refetched")
            actual = warm.build(ReportRequest())
            self.assertEqual(before, source.load_count)
            self.assertEqual(expected.token_mix, actual.token_mix)
            changed = watch_for(directory, source).report_service
            catalog = changed.pricing_provider.catalog
            model = catalog.models[0]
            changed.pricing_provider.catalog = replace(catalog, models=(replace(model,
                tiers=(replace(model.tiers[0], per_million_input=Decimal("100")), *model.tiers[1:])), *catalog.models[1:]))
            changed.build(ReportRequest())
            self.assertGreater(source.load_count, before)

    def test_unpriceable_prompts_do_not_fill_either_hundred_prompt_sample(self):
        source = SyntheticMonthSource(180, 1, month_start_ms=MONTH)
        for index in range(110, 180):
            key = f"root-{index:04d}"
            snapshot = source.snapshots[key]
            source.snapshots[key] = replace(snapshot, invocations=tuple(
                replace(item, model=ModelRef("unknown", "unpriced")) for item in snapshot.invocations))
        with tempfile.TemporaryDirectory() as directory:
            service = watch_for(directory, source).report_service
            result = service.build(ReportRequest())
            self.assertEqual(100, result.model_comparison_sample_size)
            self.assertEqual(100, result.token_mix.sample_size)
            self.assertEqual(170, source.load_count, "Skip 70 unpriceable roots, then acquire 100 eligible prompts")

    def test_session_list_detail_date_and_deep_history_have_distinct_scopes(self):
        for request, expected in ((ReportRequest(ReportKind.SESSIONS, session_limit=3), 3),
                                  (ReportRequest(ReportKind.SESSION, session_id="root-0000"), 1),
                                  (ReportRequest(ReportKind.DATE, date_text="2026-09-27"), 2), (None, 25)):
            with self.subTest(request=request), tempfile.TemporaryDirectory() as directory:
                source = SyntheticMonthSource(25, 1, month_start_ms=MONTH, today_roots=2, now_ms=NOW)
                service = watch_for(directory, source).report_service
                service.build(request) if request is not None else service.build_token_mix_history()
                self.assertEqual(expected, source.load_count)


if __name__ == "__main__":
    unittest.main()
