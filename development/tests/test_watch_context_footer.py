"""Card continuation warnings never come from stale visible prompt-table rows."""
from dataclasses import replace
from decimal import Decimal
import tempfile
import unittest

from development.tests.fixtures.pricing_catalog import threshold_catalog
from development.tests.fixtures.session_snapshots import make_snapshot, make_uncompacted_snapshot, moved_location
from development.tests.fixtures.watch_runtime import MutableSource, make_service
from src.analysis.context import PriceWarningSeverity
from src.application.live_projection import project_live
from src.domain import TokenUsage
from src.reports.prompt_rows import PromptRowProjector
from src.reports.watch_capture import capture_rows
from src.reports.watch_context import card_context
from src.watch.cards import CardSession, WatchCards
from src.watch.card_workers import CardResult
from src.watch.models import WatchProjection


class WatchContextFooterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = MutableSource(make_uncompacted_snapshot(running=True))
        _, _, self.service, _ = make_service(self.tmp.name, self.source, now_ms=4000)
        self.service.pricing_provider.catalog = threshold_catalog()

    def capture(self, tokens, *, snapshot=None, approach=75):
        snapshot = snapshot or make_uncompacted_snapshot(running=True)
        self.source.snapshot = replace(snapshot, invocations=tuple(
            replace(item, tokens=TokenUsage(input=tokens, output=0)) if item.invocation_id == 'i_next' else item
            for item in snapshot.invocations), source_revision=str(tokens))
        self.service.config['thresholds']['nextIctxPriceThresholdWarningPercent'] = approach
        self.service.invalidate_roots(('root',))
        return capture_rows(self.service, self.source.snapshot.root)

    def test_exact_boundary_running_watch_fields_disabled_and_missing_multiplier(self):
        for tokens, approach, severity in ((74000, 75, 'none'), (75001, 75, 'approaching'),
                (100000, 75, 'approaching'), (100001, 75, 'exceeded'), (80000, 0, 'none'), (120000, 0, 'exceeded')):
            with self.subTest(tokens=tokens, approach=approach):
                capture, _ = self.capture(tokens, approach=approach)
                self.assertEqual(severity, capture.context.severity)
                self.assertEqual(tokens, capture.context.tokens)
                entry = CardSession(self.source.snapshot.root, 'revision', 1, capture=capture, state='observed')
                card = WatchCards(None)._card(entry, capture.rows[-1], 4000)
                cell = project_live(WatchProjection('Watch', 'fixture', (), active_cards=(card,))).to_json()['active_cards'][0]['session_summary']['context']
                self.assertEqual(severity, cell['warning']['severity'])
                self.assertEqual(tokens, cell['watch_next_context_tokens'])
                if severity != 'none':
                    self.assertEqual(Decimal(2), capture.context.multiplier)
        self.service._threshold_multiplier = lambda model, boundary: None
        capture, _ = self.capture(120000)
        self.assertIsNone(capture.context.multiplier)
        self.assertIsNotNone(capture.context.cached_ccost)

    def test_hidden_compaction_removes_downgrades_and_invalidates_old_guidance(self):
        capture, item = self.capture(120000, snapshot=make_snapshot(running=True))
        for tokens, severity in ((20000, 'none'), (80000, 'approaching'), (120000, 'exceeded'), (None, 'none')):
            with self.subTest(tokens=tokens):
                compact = replace(item.bundle.compactions[-1], result_context_tokens=tokens)
                bundle = replace(item.bundle, compactions=(compact,))
                projector = PromptRowProjector(snapshot=item.snapshot, bundle=bundle,
                    catalog=self.service._load_catalog(), config=self.service.config)
                guidance = card_context(projector, 'root', lambda *_: None)
                self.assertEqual(severity, guidance.severity)
                self.assertEqual(tokens, guidance.tokens)
                self.assertEqual('u_next', guidance.owner_id)
                current = replace(capture, context=guidance)
                entry = CardSession(item.session, 'revision', 1, capture=current, state='observed')
                card = WatchCards(None)._card(entry, current.rows[-1], 4000)
                cell = project_live(WatchProjection('Watch', 'fixture', (), history_cards=(card,))).to_json()['history_cards'][0]['session_summary']['context']
                self.assertEqual(tokens, cell['watch_next_context_tokens'])
                self.assertEqual(severity, cell['warning']['severity'])

    def test_context_boundary_never_revives_historical_row_guidance(self):
        snapshot = moved_location(make_uncompacted_snapshot(running=False), 3500)
        capture, _ = self.capture(120000, snapshot=snapshot)
        self.assertEqual(PriceWarningSeverity.NONE, capture.context.severity)
        self.assertIsNone(capture.context.tokens)

    def test_concurrent_cards_share_valid_session_continuation_and_watch_multiplier(self):
        capture, item = self.capture(120000)
        focal = capture.rows[-1]
        older = replace(focal, event_id='older', at_ms=focal.at_ms - 1)
        capture = replace(capture, rows=(older, focal))
        cards = WatchCards(None)
        entry = CardSession(item.session, 'revision', 1, capture=capture, state='observed')
        current = cards._card(entry, focal, 4000)
        superseded = cards._card(entry, older, 4000)
        historical = cards._card(entry, None, 4000)
        self.assertEqual(current.session_context, historical.session_context)
        self.assertEqual(current.session_context, superseded.session_context)
        wire = project_live(WatchProjection('Watch', 'fixture', (), active_cards=(current,))).to_json()
        self.assertIn('2x more expensive', wire['active_cards'][0]['session_summary']['context']['warning']['display']['warning_cost'])
        self.assertNotIn('context_warning', wire['active_cards'][0]['rows'][0])
        cell = wire['active_cards'][0]['session_summary']['context']
        self.assertEqual('u_next', cell['warning']['owner_id'])
        self.assertEqual('exceeded', cell['warning']['severity'])
        self.assertEqual(120000, cell['watch_next_context_tokens'])
        multi = replace(current, rows=superseded.rows + current.rows)
        rows = project_live(WatchProjection('Watch', 'fixture', (), active_cards=(multi,))).to_json()['active_cards'][0]['rows']
        self.assertTrue(all('context_cell' not in row for row in rows))
        self.assertIn('incoming_context_tokens', rows[0]['prompt'])
        entry.state = 'unavailable'
        self.assertEqual(120000, cards._card(entry, focal, 4000).session_context.tokens)

    def test_out_of_order_capture_cannot_revive_pre_compaction_cell_warning(self):
        capture, item = self.capture(120000)
        cards = WatchCards(None)
        entry = CardSession(item.session, 'revision', 7, capture=capture, state='observed')
        cards.sessions[capture.session_id] = entry
        compacted = replace(capture, observed_at_ms=capture.observed_at_ms + 1,
            context=replace(capture.context, tokens=None, text='', severity=PriceWarningSeverity.NONE,
                context_state='invalidated'))

        cards.accept(CardResult(capture.session_id, 7, 'rows', (compacted, (), None)), 5000)
        cards.accept(CardResult(capture.session_id, 7, 'rows', (capture, (), None)), 5001)
        cards.accept(CardResult(capture.session_id, 6, 'rows', (capture, (), None)), 5002)
        card = cards._card(entry, entry.capture.rows[-1], 5002)
        wire = project_live(WatchProjection('Watch', 'fixture', (), active_cards=(card,))).to_json()

        cell = wire['active_cards'][0]['session_summary']['context']
        self.assertIsNone(cell['watch_next_context_tokens'])
        self.assertEqual('none', cell['warning']['severity'])


if __name__ == '__main__':
    unittest.main()
