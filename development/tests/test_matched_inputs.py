"""Exact first-input identities, canonical per-run boundaries and compact indexing."""
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from development.tests.fixtures.compact_reports import report_service
from development.tests.fixtures.matched_inputs import source, finite_comparisons
from development.tests.fixtures.session_snapshots import make_snapshot
from development.tests.fixtures.opencode_v1_database import create_v1_database
from src.analysis import analyze_snapshot
from src.analysis.input_identity import first_input, fingerprint, preview
from src.analysis.matched_runs import facts, grouped, period_fact
from src.application import ReportApplication
from src.domain import EventKind, MessageRole, ModelRef
from src.sources.opencode_v1 import OpenCodeV1Source
from src.sources.opencode_v2_normalization import normalize_message_bundle
from src.reports import ReportKind, ReportRequest, ReportService
from src.reports.matched_runs import project_run
from src.reports.service import SessionCatalogChangedError
from src.web.jobs import ReportJobs, parse_report


class MatchedInputsTests(unittest.TestCase):
    def service(self, history):
        service = report_service(self, history, now_ms=1_790_086_400_000)
        service.selection = replace(service.selection, warnings=())
        return service

    def fresh(self, service):
        return ReportService(selection=service.selection, pricing_provider=service.pricing_provider,
            account_provider=None, cache_repository=service.cache_repository, config=service.config, now_ms=service.now_ms)

    def test_full_text_whitespace_order_and_verified_inline_attachment_identity(self):
        message = first_input(next(iter(source(1).snapshots.values())))
        original = fingerprint(message)
        part = message.parts[0]
        for text in [part.data['text'] + ' ', part.data['text'].upper(), part.data['text'].replace('\n', ' ')]:
            self.assertNotEqual(original, fingerprint(replace(message, parts=(replace(part, data={'text': text}),))))
        extra = replace(part, data={'text': 'second'})
        self.assertNotEqual(fingerprint(replace(message, parts=(part, extra))), fingerprint(replace(message, parts=(extra, part))))
        file = replace(part, kind='file', data={'url': 'data:text/plain;base64,YQ==', 'filename': 'x', 'mime': 'text/plain'})
        a = fingerprint(replace(message, parts=(part, file)))
        same = replace(file, data={**file.data, 'url': 'data:text/plain,a'})
        different = replace(file, data={**file.data, 'url': 'data:text/plain;base64,Yg=='})
        self.assertEqual(a, fingerprint(replace(message, parts=(part, same))))
        self.assertNotEqual(a, fingerprint(replace(message, parts=(part, different))))
        for url in ['file:///private.txt', 'https://example.test/x', 'data:broken']:
            self.assertIsNone(fingerprint(replace(message, parts=(part, replace(file, data={**file.data, 'url': url})))))
        self.assertIsNone(fingerprint(replace(message, parts=(replace(part, data={'text': '  '}),))))
        self.assertIsNone(fingerprint(replace(message, parts=(replace(part, kind='unknown'),))))
        self.assertIn('withheld', preview(replace(message, parts=(replace(part, data={'text': 'password=secret'}),))))
        a = replace(message, parts=(replace(part, data={'text': 'x' * 1000 + 'a'}),))
        b = replace(message, parts=(replace(part, data={'text': 'x' * 1000 + 'b'}),))
        self.assertNotEqual(fingerprint(a), fingerprint(b), 'display preview truncation never controls identity')

    def test_safe_preview_preserves_short_truncated_markup_and_placeholder_meanings(self):
        message = first_input(next(iter(source(1).snapshots.values())))
        part = message.parts[0]
        for text, expected in [('Short input', 'Short input'), ('x' * 121, 'x' * 120 + '…'),
                               ('  Explain\n <b>this</b>  ', 'Explain <b>this</b>'),
                               ('password=synthetic', 'Input preview withheld (potentially private)')]:
            with self.subTest(text=text):
                changed = replace(message, parts=(replace(part, data={'text': text}),))

                self.assertEqual(expected, preview(changed))
        attachment = replace(part, kind='file', data={'url': 'data:text/plain,a'})
        self.assertEqual('Attachment input', preview(replace(message, parts=(attachment,))))
        self.assertEqual('Input preview unavailable', preview(None))

    def test_equal_later_input_in_a_different_root_never_joins_the_first_input_pair(self):
        history = source(2, repeats=2)
        matched = first_input(history.snapshots['root-0000']).parts[0].data['text']
        snapshot = history.snapshots['root-0003']
        first, response, later, final = snapshot.messages
        messages = (replace(first, parts=(replace(first.parts[0], data={'text': 'Different first input'}),)),
                    response, replace(later, parts=(replace(later.parts[0], data={'text': matched}),)), final)
        history.snapshots['root-0003'] = replace(snapshot, messages=messages,
            parts=tuple(part for message in messages for part in message.parts))

        result = self.service(history).build(ReportRequest(ReportKind.COMPARISONS)).comparisons

        self.assertEqual(1, result.total)
        self.assertEqual(['root-0001', 'root-0000'], [run.session_id for run in result.groups[0].runs])

    def test_synthetic_child_subtask_and_partial_history_never_promote_a_later_prompt(self):
        snapshot = next(iter(source(1).snapshots.values()))
        self.assertIsNone(first_input(replace(snapshot, complete=False)))
        self.assertIsNone(first_input(replace(snapshot, root=replace(snapshot.root, parent_session_id='parent'))))
        events = (replace(snapshot.events[0], kind=EventKind.SUBTASK), *snapshot.events[1:])
        self.assertIsNone(first_input(replace(snapshot, events=events)))
        events = (replace(snapshot.events[0], kind=EventKind.SYNTHETIC_CONTINUATION), *snapshot.events[1:])
        selected = first_input(replace(snapshot, events=events))
        self.assertEqual(snapshot.messages[2].message_id, selected.message_id)
        synthetic = replace(snapshot.messages[0].parts[0], data={'synthetic': True, 'text': 'notification'})
        self.assertIsNone(fingerprint(replace(snapshot.messages[0], parts=(synthetic,))))

    def test_normalized_v1_v2_identity_preserves_full_original_semantic_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / 'history.sqlite'
            create_v1_database(database)
            snapshot = OpenCodeV1Source(database).load_session_snapshot('ses_root')
        original = first_input(snapshot)
        self.assertIsNotNone(original)
        wire = {'info': {'id': 'different-id', 'sessionID': 'different-root', 'role': 'user'},
                'parts': [dict(part.data, id=f'wire-{index}', type=part.kind) for index, part in enumerate(original.parts)]}
        normalized, _parts = normalize_message_bundle(wire, lambda sid, eid=None: original.provenance)
        self.assertEqual(fingerprint(original), fingerprint(normalized))

    def test_child_models_physical_requests_and_historical_context_use_the_first_causal_run(self):
        snapshot = make_snapshot()
        first = replace(snapshot.messages[0], parts=(replace(snapshot.messages[0].parts[0],
            kind='text', data={'text': 'exact first user input'}),))
        messages = (first, replace(snapshot.messages[1], finish_reason='stop'), *snapshot.messages[2:])
        # The synthetic continuation is deliberately not a new match candidate.
        snapshot = replace(snapshot, complete=True, messages=messages,
            events=(replace(snapshot.events[0], kind=EventKind.USER_PROMPT, text='exact first user input'), *snapshot.events[1:]))
        service = self.service(source(1))
        catalog = service._load_comparison_catalog()
        bundle = analyze_snapshot(snapshot, tracked_provider=None, estimator=catalog.estimate, now_ms=9000)
        run = project_run(snapshot, bundle, catalog, service.config)
        record = bundle.prompts[0]
        self.assertEqual(record.model_calls, run.calls)
        self.assertEqual(1, run.linked_agents)
        self.assertEqual(500, run.duration_ms)
        self.assertEqual(sum(catalog.reference_valuation(entry.model, entry.tokens) or Decimal(0) for entry in record.entries), run.ccost)
        # Later requests carry other usage/context but cannot replace this historical anchor.
        self.assertNotEqual(bundle.prompts[-1].input_context_tokens, run.next_context_tokens)
        child = replace(record.entries[-1], model=ModelRef('other-provider', 'other-model'), variant='high')
        changed = replace(bundle, prompts=(replace(record, entries=(*record.entries[:-1], child)), *bundle.prompts[1:]))
        mixed = project_run(snapshot, changed, catalog, service.config)
        self.assertTrue(mixed.mixed)
        self.assertFalse(mixed.cost_complete)
        self.assertTrue(any(group[0] == 'other-provider' for group in mixed.contributors))
        later = replace(snapshot, invocations=tuple(replace(item, tokens=replace(item.tokens, input=999999))
            if item.initiating_event_id == 'u_next' else item for item in snapshot.invocations))
        changed_bundle = analyze_snapshot(later, tracked_provider=None, estimator=catalog.estimate, now_ms=9000)
        self.assertEqual(run, project_run(later, changed_bundle, catalog, service.config))

    def test_three_repeats_first_prompt_only_metrics_and_no_private_index_payload(self):
        history = source(1)
        service = self.service(history)
        result = service.build(ReportRequest(ReportKind.COMPARISONS)).comparisons
        self.assertTrue(result.complete)
        self.assertEqual(1, result.total)
        runs = result.groups[0].runs
        self.assertEqual(['root-0002', 'root-0001', 'root-0000'], [run.session_id for run in runs])
        self.assertEqual([300, 200, 100], [run.duration_ms for run in runs])
        self.assertEqual([1, 1, 1], [run.calls for run in runs])
        self.assertEqual(1, len({run.ccost for run in runs}))
        self.assertTrue(all(run.cost_complete and run.status == 'complete' for run in runs))
        self.assertEqual(3, len(result.groups[0].facts))
        self.assertEqual(Decimal(3), result.groups[0].facts[0].ratio)
        with service.cache_repository.database.connect() as connection:
            keys = [row[0] for row in connection.execute("SELECT cache_key FROM cache_entries WHERE namespace='matched-first-runs'")]
        entries = service.cache_repository.get_many('matched-first-runs', keys)
        payload = json.dumps([entry.payload for entry in entries.values()])
        self.assertNotIn('Exact first input', payload)
        self.assertNotIn('Quest', payload)
        self.assertNotIn('999999', payload)
        with service.cache_repository.database.connect() as connection:
            namespaces = {row[0] for row in connection.execute('SELECT DISTINCT namespace FROM cache_entries')}
        self.assertEqual({'matched-first-runs'}, namespaces, 'matching must not create raw-prompt derived cache payloads')

    def test_ten_group_pages_cache_reuse_recency_changes_and_removed_roots(self):
        history = source()
        service = self.service(history)
        first = service.build(ReportRequest(ReportKind.COMPARISONS)).comparisons
        loads = history.load_count
        self.assertEqual(11, first.total)
        self.assertEqual(10, len(first.groups))
        warm = self.fresh(service).build(ReportRequest(ReportKind.COMPARISONS)).comparisons
        self.assertEqual(first, warm)
        self.assertEqual(loads + 10, history.load_count, 'warm work hydrates ten previews, not 33 archived roots')
        second_request = ReportRequest(ReportKind.COMPARISONS, comparison_offset=10, comparison_revision=first.revision)
        second = self.fresh(service).build(second_request).comparisons
        self.assertEqual(1, len(second.groups))
        snapshot = history.snapshots['root-0000']
        root = replace(snapshot.root, updated_at_ms=service.now_ms)
        history.snapshots[root.session_id] = replace(snapshot, root=root, sessions=(root,), source_revision='late-activity')
        with self.assertRaises(SessionCatalogChangedError):
            self.fresh(service).build(second_request)
        refreshed = self.fresh(service).build(ReportRequest(ReportKind.COMPARISONS)).comparisons
        self.assertEqual('root-0000', refreshed.groups[0].runs[0].session_id)
        del history.snapshots['root-0000']
        del history.snapshots['root-0001']
        self.assertEqual(10, self.fresh(service).build(ReportRequest(ReportKind.COMPARISONS)).comparisons.total)

    def test_unavailable_cache_and_partial_source_never_become_false_empty(self):
        history = source(1)
        service = self.service(history)
        with patch.object(service.cache_repository, 'get_many', side_effect=OSError()), \
                patch.object(service.cache_repository, 'put_many', side_effect=OSError()):
            self.assertEqual(1, service.build(ReportRequest(ReportKind.COMPARISONS)).comparisons.total)
        service.selection = replace(service.selection, warnings=('partial source',))
        self.assertFalse(self.fresh(service).build(ReportRequest(ReportKind.COMPARISONS)).comparisons.complete)

    def test_321_groups_warm_pinned_pages_previews_and_changed_revision_trace(self):
        history = source(321)
        service = self.service(history)
        service.shared_web_evidence = True
        first = service.build(ReportRequest(ReportKind.COMPARISONS)).comparisons
        self.assertEqual(321, first.total)
        seen = [tuple(run.session_id for run in group.runs) for group in first.groups]
        for offset in (10, 0, 170, 320):
            with self.subTest(offset=offset):
                fresh = self.fresh(service)
                fresh.shared_web_evidence = True
                progress = []
                fresh.progress = progress.append
                before = history.load_count
                page = fresh.build(ReportRequest(ReportKind.COMPARISONS,
                    comparison_offset=offset, comparison_revision=first.revision)).comparisons
                self.assertEqual((offset, 321, first.revision), (page.offset, page.total, page.revision))
                self.assertEqual(1 if offset == 320 else 10, len(page.groups))
                self.assertEqual(len(page.groups), history.load_count - before, 'only displayed previews hydrate on warm pages')
                if offset == 0:
                    self.assertEqual(seen, [tuple(run.session_id for run in group.runs) for group in page.groups])
                previews = [p for p in progress if getattr(p, 'stage', None) == 'comparison-previews']
                self.assertEqual(list(range(len(page.groups) + 1)), [p.completed for p in previews])
                self.assertTrue(all(p.total == len(page.groups) for p in previews))
        changed = history.snapshots['root-0000']
        history.snapshots['root-0000'] = replace(changed, source_revision='synthetic-revision-change')
        result = ReportApplication(lambda now, progress: self.fresh(service)).execute(
            ReportRequest(ReportKind.COMPARISONS, comparison_offset=10, comparison_revision=first.revision)).to_json()
        self.assertEqual({'code': 'session_catalog_changed', 'retryable': False}, result['error'])

    def test_corrupt_compact_cache_is_rebuilt_without_losing_the_group(self):
        service = self.service(source(1))
        request = ReportRequest(ReportKind.COMPARISONS)
        original = service.build(request).comparisons
        repository = service.cache_repository
        with repository.database.connect() as connection:
            key = connection.execute("SELECT cache_key FROM cache_entries WHERE namespace='matched-first-runs' LIMIT 1").fetchone()[0]
        entry = repository.get('matched-first-runs', key)
        for changed in [{'contributors': [[]]}, {'ccost': 'NaN'}, {'token_totals': [1]},
                        {'session_id': 'incorrect-root'}]:
            with self.subTest(changed=changed):
                repository.put(entry.namespace, key, {**entry.payload, **changed},
                    source_revision=entry.source_revision, algorithm_version=entry.algorithm_version)
                fresh = self.fresh(service)
                previous_misses = fresh.metrics.counts['comparison_cache_misses']
                self.assertEqual(original, fresh.build(request).comparisons)
                self.assertEqual(1, fresh.metrics.counts['comparison_cache_misses'] - previous_misses)

    def test_pricing_and_identity_algorithm_changes_invalidate_derived_runs(self):
        service = self.service(source(1))
        request = ReportRequest(ReportKind.COMPARISONS)
        original = service.build(request).comparisons
        service.pricing_provider.catalog = replace(service.pricing_provider.catalog, models=())
        fresh = self.fresh(service)
        previous_misses = fresh.metrics.counts['comparison_cache_misses']
        unpriced = fresh.build(request).comparisons
        self.assertEqual(3, fresh.metrics.counts['comparison_cache_misses'] - previous_misses)
        self.assertNotEqual(original.revision, unpriced.revision)
        self.assertTrue(all(run.ccost is None and not run.cost_complete for run in unpriced.groups[0].runs))
        self.assertNotIn('cost', [fact.kind for fact in unpriced.groups[0].facts])
        with patch('src.reports.matched_inputs.ALGORITHM', 'future-first-input-rule'):
            fresh = self.fresh(service)
            previous_misses = fresh.metrics.counts['comparison_cache_misses']
            self.assertEqual(1, fresh.build(request).comparisons.total)
            self.assertEqual(3, fresh.metrics.counts['comparison_cache_misses'] - previous_misses)

    def test_large_group_has_no_row_cap_and_stable_activity_ties(self):
        history = source(1, repeats=501)
        for sid, snapshot in tuple(history.snapshots.items()):
            root = replace(snapshot.root, updated_at_ms=1_790_060_000_000)
            history.snapshots[sid] = replace(snapshot, root=root, sessions=(root,))
        batch_sizes = []

        def load_batch(ids, progress):
            batch_sizes.append(len(ids))
            return {sid: history.load_session_snapshot(sid) for sid in ids}

        with patch.object(history, 'load_session_snapshots_observed', side_effect=load_batch, create=True):
            result = self.service(history).build(ReportRequest(ReportKind.COMPARISONS)).comparisons
        # The compact all-root scan retains at most ten previews. Its displayed
        # representative is acquired separately when outside that bounded set.
        self.assertEqual([128, 128, 128, 117, 1], batch_sizes)
        self.assertEqual(1, result.total)
        self.assertEqual(501, len(result.groups[0].runs))
        self.assertEqual('root-0000', result.groups[0].runs[0].session_id)

    def test_failed_cancelled_unknown_end_and_missing_counters_are_not_successful_records(self):
        history = source(1)
        service = self.service(history)
        catalog = service._load_comparison_catalog()
        snapshot = next(iter(history.snapshots.values()))
        for error, finish, expected in [('Failure', None, 'failed'), ('MessageAbortedError', None, 'aborted'),
                                        (None, 'tool-calls', 'unknown')]:
            changed = replace(snapshot, messages=(snapshot.messages[0], replace(snapshot.messages[1],
                error_name=error, finish_reason=finish), *snapshot.messages[2:]))
            bundle = analyze_snapshot(changed, tracked_provider=None, estimator=catalog.estimate, now_ms=service.now_ms)
            run = project_run(changed, bundle, catalog, service.config)
            self.assertEqual(expected, run.status)
            self.assertEqual((), facts([run, replace(run, session_id='other')]))
        changed = replace(snapshot, invocations=(replace(snapshot.invocations[0],
            tokens=replace(snapshot.invocations[0].tokens, known_fields=())), *snapshot.invocations[1:]))
        bundle = analyze_snapshot(changed, tracked_provider=None, estimator=catalog.estimate, now_ms=service.now_ms)
        run = project_run(changed, bundle, catalog, service.config)
        self.assertFalse(run.cost_complete)
        self.assertIsNone(run.token_mix_percent)

    def test_qualified_gaps_zero_missing_prices_failures_mixed_and_period_scope(self):
        service = self.service(source(1))
        runs = service.build(ReportRequest(ReportKind.COMPARISONS)).comparisons.groups[0].runs
        invalid = [replace(run, status='failed') for run in runs]
        self.assertEqual((), facts(invalid))
        partial = [replace(run, cost_complete=False) for run in runs]
        self.assertNotIn('cost', [fact.kind for fact in facts(partial)])
        mixed = [replace(run, mixed=True) for run in runs]
        self.assertNotIn('same-time', [fact.kind for fact in facts(mixed)])
        zeros = [replace(run, duration_ms=0, ccost=Decimal(0)) for run in runs]
        self.assertTrue(all(fact.ratio is None for fact in facts(zeros)))
        self.assertIsNone(period_fact(runs, 0, service.now_ms, complete=False))
        self.assertEqual('match-speed-gap', period_fact(runs, 0, service.now_ms, complete=True).metric)
        self.assertEqual('original-thinker', period_fact(runs, service.now_ms - 1000, service.now_ms, complete=True).metric)
        self.assertEqual(1, len(grouped([*runs, runs[0]])))

    def test_ai_stats_reuses_its_period_acquisition_and_preserves_ten_baseline_metrics(self):
        history = source(1)
        service = self.service(history)
        result = service.build(ReportRequest(ReportKind.AI_STATS, stats_scope='all'))
        self.assertTrue(all(len(period.metrics) == 10 for period in result.ai_stats))
        self.assertEqual('match-speed-gap', result.ai_stats[-1].matched.metric)
        self.assertEqual(3, history.load_count, 'no separate deep match scan')
        with patch.object(history, 'load_session_snapshot', side_effect=AssertionError('warm history hydration')):
            self.assertEqual(result, self.fresh(service).build(ReportRequest(ReportKind.AI_STATS, stats_scope='all')))

    def test_application_allowlist_display_units_and_http_validation(self):
        service = self.service(source(1))
        result = ReportApplication(lambda now, progress: self.fresh(service), clock=lambda: service.now_ms).execute(
            parse_report({'kind': 'comparisons'})).to_json()
        self.assertIsNone(result['error'])
        row = result['view']['comparisons']['groups'][0]['runs'][0]
        self.assertNotIn('fingerprint', row)
        self.assertIn('precise_start', row['display'])
        self.assertIn('$', row['display_units']['usd']['ccost'])
        for value in [{'kind': 'comparisons', 'comparison_offset': 10},
                      {'kind': 'comparisons', 'comparison_offset': -10},
                      {'kind': 'comparisons', 'comparison_revision': 'bad'},
                      {'kind': 'normal', 'comparison_offset': 0}]:
            with self.assertRaises(ValueError):
                parse_report(value)

    def test_actual_finite_job_coalesces_returns_all_rows_and_can_be_cancelled(self):
        jobs = ReportJobs(target=finite_comparisons)
        self.addCleanup(jobs.close)
        request = ReportRequest(ReportKind.COMPARISONS)
        key = jobs.submit(request)
        self.assertEqual(key, jobs.submit(request))
        end = time.monotonic() + 12
        while time.monotonic() < end:
            jobs.tick(); job = jobs.snapshot(key)
            if job['status'] not in ('queued', 'running'):
                break
            time.sleep(.02)
        self.assertEqual('complete', job['status'], job.get('error'))
        self.assertEqual(10, len(job['result']['view']['comparisons']['groups']))
        self.assertEqual(key, jobs.submit(request))
        queued = jobs.submit(ReportRequest(ReportKind.COMPARISONS, comparison_offset=10, comparison_revision='a' * 64))
        jobs.cancel(queued)
        self.assertEqual('cancelled', jobs.snapshot(queued)['status'])


if __name__ == '__main__':
    unittest.main()
