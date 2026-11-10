"""Synthetic persisted new-prompt transition through canonical capture and cards."""
from dataclasses import replace
from types import SimpleNamespace

from development.tests.fixtures.context_deltas import context_snapshot
from development.tests.fixtures.pricing_catalog import catalog
from development.tests.fixtures.session_snapshots import prov
from src.analysis import analyze_snapshot
from src.domain import ActiveContext, ContextBoundary, EventKind, NormalizedEvent
from src.reports.watch_capture import capture_rows
from src.sources.opencode_v2_normalization import normalize_invocations, normalize_message_bundle
from src.watch.card_workers import CardResult
from src.watch.cards import WatchCards
from src.watch.observers import CatalogObservation


def handoff_snapshot(phase='pending'):
    snapshot = context_snapshot(incoming=160_000, outputs=(12_000,), active=True)
    if phase == 'prior':
        return snapshot
    raw = [dict(info=dict(id='next', sessionID='root', role='user', time={'created': 2000}),
                parts=[dict(id='next-text', type='text', text='Continue')]),
           dict(info=dict(id='next-assistant', sessionID='root', parentID='next', role='assistant',
                          time={'created': 2100}), parts=[])]
    if phase in {'fresh', 'tools', 'model', 'unverified', 'partial-usage'}:
        raw[-1]['info'].update(providerID='github-copilot', modelID='other' if phase == 'model' else 'gpt-test')
    if phase in {'fresh', 'tools', 'partial-usage'}:
        raw[-1]['info'].update(time={'created': 2100, 'completed': 2200}, finish='tool-calls',
            tokens={'input': 172_000, 'output': 3000, 'cache': {'read': 0, 'write': 0}})
        if phase == 'partial-usage':
            del raw[-1]['info']['tokens']['input']
    provenance = lambda session, event=None: prov(session, event, 'v2')
    messages = snapshot.messages + tuple(normalize_message_bundle(item, provenance)[0] for item in raw)
    root = replace(snapshot.root, active=phase != 'unverified')
    return replace(snapshot, root=root, sessions=(root,), messages=messages,
        parts=tuple(part for message in messages for part in message.parts),
        invocations=tuple(item for message in messages for item in normalize_invocations(message, provenance)),
        events=snapshot.events + (NormalizedEvent('next', 'root', EventKind.USER_PROMPT, 2000,
            provenance('root', 'next'), 'Continue'),),
        active_contexts=(ActiveContext('root', tuple(message.message_id for message in messages)
            if phase != 'inactive' else ('next', 'next-assistant')),),
        context_boundaries=(ContextBoundary('root', phase, 1900),)
            if phase in {'reset', 'model-selection', 'move'} else (),
        complete=phase != 'incomplete', source_revision='handoff-' + phase)


def handoff_capture(snapshot):
    service = SimpleNamespace(now_ms=2300, config={}, _load_catalog=catalog,
        _analyze_snapshot=lambda value: analyze_snapshot(value, now_ms=2300, tracked_provider=None),
        _threshold_multiplier=None)
    return capture_rows(service, snapshot.root, fresh=snapshot)[0]


def handoff_frame(frame, phase):
    snapshot = handoff_snapshot(phase)
    capture = handoff_capture(snapshot)
    cards = WatchCards(SimpleNamespace())
    root = snapshot.root
    cards.catalog(CatalogObservation((root,), (root,), {'root': 'root'},
        {'root': snapshot.source_revision}, frozenset({'root'})))
    cards.accept(CardResult('root', cards.sessions['root'].generation, 'rows', (capture, (), snapshot)), 2300)
    if phase == 'prior':
        cards.sessions['root'].terminals['u'] = 2300
    active, history, state = cards.project(2300)
    return replace(frame, active_cards=active, history_cards=history, cards_state=state,
        rows=tuple(row for card in active for row in card.rows))
