"""Sanitized read-only comparison of an observed Watch row with a CLI report."""
from decimal import Decimal
import json
import time

from src.reports import ReportKind, ReportRequest


def observe_prompt_cost(get, cookie, owner):
    deadline = time.monotonic() + 90
    keys = ("ccost", "incoming_context_ccost", "extra_ccost")
    while time.monotonic() < deadline:
        state, _ = get('/api/live', cookie=cookie)
        view = state['values'].get('live', {}).get('view') or {}
        for card in view.get('history_cards', []):
            for item in card['rows']:
                row = item['prompt']
                if row['in_progress'] or row['unresolved_cost'] or any(row[key] is None for key in keys):
                    continue
                service = owner.coordinator.history_factory(int(time.time() * 1000))
                try:
                    report = service.build(ReportRequest(ReportKind.SESSION, card['session_id']))
                    cli = next((prompt for block in report.prompt_blocks for prompt in block.rows
                        if prompt.event_id == row['event_id']), None)
                    if cli is None:
                        continue
                    latest, _ = get('/api/live', cookie=cookie)
                    current = (latest['values'].get('live', {}).get('view') or {}).get('history_cards', [])
                    retained = next((entry['prompt'] for value in current for entry in value['rows']
                        if value['session_id'] == card['session_id'] and entry['prompt']['event_id'] == row['event_id']), None)
                    if retained is None or any(retained[key] != row[key] for key in keys):
                        continue
                    assert all(Decimal(row[key]) == getattr(cli, key) for key in keys)
                    assert cli.incoming_context_ccost + cli.extra_ccost == cli.ccost
                    detail = row.get('cost_detail', {})
                    parts = detail.get('parts', [])
                    if not parts:
                        continue
                    assert row['linked_agent_count'] == cli.linked_agent_count
                    assert sum((p.known_ccost for p in cli.cost_parts), Decimal(0)) == cli.ccost
                    for observed in parts:
                        expected = [p for p in cli.cost_parts if p.agent == observed['agent'] and (
                            'main' if p.agent == 0 else 'subagents', p.provider_id, p.model_id, p.variant, p.price_tier) == (
                            observed['role'], observed['provider_id'], observed['model_id'], observed['variant'], observed['price_tier'])]
                        assert expected
                        assert Decimal(observed['known_ccost']) == sum(p.known_ccost for p in expected)
                        assert observed['calls'] == sum(p.calls for p in expected)
                        for index, amount in enumerate(observed['categories']):
                            values = [p.categories[index] for p in expected]
                            assert (None if amount is None else Decimal(amount)) == (
                                None if None in values else sum(values))
                        if all(v is not None for v in observed['categories']):
                            assert sum(Decimal(v) for v in observed['categories']) == Decimal(observed['known_ccost'])
                    print(json.dumps(dict(prompt_cost='ok', canonical_cli_raw_parity=True,
                        components_reconcile=True, detail_groups=len(parts),
                        detail_categories_reconcile=True, linked_agents=cli.linked_agent_count,
                        calls=cli.calls, model_calls_started_by_probe=0)))
                    return
                finally:
                    service.close_accounts()
        time.sleep(.25)
    raise RuntimeError('probe_prompt_cost_timeout')
