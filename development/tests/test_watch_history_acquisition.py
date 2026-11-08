"""Cross-source history proof and transient initial-acquisition recovery."""
from pathlib import Path
from dataclasses import replace
import json
import tempfile
import unittest
from unittest.mock import patch

from development.tests.fixtures.opencode_v2_service import source_with_current_service
from development.tests.fixtures.pricing_catalog import threshold_catalog
from development.tests.fixtures.history_acquisition import CaptureWorkers
from development.tests.fixtures.report_runtime import FakePricingProvider
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from development.tests.fixtures.watch_runtime import make_service
from src.cache import CacheDatabase
from src.analysis.session_cost import reconcile_session_cost
from src.application.live_projection import project_live
from src.domain import TokenUsage
from src.reports.context_guidance import complete_guidance, guidance_semantics
from src.reports.watch_capture import capture_rows
from src.sources.errors import SourceConcurrentChangeError, http_failure, transport_failure
from src.sources.opencode_v2 import OpenCodeV2Source
from src.sources.opencode_v2_interruptions import LiveInterruptionReasons
from src.sources.selection import SourceSelection
from src.watch.card_workers import CardResult
from src.watch.cards import WatchCards
from src.watch.observers import observe_catalog
from src.watch.models import WatchProjection
from src.web.composition import live_acquisition


