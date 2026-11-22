"""Exact first-input identities and the canonical runs behind the AI Stats match fact."""
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from development.tests.fixtures.compact_reports import report_service
from development.tests.fixtures.repeated_inputs import source
from development.tests.fixtures.session_snapshots import make_snapshot
from development.tests.fixtures.opencode_v1_database import create_v1_database
from src.analysis import analyze_snapshot
from src.analysis.input_identity import first_input, fingerprint
from src.analysis.matched_runs import gap, grouped, period_fact
from src.domain import EventKind, ModelRef
from src.sources.opencode_v1 import OpenCodeV1Source
from src.sources.opencode_v2_normalization import normalize_message_bundle
from src.reports import ReportKind, ReportRequest, ReportService
from src.reports.matched_runs import project_run


class FirstPromptRunTests(unittest.TestCase):
    def service(self, history):
        service = report_service(self, history, now_ms=1_790_086_400_000)
        service.selection = replace(service.selection, warnings=())
        return service

    def fresh(self, service):
        return ReportService(selection=service.selection, pricing_provider=service.pricing_provider,
            account_provider=None, cache_repository=service.cache_repository, config=service.config, now_ms=service.now_ms)

    def runs(self, history):
        service = self.service(history)
        catalog = service._load_comparison_catalog()
        return [project_run(value, analyze_snapshot(value, tracked_provider=None, estimator=catalog.estimate,
                    now_ms=service.now_ms), catalog, service.config) for value in history.snapshots.values()]

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
        a = replace(message, parts=(replace(part, data={'text': 'x' * 1000 + 'a'}),))
        b = replace(message, parts=(replace(part, data={'text': 'x' * 1000 + 'b'}),))
        self.assertNotEqual(fingerprint(a), fingerprint(b), 'long shared prefixes never merge identities')

    def test_equal_later_input_in_a_different_root_never_joins_the_first_input_pair(self):
        history = source(2, repeats=2)
        matched = first_input(history.snapshots['root-0000']).parts[0].data['text']
        snapshot = history.snapshots['root-0003']
        first, response, later, final = snapshot.messages
        messages = (replace(first, parts=(replace(first.parts[0], data={'text': 'Different first input'}),)),
                    response, replace(later, parts=(replace(later.parts[0], data={'text': matched}),)), final)
        history.snapshots['root-0003'] = replace(snapshot, messages=messages,
            parts=tuple(part for message in messages for part in message.parts))

        groups = grouped(self.runs(history))

        self.assertEqual([{'root-0000', 'root-0001'}], [{run.session_id for run in group} for group in groups])

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

    def test_three_repeats_use_first_prompt_only_metrics(self):
        runs = self.runs(source(1))

        self.assertEqual([100, 200, 300], [run.duration_ms for run in runs])
        self.assertEqual([1, 1, 1], [run.calls for run in runs])
        self.assertEqual(1, len({run.ccost for run in runs}))
        self.assertTrue(all(run.cost_complete and run.status == 'complete' for run in runs))
        self.assertEqual(Decimal(3), gap(runs, 'time').ratio)

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
            self.assertIsNone(gap([run, replace(run, session_id='other')], 'time'))
        changed = replace(snapshot, invocations=(replace(snapshot.invocations[0],
            tokens=replace(snapshot.invocations[0].tokens, known_fields=())), *snapshot.invocations[1:]))
        bundle = analyze_snapshot(changed, tracked_provider=None, estimator=catalog.estimate, now_ms=service.now_ms)
        run = project_run(changed, bundle, catalog, service.config)
        self.assertFalse(run.cost_complete)
        self.assertIsNone(run.token_mix_percent)

    def test_qualified_gaps_zero_missing_prices_failures_mixed_and_period_scope(self):
        history = source(1)
        service = self.service(history)
        runs = self.runs(history)
        self.assertIsNone(gap([replace(run, status='failed') for run in runs], 'time'))
        self.assertIsNone(gap([replace(run, cost_complete=False) for run in runs], 'cost'))
        zeros = [replace(run, duration_ms=0, ccost=Decimal(0)) for run in runs]
        self.assertTrue(all(gap(zeros, kind).ratio is None for kind in ('time', 'cost')))
        self.assertIsNone(period_fact(runs, 0, service.now_ms, complete=False))
        self.assertEqual('match-speed-gap', period_fact(runs, 0, service.now_ms, complete=True).metric)
        self.assertEqual('original-thinker', period_fact(runs, service.now_ms - 1000, service.now_ms, complete=True).metric)
        self.assertEqual(1, len(grouped([*runs, runs[0]])))

    def test_ai_stats_reuses_its_period_acquisition_and_preserves_ten_baseline_metrics(self):
        history = source(1)
        service = self.service(history)
        result = service.build(ReportRequest(ReportKind.AI_STATS, stats_scope='all'))
        self.assertTrue(all(len(period.metrics) == 13 for period in result.ai_stats))
        self.assertEqual('match-speed-gap', result.ai_stats[-1].matched.metric)
        self.assertEqual(3, history.load_count, 'no separate deep match scan')
        with patch.object(history, 'load_session_snapshot', side_effect=AssertionError('warm history hydration')):
            self.assertEqual(result, self.fresh(service).build(ReportRequest(ReportKind.AI_STATS, stats_scope='all')))

if __name__ == '__main__':
    unittest.main()
