"""Same-window quota reference estimates and provider-confirmed idle boundaries."""
from dataclasses import replace
from decimal import Decimal as D
import unittest

from development.tests.fixtures.watch_summary import summary_watch
from src.accounts.claude_code import normalize_claude_usage
from src.analysis.valuation import ComparisonCost
from src.application.display import with_display
from src.application.projection import account
from src.application.watch_accounts import watch_account, watch_quota
from src.domain import QuotaComponent
from src.reports.models import QuotaPeriodProjection


class WebQuotaCCostTests(unittest.TestCase):
    def test_ratio_uses_raw_fraction_and_formats_both_units_only_at_the_end(self):
        quota = QuotaComponent('5-hour', 'rolling', remaining_fraction=D('.9'),
            duration_seconds=18000, reset_at_ms=20000)

        wire = with_display(watch_quota(quota, QuotaPeriodProjection(quota, ComparisonCost(D(100), 2, 2), None)),
            now_ms=1000).to_json()['quota']

        self.assertEqual(('100', '900', '1000'), tuple(wire['display']['ccost_' + key]
            for key in ('used', 'remaining', 'capacity')))
        self.assertEqual(('$1.00', '$9.00', '$10.00'), tuple(wire['display_units']['usd']['ccost_' + key]
            for key in ('used', 'remaining', 'capacity')))
        self.assertIn('CCost used ÷ provider-reported fraction used', wire['display']['ccost_help'])
        self.assertIn('not a guaranteed budget', wire['display']['ccost_help'])
        self.assertIn('observed CCost ÷ native fraction used', wire['display']['ccost_brief'])
        tiny = replace(quota, remaining_fraction=D('.99999'))
        exact = with_display(watch_quota(tiny, QuotaPeriodProjection(tiny, ComparisonCost(D(1), 1, 1), None)),
            now_ms=1000).to_json()['quota']
        self.assertEqual('0%', exact['quota_display']['used']['percent'])
        self.assertEqual(('100000', '99999'), (exact['display']['ccost_capacity'], exact['display']['ccost_remaining']))

    def test_copilot_native_remaining_never_subtracts_independent_observed_cost(self):
        for limit, used, remaining, observed in ((7000, 16, 6984, 120), (25000, 2088, 22912, 1814)):
            quota = QuotaComponent('Monthly', 'fixed', used=D(used), limit=D(limit), remaining=D(remaining), unit='AI credits')

            wire = with_display(watch_quota(quota, QuotaPeriodProjection(quota, ComparisonCost(D(observed), 2, 2), None),
                provider_id='github-copilot')).to_json()['quota']

            with self.subTest(limit=limit):
                self.assertEqual((str(observed), str(remaining), str(limit)), tuple(wire['display']['ccost_' + key]
                    for key in ('used', 'remaining', 'capacity')))
                self.assertIn('Used + Remaining need not equal Capacity', wire['display']['ccost_help'])
                self.assertIn('Used + Remaining need not equal Capacity', wire['display']['ccost_brief'])
                self.assertEqual(f'${D(limit) / 100:.2f}', wire['display_units']['usd']['ccost_capacity'])

    def test_known_native_limit_survives_missing_usage_but_does_not_invent_remaining(self):
        base = QuotaComponent('Monthly', 'fixed', limit=D(7000), unit='AI credits')
        for quota, expected in ((base, '?'), (replace(base, used=D(0)), '7000'),
                                (replace(base, used=D(16)), '6984')):
            wire = with_display(watch_quota(quota, provider_id='github-copilot')).to_json()['quota']['display']
            with self.subTest(quota=quota):
                self.assertEqual(('7000', expected), (wire['ccost_capacity'], wire['ccost_remaining']))
                self.assertEqual('?', wire['ccost_used'])

    def test_no_unit_name_guesswork_pooled_scope_or_billing_budget_conversion(self):
        base = QuotaComponent('Monthly', 'fixed', limit=D(7000), used=D(16), unit='AI credits')
        for provider, quota in (('other', base), ('github-copilot', replace(base, scope='organization')),
                ('github-copilot', replace(base, scope='model', model_id='x')),
                ('github-copilot', replace(base, label='Overage budget')),
                ('github-copilot', replace(base, unit='requests')),
                ('github-copilot', replace(base, origin='inferred'))):
            wire = with_display(watch_quota(quota, provider_id=provider)).to_json()['quota']['display']
            with self.subTest(provider=provider, quota=quota):
                self.assertEqual(('?', '?'), (wire['ccost_capacity'], wire['ccost_remaining']))
                self.assertIn('Reference Capacity / Remaining unavailable', wire['ccost_brief'])

    def test_unreliable_or_out_of_window_ratio_is_unknown_not_zero_or_negative(self):
        base = QuotaComponent('5-hour', 'rolling', remaining_fraction=D('.9'), duration_seconds=18000, reset_at_ms=20000)
        cost = ComparisonCost(D(100), 2, 2)
        for quota, observed, availability in (
                (replace(base, remaining_fraction=D(1)), cost, 'available'),
                (replace(base, remaining_fraction=None), cost, 'available'),
                (replace(base, window_active=False), cost, 'available'),
                (replace(base, reset_at_ms=1000), cost, 'available'),
                (replace(base, reset_at_ms=None), cost, 'available'),
                (replace(base, reset_at_ms=20000000), cost, 'available'),
                (replace(base, limit=D(0)), cost, 'available'),
                (replace(base, used=D(110), limit=D(100)), cost, 'available'),
                (replace(base, used=D(10), remaining=D(95), limit=D(100)), cost, 'available'),
                (base, cost, 'stale'), (base, cost, 'error'),
                (base, None, 'available'), (base, ComparisonCost(D(0), 0, 0), 'available'),
                (base, ComparisonCost(D(100), 3, 2), 'available'),
                (base, ComparisonCost(D(0), 2, 0), 'available')):
            wire = with_display(watch_quota(quota, QuotaPeriodProjection(quota, observed, None),
                availability=availability), now_ms=1000).to_json()['quota']['display']
            with self.subTest(quota=quota, observed=observed, availability=availability):
                self.assertEqual(('?', '?'), (wire['ccost_capacity'], wire['ccost_remaining']))

    def test_full_usage_and_unlimited_have_distinct_zero_and_inapplicable_states(self):
        base = QuotaComponent('Weekly', 'rolling', remaining_fraction=D(0), reset_at_ms=20000)
        cost = ComparisonCost(D(100), 2, 2)
        for quota, capacity, remaining in ((base, '100', '0'), (replace(base, unlimited=True), 'N/A', '?')):
            wire = with_display(watch_quota(quota, QuotaPeriodProjection(quota, cost, None)), now_ms=1000).to_json()['quota']
            with self.subTest(quota=quota):
                self.assertEqual((capacity, remaining), (wire['display']['ccost_capacity'], wire['display']['ccost_remaining']))
                self.assertEqual('used' if quota.unlimited else 'remaining', wire['quota_display']['remaining']['mode'])
                if quota.unlimited:
                    self.assertIn('Unlimited quota', wire['display']['ccost_brief'])

    def test_idle_sdk_zero_has_native_full_remaining_without_numeric_cost_capacity(self):
        base = summary_watch().quota.accounts[0]
        native = normalize_claude_usage(base.account, {'rate_limits_available': True, 'rate_limits': {
            'five_hour': {'utilization': 0, 'resets_at': None}, 'seven_day': {'utilization': 0, 'resets_at': None}}})
        periods = tuple(QuotaPeriodProjection(q, ComparisonCost(D(0), 0, 0), None) for q in native.quotas)
        item = replace(base, account=native, quota_periods=periods)

        watch = with_display(watch_account(item), now_ms=1000).to_json()
        accounts = with_display(account(item), now_ms=1000).to_json()['observation']['quotas']

        for quota in (watch['primary']['quota'], watch['secondary'][0]['quota'], *accounts):
            with self.subTest(label=quota['label']):
                self.assertEqual(('remaining', '100%', '1', False), tuple(quota['quota_display']['remaining'][key]
                    for key in ('mode', 'percent', 'fraction', 'exhausted')))
                self.assertEqual(('0%', '0'), (quota['quota_display']['used']['percent'], quota['quota_display']['used']['fraction']))
                self.assertEqual(('0', '?', '?'), tuple(quota['display']['ccost_' + key] for key in ('used', 'remaining', 'capacity')))
                self.assertEqual('Window not started', quota['display']['reset'])
        self.assertEqual('Window not started', watch['primary']['display']['watch_reset'])

    def test_idle_unknown_untrusted_stale_invalid_and_rounded_zero_do_not_get_full_remaining(self):
        base = QuotaComponent('5-hour', 'rolling', remaining_fraction=D(1), duration_seconds=18000, window_active=False)
        for quota, availability in ((replace(base, remaining_fraction=None), 'available'), (base, 'stale'),
                (replace(base, origin='inferred'), 'available'), (replace(base, limit=D(0)), 'available'),
                (replace(base, remaining_fraction=D('.99999')), 'available'), (replace(base, used=D(1)), 'available')):
            wire = with_display(watch_quota(quota, availability=availability)).to_json()['quota']['quota_display']
            with self.subTest(quota=quota, availability=availability):
                self.assertEqual('used', wire['remaining']['mode'])

    def test_accounts_and_watch_bind_independent_identity_windows_and_reject_delayed_old_period(self):
        base = summary_watch().quota.accounts[0]
        primary = QuotaComponent('Weekly', 'rolling', remaining_fraction=D('.9'), duration_seconds=604800, reset_at_ms=20000)
        secondary = replace(primary, scope='model', model_id='model', remaining_fraction=D('.5'), reset_at_ms=30000)
        item = replace(base, account=replace(base.account, quotas=(primary, secondary), primary_quota_label='Weekly'),
            quota_periods=(QuotaPeriodProjection(secondary, ComparisonCost(D(40), 1, 1), None),
                           QuotaPeriodProjection(primary, ComparisonCost(D(100), 1, 1), None)))

        watch = with_display(watch_account(item), now_ms=1000).to_json()
        accounts = with_display(account(item), now_ms=1000).to_json()['observation']['quotas']

        self.assertEqual(('1000', '80'), tuple(q['display']['ccost_capacity'] for q in accounts))
        self.assertEqual(('1000', '80'), (watch['primary']['quota']['display']['ccost_capacity'],
            watch['secondary'][0]['quota']['display']['ccost_capacity']))
        reset = replace(primary, reset_at_ms=40000)
        delayed = with_display(watch_quota(reset, item.quota_periods[1]), now_ms=1000).to_json()['quota']['display']
        self.assertEqual(('?', '?'), (delayed['ccost_used'], delayed['ccost_capacity']))


if __name__ == '__main__':
    unittest.main()
