"""Watch native quota/period CCost independence and canonical display parity."""
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal as D
import json
from pathlib import Path
import shutil
import subprocess
import unittest

from development.tests.fixtures.watch_summary import summary_watch, authoritative_allowances
from development.tests.integration.probe_web_live import check_reference_quotas
from src.analysis.valuation import ComparisonCost
from src.application.display import with_display, web_quota_reset
from src.application.contracts import record
from src.application.live_projection import project_live
from src.application.projection import account
from src.application.watch_accounts import watch_account, watch_quota
from src.domain import QuotaComponent
from src.display import format_reset
from src.presentation.accounts import quota_parts
from src.reports.models import QuotaPeriodProjection

ROOT = Path(__file__).resolve().parents[2]


class WebWatchQuotaTests(unittest.TestCase):
    def test_read_only_native_probe_oracle_handles_missing_slots_and_detects_local_used(self):
        accounts = project_live(authoritative_allowances(summary_watch())).to_json()['accounts']
        accounts['accounts'].extend(project_live(summary_watch()).to_json()['accounts']['accounts'][1:])

        counts = check_reference_quotas(accounts)

        self.assertEqual(dict(native_capacities=2, native_amount_pairs=2, native_pace=2), counts)
        accounts['accounts'][0]['primary']['quota']['display_units']['credits']['ccost_used'] = '450'
        with self.assertRaisesRegex(AssertionError, 'native reference tokens'):
            check_reference_quotas(accounts)

    def test_authoritative_primary_and_verified_secondary_agree_across_exports_and_reset(self):
        frame = authoritative_allowances(summary_watch())
        item = frame.quota.accounts[0]

        watch = project_live(frame).to_json()['accounts']['accounts'][0]
        accounts = with_display(account(item), now_ms=frame.now_ms).to_json()['observation']['quotas']

        for index, slot in enumerate((watch['primary'], watch['secondary'][0])):
            quota = slot['quota']
            with self.subTest(index=index):
                self.assertEqual(accounts[index], quota)
                self.assertEqual(('3000', '7000', '10000') if index == 0 else ('600', '1400', '2000'),
                    tuple(quota['display']['ccost_' + key] for key in ('used', 'remaining', 'capacity')))
                self.assertEqual(('30%', '70%'), tuple(quota['quota_display'][mode]['percent'] for mode in ('used', 'remaining')))
                self.assertEqual('450' if index == 0 else '999', slot['cost']['known_ccost'])
                self.assertEqual('7000' if index == 0 else '1400', quota['ccost_pace']['ccost_remaining'])
        self.assertNotEqual(watch['primary']['quota']['reset_at_ms'], watch['secondary'][0]['quota']['reset_at_ms'])
        self.assertEqual('12.5', watch['ccost_scopes'][0]['cost']['known_ccost'])
        reset = replace(item.account.quotas[0], used=D(0), remaining=D(10000), reset_at_ms=frame.now_ms + 30 * 86400000)

        fresh = with_display(watch_quota(reset, item.quota_periods[0], provider_id='github-copilot'), now_ms=frame.now_ms).to_json()

        self.assertIsNone(fresh['cost'], 'old local window cannot donate cost or calendar')
        self.assertEqual(('0', '10000', '10000'), tuple(fresh['quota']['display']['ccost_' + key]
            for key in ('used', 'remaining', 'capacity')))

    def test_web_orientation_variants_preserve_canonical_fields_and_native_evidence(self):
        base = QuotaComponent('Monthly', used=D(5608), limit=D(25000), remaining=D(19392), unit='AI credits')
        cases = (
            (base, '77.6%', '0.77568', '19392/25000 AI credits', False),
            (replace(base, used=D(0), remaining=None), '100%', '1', '25000/25000 AI credits', False),
            (replace(base, used=D(2500), remaining=None), '90%', '0.9', '22500/25000 AI credits', False),
            (replace(base, used=D(22500), remaining=None), '10%', '0.1', '2500/25000 AI credits', False),
            (replace(base, used=D(25000), remaining=None), '0%', '0', '0/25000 AI credits', True),
            (replace(base, used=D('24999.9'), remaining=None), '>0%', '0.000004', '0.1/25000 AI credits', False),
            (replace(base, used=D(26000), remaining=None), '0%', '0', '0/25000 AI credits', True),
            (replace(base, used=None), '77.6%', '0.77568', '19392/25000 AI credits', False),
            (QuotaComponent('Weekly', remaining_fraction=D('.58')), '58%', '0.58', 'N/A units', False),
            (QuotaComponent('Weekly', limit=D(100), remaining_fraction=D('.58')), '58%', '0.58', '58/100 units', False),
        )
        for quota, percent, fraction, native, exhausted in cases:
            wire = with_display(watch_quota(quota), now_ms=1000).to_json()
            shown = wire['quota']['quota_display']['remaining']

            with self.subTest(quota=quota):
                self.assertEqual(('remaining', percent, fraction, native, exhausted),
                    tuple(shown[key] for key in ('mode', 'percent', 'fraction', 'native', 'exhausted')))
                self.assertEqual(None if quota.remaining is None else str(quota.remaining), wire['quota']['remaining'])
                self.assertEqual(None if quota.used is None else str(quota.used), wire['quota']['used'])
                self.assertEqual(quota.used is not None and quota.used > D(25000), bool(shown['note']))

    def test_remaining_falls_back_without_known_capacity_or_usage_and_keeps_native_money(self):
        base = QuotaComponent('Monthly', used=D(5608), limit=D(25000), unit='AI credits')
        for quota in (replace(base, unlimited=True), replace(base, limit=None), replace(base, limit=D(0)),
                      replace(base, used=None), replace(base, window_active=False), QuotaComponent('Unknown')):
            wire = with_display(watch_quota(quota)).to_json()['quota']

            with self.subTest(quota=quota):
                self.assertEqual(wire['quota_display']['used'], wire['quota_display']['remaining'])
                self.assertEqual('used', wire['quota_display']['remaining']['mode'])
        quota = replace(base, remaining=D(19392), remaining_money=D('7.75'), limit_money=D(10))

        shown = with_display(watch_quota(quota)).to_json()['quota']['quota_display']['remaining']

        self.assertEqual('$7.75', shown['money'], 'prefer trusted native money, never reference CCost')

    def test_remaining_keeps_independent_period_ccost_markers_and_units(self):
        quota = QuotaComponent('Monthly', used=D(2088), limit=D(25000), unit='AI credits')
        for cost in (None, ComparisonCost(D(0), 0, 0), ComparisonCost(D(1814), 3, 2), ComparisonCost(D(0), 2, 0)):
            for unit in ('credits', 'usd'):
                value = with_display(watch_quota(quota, QuotaPeriodProjection(quota, cost, None), estimated=True),
                    ccost_display_unit=unit).to_json()

                with self.subTest(cost=cost, unit=unit):
                    self.assertEqual('22912/25000 AI credits', value['quota']['quota_display']['remaining']['native'])
                    self.assertEqual('91.6%', value['quota']['quota_display']['remaining']['percent'])
                    self.assertEqual(cost is None, value['cost'] is None)
                    if cost is not None:
                        self.assertEqual(str(cost.known_ccost), value['cost']['known_ccost'])
                        self.assertEqual(cost.complete, value['cost']['complete'])
                    self.assertTrue(value['estimated'])

    def test_watch_reset_uses_duration_notation_and_keeps_other_reset_consumers(self):
        now = int(datetime(2026, 11, 3, 18, 41, tzinfo=timezone.utc).timestamp() * 1000)
        cases = ((12_000, '12s, 18:41 today'), (90_000, '1m30s, 18:42 today'),
            (300_000, '5m, 18:46 today'), (5_280_000, '1h28m, 20:09 today'),
            (82_800_000, '23h, 17:41 Wednesday'), (97_200_000, '1d3h, 21:41 Wednesday'),
            (604_799_000, '6d23h, 18:40 Tuesday'), (604_800_000, '7d, 18:41 Tuesday'))
        for elapsed, expected in cases:
            quota = QuotaComponent('Primary', reset_at_ms=now + elapsed)

            wire = with_display(watch_quota(quota), 'UTC', now).to_json()

            with self.subTest(elapsed=elapsed):
                self.assertEqual('Reset in ' + expected, wire['display']['watch_reset'])
                self.assertEqual('Reset in ' + expected, wire['quota']['display']['web_reset'])
                self.assertEqual(format_reset(now + elapsed, 'UTC', now_ms=now), wire['quota']['display']['reset'])
                self.assertEqual(now + elapsed, wire['quota']['reset_at_ms'])
        for deadline, active, expected in ((now + 604_800_001, None, 'Reset at 18:41, 2026-11-10'),
                (now, None, 'Reset expired'), (now - 1, None, 'Reset expired'),
                (None, None, 'Reset unknown'), (None, False, 'Window not started'), (0, None, 'Reset unknown')):
            quota = QuotaComponent('Primary', reset_at_ms=deadline, window_active=active)

            wire = with_display(watch_quota(quota), 'UTC', now).to_json()

            with self.subTest(deadline=deadline, active=active):
                self.assertEqual(expected, wire['display']['watch_reset'])

    def test_primary_and_secondary_reset_follow_live_time_across_midnight_and_dst(self):
        for start, elapsed, expected in (
                ((2026, 11, 3, 22, 50), 5_280_000, 'Reset in 1h28m, 01:18 Wednesday'),
                ((2026, 3, 29, 0, 30), 7_200_000, 'Reset in 2h, 04:30 today'),
                ((2026, 10, 25, 0, 30), 7_200_000, 'Reset in 2h, 03:30 today'),
                ((2026, 12, 31, 22, 30), 3_600_000, 'Reset in 1h, 00:30 Friday'),
                ((2026, 1, 31, 22, 30), 3_600_000, 'Reset in 1h, 00:30 Sunday')):
            now = int(datetime(*start, tzinfo=timezone.utc).timestamp() * 1000)
            frame = summary_watch()
            item = frame.quota.accounts[0]
            primary = QuotaComponent('5-hour', reset_at_ms=now + elapsed, primary=True)
            secondary = replace(primary, label='Weekly', primary=False)
            item = replace(item, account=replace(item.account, quotas=(primary, secondary), primary_quota_label='5-hour'))
            frame = replace(frame, now_ms=now, quota=replace(frame.quota, accounts=(item,)))

            first = project_live(frame, 'Europe/Stockholm').to_json()['accounts']['accounts'][0]
            next_frame = project_live(replace(frame, now_ms=now + 60_000), 'Europe/Stockholm').to_json()['accounts']['accounts'][0]

            with self.subTest(start=start):
                for slot, updated in ((first['primary'], next_frame['primary']), (first['secondary'][0], next_frame['secondary'][0])):
                    self.assertEqual(expected, slot['display']['watch_reset'])
                    self.assertNotEqual(expected, updated['display']['watch_reset'])
                    self.assertEqual(slot['quota']['display']['reset_at_ms'], updated['quota']['display']['reset_at_ms'])

    def test_web_reset_invalid_deadlines_never_fabricate_calendar_context(self):
        for deadline in (None, True, False, 'invalid', 0, -1, float('nan'), float('inf'), 10**30):
            with self.subTest(deadline=deadline):
                self.assertEqual('Reset unknown', web_quota_reset({'reset_at_ms': deadline}, 'UTC', 1000))
                if isinstance(deadline, float):
                    with self.assertRaises(TypeError):
                        record(reset_at_ms=deadline)
                    continue
                tokens = with_display(record(reset_at_ms=deadline), 'UTC', 1000).to_json()['display']
                self.assertEqual('Reset unknown', tokens['web_reset'])
                self.assertEqual('unknown', tokens['reset_at_ms'])

    def test_owner_fixture_matches_cli_without_reconciling_independent_cost(self):
        frame = summary_watch()
        item = frame.quota.accounts[0]

        wire = project_live(frame).to_json()['accounts']['accounts'][0]['primary']
        cli = ' '.join(str(part) for part in quota_parts(item.account.quotas[0], 'UTC',
            now_ms=frame.now_ms, watch=True))

        self.assertEqual(('2088', '25000', 'AI credits'),
            tuple(wire['quota'][key] for key in ('used', 'limit', 'unit')))
        self.assertEqual(('8.4%', '0.08352', '1814'),
            (wire['used_percent'], wire['used_fraction'], wire['cost']['known_ccost']))
        self.assertEqual('2088/25000 AI credits', wire['quota']['display']['quota_used'])
        self.assertIn('8% used', cli)
        self.assertIn('2088/25000', cli)
        self.assertNotIn('1814', cli)
        usd = with_display(watch_quota(item.account.quotas[0], item.quota_periods[0]),
            ccost_display_unit='usd').to_json()
        self.assertEqual('2088/25000 AI credits', usd['quota']['display']['quota_used'])
        self.assertEqual('$18.14', usd['cost']['display']['account_ccost'])

    def test_special_states_keep_native_observation_and_cost_independent(self):
        known = ComparisonCost(D(1814), 2, 2)
        base = QuotaComponent('Monthly', used=D(2088), limit=D(25000), unit='AI credits')
        cases = (
            ('owner example', QuotaComponent('5 hours', used=D(120), limit=D(750), unit='AI credits'),
                ComparisonCost(D(94), 2, 2), '16%', '120/750 AI credits'),
            ('zero', replace(base, used=D(0)), known, '0%', '0/25000 AI credits'),
            ('49.9%', replace(base, used=D(12475)), known, '49.9%', '12475/25000 AI credits'),
            ('50%', replace(base, used=D(12500)), known, '50%', '12500/25000 AI credits'),
            ('75%', replace(base, used=D(18750)), known, '75%', '18750/25000 AI credits'),
            ('99.9%', replace(base, used=D(24975)), known, '99.9%', '24975/25000 AI credits'),
            ('full', replace(base, used=D(25000)), known, '100%', '25000/25000 AI credits'),
            ('almost', replace(base, used=D('24999.9')), known, '<100%', '25000/25000 AI credits'),
            ('missing limit', replace(base, limit=None), known, '—', '2088 AI credits'),
            ('zero limit', replace(base, limit=D(0)), known, '—', '2088 AI credits'),
            ('unknown used', replace(base, used=None), known, '—', 'N/A/25000 AI credits'),
            ('remaining', replace(base, used=None, remaining=D(22912)), known, '8.4%', '2088/25000 AI credits'),
            ('percent only', QuotaComponent('Weekly', remaining_fraction=D('.58')), known, '42%', 'N/A units'),
            ('unlimited used', replace(base, unlimited=True), known, '—', '2088 AI credits'),
            ('unlimited unknown', replace(base, unlimited=True, used=None), known, '—', 'N/A AI credits'),
            ('unknown cost', base, None, '8.4%', '2088/25000 AI credits'),
            ('empty period', base, ComparisonCost(D(0), 0, 0), '8.4%', '2088/25000 AI credits'),
            ('unpriced period', base, ComparisonCost(D(0), 2, 0), '8.4%', '2088/25000 AI credits'),
            ('partial period', base, ComparisonCost(D(1814), 3, 2), '8.4%', '2088/25000 AI credits'),
            ('estimated period', base, known, '8.4%', '2088/25000 AI credits'),
            ('native money', replace(base, remaining_money=D('91.65'), limit_money=D(100)), known, '8.4%', '2088/25000 AI credits'),
        )
        projected = []
        for name, quota, cost, percent, native in cases:
            with self.subTest(name=name):
                wire = with_display(watch_quota(quota, QuotaPeriodProjection(quota, cost, None),
                    estimated=name == 'estimated period'), now_ms=1000).to_json()
                self.assertEqual(percent, wire['used_percent'])
                self.assertEqual(name == 'full', wire['exhausted'])
                self.assertEqual(native, wire['quota']['display']['quota_used'])
                self.assertEqual(cost is None, wire['cost'] is None)
                if cost is not None:
                    self.assertEqual(cost.complete, wire['cost']['complete'])
                projected.append(dict(name=name, value=wire, native=native, percent=percent))
        if shutil.which('node'):
            payload = dict(state='running', view=project_live(summary_watch()).to_json(), quota_cases=projected)
            result = subprocess.run([shutil.which('node'), 'development/tests/integration/web_watch_summary.cjs'],
                cwd=ROOT, input=json.dumps(payload), text=True, capture_output=True, timeout=15)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_overlapping_windows_same_label_remain_identity_scoped_and_stale(self):
        base = summary_watch().quota.accounts[0]
        primary = QuotaComponent('Weekly', used=D(20), limit=D(100), primary=True, reset_at_ms=1000)
        model = replace(primary, used=D(70), model_id='model', scope='model', primary=False, reset_at_ms=2000)
        native = replace(base.account, quotas=(primary, model), primary_quota_label='Weekly', availability='stale')
        item = replace(base, account=native, quota_periods=(
            QuotaPeriodProjection(model, ComparisonCost(D(9), 1, 1), None),
            QuotaPeriodProjection(primary, ComparisonCost(D(3), 1, 1), None)))

        wire = with_display(watch_account(item)).to_json()

        self.assertEqual('stale', wire['observation']['availability'])
        self.assertEqual(('20%', '3', 1000), (wire['primary']['used_percent'],
            wire['primary']['cost']['known_ccost'], wire['primary']['quota']['reset_at_ms']))
        self.assertEqual(('70%', '9', 2000), (wire['secondary'][0]['used_percent'],
            wire['secondary'][0]['cost']['known_ccost'], wire['secondary'][0]['quota']['reset_at_ms']))
        self.assertEqual('80/100 units', wire['primary']['quota']['quota_display']['remaining']['native'])
        self.assertEqual('30/100 units', wire['secondary'][0]['quota']['quota_display']['remaining']['native'])

    def test_invalid_denominators_are_rejected_at_canonical_boundary(self):
        for limit in (D(-1), D('NaN'), D('Infinity')):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                QuotaComponent('Monthly', used=D(2088), limit=limit)

    def test_provider_restriction_and_unknown_or_unlimited_usage_do_not_invent_exhaustion(self):
        for quota in (QuotaComponent('5-hour', status='blocked'),
                QuotaComponent('Weekly', used=D(100), status='blocked'),
                QuotaComponent('Unlimited', used=D(100), limit=D(100), unlimited=True, status='blocked'),
                QuotaComponent('Almost', used=D('99.999'), limit=D(100), status='blocked')):

            wire = watch_quota(quota).to_json()

            with self.subTest(quota=quota.label):
                self.assertFalse(wire['exhausted'])
                self.assertTrue(wire['restricted'])


if __name__ == '__main__':
    unittest.main()
