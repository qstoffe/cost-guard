"""Sanitized read-only real-source full-session/cache parity observations."""
import json
import time

from src.analysis.session_cost import reconcile_session_cost
from src.reports.sampling import AnalyzedRoot


def observe_session_cost(get, cookie, owner):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        state, _ = get('/api/live', cookie=cookie)
        view = state['values'].get('live', {}).get('view') or {}
        for card in view.get('history_cards', []):
            entry = owner.coordinator.cards.sessions.get(card['session_id'])
            if (entry is None or entry.session_cost is None or entry.cost_state != 'observed'
                    or card.get('session_summary', {}).get('cost') is None):
                continue
            observed = entry.session_cost
            service = owner.coordinator.history_factory(int(time.time() * 1000))
            try:
                snapshot = service.source.load_session_snapshot(card['session_id'])
                if not snapshot.complete or snapshot.source_revision != observed.source_revision:
                    continue
                bundle = service._analyze_snapshot(snapshot)
                report = service._range_comparison((AnalyzedRoot(snapshot.root, bundle, False),), 0)
                reused = reconcile_session_cost(service.cache_repository, snapshot, service._load_comparison_catalog())
                actual = observed.total
                assert (actual.known_ccost, actual.observed_requests, actual.priced_requests) == (
                    report.known_ccost, report.observed_requests, report.priced_requests)
                assert reused.total.known_ccost == report.known_ccost
                assert reused.valued_requests == 0 and not reused.cache_written
                assert card['session_summary']['cost'] is not None
                print(json.dumps(dict(session_cost='ok', requests=actual.observed_requests,
                    priced_requests=actual.priced_requests, report_parity=True,
                    fresh_repository_valuations=reused.valued_requests, cache_writes=reused.cache_written,
                    model_calls_started_by_probe=0)))
                return
            finally:
                service.close_accounts()
        time.sleep(.25)
    raise RuntimeError('probe_session_cost_timeout')
