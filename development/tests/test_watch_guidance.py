"""Web guidance is completed once, without delaying or re-verifying card rows."""
from contextlib import contextmanager
from concurrent.futures import Future
from dataclasses import replace
from decimal import Decimal
from threading import Event
import tempfile
import unittest
from unittest.mock import patch

from development.tests.fixtures.pricing_catalog import threshold_catalog
from development.tests.fixtures.session_snapshots import make_uncompacted_snapshot
from development.tests.fixtures.watch_runtime import MutableSource, make_service
from src.application.live_projection import project_live
from src.domain import TokenUsage
from src.reports.watch_capture import capture_rows
from src.watch.card_workers import CardResult
from src.watch.cards import CardSession, WatchCards
from src.watch.models import WatchProjection


@contextmanager
def guidance_case():
    from src.reports.context_guidance import GuidanceBinding, GuidanceScope, guidance_semantics
    from src.watch.card_guidance import CardGuidance
    from src.watch.card_workers import CardWorkers
    snapshot = make_uncompacted_snapshot(running=True)
    snapshot = replace(snapshot, invocations=tuple(replace(item,
        tokens=TokenUsage(input=120000, output=0)) if item.invocation_id == 'i_next' else item
        for item in snapshot.invocations))
    control = {'epoch': 'epoch-a', 'catalog': threshold_catalog(), 'available': True}
    clock = [10.0]
    created = []
    with tempfile.TemporaryDirectory() as tmp:
        def factory(now):
            service = make_service(tmp, MutableSource(snapshot), now_ms=now)[2]
            service.pricing_provider.catalog = control['catalog']
            created.append(service)
            return service
        service = factory(4000)
        def binding(service):
            if not control['available']:
                return None
            catalog = control['catalog']
            scope = GuidanceScope(('v2', 'synthetic-instance', control['epoch']),
                guidance_semantics(service, catalog, catalog))
            return GuidanceBinding(scope, catalog, catalog)
        workers = CardWorkers(factory)
        owner = CardGuidance(workers, service, binding=binding, monotonic=lambda: clock[0])
        cards = WatchCards(workers, guidance=owner)
        capture, _ = capture_rows(service, snapshot.root, defer_guidance=True)
        entry = CardSession(snapshot.root, snapshot.source_revision, 1,
            capture=capture, latest_ms=1, verified_generation=1, refresh_requested=False)
        cards.sessions[snapshot.root.session_id] = entry
        try:
            yield cards, owner, workers, control, clock, service, created
        finally:
            owner.cancel()
            workers.close()