class WatchHistoryAcquisitionTests(unittest.TestCase):
    def test_isolated_card_factory_preserves_observed_interruption_revision(self):
        with source_with_current_service() as (source, server, registration), tempfile.TemporaryDirectory() as tmp:
            # The durable idle ends the attempt. The live event adds only its actor.
            server.messages['ses_current'][1].update(finish='error', error=dict(type='aborted'))
            server.messages['ses_current'].append(dict(id='msg_stop', type='idle',
                outcome='interrupted', time=dict(created=5000)))
            server.events = [dict(id='evt_stop', type='session.execution.interrupted',
                created=5000, data=dict(sessionID='ses_current', reason='user'))]
            changes = source.iter_changes()
            next(changes)
            changes.close()
            observation = observe_catalog(source)
            selection = SourceSelection(source, 'v2', (), source.probe())
            def isolated_selection(_requested):
                isolated = OpenCodeV2Source(registration, timeout_seconds=2)
                return SourceSelection(isolated, 'v2', (), isolated.probe())
            with patch('src.bootstrap._account_providers', return_value=()), \
                    patch('src.web.composition.SourceSelector.select', side_effect=isolated_selection), \
                    patch('src.web.composition.CacheDatabase', side_effect=lambda _root: CacheDatabase(Path(tmp))), \
                    patch('src.web.composition.GitHubCopilotPricingProvider', side_effect=lambda **_options: FakePricingProvider()):
                driver = live_acquisition(selection=selection)
                owner = driver.coordinator
                try:
                    owner.cards.catalog(observation)
                    root = observation.roots[0]
                    service = owner.card_workers.factory(90000)
                    try:
                        capture, item = capture_rows(service, root)
                    finally:
                        service.source.close_reads()
                        service.close_accounts()
                    entry = owner.cards.sessions[root.session_id]

                    owner.cards.accept(CardResult(root.session_id, entry.generation,
                        'rows', (capture, (), item.snapshot)), 90000)
                    history = owner.cards.project(90000)[1]

                    self.assertEqual(entry.revision, item.snapshot.source_revision)
                    self.assertEqual('observed', owner.cards.history.state)
                    self.assertEqual(('ses_current',), tuple(card.session_id for card in history))
                    self.assertEqual('user', history[0].rows[0].prompt.abort_reason)
                finally:
                    owner.close()

    def test_initial_retryable_history_failure_has_bounded_automatic_recovery_grace(self):
        with source_with_current_service() as (source, _server, _registration):
            observation = observe_catalog(source)
            clock = [0.0]
            cards = WatchCards(None, monotonic=lambda: clock[0])
            cards.catalog(observation)
            root = observation.roots[0]
            entry = cards.sessions[root.session_id]

            cards.accept(CardResult(root.session_id, entry.generation, 'unavailable',
                transport_failure(TimeoutError(), phase='capture')), 90000)
            cards.project(90000)

            self.assertEqual('loading', cards.history.state, 'one transient read is not a terminal initial failure')
            clock[0] = 5
            cards.project(95000)
            self.assertEqual('unavailable', cards.history.state, 'a sustained outage remains honest')

    def test_large_catalog_automatically_retries_and_certifies_independent_winners(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = SyntheticMonthSource(2700, 1, month_start_ms=1000)
            source.snapshots = {key: replace(value, complete=True) for key, value in source.snapshots.items()}
            service = make_service(tmp, source, now_ms=1_000_000_000)[2]
            failures = {'root-2699': [SourceConcurrentChangeError('synthetic churn')],
                'root-0000': [transport_failure(TimeoutError(), phase='capture')]}
            workers = CaptureWorkers(service, failures)
            cards = WatchCards(workers, monotonic=lambda: 0)
            cards.catalog(observe_catalog(source))

            for _ in range(2700):
                cards.tick(1_000_000_000)
                history = cards.project(1_000_000_000)[1]
                self.assertLessEqual(len(workers.jobs), 4)
                if cards.history.checked < 2700:
                    self.assertEqual((), history, 'delayed candidate cannot be bypassed')
                if cards.history.state == 'observed':
                    break

            self.assertEqual((2700, 2700), (cards.history.checked, cards.history.total))
            self.assertEqual(tuple(f'root-{index:04}' for index in range(2695, 2700)),
                tuple(card.session_id for card in history))
            self.assertEqual(2, workers.attempts['root-2699'])
            self.assertEqual(2, workers.attempts['root-0000'])

    def test_revision_churn_stays_pending_for_days_then_certifies_without_retry_button(self):
        with source_with_current_service() as (source, _server, _registration), tempfile.TemporaryDirectory() as tmp:
            clock = [0.0]
            observation = observe_catalog(source)
            root = observation.roots[0]
            cards = WatchCards(None, monotonic=lambda: clock[0])
            cards.catalog(observation)
            entry = cards.sessions[root.session_id]
            for elapsed in (0, 5, 300, 2 * 86400):
                clock[0] = elapsed
                cards.accept(CardResult(root.session_id, entry.generation, 'unavailable',
                    SourceConcurrentChangeError('valid changing fixture')), 90000)
                self.assertEqual((), cards.project(90000)[1])
                self.assertEqual('loading', cards.history.state)

            service = make_service(tmp, source, now_ms=90000)[2]
            capture, item = capture_rows(service, root)
            cards.accept(CardResult(root.session_id, entry.generation, 'rows',
                (capture, (), item.snapshot)), 90000)
            history = cards.project(90000)[1]

            self.assertEqual('observed', cards.history.state)
            self.assertEqual((root.session_id,), tuple(card.session_id for card in history))
            self.assertEqual((1, 1), (cards.history.checked, cards.history.total))

    def test_certified_winners_publish_context_before_cost_and_guidance_enrich_without_new_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = SyntheticMonthSource(6, 1, month_start_ms=1000)
            source.snapshots = {key: replace(snapshot, complete=True,
                invocations=tuple(replace(item, tokens=TokenUsage(input=120000, output=10))
                    for item in snapshot.invocations)) for key, snapshot in source.snapshots.items()}
            service = make_service(tmp, source, now_ms=1_000_000)[2]
            catalog = threshold_catalog()
            service.pricing_provider.catalog = catalog
            cards = WatchCards(None)
            cards.catalog(observe_catalog(source))
            pending = []
            with patch.object(service, '_threshold_multiplier', side_effect=AssertionError('premature sample')):
                for root in source.list_sessions():
                    capture, item = capture_rows(service, root, defer_guidance=True)
                    entry = cards.sessions[root.session_id]
                    pending.append(CardResult(root.session_id, entry.generation,
                        'rows', (capture, (), item.snapshot)))
            for result in pending[:-1]:
                cards.accept(result, 1_000_000)
            self.assertEqual((), cards.project(1_000_000)[1], 'cheap candidates are not final winners')

            cards.accept(pending[-1], 1_000_000)
            history = cards.project(1_000_000)[1]
            initial = project_live(WatchProjection('Watch', 'fixture', (), history_cards=history)).to_json()

            expected_ids = tuple(f'root-{index:04}' for index in range(1, 6))
            self.assertEqual(expected_ids, tuple(card.session_id for card in history))
            for card in initial['history_cards']:
                self.assertEqual('GPT Test', card['rows'][0]['model'])
                self.assertIsNotNone(card['rows'][0]['prompt']['completed_at_ms'])
                self.assertEqual(120010, card['session_summary']['context']['watch_next_context_tokens'])
                self.assertEqual('pending', card['session_summary']['context']['warning']['guidance_state'])
                self.assertEqual('loading', card['session_summary']['state'])
                self.assertIsNone(card['session_summary']['cost'])
            proof = (cards.history.epoch, cards.history.verified_at_ms, cards.evidence_revision)
            reads = source.load_count
            entry = cards.sessions['root-0005']
            rows = entry.capture.rows

            # Independent enrichment uses already-qualified inputs, never a second winner scan.
            entry.capture = replace(entry.capture, context=complete_guidance(entry.capture.context,
                (0, 0, 0, 0, 0), catalog, guidance_semantics(service, catalog, catalog)))
            entry.cost.value = reconcile_session_cost(service.cache_repository, entry.cost.evidence, catalog)
            entry.cost.validated_key = entry.cost.source_key
            entry.cost.valuation_revision = entry.cost.value.valuation_revision
            enriched = cards.project(1_000_001)[1]
            final = project_live(WatchProjection('Watch', 'fixture', (), history_cards=enriched)).to_json()

            self.assertEqual(expected_ids, tuple(card.session_id for card in enriched))
            self.assertEqual(proof, (cards.history.epoch, cards.history.verified_at_ms, cards.evidence_revision))
            self.assertEqual(reads, source.load_count)
            self.assertIs(rows, entry.capture.rows)
            summary = final['history_cards'][-1]['session_summary']
            self.assertEqual('ready', summary['context']['warning']['guidance_state'])
            self.assertEqual('observed', summary['state'])
            self.assertEqual(1, summary['cost']['priced_requests'])
            self.assertGreater(float(summary['cost']['known_ccost']), 0)

    def test_repeated_io_failures_keep_original_confirmation_clock_and_auth_has_no_grace(self):
        with source_with_current_service() as (source, _server, _registration):
            clock = [0.0]
            cards = WatchCards(None, monotonic=lambda: clock[0])
            cards.catalog(observe_catalog(source))
            entry = cards.sessions['ses_current']
            failure = CardResult('ses_current', entry.generation, 'unavailable',
                transport_failure(TimeoutError(), phase='capture'))
            cards.accept(failure, 90000)
            clock[0] = 4.9
            cards.accept(failure, 94900)
            cards.project(94900)
            self.assertEqual('loading', cards.history.state)
            clock[0] = 5
            cards.project(95000)
            self.assertEqual('unavailable', cards.history.state)
            entry.source_status.clear()
            cards.accept(CardResult('ses_current', entry.generation, 'unavailable',
                http_failure(401, phase='capture')), 95001)
            cards.project(95001)
            self.assertEqual('unavailable', cards.history.state)

    def test_evidence_copy_is_bounded_independent_and_preserves_eviction_order(self):
        evidence = LiveInterruptionReasons()
        for index in range(1025):
            evidence.observe(dict(id=f'evt_{index:04}', type='session.execution.interrupted',
                created=1000 + index, data=dict(sessionID='ses_root', reason='user')))
        duplicate = evidence.copy()

        duplicate.observe(dict(id='evt_later', type='session.execution.interrupted',
            created=3000, data=dict(sessionID='ses_root', reason='user')))

        self.assertEqual(1024, len(evidence.signature('ses_root')))
        self.assertEqual(1024, len(duplicate.signature('ses_root')))
        self.assertNotIn(('msg_0000', 1000), evidence.signature('ses_root'))
        self.assertIn(('msg_0001', 1001), evidence.signature('ses_root'))
        self.assertNotIn(('msg_0001', 1001), duplicate.signature('ses_root'))
        self.assertNotIn(('msg_later', 3000), evidence.signature('ses_root'))

    def test_service_epoch_change_discards_old_events_even_from_existing_stream(self):
        with source_with_current_service() as (source, server, registration):
            server.events = [dict(id=f'evt_{name}', type='session.execution.interrupted',
                created=5000, data=dict(sessionID='ses_current', reason='user')) for name in ('first', 'late')]
            # Model an already-buffered old event even after its socket closes.
            stream = patch('src.sources.opencode_v2_transport.V2HttpClient.sse',
                side_effect=lambda *_args, **_options: iter(server.events))
            stream.start()
            self.addCleanup(stream.stop)
            changes = source.iter_changes()
            next(changes)
            isolated = OpenCodeV2Source(registration, timeout_seconds=2)
            self.addCleanup(isolated.close_reads)
            self.assertTrue(isolated.inherit_live_evidence(source))
            self.assertEqual((('msg_first', 5000),), isolated._interruptions.signature('ses_current'))
            value = json.loads(registration.read_text(encoding='utf-8'))
            value['pid'] += 1
            registration.write_text(json.dumps(value), encoding='utf-8')

            self.assertTrue(isolated.inherit_live_evidence(source))
            next(changes)
            changes.close()

            self.assertEqual((), source._interruptions.signature('ses_current'))
            self.assertEqual((), isolated._interruptions.signature('ses_current'))

    def test_other_registration_does_not_inherit_actor_evidence(self):
        with source_with_current_service() as (source, server, _registration), \
                source_with_current_service() as (other, _other_server, _other_registration):
            server.events = [dict(id='evt_stop', type='session.execution.interrupted',
                created=5000, data=dict(sessionID='ses_current', reason='user'))]
            changes = source.iter_changes()
            next(changes)
            changes.close()

            copied = other.inherit_live_evidence(source)

            self.assertFalse(copied)
            self.assertEqual((), other._interruptions.signature('ses_current'))

    def test_connection_refresh_in_same_epoch_retains_actor_evidence(self):
        with source_with_current_service() as (source, server, _registration):
            server.events = [dict(id='evt_stop', type='session.execution.interrupted',
                created=5000, data=dict(sessionID='ses_current', reason='user'))]
            changes = source.iter_changes()
            next(changes)
            changes.close()

            source.refresh_connection()
            health = source.probe()

            self.assertTrue(health.healthy)
            self.assertEqual((('msg_stop', 5000),), source._interruptions.signature('ses_current'))

    def test_event_after_transfer_requires_reobservation_and_rejects_old_capture(self):
        with source_with_current_service() as (source, server, registration), tempfile.TemporaryDirectory() as tmp:
            server.messages['ses_current'][1].update(finish='error', error=dict(type='aborted'))
            server.messages['ses_current'].append(dict(id='msg_stop', type='idle',
                outcome='interrupted', time=dict(created=5000)))
            cards = WatchCards(None)
            cards.catalog(observe_catalog(source))
            root = cards.sessions['ses_current'].root
            old_generation = cards.sessions['ses_current'].generation
            isolated = OpenCodeV2Source(registration, timeout_seconds=2)
            self.addCleanup(isolated.close_reads)
            isolated.inherit_live_evidence(source)
            service = make_service(tmp, isolated, now_ms=90000)[2]
            self.addCleanup(service.close_accounts)
            server.events = [dict(id='evt_stop', type='session.execution.interrupted',
                created=5000, data=dict(sessionID='ses_current', reason='user'))]
            changes = source.iter_changes()
            next(changes)
            changes.close()
            old_capture, old_item = capture_rows(service, root)
            self.assertEqual(old_generation, cards.sessions['ses_current'].generation,
                'event receipt alone does not advance the card generation')

            cards.catalog(observe_catalog(source))
            cards.accept(CardResult('ses_current', old_generation, 'rows',
                (old_capture, (), old_item.snapshot)), 90000)

            self.assertEqual((), cards.project(90000)[1])
            self.assertIsNone(cards.sessions['ses_current'].capture)
            isolated.inherit_live_evidence(source)
            capture, item = capture_rows(service, root)
            cards.accept(CardResult('ses_current', cards.sessions['ses_current'].generation,
                'rows', (capture, (), item.snapshot)), 90000)
            history = cards.project(90000)[1]
            self.assertEqual('observed', cards.history.state)
            self.assertEqual('user', history[0].rows[0].prompt.abort_reason)


if __name__ == '__main__':
    unittest.main()
