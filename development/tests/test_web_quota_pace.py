"""Reference-only Web remaining pace; native calendar and CLI values stay intact."""
from dataclasses import replace
from datetime import datetime
from decimal import Decimal as D
import unittest

from development.tests.fixtures.account_views import account_report, NOW
from src.analysis.quota_pace import QuotaPace, quota_pace
from src.analysis.valuation import ComparisonCost
from src.application.display import with_display
from src.application.projection import account
from src.application.watch_accounts import watch_account, watch_quota
from src.domain import QuotaComponent
from src.reports.models import QuotaPeriodProjection


class WebQuotaPaceTests(unittest.TestCase):
    def test_ratio_pace_rounds_each_unrounded_rate_not_the_display_balance(self):
        quota = QuotaComponent('Monthly', 'fixed', used=D(10), remaining=D(90), limit=D(100),
            unit='messages', reset_at_ms=NOW + 9 * 86400000)
        native = QuotaPace('Monthly', 'messages', D(10), 9, 3, D(30))
        period = QuotaPeriodProjection(quota, ComparisonCost(D(613), 1, 1), native)

        wire = with_display(watch_quota(quota, period), now_ms=NOW).to_json()['quota']
        pace = wire['ccost_pace']

        self.assertEqual('5517', pace['ccost_remaining'])
        self.assertEqual(('613', '1839'), (pace['ccost_per_day'], pace['ccost_per_workday']))
        self.assertEqual(('600', '2000'), tuple(pace['display'][key] for key in ('ccost_per_day', 'ccost_per_workday')))
        self.assertEqual('$6.00', pace['display_units']['usd']['ccost_per_day'])
        self.assertIn('613 Credits ($6.13)', pace['display_units']['usd']['ccost_per_day_help'])
        self.assertEqual('ratio', pace['capacity_basis'])

    def test_same_reference_budget_and_full_precision_on_both_surfaces(self):
        base = account_report().accounts_quotas.accounts[0]
        quota = QuotaComponent('Monthly', 'fixed', remaining=D(10000), used=D(10000),
            limit=D(20000), unit='AI credits', reset_at_ms=NOW + 10 * 86400000)
        native_pace = QuotaPace('Monthly', 'AI credits', D(1000), 10, 5, D(2000))
        period = QuotaPeriodProjection(quota, ComparisonCost(D(7), 1, 1), native_pace)
        item = replace(base, account=replace(base.account, quotas=(quota,)), quota_periods=(period,), pace=(native_pace,))

        for unit in ('credits', 'usd'):
            watch = with_display(watch_account(item), now_ms=NOW, ccost_display_unit=unit).to_json()
            ordinary = with_display(account(item), now_ms=NOW, ccost_display_unit=unit).to_json()
            pace = watch['primary']['quota']['ccost_pace']

            with self.subTest(unit=unit):
                self.assertEqual(pace, ordinary['observation']['quotas'][0]['ccost_pace'])
                self.assertEqual(('10000', '1000', '2000'), tuple(pace[key] for key in
                    ('ccost_remaining', 'ccost_per_day', 'ccost_per_workday')))
                self.assertEqual(('1000', '2000') if unit == 'credits' else ('$10.00', '$20.00'),
                    tuple(pace['display'][key] for key in ('ccost_per_day', 'ccost_per_workday')))
                self.assertEqual('1000', watch['primary']['pace']['display']['per_day'])
                self.assertEqual('1000', ordinary['pace'][0]['display']['per_day'])
                self.assertEqual('7', watch['primary']['cost']['known_ccost'])

    def test_nonreference_messages_use_ratio_not_native_balance_and_never_join_by_label(self):
        base = account_report().accounts_quotas.accounts[0]
        primary = QuotaComponent('Same name', 'fixed', used=D(20), limit=D(100), remaining=D(80),
            unit='messages', reset_at_ms=NOW + 86400000)
        secondary = replace(primary, scope='model', model_id='model', reset_at_ms=NOW + 2 * 86400000)
        periods = (QuotaPeriodProjection(secondary, ComparisonCost(D(40), 1, 1),
                       QuotaPace('Same name', 'messages', D(40), 2, 1, D(80))),
                   QuotaPeriodProjection(primary, ComparisonCost(D(100), 1, 1),
                       QuotaPace('Same name', 'messages', D(80), 1, 1, D(80))))
        item = replace(base, account=replace(base.account, quotas=(primary, secondary)), quota_periods=periods)

        watch = with_display(watch_account(item), now_ms=NOW).to_json()
        ordinary = with_display(account(item), now_ms=NOW).to_json()['observation']['quotas']

        self.assertEqual(('400', '80'), tuple(q['ccost_pace']['ccost_per_day'] for q in ordinary))
        self.assertEqual(ordinary[0]['ccost_pace'], watch['primary']['quota']['ccost_pace'])
        self.assertEqual(ordinary[1]['ccost_pace'], watch['secondary'][0]['quota']['ccost_pace'])
        self.assertEqual('$4.00', ordinary[0]['ccost_pace']['display_units']['usd']['ccost_per_day'])
        # An equal-looking quota from a previous window must not donate its cost or calendar.
        delayed = with_display(watch_quota(replace(primary, reset_at_ms=NOW + 3 * 86400000), periods[1]),
            now_ms=NOW).to_json()
        self.assertIsNone(delayed['quota']['ccost_pace'])

    def test_unavailable_reference_basis_does_not_fall_back_to_native_or_verified_capacity_alone(self):
        quota = QuotaComponent('Monthly', 'fixed', used=D(20), limit=D(100), remaining=D(80),
            unit='messages', reset_at_ms=NOW + 86400000)
        pace = QuotaPace('Monthly', 'messages', D(80), 1, 1, D(80))
        for current, cost, availability in (
                (quota, None, 'available'), (quota, ComparisonCost(D(100), 2, 1), 'available'),
                (replace(quota, reference_ccost_capacity=D(10000), used=None, remaining=None), None, 'available'),
                (replace(quota, unlimited=True), None, 'available'),
                (replace(quota, window_active=False), ComparisonCost(D(100), 1, 1), 'available'),
                (replace(quota, reset_at_ms=NOW), ComparisonCost(D(100), 1, 1), 'available'),
                (replace(quota, remaining=None, used=None), None, 'available'),
                (quota, ComparisonCost(D(100), 1, 1), 'stale')):
            wire = with_display(watch_quota(current, QuotaPeriodProjection(current, cost, pace),
                availability=availability), now_ms=NOW).to_json()
            with self.subTest(quota=current, availability=availability):
                self.assertIsNone(wire['quota']['ccost_pace'])
                self.assertEqual('80', wire['pace']['per_day'], 'the native contract is independent')

    def test_verified_native_reference_mapping_drives_pace_without_observed_cost(self):
        quota = QuotaComponent('Monthly', 'fixed', used=D(3), limit=D(10), remaining=D(7), unit='messages',
            reference_ccost_capacity=D('10000.01'), reset_at_ms=NOW + 3 * 86400000)
        pace = QuotaPace('Monthly', 'messages', D(7) / 3, 3, 0, None)

        wire = with_display(watch_quota(quota, QuotaPeriodProjection(quota, None, pace)), now_ms=NOW).to_json()['quota']

        self.assertEqual(('3001', '7001', '10001'), tuple(wire['display']['ccost_' + key]
            for key in ('used', 'remaining', 'capacity')))
        self.assertEqual(str(D('7000.007') / 3), wire['ccost_pace']['ccost_per_day'])
        self.assertIsNone(wire['ccost_pace']['ccost_per_workday'])

    def test_invalid_native_balances_never_enter_the_reference_projection(self):
        for remaining in (D(-1), D('NaN'), D('Infinity')):
            with self.subTest(remaining=remaining), self.assertRaises(ValueError):
                QuotaComponent('Monthly', 'fixed', remaining=remaining, limit=D(100), unit='AI credits')

    def test_remaining_rounding_zero_tiny_values_and_no_workdays(self):
        for remaining, days, credits, usd in ((D(0), 1, '0', '$0.00'),
                (D('.001'), 1, '<0.1', '$0.00'), (D('.99'), 1, '0.9', '$0.01'),
                (D('1.99'), 1, '1', '$0.02'), (D('100.01'), 3, '33', '$0.33')):
            quota = QuotaComponent('Monthly', 'fixed', remaining=remaining, limit=D(20000),
                unit='AI credits', reset_at_ms=NOW + days * 86400000)
            native = QuotaPace('Monthly', 'AI credits', remaining / days, days, 0, None)

            wire = with_display(watch_quota(quota, QuotaPeriodProjection(quota, None, native),
                provider_id='github-copilot'), now_ms=NOW).to_json()['quota']['ccost_pace']

            with self.subTest(remaining=remaining, days=days):
                self.assertEqual(str(remaining / days), wire['ccost_per_day'])
                self.assertEqual(credits, wire['display']['ccost_per_day'])
                self.assertEqual(usd, wire['display_units']['usd']['ccost_per_day'])
                self.assertIsNone(wire['ccost_per_workday'])
                self.assertEqual(0, wire['workdays'])

    def test_existing_local_calendar_holiday_dst_final_day_and_expiry_counts(self):
        for start, reset, calendar, days, workdays in (
                ('2026-03-29T00:30:00+00:00', '2026-03-31T00:00:00+00:00', 'SE', 2, 1),
                ('2026-05-01T10:00:00+00:00', '2026-05-02T00:00:00+00:00', 'SE', 1, 0),
                ('2026-05-01T10:00:00+00:00', '2026-05-02T00:00:00+00:00', '', 1, 1)):
            now = int(datetime.fromisoformat(start).timestamp() * 1000)
            deadline = int(datetime.fromisoformat(reset).timestamp() * 1000)
            quota = QuotaComponent('Monthly', 'fixed', remaining=D(10000), limit=D(20000),
                unit='AI credits', reset_at_ms=deadline)
            native = quota_pace(quota, now_ms=now, timezone_id='Europe/Stockholm', workday_calendar=calendar)

            wire = with_display(watch_quota(quota, QuotaPeriodProjection(quota, None, native),
                provider_id='github-copilot'), now_ms=now).to_json()['quota']['ccost_pace']
            expired = with_display(watch_quota(quota, QuotaPeriodProjection(quota, None, native),
                provider_id='github-copilot'), now_ms=deadline).to_json()['quota']['ccost_pace']

            with self.subTest(start=start, calendar=calendar):
                self.assertEqual((days, workdays), (wire['days'], wire['workdays']))
                self.assertEqual(str(D(10000) / days), wire['ccost_per_day'])
                self.assertIsNone(expired, 'a retained old calendar cannot extend the quota window')


if __name__ == '__main__':
    unittest.main()
