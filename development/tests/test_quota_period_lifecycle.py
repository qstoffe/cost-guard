"""Native-period lifecycle truth shared by CLI, Web and delayed history publication."""
from concurrent.futures import Future
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace
import json
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from development.tests.fixtures.account_periods import DAY, MONTH, NOW, HOUR, project, request, subscription
from development.tests.fixtures.quota_rendering import quotas, report_text, watch_text
from development.tests.fixtures.report_runtime import FakePricingProvider
from development.tests.fixtures.watch_runtime import MutableSource, make_service
from development.tests.fixtures.watch_summary import summary_watch
from src.analysis.period_ccost import monthly_quota_window, quota_window
from src.accounts.acquisition import AccountUpdate
from src.application.display import with_display
from src.application.projection import account
from src.application.watch_accounts import watch_account
from src.domain import QuotaComponent
from src.domain.acquisition import AcquisitionMetrics
from src.numbers import ccost_display
from src.presentation.accounts import capacity_lines
from src.presentation.terminal import AnsiStyler
from src.reports.accounts import WatchAccountProjection, account_projections
from src.watch.accounts import reconcile_accounts
from src.watch.account_refresh import WatchAccountRefresh
from src.watch.coordinator import WatchCoordinator
from src.watch.web_coordinator import WebWatchCoordinator

ROOT = Path(__file__).resolve().parents[2]


def empty(component):
    return replace(component, window_active=False, reset_at_ms=None, used=D(0), remaining_fraction=D(1))


