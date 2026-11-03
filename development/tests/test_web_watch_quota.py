"""Watch native quota/period CCost independence and canonical display parity."""
from dataclasses import replace
from decimal import Decimal as D
import json
from pathlib import Path
import shutil
import subprocess
import unittest

from development.tests.fixtures.watch_summary import summary_watch
from src.analysis.valuation import ComparisonCost
from src.application.display import with_display
from src.application.live_projection import project_live
from src.application.watch_accounts import watch_account, watch_quota
from src.domain import QuotaComponent
from src.presentation.accounts import quota_parts
from src.reports.models import QuotaPeriodProjection

ROOT = Path(__file__).resolve().parents[2]


class WebWatchQuotaTests(unittest.TestCase):
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
            ('zero', replace(base, used=D(0)), known, '0%', '0/25000 AI credits'),
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
        )
        projected = []
        for name, quota, cost, percent, native in cases:
            with self.subTest(name=name):
                wire = with_display(watch_quota(quota, QuotaPeriodProjection(quota, cost, None),
                    estimated=name == 'estimated period')).to_json()
                self.assertEqual(percent, wire['used_percent'])
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

    def test_invalid_denominators_are_rejected_at_canonical_boundary(self):
        for limit in (D(-1), D('NaN'), D('Infinity')):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                QuotaComponent('Monthly', used=D(2088), limit=limit)


if __name__ == '__main__':
    unittest.main()