class WatchGuidanceTests(unittest.TestCase):
    def test_deferred_capture_preserves_rows_tokens_and_warning_without_starting_sample(self):
        snapshot = make_uncompacted_snapshot(running=True)
        snapshot = replace(snapshot, invocations=tuple(replace(item,
            tokens=TokenUsage(input=120000, output=0)) if item.invocation_id == 'i_next' else item
            for item in snapshot.invocations))
        with tempfile.TemporaryDirectory() as tmp:
            service = make_service(tmp, MutableSource(snapshot), now_ms=4000)[2]
            service.pricing_provider.catalog = threshold_catalog()
            expected, _ = capture_rows(service, snapshot.root)

            with patch.object(service, '_threshold_multiplier', side_effect=AssertionError('per-card sampling')):
                actual, _ = capture_rows(service, snapshot.root, defer_guidance=True)

            self.assertEqual(expected.rows, actual.rows)
            self.assertEqual(expected.context.tokens, actual.context.tokens)
            self.assertEqual(expected.context.text, actual.context.text)
            self.assertEqual(expected.context.severity, actual.context.severity)
            self.assertEqual(expected.context.cached_ccost, actual.context.cached_ccost)
            self.assertEqual('pending', actual.context.guidance_state)
            self.assertIsNone(actual.context.multiplier)
            self.assertEqual(Decimal(2), expected.context.multiplier)

    def test_enrichment_changes_only_current_context_not_card_or_history_proof(self):
        from src.reports.context_guidance import complete_guidance, guidance_semantics
        snapshot = make_uncompacted_snapshot(running=True)
        snapshot = replace(snapshot, invocations=tuple(replace(item,
            tokens=TokenUsage(input=120000, output=0)) if item.invocation_id == 'i_next' else item
            for item in snapshot.invocations))
        with tempfile.TemporaryDirectory() as tmp:
            source = MutableSource(snapshot)
            service = make_service(tmp, source, now_ms=4000)[2]
            catalog = threshold_catalog()
            service.pricing_provider.catalog = catalog
            expected, _ = capture_rows(service, snapshot.root)
            mix = service._comparison_mix[0]
            capture, _ = capture_rows(service, snapshot.root, defer_guidance=True)
            cards = WatchCards(None)
            entry = CardSession(snapshot.root, snapshot.source_revision, 7)
            cards.sessions[snapshot.root.session_id] = entry
            cards.accept(CardResult(snapshot.root.session_id, 7, 'rows', (capture, (), snapshot)), 4000)
            accepted_rows = entry.capture.rows
            proof_before = (entry.verified_generation, cards.evidence_revision,
                entry.capture.observed_at_ms, cards.history.epoch, cards.history.verified_at_ms)
            reads_before = source.load_count

            context = complete_guidance(entry.capture.context, mix, catalog,
                guidance_semantics(service, catalog, catalog))
            entry.capture = replace(entry.capture, context=context)
            card = cards._card(entry, entry.capture.rows[-1], 5000)
            warning = project_live(WatchProjection('Watch', 'fixture', (), active_cards=(card,))).to_json()[
                'active_cards'][0]['session_summary']['context']['warning']

            self.assertEqual(expected.context.multiplier, context.multiplier)
            self.assertEqual('ready', context.guidance_state)
            self.assertEqual('ready', warning['guidance_state'])
            self.assertIn('2x more expensive', warning['display']['warning_cost'])
            self.assertEqual(reads_before, source.load_count)
            self.assertEqual(proof_before, (entry.verified_generation, cards.evidence_revision,
                entry.capture.observed_at_ms, cards.history.epoch, cards.history.verified_at_ms))
            self.assertIs(accepted_rows, entry.capture.rows)
            self.assertEqual(capture.rows, accepted_rows)
            superseded = replace(context, owner_id='new-owner', tokens=None, text='',
                price_threshold=None, multiplier=None, guidance_state='ready')
            self.assertEqual(superseded, complete_guidance(superseded, mix, catalog, context.guidance_signature))
            self.assertIsNone(complete_guidance(capture.context, mix, catalog, 'obsolete').multiplier)

    def test_one_producer_is_charged_as_history_while_active_and_other_history_can_run(self):
        from src.reports.context_guidance import GuidanceBinding, GuidanceScope, guidance_semantics
        from src.watch.card_guidance import CardGuidance
        from src.watch.card_workers import CardRequest, CardWorkers
        source = MutableSource(make_uncompacted_snapshot(running=True))
        entered, release = Event(), Event()
        with tempfile.TemporaryDirectory() as tmp:
            def factory(now):
                return make_service(tmp, source, now_ms=now)[2]
            service = factory(4000)
            def binding(service):
                catalog = service._load_catalog()
                scope = GuidanceScope(('v2', 'synthetic-instance', 'epoch-a'),
                    guidance_semantics(service, catalog, catalog))
                return GuidanceBinding(scope, catalog, catalog)
            workers = CardWorkers(factory)
            guidance = CardGuidance(workers, service, binding=binding)
            cards = WatchCards(workers, guidance=guidance)
            capture, _ = capture_rows(service, source.snapshot.root, defer_guidance=True)
            # This fixture needs guidance regardless of its ordinary model's price tiers.
            capture = replace(capture, context=replace(capture.context, price_threshold=100000,
                model_id='gpt-test', guidance_state='pending'))
            entry = CardSession(source.snapshot.root, source.snapshot.source_revision, 1,
                capture=capture, latest_ms=1, verified_generation=1, refresh_requested=False)
            cards.sessions[entry.root.session_id] = entry
            def collect(*args, **kwargs):
                entered.set()
                if not release.wait(5):
                    raise RuntimeError('fixture release missing')
                from src.reports.context_sample import ContextSample
                return ContextSample((), (), 0)
            try:
                with patch('src.watch.card_guidance.collect_context_sample', side_effect=collect):
                    cards.tick(4000)
                    self.assertTrue(entered.wait(3))
                    future = guidance.attempt.future
                    for _ in range(20):
                        guidance.tick(cards, 4000)
                    self.assertIs(future, guidance.attempt.future)
                    self.assertEqual(1, len(workers.jobs))
                    self.assertEqual(1, len(workers.history_jobs))
                    requests = tuple(CardRequest(replace(entry.root, session_id=f'history-{n}'), 1,
                        historical=True) for n in range(3))
                    with patch.object(workers, '_capture', side_effect=lambda *args: release.wait(5)):
                        accepted = workers.submit_many(requests, 4000)
                        self.assertEqual(('history-0', 'history-1'), accepted)
                        self.assertEqual(3, len(workers.history_jobs))
                        self.assertTrue(workers.submit(replace(entry.root, session_id='active'), 1, 4000))
                        self.assertEqual(4, len(workers.jobs))
                        self.assertFalse(workers.submit(replace(entry.root, session_id='overflow'), 1, 4000))
            finally:
                release.set()
                guidance.cancel()
                workers.close()

    def test_observed_registration_epoch_is_nonsecret_and_survives_same_epoch_reconnect_only(self):
        import json
        from development.tests.fixtures.opencode_v2_service import source_with_current_service
        with source_with_current_service() as (source, server, registration):
            source.refresh_observation_epoch()
            first = source.observation_epoch
            calls = len(server.requests)

            source.refresh_connection()
            source.refresh_observation_epoch()

            self.assertEqual(first, source.observation_epoch)
            self.assertRegex(first, r'^registration-v1:[a-f0-9]{64}$')
            self.assertEqual(calls, len(server.requests))
            value = json.loads(registration.read_text(encoding='utf-8'))
            value['pid'] += 1
            registration.write_text(json.dumps(value), encoding='utf-8')
            source.refresh_observation_epoch()
            self.assertNotEqual(first, source.observation_epoch)
            self.assertEqual(calls, len(server.requests))

    def test_completed_empty_sample_is_ready_and_expiry_and_rollback_cannot_resurrect_it(self):
        from src.reports.context_sample import ContextSample
        with guidance_case() as (cards, owner, workers, _control, clock, _service, _created):
            with patch('src.watch.card_guidance.collect_context_sample', return_value=ContextSample((), (), 0)) as collect:
                cards.tick(4000)
                owner.attempt.future.result(timeout=3)
                cards.tick(4001)
                first = owner.observation
                self.assertIsNotNone(first)
                self.assertEqual(1, collect.call_count)
                context = cards.sessions['root'].capture.context
                self.assertEqual('ready', context.guidance_state)
                self.assertEqual(Decimal(2), context.multiplier)  # Canonical empty-sample sorting mix.
                clock[0] += 899.999
                cards.tick(903999)
                self.assertIs(first, owner.observation)
                self.assertEqual(1, collect.call_count)

                clock[0] += .001
                owner.tick(cards, 904000)

                self.assertIs(first, owner.observation)
                self.assertEqual('refreshing', cards.sessions['root'].capture.context.guidance_state)
                self.assertEqual(Decimal(2), cards.sessions['root'].capture.context.multiplier)
                self.assertTrue(owner.admit(904000))
                owner.attempt.future.result(timeout=3)
                workers.drain()
                owner.tick(cards, 904001)
                second = owner.observation
                self.assertIsNot(first, second)
                owner.tick(cards, 903000)
                owner.tick(cards, 904001)
                self.assertIsNone(owner.observation)
                self.assertEqual(2, collect.call_count)

    def test_slow_valid_guidance_outlives_cache_ttl_and_publishes_honest_dated_value(self):
        from src.application.display import history_tokens
        from src.reports.context_sample import ContextSample
        entered, release = Event(), Event()
        with guidance_case() as (cards, owner, workers, _control, clock, _service, _created):
            proof = cards.evidence_revision
            def slow(*args, **kwargs):
                entered.set()
                release.wait(5)
                return ContextSample((), (), 0)
            with patch('src.watch.card_guidance.collect_context_sample', side_effect=slow):
                cards.tick(4000)
                self.assertTrue(entered.wait(2))
                attempt = owner.attempt
                try:
                    clock[0] += 2 * 86400
                    owner.tick(cards, 4000 + 2 * 86400000)
                    self.assertIs(attempt, owner.attempt)
                    self.assertFalse(attempt.cancelled.is_set())
                    self.assertEqual('pending', cards.sessions['root'].capture.context.guidance_state)
                finally:
                    release.set()
                    attempt.future.result(timeout=3)
                workers.drain()
                owner.tick(cards, 4001 + 2 * 86400000)
            context = cards.sessions['root'].capture.context

            self.assertEqual('refreshing', context.guidance_state)
            self.assertEqual(Decimal(2), context.multiplier)
            self.assertEqual(4000, context.guidance_sample_at_ms)
            text = history_tokens(dict(severity=context.severity, multiplier=context.multiplier,
                guidance_state=context.guidance_state, guidance_sample_at_ms=context.guidance_sample_at_ms), 'UTC')
            self.assertIn('2x more expensive', text['warning_cost'])
            self.assertIn('1970-01-01 00:00; updating', text['warning_cost'])
            self.assertEqual(proof, cards.evidence_revision)
            self.assertTrue(owner.pending, 'expired samples refresh without discarding usable dated guidance')

    def test_failed_guidance_keeps_verified_card_and_automatically_retries_one_coalesced_attempt(self):
        from src.sources.errors import transport_failure
        with guidance_case() as (cards, owner, workers, _control, clock, _service, _created):
            proof = cards.evidence_revision
            with patch('src.watch.card_guidance.collect_context_sample',
                    side_effect=transport_failure(TimeoutError(), phase='messages')):
                cards.tick(4000)
                owner.attempt.future.result(timeout=3)
                cards.tick(4001)
            entry = cards.sessions['root']
            self.assertEqual('unavailable', entry.capture.context.guidance_state)
            self.assertIsNone(entry.source_status.failed_at)
            self.assertEqual(1, entry.verified_generation)
            self.assertFalse(owner.pending)
            clock[0] += 5

            cards.tick(9001)
            owner.attempt.future.result(timeout=3)
            cards.tick(9002)

            self.assertEqual('ready', entry.capture.context.guidance_state)
            self.assertEqual(Decimal(2), entry.capture.context.multiplier)
            self.assertEqual(proof, cards.evidence_revision)
            self.assertFalse(workers.jobs)

    def test_scope_a_b_a_cancellation_keeps_permit_until_read_exits_and_rejects_late_result(self):
        from src.reports.context_sample import ContextSample
        entered, cancelled, release = Event(), Event(), Event()
        with guidance_case() as (cards, owner, workers, control, clock, _service, created):
            factory = workers.factory
            def isolated(now):
                service = factory(now)
                service.source.cancel_reads = cancelled.set
                return service
            workers.factory = isolated
            def blocked(*args, **kwargs):
                entered.set()
                if not release.wait(5):
                    raise RuntimeError('fixture release missing')
                # Deliberately return a late success without cooperating with check().
                return ContextSample((), (), 0)
            try:
                with patch('src.watch.card_guidance.collect_context_sample', side_effect=blocked):
                    cards.tick(4000)
                    self.assertTrue(entered.wait(3))
                    old = owner.attempt
                    control['epoch'] = 'epoch-b'
                    clock[0] += 1
                    owner.tick(cards, 5000)
                    self.assertTrue(cancelled.is_set())
                    self.assertFalse(old.future.done())
                    self.assertEqual(1, len(workers.jobs))
                    self.assertFalse(owner.admit(5000))
                    control['epoch'] = 'epoch-a'
                    clock[0] += 1
                    owner.tick(cards, 6000)
                    release.set()
                    old.future.result(timeout=3)
                    workers.drain()
                    owner.tick(cards, 6001)
                    self.assertIsNone(owner.observation)
                    self.assertIsNone(owner.attempt)
                    self.assertTrue(owner.pending)
                    self.assertEqual(2, len(created))
            finally:
                release.set()

    def test_price_change_requalifies_compact_costs_and_threshold_without_rehydrating(self):
        from src.pricing.catalog import PricingCatalog
        from src.reports.context_guidance import complete_guidance
        with guidance_case() as (cards, owner, workers, control, clock, service, created):
            cards.tick(4000)
            owner.attempt.future.result(timeout=3)
            cards.tick(4001)
            entry = cards.sessions['root']
            original = entry.capture.context
            model = control['catalog'].models[0]
            # Same model, changed tier boundary and rates. All price-derived fields must change coherently.
            tiers = (replace(model.tiers[0], max_input_tokens=200000,
                per_million_input=Decimal(3), per_million_cache_read=Decimal('.3')),
                replace(model.tiers[1], min_input_tokens=200001,
                    per_million_input=Decimal(9), per_million_cache_read=Decimal('.9')))
            control['catalog'] = PricingCatalog((replace(model, tiers=tiers),))
            reads_before = sum(value.source.load_count for value in created)
            proof_before = (entry.verified_generation, cards.evidence_revision, entry.capture.observed_at_ms)
            clock[0] += 1

            owner.tick(cards, 5000)

            current = entry.capture.context
            self.assertEqual('none', current.severity)  # 120K is below 75% of the new 200K boundary.
            self.assertEqual(0, current.price_threshold)
            self.assertIsNone(current.multiplier)
            self.assertNotEqual(original.cached_ccost, current.cached_ccost)
            self.assertEqual(original.price_basis.costs(control['catalog']),
                (current.cached_ccost, current.fresh_ccost))
            self.assertEqual(reads_before, sum(value.source.load_count for value in created))
            self.assertEqual(proof_before, (entry.verified_generation, cards.evidence_revision,
                entry.capture.observed_at_ms))
            # A delayed completion using the old semantics cannot restore the old tier warning.
            self.assertEqual(current, complete_guidance(current, (0, 0, 0, 0, 0),
                control['catalog'], original.guidance_signature))

    def test_active_demand_promotes_existing_unadmitted_work_without_queuing_or_stealing_reservation(self):
        from src.reports.context_sample import ContextSample
        entered, release = Event(), Event()
        with guidance_case() as (cards, owner, workers, _control, _clock, _service, _created):
            # A deterministic occupied-permit seam; actual concurrent accounting is tested separately.
            occupied = {f'occupied-{n}': Future() for n in range(4)}
            workers.jobs.update(occupied)
            workers.history_jobs.update(tuple(occupied)[:3])
            entry = cards.sessions['root']
            terminal = replace(entry.capture, rows=tuple(replace(row, in_progress=False,
                completed_at_ms=3000) for row in entry.capture.rows))
            entry.capture = terminal
            def blocked(*args, **kwargs):
                entered.set()
                if not release.wait(5):
                    raise RuntimeError('fixture release missing')
                return ContextSample((), (), 0)
            try:
                with patch('src.watch.card_guidance.collect_context_sample', side_effect=blocked):
                    cards.tick(4000)
                    self.assertTrue(owner.pending)
                    self.assertFalse(owner.active_demand)
                    self.assertIsNone(owner.attempt)
                    entry.capture = replace(terminal, rows=(replace(terminal.rows[-1], in_progress=True),))
                    owner.tick(cards, 4001)
                    self.assertTrue(owner.active_demand)
                    self.assertIsNone(owner.attempt)
                    del workers.jobs['occupied-0']
                    workers.history_jobs.remove('occupied-0')

                    cards.tick(4002)

                    self.assertTrue(entered.wait(3))
                    self.assertIsNotNone(owner.attempt)
                    self.assertEqual(4, len(workers.jobs))
                    self.assertEqual(3, len(workers.history_jobs))
            finally:
                release.set()
                for key, future in occupied.items():
                    workers.jobs.pop(key, None)
                    workers.history_jobs.discard(key)
                    future.cancel()

    def test_cancellation_during_factory_setup_closes_late_source_and_never_releases_permit_early(self):
        entered, release, cancelled, closed = Event(), Event(), Event(), Event()
        with guidance_case() as (cards, owner, workers, _control, _clock, _service, _created):
            original = workers.factory
            def factory(now):
                entered.set()
                if not release.wait(5):
                    raise RuntimeError('fixture release missing')
                service = original(now)
                service.source.cancel_reads = cancelled.set
                service.source.close_reads = closed.set
                return service
            workers.factory = factory
            try:
                cards.tick(4000)
                self.assertTrue(entered.wait(3))
                attempt = owner.attempt

                owner.cancel()

                self.assertFalse(attempt.future.done())
                self.assertEqual(1, len(workers.jobs))
                release.set()
                self.assertIsNone(attempt.future.result(timeout=3))
                self.assertTrue(cancelled.is_set())
                self.assertTrue(closed.is_set())
                workers.drain()
                self.assertFalse(workers.jobs)
                self.assertIsNone(owner.observation)
            finally:
                release.set()

    def test_late_guidance_cannot_restore_a_superseded_hidden_compaction_anchor(self):
        from src.reports.context_sample import ContextSample
        entered, release = Event(), Event()
        with guidance_case() as (cards, owner, workers, _control, _clock, _service, _created):
            def blocked(*args, **kwargs):
                entered.set()
                if not release.wait(5):
                    raise RuntimeError('fixture release missing')
                return ContextSample((), (), 0)
            try:
                with patch('src.watch.card_guidance.collect_context_sample', side_effect=blocked):
                    cards.tick(4000)
                    self.assertTrue(entered.wait(3))
                    entry = cards.sessions['root']
                    context = replace(entry.capture.context, owner_id='after-hidden-compaction',
                        tokens=None, text='', severity='none', multiplier=None, price_threshold=0,
                        price_basis=None, cached_ccost=None, fresh_ccost=None, guidance_state='ready')
                    entry.capture = replace(entry.capture, context=context, observed_at_ms=5000)
                    proof = (entry.verified_generation, cards.evidence_revision, entry.capture.observed_at_ms)
                    release.set()
                    owner.attempt.future.result(timeout=3)

                    cards.tick(5001)

                    self.assertEqual(context, entry.capture.context)
                    self.assertEqual(proof, (entry.verified_generation, cards.evidence_revision,
                        entry.capture.observed_at_ms))
            finally:
                release.set()

    def test_binding_reads_only_local_registration_and_cached_prices_and_rejects_unknown_epoch(self):
        from development.tests.fixtures.opencode_v2_service import source_with_current_service
        from src.reports.context_guidance import cached_guidance_binding
        with source_with_current_service() as (source, server, registration), tempfile.TemporaryDirectory() as tmp:
            service = make_service(tmp, source)[2]
            catalog = threshold_catalog()
            service.pricing_provider.cached_catalog = lambda: catalog
            calls = len(server.requests)
            with patch.object(service.pricing_provider, 'get_catalog', side_effect=AssertionError('network prices')):
                binding = cached_guidance_binding(service)
                self.assertIsNotNone(binding)
                self.assertEqual(catalog.analysis_signature, binding.catalog.analysis_signature)
                self.assertEqual(calls, len(server.requests))
                registration.unlink()
                owner_binding = None
                try:
                    owner_binding = cached_guidance_binding(service)
                except Exception as error:
                    from src.sources.errors import SourceError
                    self.assertIsInstance(error, SourceError)
                self.assertIsNone(owner_binding)
                self.assertIsNone(source.observation_epoch)


if __name__ == '__main__':
    unittest.main()
