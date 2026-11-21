"""Finite historical observations under synthetic live churn, never private sessions."""
from dataclasses import replace
import sqlite3
import time
import unittest
from unittest.mock import patch

from development.tests.fixtures.compact_reports import report_service, NOW
from development.tests.fixtures.synthetic_month import SyntheticMonthSource, make_root_snapshot
from src.reports import ReportKind, ReportRequest, ReportService
from src.reports.history_cohort import HistoryCohort, NAMESPACE, TRANSIENT
from src.reports.history_work import HistoryCheckpointError, HistoryContinuation

DAY = 86_400_000


class HistoryCohortTests(unittest.TestCase):
    def service(self, original, *, scan='test-scan'):
        service = ReportService(selection=original.selection, pricing_provider=original.pricing_provider,
            account_provider=None, cache_repository=original.cache_repository, config=original.config, now_ms=NOW,
            cache_token_mix_history=True)
        service.shared_web_evidence = service.allow_partial_history = True
        service.history_scan = service.stats_scan = scan
        service.history_slice_roots = service.history_batch_size = service.stats_slice_roots = 4
        service.history_checkpoint = lambda _proof: None
        return service

    def build(self, service, kind, scope='all'):
        return (service.build_token_mix_history(scope=scope) if kind == 'token-mix' else
                service.build(ReportRequest(ReportKind.AI_STATS, stats_scope=scope)))

    def cohort(self, service, scan='test'):
        sessions = service.source.list_sessions()
        roots = [s for s in sessions if s.parent_session_id is None]
        versions = service.source.get_session_tree_revisions([r.session_id for r in roots])
        return HistoryCohort(service, scan, sessions, roots, versions, service._load_comparison_catalog())

    def test_reparenting_invalidates_both_initial_trees_and_omission_is_durable(self):
        source = SyntheticMonthSource(3, 2, month_start_ms=NOW - DAY, children_per_root=1)
        original = report_service(self, source)
        first = self.cohort(original)
        left, right = source.snapshots['root-0000'], source.snapshots['root-0001']
        child = left.sessions[1]
        source.snapshots['root-0000'] = replace(left, sessions=(left.root,))
        source.snapshots['root-0001'] = replace(right,
            sessions=(*right.sessions, replace(child, parent_session_id=right.root.session_id)))

        changed = self.cohort(original)
        source.snapshots['root-0000'], source.snapshots['root-0001'] = left, right
        restored = self.cohort(original)

        self.assertEqual(first.signature, changed.signature)
        self.assertEqual({'root-0000', 'root-0001'}, changed.omitted)
        self.assertEqual(changed.omitted, restored.omitted, 'a scan never reopens resolved omissions')
        self.assertEqual(3, restored.total)

    def test_deleted_archived_and_new_descendant_roots_are_omitted_not_new_cohorts(self):
        for mutation in ('delete', 'archive', 'child'):
            with self.subTest(mutation=mutation):
                source = SyntheticMonthSource(2, 2, month_start_ms=NOW - DAY)
                original = report_service(self, source)
                initial = self.cohort(original)
                before = source.snapshots['root-0000']
                if mutation == 'delete':
                    del source.snapshots['root-0000']
                elif mutation == 'archive':
                    root = replace(before.root, archived_at_ms=NOW)
                    source.snapshots[root.session_id] = replace(before, root=root, sessions=(root,))
                else:
                    child = replace(make_root_snapshot(10, 1, month_start_ms=NOW - DAY).root,
                        parent_session_id=before.root.session_id)
                    source.snapshots[before.root.session_id] = replace(before, sessions=(*before.sessions, child))

                current = self.cohort(original)

                self.assertEqual({'root-0000'}, current.omitted)
                self.assertEqual(initial.signature, current.signature)

    def test_missing_corrupt_or_dependency_incompatible_resume_never_restarts_silently(self):
        source = SyntheticMonthSource(2, 1, month_start_ms=NOW - DAY)
        original = report_service(self, source)
        original.history_resuming = True
        with self.assertRaisesRegex(HistoryCheckpointError, 'history_checkpoint_unavailable'):
            self.cohort(original)
        original.history_resuming = False
        initial = self.cohort(original)
        for value in ({}, {**initial.value, 'omitted': [{}]}, {**initial.value, 'binding': 'old'}):
            original.cache_repository.put(NAMESPACE, initial.key, value, algorithm_version=NAMESPACE)
            with self.assertRaisesRegex(HistoryCheckpointError, 'history_checkpoint_unavailable'):
                self.cohort(original)

    def test_identity_rotation_is_not_downgraded_to_partial_coverage(self):
        source = SyntheticMonthSource(2, 1, month_start_ms=NOW - DAY)
        original = report_service(self, source)
        self.cohort(original)
        before = source.snapshots['root-0000']
        root = replace(before.root, provenance=replace(before.root.provenance, source_instance='rotated-source'))
        source.snapshots[root.session_id] = replace(before, root=root, sessions=(root,))

        with self.assertRaisesRegex(HistoryCheckpointError, 'source_identity_changed'):
            self.cohort(original)

    def test_ancient_verified_roots_cannot_fabricate_today_zero_when_recent_root_is_omitted(self):
        from src.reports.ai_stats import StatsCheckpointError
        for kind in ('token-mix', 'ai-stats'):
            with self.subTest(kind=kind):
                source = SyntheticMonthSource(1, 2, month_start_ms=NOW - 60 * DAY)
                recent = replace(make_root_snapshot(1, 2, month_start_ms=NOW - 3_600_000), complete=True)
                source.snapshots[recent.root.session_id] = recent
                original = report_service(self, source)
                first = self.service(original)
                first.history_slice_roots = first.history_batch_size = first.stats_slice_roots = 1
                try:
                    self.build(first, kind, 'today')
                except HistoryContinuation:
                    pass
                source.snapshots[recent.root.session_id] = replace(recent, source_revision='recent-changed')
                resumed = self.service(original)
                resumed.history_slice_roots = resumed.stats_slice_roots = 100

                if kind == 'token-mix':
                    report = resumed.build_token_mix_history(scope='today')
                    self.assertEqual('unknown', report.token_mix_period['coverage'])
                    self.assertEqual(1, report.history_omitted_roots)
                else:
                    with self.assertRaisesRegex(StatsCheckpointError, 'revision_churn'):
                        resumed.build(ReportRequest(ReportKind.AI_STATS, stats_scope='today'))

    def test_all_time_succeeds_but_seven_days_has_no_verified_usage_after_a_root_changes(self):
        from src.application.projection import project
        source = SyntheticMonthSource(3, 2, month_start_ms=NOW - 60 * DAY)
        recent = replace(make_root_snapshot(3, 2, month_start_ms=NOW - DAY), complete=True)
        source.snapshots[recent.root.session_id] = recent
        original = report_service(self, source)
        all_time = self.service(original, scan='all').build_token_mix_history(scope='all')
        for sid in ('root-0000', 'root-0001'):
            source.snapshots[sid] = replace(source.snapshots[sid], source_revision='changed-before-selection')
        first = self.service(original, scan='week')
        first.history_slice_roots = first.history_batch_size = 1
        proofs = []
        first.history_checkpoint = proofs.append
        with self.assertRaises(HistoryContinuation):
            first.build_token_mix_history(scope='7-days')
        source.snapshots[recent.root.session_id] = replace(recent, source_revision='changed-after-checkpoint')
        resumed = self.service(original, scan='week')
        resumed.history_resuming = True

        selected = resumed.build_token_mix_history(scope='7-days')

        self.assertGreater(all_time.token_mix.request_count, 0)
        self.assertEqual(4, proofs[-1]['total'])
        self.assertEqual(1, selected.history_omitted_roots)
        self.assertEqual('7-days', selected.token_mix_period['period'])
        self.assertEqual(NOW, selected.token_mix_period['end_ms'])
        self.assertEqual('unknown', selected.token_mix_period['coverage'])
        self.assertIsNone(project(selected).to_json()['token_mix'])

    def test_failed_omission_write_is_not_continuation_proof_and_expired_state_is_pruned(self):
        source = SyntheticMonthSource(2, 1, month_start_ms=NOW - DAY)
        original = report_service(self, source)
        initial = self.cohort(original)
        with patch.object(original.cache_repository, 'put', side_effect=sqlite3.OperationalError('readonly')):
            with self.assertRaisesRegex(HistoryCheckpointError, 'history_checkpoint_unavailable'):
                initial.omit(('root-0000',))
        self.assertEqual(set(), self.cohort(original).omitted)
        original.cache_repository.put(TRANSIENT, 'old', [])
        with original.cache_repository.database.connect(operation='write') as connection:
            connection.execute("UPDATE cache_entries SET updated_at_utc=datetime('now','-2 days') WHERE namespace IN (?,?)",
                (NAMESPACE, TRANSIENT))

        self.cohort(original, 'new-observation')

        self.assertIsNone(original.cache_repository.get(NAMESPACE, initial.key))
        self.assertIsNone(original.cache_repository.get(TRANSIENT, 'old'))

    def test_seven_day_cohort_reuses_verified_children_and_converges_after_arrivals(self):
        for changes in (0, 1, 12):
            with self.subTest(changes=changes):
                source = SyntheticMonthSource(24, 2, month_start_ms=NOW - DAY, children_per_root=1)
                source.snapshots = {sid: replace(tree, complete=True) for sid, tree in source.snapshots.items()}
                sid = 'root-0023'
                tree = source.snapshots[sid]
                child = replace(tree.sessions[1], active=True)
                source.snapshots[sid] = replace(tree, sessions=(tree.root, child))
                future_root = make_root_snapshot(50, 2, month_start_ms=NOW)
                source.snapshots[future_root.root.session_id] = future_root
                original = report_service(self, source)
                proofs = []
                for slice_index in range(8):
                    service = self.service(original)
                    service.history_resuming = slice_index > 0
                    service.history_checkpoint = proofs.append
                    try:
                        first = self.build(service, 'token-mix', '7-days')
                        break
                    except HistoryContinuation:
                        if slice_index == 0:
                            for index in range(changes):
                                root_id = f'root-{index:04d}'
                                source.snapshots[root_id] = replace(source.snapshots[root_id], source_revision='changed')
                                arrival = make_root_snapshot(100 + index, 2, month_start_ms=NOW)
                                source.snapshots[arrival.root.session_id] = replace(arrival, complete=True)
                else:
                    self.fail('initial 24-root cohort never completed')

                self.assertEqual({24}, {proof['total'] for proof in proofs})
                self.assertEqual(1, len({proof['signature'] for proof in proofs}))
                self.assertEqual(changes, first.history_omitted_roots)
                self.assertEqual(NOW, first.token_mix_period['end_ms'])
                self.assertEqual(4 * (24 - changes), first.token_mix.request_count)
                self.assertEqual(522 * (24 - changes), first.token_mix.total_tokens)
                self.assertEqual(4 * (24 - changes), first.token_mix.sample_size)

                refreshed = self.service(original, scan='catch-up')
                refreshed.now_ms += DAY
                refreshed.history_slice_roots = 100
                settled = self.build(refreshed, 'token-mix', '7-days')
                reference = report_service(self, source, now_ms=NOW + DAY)
                expected = self.build(reference, 'token-mix', '7-days')

                self.assertEqual(0, settled.history_omitted_roots)
                self.assertEqual(4 * 24 + 2 * (1 + changes), settled.token_mix.request_count)
                self.assertEqual(expected.token_mix, settled.token_mix)
                self.assertEqual(expected.token_mix_observed_totals, settled.token_mix_observed_totals)

    def test_zero_one_and_ten_changing_roots_finish_and_next_observation_converges(self):
        self.measurements = []
        for kind in ('token-mix', 'ai-stats'):
            for changing in (0, 1, 10):
                with self.subTest(kind=kind, changing=changing):
                    source = SyntheticMonthSource(24, 3, month_start_ms=NOW - DAY, running_roots=changing)
                    source.snapshots = {sid: replace(s, complete=True) for sid, s in source.snapshots.items()}
                    original = report_service(self, source)
                    proofs, slices, started = [], 0, time.perf_counter()
                    while slices < 10:
                        service = self.service(original)
                        service.history_checkpoint = proofs.append
                        slices += 1
                        try:
                            result = self.build(service, kind)
                            if kind == 'token-mix' or result.ai_stats_work['scopes']['all']['ready']:
                                break
                        except HistoryContinuation:
                            pass
                        for index in range(changing):
                            sid = f'root-{index:04d}'
                            source.snapshots[sid] = replace(source.snapshots[sid], source_revision=f'churn-{slices}')
                        added = replace(make_root_snapshot(100 + slices, 3, month_start_ms=NOW - DAY), complete=True)
                        source.snapshots[added.root.session_id] = added
                    cold_ms, cold_reads = (time.perf_counter() - started) * 1000, source.load_count
                    self.assertLessEqual(slices, 6)
                    self.assertEqual(changing, result.history_omitted_roots)
                    if kind == 'token-mix':
                        self.assertEqual(1, len({p['signature'] for p in proofs}))
                        self.assertEqual({24}, {p['total'] for p in proofs})
                    else:
                        self.assertEqual(24, result.ai_stats_work['total'])
                        self.assertEqual(changing, result.ai_stats_work['omitted'])
                    # A settled next scan includes arrivals and old-root updates.
                    refreshed = self.service(original, scan='settled')
                    refreshed.history_slice_roots = refreshed.stats_slice_roots = 100
                    next_result = self.build(refreshed, kind)
                    independent = self.build(report_service(self, source), kind)
                    self.assertEqual(independent.ai_stats if kind == 'ai-stats' else independent.token_mix,
                        next_result.ai_stats if kind == 'ai-stats' else next_result.token_mix)
                    before = source.load_count
                    warm = self.service(original, scan='warm')
                    warm.history_slice_roots = warm.stats_slice_roots = 100
                    self.build(warm, kind)
                    self.measurements.append(dict(kind=kind, changing=changing, slices=slices, restarts=0,
                        cold_root_reads=cold_reads, warm_root_reads=source.load_count - before, first_useful_ms=round(cold_ms, 2)))


if __name__ == '__main__':
    unittest.main()