class QuotaPeriodLifecycleTests(unittest.TestCase):
    def test_reported_604_never_decays_in_empty_period_or_erases_today(self):
        native = subscription()
        native = replace(native, quotas=(empty(native.quotas[0]), native.quotas[1]))
        prior = request("previous-period", NOW - 4 * HOUR, amount=6_040_000)
        for minute in (0, 1, 30, 61, 120):
            row = project((native,), (prior,), now_ms=NOW + minute * 60_000)[0]
            scopes = dict(row.ccost_scopes)
            self.assertEqual((D(0), D(604)), (scopes["5-hour"].ccost, scopes["today"].ccost))
            self.assertNotIn("5-hour", row.ccost_estimated_scopes)
            dto = with_display(account(row), now_ms=NOW).to_json()
            wire = {scope["name"]: scope["cost"] for scope in dto["ccost_scopes"]}
            self.assertEqual("0", wire["5-hour"]["display"]["account_ccost"])
            self.assertEqual("604", wire["today"]["display"]["account_ccost"])
        row = project((native,), (prior,))[0]
        for width in (65, 160):
            for unit, expected in (("credits", "0"), ("usd", "$0.00")):
                with ccost_display(unit):
                    text = "\n".join(capacity_lines(row, AnsiStyler({}, enabled=False), "UTC",
                                                  width=width, now_ms=NOW, watch=True))
                    self.assertIn(f"0% used ({expected})", text)
                    self.assertIn("not started", " ".join(text.split()))
            for text in (report_text(replace(quotas(row), now_ms=NOW), width=width),
                         watch_text(replace(quotas(row), now_ms=NOW), width=width)):
                self.assertIn("0% used (0)", text)

    def test_empty_zero_is_provider_evidence_not_history_or_account_guess(self):
        one, two = subscription(), subscription(identity="two")
        one = replace(one, quotas=(empty(one.quotas[0]),))
        two = replace(two, quotas=(empty(two.quotas[0]),))
        for row in project((one, two), (request("unassigned", NOW),)):
            self.assertEqual(D(0), dict(row.ccost_scopes)["5-hour"].ccost)
            self.assertIsNone(dict(row.ccost_scopes)["today"])
        self.assertEqual(D(0), dict(project((one,), ())[0].ccost_scopes)["5-hour"].ccost)
        before_history = WatchAccountProjection(AcquisitionMetrics()).project((one,), (), FakePricingProvider().catalog,
            now_ms=NOW, day_start_ms=DAY, month_start_ms=MONTH, timezone_id="UTC", workday_calendar="")[0]
        self.assertEqual(D(0), dict(before_history.accounts[0].ccost_scopes)["5-hour"].ccost)
        self.assertIsNone(dict(before_history.accounts[0].ccost_scopes)["today"])

    def test_unknown_stale_and_contradictory_are_never_confirmed_zero(self):
        native = subscription()
        inactive = empty(native.quotas[0])
        for changes in ({"reset_at_ms": NOW + HOUR}, {"used": D(1)},
                        {"remaining_fraction": D(".99")}, {"origin": "estimated"},
                        {"remaining": D(5), "limit": D(10)}, {"scope": "unsupported"},
                        {"window_active": None}, {"scope": "model", "model_id": None}):
            with self.subTest(changes=changes):
                component = replace(inactive, **changes)
                self.assertIsNone(quota_window(component, NOW))
                row = project((replace(native, quotas=(component,)),), (), observed_start_ms=MONTH)[0]
                self.assertIsNone(dict(row.ccost_scopes)["5-hour"])
        for availability in ("stale", "error", "unavailable"):
            row = project((replace(native, quotas=(inactive,), availability=availability),),
                          (request("today", NOW),), observed_start_ms=MONTH)[0]
            self.assertIsNone(dict(row.ccost_scopes)["5-hour"])
            self.assertEqual(D(100), dict(row.ccost_scopes)["today"].ccost)

    def test_active_rounded_zero_keeps_exact_start_dedup_and_pre_watch_usage(self):
        native = subscription()
        start = NOW - 4 * HOUR
        first = request("at-start", start, ref=native.ref)
        entries = (request("before", start - 1, ref=native.ref), first,
                   replace(first, session_id="fork"), request("at-now", NOW, ref=native.ref),
                   request("future", NOW + 1, ref=native.ref))
        row = project((native,), entries)[0]
        self.assertEqual((D(200), 2), (dict(row.ccost_scopes)["5-hour"].ccost,
                                     dict(row.ccost_scopes)["5-hour"].observed_requests))
        self.assertIn("0% used (200)", watch_text(replace(quotas(row), now_ms=NOW), width=160))

    def test_reset_lifecycle_weekly_independence_and_cached_history_rebinding(self):
        native = subscription()
        native = replace(native, quotas=(native.quotas[0], replace(native.quotas[1], reset_at_ms=NOW + 24 * HOUR)))
        entries = (request("old", NOW - HOUR, ref=native.ref), request("new", NOW + HOUR, ref=native.ref))
        projector = WatchAccountProjection(AcquisitionMetrics())
        options = dict(day_start_ms=DAY, month_start_ms=MONTH, timezone_id="UTC", workday_calendar="",
                       observed_start_ms=MONTH)
        initial = projector.project((native,), entries, FakePricingProvider().catalog, now_ms=NOW, **options)[0]
        self.assertEqual(D(100), dict(initial.accounts[0].ccost_scopes)["5-hour"].ccost)
        snapshot = projector.history
        reset = NOW + HOUR
        inactive = replace(native, fetched_at_ms=reset, quotas=(empty(native.quotas[0]), native.quotas[1]))
        active = replace(inactive, quotas=(replace(native.quotas[0], reset_at_ms=reset + 5 * HOUR), native.quotas[1]))
        for state, expected in ((native, None), (inactive, D(0)), (inactive, D(0)), (active, D(100))):
            row = snapshot.project((state,), now_ms=reset, today_start_ms=DAY, month_start_ms=MONTH,
                                   timezone_id="UTC", workday_calendar="")[0]
            value = dict(row.ccost_scopes)["5-hour"]
            self.assertEqual(expected, None if value is None else value.ccost)
            self.assertEqual(D(200), dict(row.ccost_scopes)["weekly"].ccost)
        other = replace(active, ref=subscription(identity="other").ref)
        self.assertEqual(D(0), dict(snapshot.project((other,), now_ms=reset, today_start_ms=DAY,
            month_start_ms=MONTH, timezone_id="UTC", workday_calendar="")[0].ccost_scopes)["5-hour"].ccost)

    def test_weekly_only_and_model_periods_never_invent_five_hours(self):
        native = subscription()
        weekly = native.quotas[1]
        history = (request("model", NOW, ref=native.ref), request("other-model", NOW, model="claude-test", ref=native.ref))
        for component, expected in ((empty(weekly), D(0)), (weekly, D(300)),
                (replace(weekly, scope="model", model_id="gpt-test"), D(100))):
            row = project((replace(native, quotas=(component,)),), history)[0]
            self.assertEqual(expected, dict(row.ccost_scopes)["weekly"].ccost)
            self.assertNotIn("5-hour", dict(row.ccost_scopes))

    def test_monthly_native_rollover_remains_distinct_from_daily_and_local_month(self):
        def at(year, month, day=1, hour=0):
            return int(datetime(year, month, day, hour, tzinfo=timezone.utc).timestamp() * 1000)
        now, reset = at(2026, 12, 31, 23), at(2027, 1)
        monthly = QuotaComponent("Monthly", "fixed", reset_at_ms=reset)
        self.assertEqual((at(2026, 12), now + 1), monthly_quota_window(monthly, now))
        self.assertIsNone(monthly_quota_window(monthly, reset))
        january = replace(monthly, reset_at_ms=at(2027, 2))
        self.assertEqual((reset, reset + 1), monthly_quota_window(january, reset))
        for changes in ({"reset_at_ms": at(2027, 2, 15)}, {"window_active": False}, {"reset_at_ms": None}):
            self.assertIsNone(monthly_quota_window(replace(monthly, **changes), now))
        native = replace(subscription("github-copilot"), quotas=(monthly,))
        row = project((native,), (request("local-month", MONTH, provider="github-copilot"),
                                 request("today", NOW, provider="github-copilot")))[0]
        self.assertEqual((D(100), D(200)), tuple(dict(row.ccost_scopes)[name].ccost for name in ("today", "this month")))
        self.assertNotIn("Monthly", dict(row.ccost_scopes))  # CLI monthly fields intentionally say Today.

    def test_delayed_native_observation_and_partial_reset_cannot_restore_old_window(self):
        old = subscription()
        current = replace(old, fetched_at_ms=NOW + 1, quotas=(empty(old.quotas[0]), old.quotas[1]))
        rows, seen, _ = reconcile_accounts((current,), (old,), {current.key: NOW + 1}, now_ms=NOW + 2)
        self.assertEqual((current,), rows)
        self.assertEqual(NOW + 1, seen[current.key])
        partial = replace(current, availability="partial")
        rows, _, _ = reconcile_accounts((old,), (partial,), {old.key: NOW}, now_ms=NOW + 1)
        self.assertIsNone(rows[0].quotas[0].reset_at_ms)
        self.assertEqual("partial", rows[0].availability)

    def test_watch_native_month_has_its_own_history_cost_and_canonical_pace(self):
        start = int(datetime(2026, 10, 1, tzinfo=timezone.utc).timestamp() * 1000)
        reset = int(datetime(2026, 11, 1, tzinfo=timezone.utc).timestamp() * 1000)
        monthly = QuotaComponent('Monthly', 'fixed', used=D(22), remaining=D(78), limit=D(100),
                                 unit='AI credits', reset_at_ms=reset)
        native = replace(subscription('github-copilot'), quotas=(monthly,))
        first = request('month-start', start, provider='github-copilot', ref=native.ref)
        entries = (request('before', start - 1, provider='github-copilot', ref=native.ref), first,
                   replace(first, session_id='fork'), request('today', NOW, provider='github-copilot', ref=native.ref))

        row = project((native,), entries, watch=True, observed_start_ms=start)[0]
        wire = with_display(watch_account(row), now_ms=NOW).to_json()

        self.assertEqual(D(100), dict(row.ccost_scopes)['today'].ccost)
        self.assertEqual(D(200), row.quota_periods[0].cost.ccost)
        self.assertIs(row.pace[0], row.quota_periods[0].pace)
        self.assertEqual('200', wire['primary']['cost']['display']['account_ccost'])
        self.assertEqual('11', wire['primary']['pace']['display']['per_day'])  # 78 / 7, rounded down by CLI.
        reference = wire['primary']['quota']['ccost_pace']
        self.assertEqual(str(D(78) / 7), reference['ccost_per_day'])
        self.assertEqual('$0.11', reference['display_units']['usd']['ccost_per_day'])
        self.assertEqual([], wire['secondary'])
        # Partial daily acquisition must not claim the full month or erase Today.
        pending = account_projections((native,), entries, FakePricingProvider().catalog, now_ms=NOW,
            today_start_ms=DAY, month_start_ms=MONTH, watch=True, observed_start_ms=DAY, require_history=True)[0]
        self.assertIsNone(pending.quota_periods[0].cost)
        self.assertEqual(D(100), dict(pending.ccost_scopes)['today'].ccost)
        self.assertEqual((), project((native,), entries)[0].quota_periods)  # Ordinary Accounts is unchanged.

    def test_watch_month_unknown_stale_empty_and_rollover_rebind_without_old_cost(self):
        start = int(datetime(2026, 10, 1, tzinfo=timezone.utc).timestamp() * 1000)
        reset = int(datetime(2026, 11, 1, tzinfo=timezone.utc).timestamp() * 1000)
        monthly = QuotaComponent('Monthly', 'fixed', reset_at_ms=reset, used=D(0), remaining_fraction=D(1))
        native = replace(subscription('github-copilot'), quotas=(monthly,))
        entries = (request('old', NOW, provider='github-copilot', ref=native.ref),)
        projector = WatchAccountProjection(AcquisitionMetrics())
        projector.project((native,), entries, FakePricingProvider().catalog, now_ms=NOW,
            day_start_ms=DAY, month_start_ms=MONTH, timezone_id='UTC', workday_calendar='', observed_start_ms=start)
        for component, availability, expected in ((monthly, 'available', D(100)),
                (monthly, 'stale', None), (replace(monthly, reset_at_ms=reset + HOUR), 'available', None),
                (empty(monthly), 'available', D(0)), (replace(monthly, reset_at_ms=None), 'available', None)):
            row = projector.history.project((replace(native, quotas=(component,), availability=availability),),
                now_ms=NOW, today_start_ms=DAY, month_start_ms=MONTH, timezone_id='UTC', workday_calendar='')[0]
            cost = row.quota_periods[0].cost
            self.assertEqual(expected, None if cost is None else cost.ccost)
        new_month = replace(monthly, reset_at_ms=int(datetime(2026, 12, 1, tzinfo=timezone.utc).timestamp() * 1000))
        row = projector.history.project((replace(native, quotas=(new_month,)),), now_ms=reset,
            today_start_ms=reset, month_start_ms=reset, timezone_id='UTC', workday_calendar='')[0]
        self.assertEqual(D(0), row.quota_periods[0].cost.ccost)

    def test_watch_duplicate_quota_labels_keep_model_specific_cost_associations(self):
        native = subscription()
        account_quota = replace(native.quotas[0], label='Shared')
        model_quota = replace(account_quota, scope='model', model_id='gpt-test')
        native = replace(native, quotas=(account_quota, model_quota))
        entries = (request('one', NOW, ref=native.ref), request('two', NOW, model='claude-test', ref=native.ref))

        row = project((native,), entries, watch=True, observed_start_ms=MONTH)[0]
        wire = with_display(watch_account(row), now_ms=NOW).to_json()

        self.assertEqual('300', wire['primary']['cost']['display']['account_ccost'])
        self.assertEqual('100', wire['secondary'][0]['cost']['display']['account_ccost'])

    def test_old_account_mailbox_does_not_regress_successful_observation_epoch(self):
        old = subscription()
        current = replace(old, fetched_at_ms=NOW + 1, quotas=(empty(old.quotas[0]), old.quotas[1]))
        refresh = WatchAccountRefresh(SimpleNamespace(), clock_ms=lambda: NOW + 2, monotonic=lambda: 0)
        refresh.snapshots = (current,)
        refresh.seen_ms = {current.key: NOW + 1}
        update = AccountUpdate((old,), (old.key,), ((old.key, NOW),))

        refresh._publish(update)

        self.assertEqual((current,), refresh.snapshots)
        self.assertEqual(NOW + 1, refresh.seen_ms[current.key])

    def test_delayed_web_history_reprojects_current_account_and_keeps_today(self):
        old = subscription()
        projector = WatchAccountProjection(AcquisitionMetrics())
        projector.project((old,), (request("old", NOW - HOUR, amount=6_040_000),), FakePricingProvider().catalog,
            now_ms=NOW, day_start_ms=DAY, month_start_ms=MONTH, timezone_id="Europe/Stockholm", workday_calendar="",
            observed_start_ms=MONTH)
        current = replace(old, quotas=(empty(old.quotas[0]), old.quotas[1]))
        with tempfile.TemporaryDirectory() as tmp:
            config, selection, service, _ = make_service(tmp, MutableSource(), now_ms=NOW)
            service.config["timezone"] = "Europe/Stockholm"
            owner = WebWatchCoordinator(selection=selection, report_service=service, config=config,
                                       service_factory=lambda now: None)
            self.addCleanup(owner.close)
            owner.accounts.snapshots = (current,)
            completed = Future()
            completed.set_result((projector.history, SimpleNamespace(day_start_ms=DAY)))
            owner.history_job = completed
            owner.history_due_ms = NOW + HOUR
            observation = SimpleNamespace(revisions={}, sessions=(), active_candidates=(), live_candidates=())
            owner.history_revision = ()
            with patch.object(owner.accounts, "refresh", return_value=True):
                owner._refresh_quota(observation, now_ms=NOW)
            base = replace(summary_watch(), quota=owner.quota)
            with patch.object(WatchCoordinator, "_build_projection", return_value=base), \
                    patch.object(owner.cards, "tick"), patch.object(owner.cards, "project", return_value=((), (), "observed")):
                frame = owner._build_projection(now_ms=NOW)
            scopes = dict(frame.quota.accounts[0].ccost_scopes)
            self.assertEqual((D(0), D(604)), (scopes["5-hour"].ccost, scopes["today"].ccost))

    @unittest.skipUnless(shutil.which("node"), "optional JS VM unavailable")
    def test_web_accounts_render_zero_period_and_nonzero_today(self):
        native = subscription()
        native = replace(native, quotas=(empty(native.quotas[0]),))
        row = project((native,), (request("old", NOW - HOUR, amount=6_040_000),))[0]
        dto = with_display(account(row), now_ms=NOW).to_json()
        result = subprocess.run(["node", "development/tests/integration/web_period_ccost.cjs"], input=json.dumps(dto),
            text=True, capture_output=True, cwd=ROOT, timeout=10)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
