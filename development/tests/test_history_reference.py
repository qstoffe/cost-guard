"""Independent Earlier expectation from complete snapshots, not product card state."""
from dataclasses import replace
import json
import unittest
from types import SimpleNamespace
from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from development.tests.integration.history_reference import HistoryReference
from src.sources.errors import SourceConcurrentChangeError


class ReferenceSource(SyntheticMonthSource):
    observation_epoch = 'reference-epoch'

    def __init__(self, roots=8):
        super().__init__(roots, 1, month_start_ms=1000)
        self.snapshots = {key: replace(value, complete=True) for key, value in self.snapshots.items()}
        self.batches = []
        self.failing = set()

    def load_session_snapshots(self, keys):
        self.batches.append(tuple(keys))
        if self.failing.intersection(keys):
            raise SourceConcurrentChangeError('Synthetic changing tree')
        return {key: self.load_session_snapshot(key) for key in keys}


class HistoryReferenceTests(unittest.TestCase):
    def run_oracle(self, reference, host=None, **options):
        from development.tests.integration.real_history_oracle import run
        source = Mock()
        reference.revisions = dict.fromkeys(range(1000))
        reference.summary.return_value = dict(roots=1000, missing=0)
        host = host or Mock(failure=None)
        host.browser_url.return_value = 'http://127.0.0.1:12345/#bootstrap=synthetic'
        host.thread.is_alive.return_value = host.live.thread.is_alive.return_value = False
        host.jobs._parked = {}
        with TemporaryDirectory() as directory, \
                patch('development.tests.integration.real_history_oracle.load_configuration',
                    return_value=SimpleNamespace(values={'openCode':{'source':'v2'}})), \
                patch('development.tests.integration.real_history_oracle.SourceSelector') as selector, \
                patch('development.tests.integration.real_history_oracle.HistoryReference', return_value=reference), \
                patch('development.tests.integration.real_history_oracle.WebHost', return_value=host), \
                patch('development.tests.integration.real_history_oracle.probe_lifecycle', return_value=nullcontext()), \
                patch('development.tests.integration.real_history_oracle.time.sleep'), \
                patch('development.tests.integration.real_history_oracle.subprocess.run', return_value=SimpleNamespace(
                    returncode=0, stdout=json.dumps(dict(outcome='PASS', browser_exited=True)))) as browser, \
                patch('builtins.print'):
            selector.return_value.select.return_value = SimpleNamespace(selected='v2', source=source)
            passed = run(Path.cwd(), Path(directory) / 'output', Path('synthetic-browser'), **options)
            facts = json.loads((Path(directory) / 'output' / 'result.json').read_text(encoding='utf-8'))
        rendered = [json.loads(call.kwargs['input'])['history_rows'] for call in browser.call_args_list]
        return passed, facts, rendered, source

    def test_serial_oracle_defers_reference_reads_and_validates_the_first_verified_certificate(self):
        reference = Mock()
        reference.refresh.return_value = reference.matches.return_value = True
        reference.expected.return_value = tuple((str(index), 'prompt', index) for index in range(5))
        host = Mock(failure=None)
        pending = dict(verified=False, revisions={'root':'pending'})
        first = dict(verified=True, revisions={'root':'first'})
        later = dict(verified=True, revisions={'root':'later'})

        def publish_sequence():
            # Only preparation has read the reference while the product is acquiring history.
            for _ in range(3):
                self.assertEqual(reference.refresh.call_count, 1)
                host.live.publish('live', dict(view=dict(history_state='observed')))

        host.start.side_effect = publish_sequence
        with patch('development.tests.integration.real_history_oracle.product_proof',
                side_effect=[pending, first, later]):
            passed, facts, _rendered, source = self.run_oracle(reference, host, serial_first=True)

        self.assertTrue(passed)
        self.assertIs(reference.matches.call_args_list[0].args[0], first)
        self.assertIs(reference.matches.call_args_list[1].args[0], later)
        self.assertTrue(facts['first_certificate_validation']['matched'])
        self.assertEqual(facts['timed_product_phase']['live_publications'], 2)
        self.assertEqual(facts['timed_product_phase']['reference_refreshes'], 0)
        self.assertGreaterEqual(facts['first_independently_matched_seconds'],
            facts['first_product_certified_seconds'])
        source.close_reads.assert_called_once_with()

    def test_serial_oracle_never_uses_a_later_matching_proof_to_bless_the_timed_first_certificate(self):
        reference = Mock()
        reference.refresh.return_value = True
        reference.expected.return_value = tuple((str(index), 'prompt', index) for index in range(5))
        first = dict(verified=True, revisions={'root':'first'})
        later = dict(verified=True, revisions={'root':'later'})
        reference.matches.side_effect = lambda proof: proof is later
        host = Mock(failure=None)
        host.start.side_effect = lambda: [host.live.publish('live', dict(view={})) for _ in range(2)]
        with patch('development.tests.integration.real_history_oracle.product_proof', side_effect=[first, later]):
            passed, facts, rendered, source = self.run_oracle(reference, host, serial_first=True)

        self.assertFalse(passed)
        reference.matches.assert_called_once_with(first)
        self.assertEqual(reference.refresh.call_count, 2, 'prepare and one post-boundary validation only')
        self.assertEqual(rendered, [])
        self.assertFalse(facts['first_certificate_validation']['matched'])
        self.assertEqual(facts['failure']['code'], 'probe_first_certificate_validation_inconclusive')
        self.assertIn('closure', facts)
        source.close_reads.assert_called_once_with()

    def test_owned_oracle_host_publishes_headless_readiness_before_requesting_browser_link(self):
        reference = Mock()
        reference.refresh.return_value = reference.matches.return_value = True
        reference.expected.return_value = tuple((str(index), 'prompt', index) for index in range(5))
        host = Mock(failure=None)

        def link_after_ready():
            host.publish_ready.assert_called_once_with()
            return host.browser_url.return_value

        host.browser_url.side_effect = link_after_ready

        passed, _facts, _rendered, source = self.run_oracle(reference, host)

        self.assertTrue(passed)
        host.start.assert_called_once_with()
        host.browser_url.assert_called_once_with()
        source.close_reads.assert_called_once_with()

    def test_oracle_rerenders_new_winners_after_a_live_change_and_passes_only_on_a_stable_rematch(self):
        before = tuple((f'old-{index}', 'prompt', index) for index in range(5))
        after = before[1:] + (('new', 'prompt', 9),)
        reference = Mock()
        reference.refresh.return_value = True
        # pre-browser match; stale proof after browser 1, then re-match; stable after browser 2.
        reference.matches.side_effect = [True, False, True, True]
        # preparation, cycle-1 render, changed after re-match, cycle-2 render, stable.
        reference.expected.side_effect = [before, before, after, after, after]

        passed, facts, rendered, _source = self.run_oracle(reference)

        self.assertTrue(passed)
        self.assertEqual(rendered, [[list(row) for row in before], [list(row) for row in after]])
        self.assertEqual((facts['browser_cycles'], facts['post_browser_revalidated']), (2, True))
        self.assertEqual(len(facts['post_browser_rematch_seconds']), 2)

    def test_oracle_stays_inconclusive_when_winners_keep_changing_after_each_browser_check(self):
        winners = [tuple((f'w{cycle}-{index}', 'prompt', index) for index in range(5)) for cycle in range(4)]
        reference = Mock()
        reference.refresh.return_value = reference.matches.return_value = True
        reference.expected.side_effect = [winners[0], winners[0], winners[1], winners[1], winners[2],
            winners[2], winners[3]]

        passed, facts, rendered, _source = self.run_oracle(reference)

        self.assertFalse(passed)
        self.assertEqual(len(rendered), 3)
        self.assertEqual(facts['failure']['code'], 'probe_history_winners_kept_changing')
        self.assertNotIn('post_browser_revalidated', facts)

    def test_reference_uses_fresh_complete_global_transport_not_the_scoped_card_reader(self):
        from development.tests.fixtures.opencode_v2_service import source_with_current_service
        with source_with_current_service() as (source, _server, _registration):
            reference = HistoryReference(source, clock_ms=lambda: 1_000_000)

            self.assertTrue(reference.refresh())

            self.assertIsNone(source._card_trees)
            self.assertGreater(source.metrics.counts['full_catalog_fetches'], 1)
            self.assertEqual(0, source.metrics.counts.get('scoped_catalog_brackets', 0))
            self.assertIsNotNone(reference.expected())

    def test_actual_product_proof_is_detached_and_cannot_treat_pending_history_as_certified(self):
        from development.tests.integration.real_history_oracle import product_proof
        entry = SimpleNamespace(revision='revision', generation=1, verified_generation=1,
            source_status=SimpleNamespace(failed_at=None), history_status=SimpleNamespace(failed_at=None))
        owner = SimpleNamespace(cards=SimpleNamespace(sessions={'root':entry}),
            source=SimpleNamespace(observation_epoch='epoch'))
        driver = SimpleNamespace(coordinator=owner, error=None)
        view = dict(history_state='observed', history_checked=1, history_total=1, history_epoch=1,
            history_cards=[dict(session_id='root', rows=[dict(prompt=dict(event_id='prompt', completed_at_ms=100))])])

        proof = product_proof(driver, dict(view=view))
        entry.revision = 'changed'
        view['history_cards'][0]['rows'][0]['prompt']['completed_at_ms'] = 200

        self.assertEqual({'root':'revision'}, proof['revisions'])
        self.assertEqual((('root', 'prompt', 100),), proof['rows'])
        self.assertTrue(proof['verified'])
        view['history_state'] = 'loading'
        self.assertIsNone(product_proof(driver, dict(view=view)))
        view['history_state'] = 'observed'
        entry.verified_generation = 0
        self.assertFalse(product_proof(driver, dict(view=view))['verified'])

    def test_complete_population_ranks_finishes_not_catalog_activity_and_keeps_only_scalars(self):
        source = ReferenceSource()
        source.snapshots = {key: replace(value, root=replace(value.root, updated_at_ms=9_000_000-index))
            for index, (key, value) in enumerate(source.snapshots.items())}
        reference = HistoryReference(source, clock_ms=lambda: 1_000_000)

        self.assertTrue(reference.refresh())

        expected = tuple((f'root-{index:04d}', f'root-{index:04d}-u-0000', 1300 + index * 60_000)
            for index in range(3, 8))
        self.assertEqual(expected, reference.expected())
        self.assertEqual(expected[-3:], reference.expected(mini=True))
        self.assertTrue(all(len(batch) <= 3 for batch in source.batches))
        self.assertEqual(8, source.load_count)
        self.assertFalse(any(hasattr(fact, 'snapshot') or hasattr(fact, 'prompts') for fact in reference.facts.values()))
        self.assertNotIn('root-', json.dumps(reference.summary()))

    def test_reconciliation_reads_only_changed_roots_and_removes_deleted_members(self):
        source = ReferenceSource()
        reference = HistoryReference(source, clock_ms=lambda: 1_000_000)
        self.assertTrue(reference.refresh())
        source.snapshots['root-0007'] = replace(source.snapshots['root-0007'], source_revision='changed')
        source.snapshots.pop('root-0006')
        source.batches.clear()

        self.assertTrue(reference.refresh())

        self.assertEqual([('root-0007',)], source.batches)
        self.assertEqual(9, source.load_count)
        self.assertEqual(7, reference.summary()['roots'])
        self.assertNotIn('root-0006', reference.facts)

    def test_incomplete_or_churning_root_is_not_an_authorized_exclusion(self):
        source = ReferenceSource()
        source.snapshots['root-0007'] = replace(source.snapshots['root-0007'], complete=False)
        source.failing.add('root-0000')
        reference = HistoryReference(source, clock_ms=lambda: 1_000_000)

        self.assertFalse(reference.refresh())

        self.assertIsNone(reference.expected())
        self.assertGreater(reference.summary()['missing'], 0)
        source.failing.clear()
        source.snapshots['root-0007'] = replace(source.snapshots['root-0007'], complete=True)
        self.assertTrue(reference.refresh())
        self.assertEqual(5, len(reference.expected()))

    def test_epoch_change_during_scan_discards_all_previous_evidence(self):
        source = ReferenceSource()
        original = source.load_session_snapshots

        def changed(keys):
            snapshots = original(keys)
            source.observation_epoch = 'different-epoch'
            return snapshots

        source.load_session_snapshots = changed
        reference = HistoryReference(source, clock_ms=lambda: 1_000_000)

        self.assertFalse(reference.refresh())

        self.assertEqual({}, reference.facts)
        self.assertIsNone(reference.expected())
        self.assertEqual(1, reference.summary()['epoch_invalidations'])

    def test_time_sensitive_tool_continuation_is_reanalyzed_after_its_boundary(self):
        source = ReferenceSource(1)
        snapshot = source.snapshots['root-0000']
        source.snapshots['root-0000'] = replace(snapshot,
            messages=tuple(replace(row, finish_reason='tool-calls') if row.parent_message_id else row
                for row in snapshot.messages))
        now = [2000]
        reference = HistoryReference(source, clock_ms=lambda: now[0])
        self.assertTrue(reference.refresh())
        self.assertEqual((), reference.expected())

        now[0] = 61_301
        self.assertIsNone(reference.expected(), 'elapsed canonical lifecycle boundary invalidates old scalar')
        self.assertTrue(reference.refresh())

        self.assertEqual((('root-0000', 'root-0000-u-0000', 1300),), reference.expected())
        self.assertEqual(2, source.load_count)

    def test_comparison_requires_matching_epoch_membership_revisions_prompt_finish_and_order(self):
        source = ReferenceSource()
        reference = HistoryReference(source, clock_ms=lambda: 1_000_000)
        self.assertTrue(reference.refresh())
        proof = dict(epoch=source.observation_epoch, revisions=dict(reference.revisions),
            verified=True, rows=reference.expected())
        self.assertTrue(reference.matches(proof))
        for changed in (dict(proof, epoch='other'), dict(proof, verified=False),
                dict(proof, rows=proof['rows'][::-1]), dict(proof, revisions={}),
                dict(proof, rows=(*proof['rows'][:-1], (*proof['rows'][-1][:-1], -1)))):
            self.assertFalse(reference.matches(changed))


if __name__ == '__main__':
    unittest.main()
