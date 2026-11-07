"""Same-window quota reference estimates and provider-confirmed idle boundaries."""
from dataclasses import replace
from decimal import Decimal as D
import unittest

from development.tests.fixtures.watch_summary import summary_watch
from src.accounts.claude_code import normalize_claude_usage
from src.analysis.valuation import ComparisonCost
from src.application.display import with_display
from src.application.projection import account
from src.application.quota_ccost import quota_ccost_tokens
from src.application.watch_accounts import watch_account, watch_quota
from src.domain import QuotaComponent
from src.reports.models import QuotaPeriodProjection
from src.numbers import ccost_amount


class WebQuotaCCostTests(unittest.TestCase):
    def test_factual_labels_and_decimal_thirty_day_equivalents_in_both_units(self):
        for duration, used, fraction, label, capacity, monthly in (
                (18000, 100, '.9', '5-hour Capacity', '1000', D(144000)),
                (604800, 840, '0', 'Weekly Capacity', '840', D(3600)),
                (86400, 1, '.9', 'Daily Capacity', '10', D(300)),
                (604800, 1, '.7', 'Weekly Capacity', None, D(100) / D(7))):
            quota = QuotaComponent('arbitrary plan name', 'rolling', remaining_fraction=D(fraction),
                duration_seconds=duration, reset_at_ms=20000)
            wire = with_display(watch_quota(quota, QuotaPeriodProjection(quota, ComparisonCost(D(used), 1, 1), None)),
                now_ms=1000).to_json()['quota']
            with self.subTest(duration=duration, fraction=fraction):
                self.assertEqual(label, wire['display']['capacity_label'])
                self.assertEqual(ccost_amount(monthly) + ' (guesstimate)', wire['display']['monthly_capacity'])
                self.assertEqual(f'${monthly / 100:.2f} (guesstimate)', wire['display_units']['usd']['monthly_capacity'])
                self.assertIn('2,592,000', wire['display']['monthly_capacity_help'])
                self.assertIn('never add', wire['display']['monthly_capacity_help'])
                if capacity:
                    self.assertEqual(capacity + ' (guesstimate)', wire['display']['ccost_capacity'])

    def test_source_verified_fixed_weekly_reference_capacity_is_still_extrapolated_as_guesstimate(self):
        quota = QuotaComponent('Weekly', 'fixed', duration_seconds=604800, reset_at_ms=20000,
            reference_ccost_capacity=D(840), unit='requests', used=D(1), limit=D(100))
        wire = with_display(watch_quota(quota), now_ms=1000).to_json()['quota']['display']
        self.assertEqual(('native', '840', '3600 (guesstimate)'),
            (wire['capacity_basis'], wire['ccost_capacity'], wire['monthly_capacity']))
        self.assertIn('Source-verified', wire['ccost_help'])
        unverified = with_display(watch_quota(replace(quota, reference_ccost_capacity=None)), now_ms=1000).to_json()['quota']['display']
        self.assertEqual('N/A', unverified['monthly_capacity'], 'requests and native money are not reference credits')

    def test_native_monthly_is_one_capacity_even_when_original_is_ratio_estimated(self):
        for provider in ('github-copilot', 'other'):
            quota = QuotaComponent('Monthly', 'fixed', used=D(10), limit=D(100), unit='AI credits', reset_at_ms=20000)
            wire = with_display(watch_quota(quota, QuotaPeriodProjection(quota, ComparisonCost(D(2), 1, 1), None),
                provider_id=provider), now_ms=1000).to_json()['quota']['display']
            self.assertEqual(('Monthly Capacity', '', ''),
                (wire['capacity_label'], wire['monthly_capacity'], wire['monthly_capacity_help']))
            self.assertEqual('100' if provider == 'github-copilot' else '20 (guesstimate)', wire['ccost_capacity'])
        unknown = with_display(watch_quota(QuotaComponent('Monthly plan', 'unknown')), now_ms=1000).to_json()['quota']['display']
        self.assertEqual(('Capacity', 'N/A'), (unknown['capacity_label'], unknown['monthly_capacity']))

    def test_unprovable_monthly_equivalents_are_na_with_specific_reasons(self):
        base = QuotaComponent('5-hour', 'rolling', remaining_fraction=D('.9'), duration_seconds=18000, reset_at_ms=20000)
        cost = ComparisonCost(D(100), 2, 2)
        for quota, observed, availability, reason in (
                (replace(base, duration_seconds=None), cost, 'available', 'duration'),
                (replace(base, duration_seconds=0), cost, 'available', 'duration'),
                (replace(base, period='unknown'), cost, 'available', 'duration'),
                (replace(base, origin='inferred'), cost, 'available', 'duration'),
                (replace(base, unlimited=True), cost, 'available', 'finite'),
                (replace(base, window_active=False), cost, 'available', 'active'),
                (replace(base, reset_at_ms=None), cost, 'available', 'active'),
                (replace(base, reset_at_ms=20000000), cost, 'available', 'active'),
                (replace(base, reset_at_ms=1000), cost, 'available', 'expired'),
                (replace(base, used=D(101), limit=D(100)), cost, 'available', 'Contradictory'),
                (replace(base, used=D(10), remaining=D(95), limit=D(100)), cost, 'available', 'Contradictory'),
                (replace(base, used=D(10), remaining_fraction=D('.8'), limit=D(100)), cost, 'available', 'Contradictory'),
                (base, cost, 'stale', 'stale'), (base, cost, 'error', 'unavailable'),
                (base, None, 'available', 'compatible'),
                (base, ComparisonCost(D(100), 3, 2), 'available', 'incomplete'),
                (base, ComparisonCost(D(0), 2, 0), 'available', 'incomplete')):
            tokens = with_display(watch_quota(quota, QuotaPeriodProjection(quota, observed, None),
                availability=availability), now_ms=1000).to_json()['quota']['display']
            with self.subTest(quota=quota, availability=availability, reason=reason):
                self.assertEqual('N/A', tokens['monthly_capacity'])
                self.assertIn(reason, tokens['monthly_capacity_help'])
        values = dict(dict(watch_quota(base, QuotaPeriodProjection(base, cost, None)).fields)['quota'].fields)
        self.assertEqual('N/A', quota_ccost_tokens({**values, 'remaining_fraction': '1.1'}, 1000)['monthly_capacity'])

    def test_ratio_uses_raw_fraction_and_formats_both_units_only_at_the_end(self):
        quota = QuotaComponent('5-hour', 'rolling', remaining_fraction=D('.9'),
            duration_seconds=18000, reset_at_ms=20000)

        wire = with_display(watch_quota(quota, QuotaPeriodProjection(quota, ComparisonCost(D(100), 2, 2), None)),
            now_ms=1000).to_json()['quota']

        self.assertEqual(('100', '900', '1000 (guesstimate)'), tuple(wire['display']['ccost_' + key]
            for key in ('used', 'remaining', 'capacity')))
        self.assertEqual(('$1.00', '$9.00', '$10.00 (guesstimate)'), tuple(wire['display_units']['usd']['ccost_' + key]
            for key in ('used', 'remaining', 'capacity')))
        self.assertIn('observed CCost ÷ native fraction used', wire['display']['ccost_help'])
        self.assertEqual('ratio', wire['display']['capacity_basis'])
        self.assertIn('not a guaranteed budget', wire['display']['ccost_help'])
        self.assertIn('observed CCost ÷ native fraction used', wire['display']['ccost_brief'])
        tiny = replace(quota, remaining_fraction=D('.99999'))
        exact = with_display(watch_quota(tiny, QuotaPeriodProjection(tiny, ComparisonCost(D(1), 1, 1), None)),
            now_ms=1000).to_json()['quota']
        self.assertEqual('0%', exact['quota_display']['used']['percent'])
        self.assertEqual(('100000 (guesstimate)', '99999'), (exact['display']['ccost_capacity'], exact['display']['ccost_remaining']))

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
                self.assertEqual('native', wire['display']['capacity_basis'])

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
        for quota, capacity, remaining in ((base, '100 (guesstimate)', '0'), (replace(base, unlimited=True), 'N/A', '?')):
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

        self.assertEqual(('1000 (guesstimate)', '80 (guesstimate)'), tuple(q['display']['ccost_capacity'] for q in accounts))
        self.assertEqual(('1000 (guesstimate)', '80 (guesstimate)'), (watch['primary']['quota']['display']['ccost_capacity'],
            watch['secondary'][0]['quota']['display']['ccost_capacity']))
        reset = replace(primary, reset_at_ms=40000)
        delayed = with_display(watch_quota(reset, item.quota_periods[1]), now_ms=1000).to_json()['quota']['display']
        self.assertEqual(('?', '?'), (delayed['ccost_used'], delayed['ccost_capacity']))


if __name__ == '__main__':
    unittest.main()
