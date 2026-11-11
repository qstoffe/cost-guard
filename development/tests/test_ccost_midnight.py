"""Cross-provider midnight, late source history, attribution and shared projections."""
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal as D
import tempfile
import unittest

from development.tests.fixtures.account_midnight import accounts, snapshot, ROUTES, EXPECTED, CATALOG
from development.tests.fixtures.account_periods import request
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from development.tests.fixtures.watch_runtime import make_service
from src.analysis.timezones import local_day_start_ms, local_month_start_ms
from src.analysis.valuation import comparison_cost, unique_usage
from src.application.display import with_display
from src.application.watch_accounts import watch_account
from src.domain import CostDisposition
from src.reports.accounts import account_projections
from src.watch.today_ccost import WatchTodayCCost
from src.watch.web_coordinator import WebWatchCoordinator


class MidnightCCostTests(unittest.TestCase):
    def test_source_history_rolls_over_then_publishes_each_account_and_global_today(self):
        # Explicit UTC instants for local midnight: winter, summer, DST day and UTC control.
        for zone, instant in (('Europe/Stockholm', '2026-11-10T23:00:00'),
                              ('Europe/Stockholm', '2026-07-14T22:00:00'),
                              ('Europe/Stockholm', '2026-03-28T23:00:00'),
                              ('UTC', '2026-03-29T00:00:00')):
            midnight = int(datetime.fromisoformat(instant).replace(tzinfo=timezone.utc).timestamp() * 1000)
            with self.subTest(zone=zone, instant=instant), tempfile.TemporaryDirectory() as tmp:
                native = accounts()
                source = SyntheticMonthSource(0, 1, month_start_ms=midnight)
                old = tuple(snapshot(i, midnight - 1000, route, amount=1000000, active=True) for i, route in enumerate(ROUTES))
                source.snapshots = {item.root.session_id: item for item in old}

                def factory(now):
                    job = make_service(tmp, source, now_ms=now)[2]
                    job.config['timezone'] = zone
                    job.pricing_provider.catalog = CATALOG
                    return job

                config, selection, service, _ = make_service(tmp, source, now_ms=midnight - 1)
                config['timezone'] = zone
                service.pricing_provider.catalog = CATALOG
                owner = WebWatchCoordinator(selection=selection, report_service=service, config=config, service_factory=factory)
                tracker = WatchTodayCCost(zone)
                try:
                    # CLI retention and Web's independent background-history lane.
                    for now, expected in ((midnight - 1, (D(100), D(100), D(400))), (midnight, (D(0),) * 3)):
                        history, daily = owner._account_history(source.list_sessions(), native, now)
                        rows = history.project(native, now_ms=now, today_start_ms=local_day_start_ms(zone, now_ms=now),
                            month_start_ms=local_month_start_ms(zone, now_ms=now), timezone_id=zone, workday_calendar='')
                        self.assertEqual(dict(zip(('github-copilot', 'openai', 'claude-code'), expected)),
                            {row.account.ref.provider_id: dict(row.ccost_scopes)['today'].ccost for row in rows})
                        service.set_now_ms(now)
                        tracker.refresh_available_history(service, source.list_sessions(), native, now)
                        self.assertEqual(sum(expected), tracker.project_from_report(service, now).ccost)
                        self.assertEqual(sum(expected), daily.total.ccost)

                    # No inference: genuinely new completed source-shaped requests arrive after midnight.
                    for i, route in enumerate(ROUTES):
                        item = snapshot(10 + i, midnight + 1000, route, amount=(i + 1) * 10000, started=midnight - 500)
                        source.snapshots[item.root.session_id] = item
                    now = midnight + 2000
                    history, daily = owner._account_history(source.list_sessions(), native, now)
                    rows = history.project(native, now_ms=now, today_start_ms=midnight,
                        month_start_ms=local_month_start_ms(zone, now_ms=now), timezone_id=zone, workday_calendar='')
                    self.assertEqual(dict(zip(('github-copilot', 'openai', 'claude-code'), EXPECTED)),
                        {row.account.ref.provider_id: dict(row.ccost_scopes)['today'].ccost for row in rows})
                    self.assertEqual((D(15), 3, True), (daily.total.ccost, daily.total.observed_requests, daily.total.complete))
                    service.set_now_ms(now)
                    tracker.refresh_available_history(service, source.list_sessions(), native, now)
                    self.assertEqual(D(15), tracker.project_from_report(service, now).ccost)
                    for row in rows:
                        wire = with_display(watch_account(row)).to_json()
                        today = next(scope['cost'] for scope in wire['ccost_scopes'] if scope['name'] == 'today')
                        expected = {'github-copilot': ('1', '$0.01'), 'openai': ('2', '$0.02'), 'claude-code': ('12', '$0.12')}[row.account.ref.provider_id]
                        self.assertEqual(expected, tuple(today['display_units'][unit]['account_ccost'] for unit in ('credits', 'usd')))
                        self.assertIsNone(row.billed_today)
                    loads = source.load_count
                    repeated = owner._account_history(source.list_sessions(), native, now + 1)[1]
                    self.assertEqual(daily.total, repeated.total)
                    self.assertEqual(loads + len(old), source.load_count,
                        'active old roots recheck; unchanged completed roots reuse history')
                    # Late telemetry in the same source request invalidates its revision/cache.
                    corrected = snapshot(10, midnight + 1000, ROUTES[0], amount=20000, started=midnight - 500)
                    source.snapshots[corrected.root.session_id] = replace(corrected, source_revision='late-telemetry')
                    history, caught_up = owner._account_history(source.list_sessions(), native, now + 2)
                    self.assertEqual(D(16), caught_up.total.ccost)
                    caught_up_rows = history.project(native, now_ms=now + 2, today_start_ms=midnight,
                        month_start_ms=local_month_start_ms(zone, now_ms=now), timezone_id=zone, workday_calendar='')
                    row = next(row for row in caught_up_rows if row.account.ref.provider_id == 'github-copilot')
                    self.assertEqual(D(2), dict(row.ccost_scopes)['today'].ccost)
                finally:
                    owner.close()

    def test_completion_boundary_late_history_and_unknowns_are_not_fake_zero(self):
        native = accounts()
        midnight = 86400000
        entries = tuple(request(str(i), midnight + 1, provider=route, amount=(i + 1) * 10000,
            model='claude-opus-5-5' if route == 'claude-agent' else 'gpt-test') for i, route in enumerate(ROUTES))
        entries = tuple(replace(entry, reported_cost=D(0), cost_disposition=CostDisposition.UNKNOWN) for entry in entries)

        def project(records, *, observed=midnight, population=native):
            return account_projections(population, records, CATALOG, now_ms=midnight + 100,
                today_start_ms=midnight, month_start_ms=0, observed_start_ms=observed, require_history=True, watch=True)

        self.assertTrue(all(dict(row.ccost_scopes)['today'] is None for row in project(entries, observed=None)))
        rows = project(entries)
        self.assertEqual(sorted(EXPECTED), sorted(dict(row.ccost_scopes)['today'].ccost for row in rows))
        unknown = replace(entries[0], message_id='unknown', model=replace(entries[0].model, model='unpriced'))
        zero = replace(unknown, message_id='zero', tokens=replace(unknown.tokens, input=0))
        foreign = replace(entries[0], message_id='foreign', model=replace(entries[0].model, provider='unmapped'))
        # Clone and a repeated child physical request are deduplicated globally and per account.
        records = (*entries, replace(entries[0], session_id='child'), unknown, zero, foreign)
        copilot = next(row for row in project(records) if row.account.ref.provider_id == 'github-copilot')
        cost = dict(copilot.ccost_scopes)['today']
        self.assertEqual((D(1), 3, 2, False), (cost.known_ccost, cost.observed_requests, cost.priced_requests, cost.complete))
        global_cost = comparison_cost(unique_usage(records), CATALOG.reference_valuation)
        self.assertEqual((D(16), 6, 5, False), (global_cost.known_ccost, global_cost.observed_requests, global_cost.priced_requests, global_cost.complete))
        second = replace(native[0], ref=replace(native[0].ref, account_id='second'))
        ambiguous = project(entries, population=(*native, second))
        self.assertTrue(all(dict(row.ccost_scopes)['today'] is None for row in ambiguous if row.account.ref.provider_id == 'github-copilot'))
        proven = (replace(entries[0], account_ref=native[0].ref), *entries[1:])
        isolated = project(proven, population=(*native, second))
        self.assertEqual([D(1), D(0)], [dict(row.ccost_scopes)['today'].ccost for row in isolated if row.account.ref.provider_id == 'github-copilot'])


if __name__ == '__main__':
    unittest.main()
