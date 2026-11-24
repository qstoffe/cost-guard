"""Qualified subscription estimates through archive reopen and the shipped Live DTO."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from development.tests.fixtures.account_periods import DAY, HOUR, MONTH, NOW, request, subscription
from development.tests.fixtures.report_runtime import FakePricingProvider
from development.tests.fixtures.watch_summary import summary_watch
from src.analysis.period_ccost import PeriodCCostIndex
from src.application.live_projection import project_live
from src.cache.web_archive import WebArchive
from src.reports.accounts import AccountPeriodHistory
from src.watch.quota_capacity_history import QuotaCapacityHistory


def observed(account, when, **changes):
    return replace(account, fetched_at_ms=when, quotas=tuple(replace(q, **changes) for q in account.quotas))


def idle(account, when):
    return observed(account, when, reset_at_ms=None, window_active=False, remaining_fraction=D(1))


@contextmanager
def open_capacity(directory):
    with ThreadPoolExecutor(max_workers=1) as lane:
        owner = QuotaCapacityHistory(WebArchive(Path(directory)), lane)
        # Drain initial archive recovery without racing the first synthetic frame.
        lane.submit(lambda: None).result(timeout=5)
        yield owner
        owner.flush()


def live_slots(owner, accounts, now, entries=(), *, through=None, start=MONTH):
    catalog = FakePricingProvider().catalog
    history = AccountPeriodHistory(PeriodCCostIndex(entries, catalog.reference_valuation), catalog,
                                   start, now if through is None else through)
    rows = history.project(accounts, now_ms=now, today_start_ms=DAY, month_start_ms=MONTH,
                           timezone_id="UTC", workday_calendar="")
    offers = owner.project(rows, (history,), now)
    base = summary_watch()
    view = project_live(replace(base, now_ms=now, quota=replace(base.quota, accounts=rows),
                                quota_capacity_offers=offers)).to_json()
    return [[slot['quota'] for slot in (row['primary'], *row['secondary'])]
            for row in view['accounts']['accounts']]


class QuotaCapacityHistoryTests(unittest.TestCase):
    def test_separate_account_and_quota_estimates_survive_an_idle_restart(self):
        accounts = []
        for name in ('a', 'b'):
            base = subscription(identity=name)
            short, weekly = base.quotas
            accounts.append(replace(base, primary_quota_label=short.label, quotas=(
                replace(short, remaining_fraction=D('.99')), replace(weekly, remaining_fraction=D('.8')))))
        entries = (request('a', NOW, amount=102410, ref=accounts[0].ref),
                   request('b', NOW, amount=400000, ref=accounts[1].ref))
        empty = tuple(idle(a, NOW + HOUR) for a in accounts)
        with TemporaryDirectory() as directory:
            with open_capacity(directory) as owner:
                cold = live_slots(owner, tuple(idle(a, NOW - HOUR) for a in accounts), NOW - HOUR)
                self.assertTrue(all(q['display']['ccost_capacity'] == '?' for row in cold for q in row))
                live_slots(owner, accounts, NOW, entries)
            with open_capacity(directory) as reopened:
                rows = live_slots(reopened, tuple(reversed(empty)), NOW + HOUR)
                self.assertEqual([[D('1024.1'), D('51.205')], [D(4000), D(200)]],
                                 [[D(q['ccost_reference']['capacity']) for q in row] for row in rows])
                short = rows[0][0]
                self.assertEqual(D('147470.4'), D(short['ccost_reference']['monthly_capacity']))
                self.assertTrue(short['display']['monthly_capacity'].startswith('~'))
                for row in rows:
                    for q in row:
                        self.assertEqual('0%', q['quota_display']['used']['percent'])
                        self.assertEqual('0', q['display']['ccost_used'])
                        self.assertTrue(q['display']['ccost_capacity'].startswith('~'))
                        self.assertIn('earlier qualified', q['display']['capacity_help'])
                changed = replace(empty[0], plan='Different subscription')
                self.assertEqual('?', live_slots(reopened, (changed,), NOW + HOUR)[0][0]['display']['ccost_capacity'])

    def test_new_window_requires_matching_qualified_usage_and_native_capacity_wins(self):
        base = subscription()
        active = replace(base, quotas=(replace(base.quotas[0], remaining_fraction=D('.9')),))
        # A full old window: 100 credits at 10% implies 1000 credits of capacity.
        start = NOW + HOUR
        near = observed(active, start + 60000, reset_at_ms=start + 5 * HOUR, remaining_fraction=D('.9501'))
        at = observed(near, start + 120000, remaining_fraction=D('.95'))
        entries = (request('new', start + 1, amount=200000, ref=active.ref),)
        with TemporaryDirectory() as directory:
            with open_capacity(directory) as owner:
                live_slots(owner, (active,), NOW, (request('old', NOW, ref=active.ref),))
                def capacity(account, usage, **options):
                    q = live_slots(owner, (account,), account.fetched_at_ms, usage, **options)[0][0]
                    return q['display']['ccost_capacity']

                self.assertEqual('~1000', capacity(near, entries))  # 4.99%, though displayed as 5%
                for extra in ((request('unassigned', start + 2),),
                              (request('unpriced', start + 2, model='no-price', ref=active.ref),)):
                    self.assertEqual('~1000', capacity(at, entries + extra))
                self.assertEqual('~1000', capacity(at, entries, through=at.fetched_at_ms - 1))
                self.assertEqual('~1000', capacity(at, entries, start=start + 1))
                self.assertEqual('~400', capacity(at, entries))  # 20 credits at 5%
                native = observed(at, at.fetched_at_ms + 1, reference_ccost_capacity=D(731))
                self.assertEqual('731', capacity(native, entries))
                self.assertEqual('?', capacity(replace(at, availability='stale'), entries))
            with open_capacity(directory) as reopened:
                reset = idle(at, start + 5 * HOUR)
                self.assertEqual('~400', live_slots(reopened, (reset,), reset.fetched_at_ms)[0][0]['display']['ccost_capacity'])
