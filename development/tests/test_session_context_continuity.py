"""Source-shaped session observations across missing prompt handoff publications."""
from dataclasses import replace
import json
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace
import unittest

from development.tests.fixtures.mini_context import handoff_snapshot, handoff_capture, handoff_frame
from development.tests.fixtures.watch_summary import summary_watch
from development.tests.fixtures.pricing_catalog import catalog
from src.analysis import analyze_snapshot
from src.application.live_projection import project_live
from src.domain import ActiveContext, EventKind, NormalizedEvent, TerminalEvidence, TerminalOutcome
from src.reports.sampling import AnalyzedRoot
from src.reports.session_summary import context_fields
from src.reports.watch_context import retain_session_context
from src.watch.card_workers import CardResult
from src.watch.cards import WatchCards
from src.watch.observers import CatalogObservation


class SessionContextContinuityTests(unittest.TestCase):
    def test_source_shaped_missing_handoff_sequence_reaches_renderer(self):
        replay = []
        for index, phase in enumerate(('prior', 'early', 'pending', 'fresh')):
            wire = project_live(replace(handoff_frame(summary_watch(), phase), now_ms=3000 + index)).to_json()
            replay.append(dict(state='running', view=wire))
        self.assertIsNone(replay[1]['view']['active_cards'][0]['context_handoff'])
        self.assertIsNone(replay[1]['view']['active_cards'][0]['rows'][0]['live_context']['watch_next_context_tokens'])
        self.assertEqual([230000, 230000, 230000, 235000], [item['view']['active_cards'][0]
            ['session_summary']['context']['watch_next_context_tokens'] for item in replay])
        payload = dict(replay[0], replay=replay)
        result = subprocess.run([shutil.which('node'), 'development/tests/integration/mini_watch.cjs'],
            cwd=Path(__file__).resolve().parents[2], input=json.dumps(payload), text=True,
            encoding='utf-8', capture_output=True, timeout=15)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(['230k', '230k', '230k', '235k'], json.loads(result.stdout))

    def test_fresh_source_summary_and_catalog_share_pending_and_real_invalidation(self):
        for phase, expected, status in (('early', 230000, 'pending'), ('pending', 230000, 'pending'),
                ('unverified', 230000, 'pending'), ('fresh', 235000, 'ready-current'),
                ('reset', None, 'invalidated'), ('model', None, 'invalidated'),
                ('move', None, 'invalidated'), ('inactive', None, 'invalidated')):
            snapshot = handoff_snapshot(phase)
            capture = handoff_capture(snapshot)
            with self.subTest(phase=phase):
                self.assertEqual((expected, status), (capture.context.tokens, capture.context.context_state))
                if snapshot.complete:
                    item = AnalyzedRoot(snapshot.root, analyze_snapshot(snapshot, now_ms=2500, tracked_provider=None), False, snapshot)
                    self.assertEqual(expected, context_fields(item, catalog()).get('context_tokens'))

    def test_stop_or_error_after_valid_context_does_not_retire_session(self):
        for outcome in (TerminalOutcome.CANCELLATION, TerminalOutcome.FAILURE):
            snapshot = handoff_snapshot('pending')
            messages = tuple(replace(item, termination=TerminalEvidence(1200, outcome, 'user'),
                error_name='MessageAbortedError' if outcome is TerminalOutcome.CANCELLATION else 'APIError')
                if item.message_id == 'a0' else item for item in snapshot.messages)
            capture = handoff_capture(replace(snapshot, messages=messages))
            self.assertEqual(230000, capture.context.tokens)
            self.assertEqual('pending', capture.context.context_state)
            self.assertEqual('', capture.context.text, 'unknown current model cannot inherit prior price warning')

    def test_pending_memory_is_scoped_and_source_membership_can_invalidate(self):
        previous = handoff_capture(handoff_snapshot('fresh')).context
        pending = replace(previous, owner_id='third', tokens=None, context_state='pending')
        self.assertEqual(235000, retain_session_context(pending, previous).tokens)
        for field, value in (('context_scope', 'other-source'), ('context_epoch', 'compaction'),
                ('context_model', 'other'), ('context_provider', 'other'), ('context_state', 'invalidated')):
            with self.subTest(field=field):
                self.assertIsNone(retain_session_context(replace(pending, **{field: value}), previous).tokens)
        snapshot = replace(handoff_snapshot('fresh'), active_contexts=(ActiveContext('root', ('third',)),))
        invalid = retain_session_context(pending, previous, snapshot)
        self.assertEqual((None, 'invalidated'), (invalid.tokens, invalid.context_state))

    def test_card_owner_retains_partial_unknown_without_requiring_a_previous_dom(self):
        cards = WatchCards(SimpleNamespace())
        for phase in ('prior', 'early', 'pending', 'fresh'):
            snapshot = handoff_snapshot(phase)
            capture = handoff_capture(snapshot)
            cards.catalog(CatalogObservation((snapshot.root,), (snapshot.root,), {'root': 'root'},
                {'root': snapshot.source_revision}, frozenset({'root'})))
            entry = cards.sessions['root']
            cards.accept(CardResult('root', entry.generation, 'rows', (capture, (), snapshot)), 2500)
            self.assertEqual(235000 if phase == 'fresh' else 230000, entry.capture.context.tokens)
        # Genuine source removal retires the owner even if the same ID reappears.
        cards.catalog(CatalogObservation((), (), {}, {}, frozenset()))
        self.assertEqual({}, cards.sessions)

    def test_many_pending_prompts_do_not_require_predecessor_in_bounded_rows(self):
        snapshot = handoff_snapshot('pending')
        user, assistant = snapshot.messages[-2:]
        extra = tuple(replace(message, message_id=f'{message.message_id}-{index}',
            parent_message_id=f'next-{index}' if message is assistant else None,
            created_at_ms=2200 + index * 100, completed_at_ms=None,
            termination=TerminalEvidence(2210 + index * 100, TerminalOutcome.CANCELLATION, 'user')
                if message is assistant and index < 8 else None)
            for index in range(1, 9) for message in (user, assistant))
        events = tuple(NormalizedEvent(f'next-{index}', 'root', EventKind.USER_PROMPT,
            2200 + index * 100, user.provenance, 'Continue') for index in range(1, 9))
        messages = tuple(replace(item, termination=TerminalEvidence(2250, TerminalOutcome.CANCELLATION, 'user'))
            if item is assistant else item for item in snapshot.messages) + extra
        root = replace(snapshot.root, active=False)
        snapshot = replace(snapshot, root=root, sessions=(root,), messages=messages, events=snapshot.events + events,
            active_contexts=(ActiveContext('root', tuple(item.message_id for item in messages)),))
        capture = handoff_capture(snapshot, now_ms=3200)
        self.assertEqual(230000, capture.context.tokens)
        self.assertEqual('pending', capture.context.context_state)
        self.assertNotIn('u', [row.event_id for row in capture.rows])
        self.assertEqual('next-8', capture.context.owner_id)

    def test_explicit_compaction_and_source_instance_are_not_pending_aliases(self):
        snapshot = handoff_snapshot('pending')
        user = snapshot.messages[-2]
        compaction = replace(user, message_id='compact', created_at_ms=1900,
            parts=(replace(user.parts[0], kind='compaction', data={}),))
        snapshot = replace(snapshot, messages=snapshot.messages + (compaction,),
            parts=snapshot.parts + compaction.parts,
            events=snapshot.events + (NormalizedEvent('compact', 'root', EventKind.COMPACTION,
                1900, user.provenance, ''),))
        context = handoff_capture(snapshot).context
        self.assertEqual((None, 'invalidated'), (context.tokens, context.context_state))
        prior = handoff_snapshot('prior')
        before = handoff_capture(prior).context
        root = replace(prior.root, provenance=replace(prior.root.provenance, source_instance='replacement'))
        after = handoff_capture(replace(prior, root=root, sessions=(root,))).context
        self.assertNotEqual(before.context_scope, after.context_scope)

    def test_supported_anchor_after_an_older_compaction_can_still_carry(self):
        snapshot = handoff_snapshot('pending')
        event = NormalizedEvent('old-compaction', 'root', EventKind.COMPACTION, 500,
            snapshot.root.provenance, '')
        capture = handoff_capture(replace(snapshot, events=(event,) + snapshot.events))
        self.assertEqual((230000, 'pending'), (capture.context.tokens, capture.context.context_state))


if __name__ == '__main__':
    unittest.main()
