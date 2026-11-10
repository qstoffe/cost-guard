"""Same-window quota reference estimates and provider-confirmed idle boundaries."""
from dataclasses import replace
from decimal import Decimal as D
import unittest

from development.tests.fixtures.watch_summary import summary_watch
from src.accounts.claude_code import normalize_claude_usage
from src.analysis.valuation import ComparisonCost
from src.application.display import with_display
from src.application.projection import account
from src.application.quota_ccost import quota_ccost_tokens, quota_ccost_values
from src.application.watch_accounts import watch_account, watch_quota
from src.domain import QuotaComponent
from src.reports.models import QuotaPeriodProjection
from src.numbers import ccost_amount


class WebQuotaCCostTests(unittest.TestCase):
    def test_factual_labels_and_decimal_thirty_day_equivalents_in_both_units(self):
        for duration, used, fraction, label, capacity, monthly, rounded in (
                (18000, 100, '.9', '5-hour Capacity', '1000', D(144000), D(140000)),
                (604800, 840, '0', 'Weekly Capacity', '800', D(3600), D(3600)),
                (86400, 1, '.9', 'Daily Capacity', '10', D(300), D(300)),
                (604800, 1, '.7', 'Weekly Capacity', None, D(1) / D('.3') * D(2592000) / D(604800), D(14))):
            quota = QuotaComponent('arbitrary plan name', 'rolling', remaining_fraction=D(fraction),
                duration_seconds=duration, reset_at_ms=20000)
            wire = with_display(watch_quota(quota, QuotaPeriodProjection(quota, ComparisonCost(D(used), 1, 1), None)),
                now_ms=1000).to_json()['quota']
            with self.subTest(duration=duration, fraction=fraction):
                self.assertEqual(label, wire['display']['capacity_label'])
                self.assertEqual('~' + ccost_amount(rounded), wire['display']['monthly_capacity'])
                self.assertEqual(f'~${rounded / 100:.2f}', wire['display_units']['usd']['monthly_capacity'])
                self.assertEqual(monthly, D(wire['ccost_reference']['monthly_capacity']))
                self.assertTrue(wire['ccost_reference']['monthly_applicable'])
                self.assertIn('Theoretical standardized 30-day reference equivalent', wire['display']['monthly_capacity_help'])
                self.assertIn('not an actual monthly provider entitlement', wire['display']['monthly_capacity_help'])
                self.assertIn(f'× (30 days ÷ {duration} seconds) = ', wire['display']['monthly_capacity_help'])
                self.assertIn(format(monthly, 'f') + ' Credits', wire['display']['monthly_capacity_help'])
                if capacity:
                    self.assertEqual('~' + capacity, wire['display']['ccost_capacity'])

    def test_source_verified_fixed_weekly_reference_capacity_is_still_extrapolated_as_guesstimate(self):
        quota = QuotaComponent('Weekly', 'fixed', duration_seconds=604800, reset_at_ms=20000,
            reference_ccost_capacity=D(840), unit='requests', used=D(1), limit=D(100))
        wire = with_display(watch_quota(quota), now_ms=1000).to_json()['quota']['display']
        self.assertEqual(('native', '840', '~3600'),
            (wire['capacity_basis'], wire['ccost_capacity'], wire['monthly_capacity']))
        self.assertIn('Source-verified', wire['ccost_help'])
        unverified = with_display(watch_quota(replace(quota, reference_ccost_capacity=None)), now_ms=1000).to_json()['quota']['display']
        self.assertEqual('N/A', unverified['monthly_capacity'], 'requests and native money are not reference credits')

    def test_capacity_help_keeps_exact_snapshot_inputs_and_distinct_native_provenance(self):
        raw_used = D('613.1234567890123456789012345')
        quota = QuotaComponent('5-hour', 'rolling', remaining_fraction=D('.8'), duration_seconds=18000, reset_at_ms=20000)
        period = QuotaPeriodProjection(quota, ComparisonCost(raw_used, 1, 1), None)

        wire = with_display(watch_quota(quota, period), now_ms=1000).to_json()['quota']

        help_text = wire['display']['capacity_help']
        self.assertIn('Observed same-window CCost used: 613.1234567890123456789012345 Credits', help_text)
        self.assertIn('613.1234567890123456789012345 ÷ 0.2 = 3065.617283945061728394506172 Credits', help_text)
        self.assertIn('3065.617283945061728394506172 × (30 days ÷ 18000 seconds)', wire['display']['monthly_capacity_help'])
        self.assertNotIn('Observed', wire['display']['monthly_capacity_help'])
        self.assertIn('Credits ($30.66)', wire['display_units']['usd']['capacity_help'])
        verified = replace(quota, reference_ccost_capacity=D('949.1234567890123456789012345'))

        native = with_display(watch_quota(verified), now_ms=1000).to_json()['quota']['display']

        self.assertIn('Unrounded Capacity: 949.1234567890123456789012345 Credits', native['capacity_help'])
        self.assertIn('Source-verified reference CCost allowance.', native['capacity_help'])
        self.assertNotRegex(native['capacity_help'], r'÷|estimate|Observed')
        self.assertEqual('950', native['ccost_capacity'], 'normal verified formatter, not estimate rounding or ~')

    def test_native_monthly_is_one_capacity_even_when_original_is_ratio_estimated(self):
        for provider in ('github-copilot', 'other'):
            quota = QuotaComponent('Monthly', 'fixed', used=D(10), limit=D(100), unit='AI credits', reset_at_ms=20000)
            projected = with_display(watch_quota(quota, QuotaPeriodProjection(quota, ComparisonCost(D(2), 1, 1), None),
                provider_id=provider), now_ms=1000).to_json()['quota']
            self.assertFalse(projected['ccost_reference']['monthly_applicable'])
            wire = projected['display']
            self.assertEqual(('Monthly Capacity', '', ''),
                (wire['capacity_label'], wire['monthly_capacity'], wire['monthly_capacity_help']))
            self.assertEqual('100' if provider == 'github-copilot' else '~20', wire['ccost_capacity'])
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

        self.assertEqual(('100', '900', '~1000'), tuple(wire['display']['ccost_' + key]
            for key in ('used', 'remaining', 'capacity')))
        self.assertEqual(('$1.00', '$9.00', '~$10.00'), tuple(wire['display_units']['usd']['ccost_' + key]
            for key in ('used', 'remaining', 'capacity')))
        self.assertIn('observed CCost ÷ native fraction used', wire['display']['ccost_help'])
        self.assertEqual('ratio', wire['display']['capacity_basis'])
        self.assertIn('not a guaranteed budget', wire['display']['ccost_help'])
        self.assertIn('observed CCost ÷ native fraction used', wire['display']['ccost_brief'])
        tiny = replace(quota, remaining_fraction=D('.99999'))
        exact = with_display(watch_quota(tiny, QuotaPeriodProjection(tiny, ComparisonCost(D(1), 1, 1), None)),
            now_ms=1000).to_json()['quota']
        self.assertEqual('0%', exact['quota_display']['used']['percent'])
        self.assertEqual(('~100000', '100000'), (exact['display']['ccost_capacity'], exact['display']['ccost_remaining']))
        self.assertEqual('99999', exact['ccost_reference']['remaining'])

    def test_estimates_keep_raw_calculations_observed_used_and_identity_in_both_units(self):
        quota = QuotaComponent('Weekly', 'rolling', remaining_fraction=D('.9'), duration_seconds=604800, reset_at_ms=20000)
        period = QuotaPeriodProjection(quota, ComparisonCost(D(613), 1, 1), None)

        wire = with_display(watch_quota(quota, period), now_ms=1000).to_json()['quota']

        self.assertEqual(('613', '5500', '~6000'), tuple(wire['display']['ccost_' + key]
            for key in ('used', 'remaining', 'capacity')))
        self.assertEqual(('613', '5517', '6.13E+3'), tuple(wire['ccost_reference'][key]
            for key in ('used', 'remaining', 'capacity')))
        self.assertEqual('0.9', wire['remaining_fraction'])
        self.assertIn('5517 Credits', wire['display']['ccost_remaining_help'])
        self.assertIn('6130 Credits ($61.30)', wire['display_units']['usd']['ccost_capacity_help'])
        self.assertIn('Observed same-window CCost used: 613 Credits', wire['display']['capacity_help'])
        self.assertIn('Provider-reported fraction used: 0.1', wire['display']['capacity_help'])
        self.assertIn('Unrounded Capacity (estimate): 613 ÷ 0.1 = 6130 Credits', wire['display']['capacity_help'])
        self.assertIn('not verified provider usage', wire['display']['ccost_capacity_help'])
        self.assertEqual('$55.00', wire['display_units']['usd']['ccost_remaining'])

    def test_copilot_native_amounts_never_use_independent_observed_cost(self):
        for limit, used, remaining, observed in ((10000, 3123, 6877, 450), (10000, 3000, 7000, 450), (7000, 16, 6984, 120), (25000, 2088, 22912, 1814)):
            quota = QuotaComponent('Monthly', 'fixed', used=D(used), limit=D(limit), remaining=D(remaining), unit='AI credits')

            wire = with_display(watch_quota(quota, QuotaPeriodProjection(quota, ComparisonCost(D(observed), 2, 2), None),
                provider_id='github-copilot')).to_json()['quota']

            with self.subTest(limit=limit):
                self.assertEqual((ccost_amount(D(used)), ccost_amount(D(remaining)), ccost_amount(D(limit))), tuple(wire['display']['ccost_' + key]
                    for key in ('used', 'remaining', 'capacity')))
                self.assertIn('Provider-reported quota Used/Remaining', wire['display']['ccost_help'])
                self.assertIn('OpenCode-observed CCost is separate', wire['display']['ccost_brief'])
                self.assertEqual((f'${D(used) / 100:.2f}', f'${D(remaining) / 100:.2f}', f'${D(limit) / 100:.2f}'),
                    tuple(wire['display_units']['usd']['ccost_' + key] for key in ('used', 'remaining', 'capacity')))
                self.assertEqual(f'${D(limit) / 100:.2f}', wire['display_units']['usd']['ccost_capacity'])
                self.assertEqual('native', wire['display']['capacity_basis'])
                self.assertEqual('', wire['display']['ccost_remaining_help'])
                self.assertEqual('', wire['display']['ccost_capacity_help'])

    def test_known_native_limit_survives_missing_usage_but_does_not_invent_remaining(self):
        base = QuotaComponent('Monthly', 'fixed', limit=D(7000), unit='AI credits')
        for quota, expected in ((base, '?'), (replace(base, used=D(0)), '7000'),
                                (replace(base, used=D(16)), '6984')):
            wire = with_display(watch_quota(quota, provider_id='github-copilot')).to_json()['quota']['display']
            with self.subTest(quota=quota):
                self.assertEqual(('7000', expected), (wire['ccost_capacity'], wire['ccost_remaining']))
                self.assertEqual('?' if quota.used is None else str(quota.used), wire['ccost_used'])

    def test_native_complements_fraction_and_external_only_usage_ignore_local_pricing(self):
        base = QuotaComponent('Monthly', 'fixed', used=D(3000), remaining=D(7000), limit=D(10000), unit='AI credits')
        for quota in (base, replace(base, used=None), replace(base, remaining=None),
                replace(base, used=None, remaining=None, remaining_fraction=D('.7')),
                replace(base, used=D(0), remaining=D(10000)), replace(base, used=D(10000), remaining=D(0))):
            for cost in (None, ComparisonCost(D(450), 1, 1), ComparisonCost(D(0), 3, 0)):
                wire = with_display(watch_quota(quota, QuotaPeriodProjection(quota, cost, None),
                    provider_id='github-copilot-enterprise', estimated=True, note='Observed attribution only')).to_json()['quota']
                expected = ('0', '10000') if quota.used == 0 else ('10000', '0') if quota.remaining == 0 else ('3000', '7000')
                with self.subTest(quota=quota, cost=cost):
                    self.assertEqual((*expected, '10000'), tuple(wire['display']['ccost_' + key]
                        for key in ('used', 'remaining', 'capacity')))
                    self.assertNotIn('partial attribution', wire['display']['ccost_help'])
                    self.assertNotIn('Observed attribution only', wire['display']['ccost_help'])

    def test_verified_conversion_scales_native_ratio_before_display_rounding(self):
        for used, remaining, fraction in ((D(3), D(7), None), (None, D(7), None),
                (D(3), None, None), (None, None, D('.7'))):
            quota = QuotaComponent('Weekly', 'fixed', used=used, remaining=remaining, limit=D(10),
                remaining_fraction=fraction, unit='requests', duration_seconds=604800, reset_at_ms=20000,
                reference_ccost_capacity=D('10000.123456789'))
            values = dict(dict(watch_quota(quota).fields)['quota'].fields)

            reference = quota_ccost_values(values, 1000)
            wire = with_display(watch_quota(quota), now_ms=1000).to_json()['quota']

            self.assertEqual((D('3000.0370370367'), D('7000.0864197523'), D('10000.123456789')),
                tuple(reference[key] for key in ('used', 'remaining', 'capacity')))
            self.assertEqual(('$30.00', '$70.00', '$100.00'), tuple(wire['display_units']['usd']['ccost_' + key]
                for key in ('used', 'remaining', 'capacity')))
        fraction_only = replace(quota, limit=None)
        wire = with_display(watch_quota(fraction_only), now_ms=1000).to_json()['quota']['display']
        self.assertEqual(('3001', '7001'), (wire['ccost_used'], wire['ccost_remaining']))

    def test_invalid_or_unavailable_native_allowance_never_falls_back_to_observed_used(self):
        base = QuotaComponent('Monthly', 'fixed', used=D(3000), remaining=D(7000), limit=D(10000),
            unit='AI credits', reset_at_ms=20000)
        for quota, availability in ((replace(base, used=D(11000)), 'available'),
                (replace(base, remaining=D(9000)), 'available'),
                (replace(base, remaining_fraction=D('.6')), 'available'),
                (replace(base, limit=D(0)), 'available'), (replace(base, limit=None), 'available'),
                (replace(base, status='blocked'), 'available'), (replace(base, status='paused'), 'available'),
                (replace(base, window_active=False), 'available'), (replace(base, reset_at_ms=1000), 'available'),
                (base, 'stale'), (base, 'error'), (base, 'unavailable')):
            wire = with_display(watch_quota(quota, QuotaPeriodProjection(quota, ComparisonCost(D(450), 1, 1), None),
                provider_id='github-copilot', availability=availability), now_ms=1000).to_json()['quota']
            with self.subTest(quota=quota, availability=availability):
                self.assertEqual(('?', '?', '?'), tuple(wire['display']['ccost_' + key]
                    for key in ('used', 'remaining', 'capacity')))
                self.assertEqual(str(quota.used), wire['used'], 'native diagnostics are not clamped or discarded')

    def test_partial_native_snapshot_retains_large_exact_amounts_without_local_pricing(self):
        quota = QuotaComponent('Monthly', 'fixed', used=D('3000000000000000.125'),
            remaining=D('7000000000000000.875'), limit=D('10000000000000001'), unit='AI credits')
        values = dict(dict(watch_quota(quota, provider_id='github-copilot', availability='partial').fields)['quota'].fields)

        reference = quota_ccost_values(values, 1000)

        self.assertEqual((quota.used, quota.remaining, quota.limit), tuple(reference[key]
            for key in ('used', 'remaining', 'capacity')))
        self.assertEqual(reference['capacity'], reference['used'] + reference['remaining'])
        self.assertEqual('native', reference['basis'])

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
        for quota, capacity, remaining in ((base, '~100', '0'), (replace(base, unlimited=True), 'N/A', '?')):
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

        self.assertEqual(('~1000', '~80'), tuple(q['display']['ccost_capacity'] for q in accounts))
        self.assertEqual(('~1000', '~80'), (watch['primary']['quota']['display']['ccost_capacity'],
            watch['secondary'][0]['quota']['display']['ccost_capacity']))
        reset = replace(primary, reset_at_ms=40000)
        delayed = with_display(watch_quota(reset, item.quota_periods[1]), now_ms=1000).to_json()['quota']['display']
        self.assertEqual(('?', '?'), (delayed['ccost_used'], delayed['ccost_capacity']))


if __name__ == '__main__':
    unittest.main()
