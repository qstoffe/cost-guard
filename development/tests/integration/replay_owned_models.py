"""Offline replay of explicitly supplied, owned Claude model acceptance captures.

Never enumerates native sessions or submits inference. Output is sanitized scalars;
observer metadata is an independent comparison, never a production model override.
"""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.analysis import analyze_snapshot
from src.application.display import with_display
from src.application.projection import prompt, project
from development.tests.fixtures.claude_alias import desktop_service, snapshot as synthetic_snapshot, catalog
from development.tests.fixtures.session_snapshots import make_snapshot
from src.reports import ReportKind, ReportRequest
from src.domain import MessageRole, ModelRef, NormalizedSession, Provenance, SessionCapabilities, SessionSnapshot
from src.pricing.catalog import PricingCatalog
from src.pricing.github_copilot import _default_fetch_text, DOCS_API_BODY, PRICING_ARTICLE_PATH, parse_pricing_markdown
from src.reports.prompt_rows import PromptRowProjector
from src.sources.opencode_v2_events import normalize_event
from src.sources.opencode_v2_model_identity import DesktopModelCatalog
from src.sources.opencode_v2_normalization import normalize_invocations, normalize_message_bundle
from src.sources.opencode_v2_wire import normalize_message_items


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def replay(directory, prices):
    models = read(directory / 'models.json')
    providers = read(directory / 'providers-replay.json')
    assert providers['location'] == models['location'], 'catalog_location_mismatch'
    location = models['location']['directory']
    class CatalogReplay:
        def json(self, route, *, query, **_kwargs):
            assert query == {'location[directory]': location}
            return providers if route == '/api/provider' else models
    identities = DesktopModelCatalog(lambda: CatalogReplay())
    observer = [json.loads(line) for line in (directory / 'evidence.jsonl').read_text().splitlines()]
    matrix, browser_rows = [], []
    for model in models['data']:
        if model['providerID'] != 'claude-agent' or not model['enabled'] or model['status'] == 'deprecated':
            continue
        selected = model['id']
        assert Path(selected).name == selected
        path = directory / (selected + '-messages.json')
        if not path.exists():
            matrix.append(dict(selected=selected, state='NOT RUN'))
            continue
        native = read(directory / (selected + '-session.json'))['data']
        assert native['location']['directory'] == location
        provenance = lambda sid, eid=None: Provenance('opencode', 'v2', 'owned-capture', sid, eid)
        bundles, _shape = normalize_message_items(read(path)['data'], session=native)
        messages, latest = [], None
        for bundle in sorted(bundles, key=lambda b: b['info']['time']['created']):
            message, _parts = normalize_message_bundle(bundle, provenance)
            if message.role is MessageRole.USER:
                latest = message.message_id
            elif message.role is MessageRole.ASSISTANT:
                message = replace(message, model=identities.resolve(message.model, location),
                    parent_message_id=message.parent_message_id or latest)
            messages.append(message)
        root = NormalizedSession(native['id'], 'Owned replay', native['time']['created'],
            max(m.completed_at_ms or m.created_at_ms for m in messages), provenance(native['id']), SessionCapabilities())
        invocations = tuple(i for m in messages for i in normalize_invocations(m, provenance))
        snapshot = SessionSnapshot(root, (root,), tuple(messages), tuple(p for m in messages for p in m.parts),
            tuple(e for m in messages if (e := normalize_event(m)) is not None), invocations, 'saved-owned-replay')
        bundle = analyze_snapshot(snapshot, tracked_provider=None, now_ms=root.updated_at_ms + 1)
        record = bundle.prompts[0]
        row = PromptRowProjector(snapshot=snapshot, bundle=bundle, catalog=prices, config={}).prompt(record)
        assert all(i.model.provider == 'claude-agent' and i.model.recorded_model == selected for i in invocations)
        tokens = [i.tokens for i in invocations]
        finishes = [e for e in observer if e.get('id') == selected and e['kind'] == 'finish']
        executed = sorted({e['modelId'] for e in observer if e.get('id') == selected and e['kind'] == 'response'})
        production = sorted({i.model.model for i in invocations})
        if finishes:
            assert row.calls == 1 and len(finishes) == 1
            expected = finishes[0]['usage']
            assert (tokens[0].input, tokens[0].cache_read, tokens[0].cache_write, tokens[0].output) == (
                expected['inputTokens']['noCache'], expected['inputTokens']['cacheRead'],
                expected['inputTokens']['cacheWrite'], expected['outputTokens']['total'])
            assert not row.unresolved_cost and row.ccost > 0
        else:
            assert all(not token.known_fields for token in tokens), 'failed_usage_must_remain_unknown'
            assert not invocations or row.unresolved_cost
        safe = replace(row, event_id=selected, at_ms=1000, preview='', prompt_number=1)
        wire = with_display(prompt(safe, details=True)).to_json()
        assert 'claude-agent/' + selected in wire['display']['model_detail_help'], (selected, wire['display']['model_detail_help'], row.recorded_selections,
            [(m.role.value, m.session_id == record.session_id, m.parent_message_id == record.prompt_id) for m in messages])
        browser_rows.append(wire)
        matrix.append(dict(selected=selected, state='RUN' if finishes else 'FAIL',
            reconciliation='PASS (saved-request replay)' if finishes else 'missing usage remains unknown',
            observed_executed=executed, production_model=production, label=row.watch_model,
            reference_ccost=str(row.ccost) if finishes else None,
            observed_aggregate_ccost=str(row.ccost), observed_requests=row.calls,
            catalog_estimate=any(i.model.resolution is not None for i in invocations),
            usage=[[t.input, t.cache_read, t.cache_write, t.output] for t in tokens] if finishes else None))
    return dict(matrix=matrix, browser_rows=browser_rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('captures', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    markdown = _default_fetch_text(DOCS_API_BODY + PRICING_ARTICLE_PATH, 20)
    prices = PricingCatalog(parse_pricing_markdown(markdown), retrieved_at_ms=int(time.time() * 1000),
        source_revision='fresh-public-reference')
    result = replay(args.captures, prices)
    test = unittest.TestCase()
    try:
        fixture = desktop_service(test, snapshots=(synthetic_snapshot(),
            synthetic_snapshot(1, 'claude-sonnet-5-5', 'github-copilot')))
        result['synthetic_views'] = {kind.value: project(fixture.build(ReportRequest(kind,
            **({'session_id': 'root-0000'} if kind is ReportKind.SESSION else {}))), prompt_details=True).to_json()
            for kind in (ReportKind.SESSIONS, ReportKind.SESSION, ReportKind.COMPARISONS, ReportKind.AI_STATS)}
        saved = make_snapshot()
        saved = replace(saved, invocations=tuple(replace(item,
            model=ModelRef('openrouter', 'vendor/future-release') if item.summary else
                ModelRef('github-copilot' if item.session_id == 'child' else 'claude-agent', 'claude-sonnet-5-5'))
            for item in saved.invocations))
        bundle = analyze_snapshot(saved, tracked_provider=None)
        projector = PromptRowProjector(snapshot=saved, bundle=bundle, catalog=catalog(), config={})
        result['synthetic_prompt_cases'] = [with_display(prompt(row, details=True)).to_json() for row in (
            projector.prompt(bundle.prompts[0]), projector.compaction(bundle.compactions[0], 3))]
    finally:
        test.doCleanups()
    result['limits'] = 'Owned saved-request replay, not historical recovery, live UI acquisition or full-catalog PASS.'
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in result.items()
        if key not in ('browser_rows', 'synthetic_views', 'synthetic_prompt_cases')}))


if __name__ == '__main__':
    main()
