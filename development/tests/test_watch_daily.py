"""Full-day request population, causal prompt count and coherent Web publication."""
from concurrent.futures import Future
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path
import json
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from development.tests.fixtures.watch_runtime import make_service
from development.tests.fixtures.watch_summary import summary_watch
from src.accounts.base import normalize_quota
from src.accounts.openai_subscription import convert_usage_payload
from src.analysis.daily_usage import daily_usage, prompt_attributions, request_identity
from src.analysis.models import TraceEntry
from src.analysis.timezones import local_day_start_ms
from src.application.live_projection import project_live
from src.application.watch_accounts import primary_quota, watch_account, watch_quota
from src.domain import AccountRef, ModelRef, QuotaComponent, TokenUsage
from src.reports.history import WatchHistoryAcquisition
from src.presentation.accounts import account_capacity_parts
from src.sources.errors import transport_failure, http_failure
from src.watch.web_coordinator import WebWatchCoordinator
from src.watch.accounts import reconcile_accounts

ROOT = Path(__file__).resolve().parents[2]


def entry(message, when=100, *, session="root", model="priced", step=None):
    return TraceEntry(session, "user", message, step, when, 0, ModelRef("provider", model), None,
        TokenUsage(input=10, cache_read=5, cache_write=2, output=3, reasoning=1), source_instance="source")


def categories(model, tokens):
    if model.model == "unknown":
        return None
    factor = 2 if model.model == "tier" and tokens.input >= 10 else 1
    return tuple(D(value * factor) for value in
        (tokens.input, tokens.cache_read, tokens.cache_write, tokens.output + tokens.reasoning))


def total(model, tokens):
    parts = categories(model, tokens)
    return None if parts is None else sum(parts)


def project(entries, mapping, *, now=1000, day=0):
    return daily_usage(entries, mapping, day_start_ms=day, now_ms=now,
        valuation=total, category_valuation=categories)


class WatchDailyTests(unittest.TestCase):
    def test_full_population_per_request_tiers_and_causal_prompt_count(self):
        records = tuple(entry(str(index), 100 + index, session=f"session-{index // 2}", model="tier" if index % 2 else "priced")
                        for index in range(24))
        mapping = {request_identity(item): ("source", item.session_id, "initiator") for item in records}
        # A cloned physical request and an attributed child repeated in another view add nothing.
        child = entry("child", 150, session="child")
        records += (child, replace(records[0], session_id="fork"))
        mapping[request_identity(child)] = mapping[request_identity(records[0])]
        mapping[request_identity(records[-1])] = mapping[request_identity(records[0])]
        result = project(records, mapping)
        self.assertEqual(12, result.prompt_count)
        self.assertEqual(25, result.mix.request_count)
        self.assertEqual((D(370), D(185), D(74), D(148)), result.mix.costs)
        self.assertEqual(D(777), result.total.known_ccost)
        self.assertEqual(result.total.known_ccost, sum(result.mix.costs))
        self.assertEqual(100, sum(result.mix.percentages))

    def test_compaction_is_known_non_prompt_missing_attribution_is_partial(self):
        normal, child, compact, orphan = (entry(name) for name in ("normal", "child", "compact", "orphan"))
        prompt = SimpleNamespace(prompt_kind="prompt", session_id="root", prompt_id="initiator", entries=(normal, child))
        bundle = SimpleNamespace(prompts=(prompt,), compactions=(SimpleNamespace(entries=(compact,)),))
        mapping = prompt_attributions(bundle)
        result = project((normal, child, compact, orphan), mapping)
        self.assertEqual((1, False, 4, D(84)),
            (result.prompt_count, result.prompt_count_complete, result.mix.request_count, result.total.ccost))
        self.assertIsNone(mapping[request_identity(compact)])

    def test_unknown_prices_and_telemetry_remain_in_mix_and_total(self):
        known, unknown = entry("known"), entry("unknown", model="unknown")
        partial = replace(entry("partial"), tokens=TokenUsage(input=10, known_fields=("input",)))
        result = project((known, unknown, partial), {})
        self.assertEqual(3, result.mix.request_count)
        self.assertEqual(2, result.mix.priced_requests)
        self.assertFalse(result.mix.cost_complete)
        self.assertIsNone(result.mix.total_tokens)
        self.assertEqual((None,) * 4, result.mix.percentages)
        self.assertEqual(result.total.known_ccost, sum(result.mix.costs))
        self.assertFalse(result.prompt_count_complete)

    def test_cross_midnight_dst_and_zero_day(self):
        now = int(datetime(2026, 3, 29, 12, tzinfo=timezone.utc).timestamp() * 1000)
        day = local_day_start_ms("Europe/Stockholm", now_ms=now)
        yesterday, today = entry("yesterday", day - 1), entry("today", day)
        mapping = {request_identity(item): ("source", "root", "continuing") for item in (yesterday, today)}
        result = project((yesterday, today), mapping, now=now, day=day)
        self.assertEqual((1, 1, D(21)), (result.prompt_count, result.mix.request_count, result.total.ccost))
        zero = project((yesterday,), mapping, now=now, day=day)
        self.assertEqual((0, 0, D(0), True),
            (zero.prompt_count, zero.mix.request_count, zero.total.ccost, zero.prompt_count_complete))

    def test_retention_reconciliation_steps_and_prompt_identity_share_one_population(self):
        history = WatchHistoryAcquisition()
        history.scope_start_ms = history.day_start_ms = 0
        def record(entries):
            prompt = SimpleNamespace(prompt_kind="prompt", session_id="root", prompt_id="user", entries=entries)
            history.record("root", SimpleNamespace(trace_entries=entries, prompts=(prompt,), compactions=(),
                cacheable=False), now_ms=1000)
            history.entries()
        record((entry("message"),))
        record((entry("message", step="step-1"), entry("message", step="step-2")))
        record(())
        result = project(history.retained_entries(), history.prompt_of)
        self.assertEqual((1, 2, D(42)), (result.prompt_count, result.mix.request_count, result.total.ccost))
        self.assertTrue(result.prompt_count_complete)

    def test_background_lane_retains_history_and_does_not_rehydrate_unchanged_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = SyntheticMonthSource(8, 8, month_start_ms=1000)
            config, selection, service, _ = make_service(tmp, source, now_ms=80_000_000)
            def factory(now):
                return make_service(tmp, source, now_ms=now)[2]
            owner = WebWatchCoordinator(selection=selection, report_service=service, config=config, service_factory=factory)
            self.addCleanup(owner.close)
            sessions = source.list_sessions()
            first = owner._account_history(sessions, (), 80_000_000)
            self.assertEqual(64, first[1].prompt_count)
            self.assertEqual(64, first[1].mix.request_count)
            loads = source.load_count
            second = owner._account_history(sessions, (), 80_000_001)
            self.assertEqual(loads, source.load_count)
            second = owner._account_history((), (), 80_000_002)
            self.assertEqual(first[1].total, second[1].total)
            self.assertEqual(first[1].mix, second[1].mix)
            self.assertEqual(first[1].prompt_count, second[1].prompt_count)

    def test_watch_quota_primary_stability_accuracy_and_unlimited(self):
        native = summary_watch().quota.accounts[1].account
        primary = primary_quota(native)
        self.assertEqual("5-hour", primary.label)
        missing = primary_quota(replace(native, quotas=(native.quotas[1],)))
        self.assertEqual(("5-hour", None), (missing.label, missing.remaining_fraction))
        for remaining, expected in ((".75", "25%"), (".00001", "<100%"), (".001", "99.9%"), ("0", "100%")):
            wire = watch_quota(replace(primary, remaining_fraction=D(remaining))).to_json()
            self.assertEqual(expected, wire['used_percent'])
        self.assertIsNone(watch_quota(replace(primary, unlimited=True)).to_json()['used_fraction'])
        explicit = replace(native, primary_quota_label='Monthly', quotas=(native.quotas[1],))
        self.assertEqual('Monthly', primary_quota(explicit).label)
        self.assertIsNone(primary_quota(explicit).remaining_fraction)

    def test_native_month_background_history_includes_pre_watch_and_reuses_stable_roots(self):
        start = int(datetime(2026, 10, 1, tzinfo=timezone.utc).timestamp() * 1000)
        now = int(datetime(2026, 10, 25, 12, tzinfo=timezone.utc).timestamp() * 1000)
        monthly = QuotaComponent('Monthly', 'fixed', remaining=D(100),
            reset_at_ms=int(datetime(2026, 11, 1, tzinfo=timezone.utc).timestamp() * 1000))
        native = replace(summary_watch().quota.accounts[0].account, quotas=(monthly,))
        with tempfile.TemporaryDirectory() as tmp:
            source = SyntheticMonthSource(4, 3, month_start_ms=start, today_roots=1, now_ms=now)
            config, selection, service, _ = make_service(tmp, source, now_ms=now)
            owner = WebWatchCoordinator(selection=selection, report_service=service, config=config,
                service_factory=lambda clock: make_service(tmp, source, now_ms=clock)[2])
            self.addCleanup(owner.close)

            history, today = owner._account_history(source.list_sessions(), (native,), now)
            loads = source.load_count
            owner._account_history(source.list_sessions(), (native,), now + 1)
            row = history.project((native,), now_ms=now, today_start_ms=local_day_start_ms('UTC', now_ms=now),
                month_start_ms=start, timezone_id='UTC', workday_calendar='')[0]

            self.assertEqual(start, history.observed_start_ms)
            self.assertEqual(3, today.mix.request_count)
            self.assertEqual(12, row.quota_periods[0].cost.observed_requests)
            self.assertEqual(loads, source.load_count)

    def test_previous_day_background_result_cannot_repopulate_new_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = SyntheticMonthSource(1, 1, month_start_ms=1000)
            config, selection, service, _ = make_service(tmp, source, now_ms=80_000_000)
            owner = WebWatchCoordinator(selection=selection, report_service=service, config=config,
                service_factory=lambda now: make_service(tmp, source, now_ms=now)[2])
            self.addCleanup(owner.close)
            yesterday = owner._account_history(source.list_sessions(), (), 80_000_000)
            completed = Future(); completed.set_result(yesterday)
            owner.history_job = completed
            pending = Future()
            observation = SimpleNamespace(revisions={}, sessions=(), active_candidates=frozenset(), live_candidates=frozenset())
            with patch.object(owner.accounts, 'refresh', return_value=False), patch.object(owner.history_pool, 'submit', return_value=pending) as submit:
                owner._refresh_quota(observation, now_ms=86_400_001)
            self.assertIsNone(owner.daily_usage)
            self.assertIsNone(owner.history_quota)
            self.assertEqual(86_400_001, submit.call_args.args[3])
            pending.cancel()

    def test_daily_failure_confirmation_retains_observation_and_retries_on_existing_lane(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = SyntheticMonthSource(1, 1, month_start_ms=1000)
            config, selection, service, _ = make_service(tmp, source, now_ms=80_000_000)
            clock = [0.0]
            owner = WebWatchCoordinator(selection=selection, report_service=service, config=config,
                service_factory=lambda now: make_service(tmp, source, now_ms=now)[2], monotonic=lambda: clock[0])
            self.addCleanup(owner.close)
            observed = owner._account_history(source.list_sessions(), (), 80_000_000)
            owner.history_quota, owner.daily_usage = observed
            observation = SimpleNamespace(revisions={}, sessions=(), active_candidates=frozenset(), live_candidates=frozenset())
            owner.history_revision = ()
            owner.history_due_ms = 80_060_000
            failure = transport_failure(TimeoutError(), phase='daily')
            with patch.object(owner, 'history_factory', side_effect=failure):
                failure = owner._account_history(source.list_sessions(), (), 80_000_001)
            self.assertEqual('connection_timeout', failure.code.value)
            pending = Future()
            with patch.object(owner.accounts, 'refresh', return_value=False), patch.object(
                    owner.history_pool, 'submit', return_value=pending) as submit:
                for seconds in (0, 4, 5):
                    clock[0] = seconds
                    completed = Future(); completed.set_result(failure)
                    owner.history_job = completed
                    owner._refresh_quota(observation, now_ms=80_000_000 + seconds * 1000)
                    frame = owner._build_projection(now_ms=80_000_000 + seconds * 1000)
                    self.assertEqual('retrying' if seconds < 5 else 'unavailable', frame.daily_state)
                    self.assertEqual(observed[1], frame.daily_usage)
                submit.assert_called_once()
                self.assertEqual(80_005_000, submit.call_args.args[3])
                completed = Future(); completed.set_result(observed)
                owner.history_job = completed
                owner._refresh_quota(observation, now_ms=80_005_001)
                self.assertIsNone(owner.daily_status.state(retained=True))
            pending.cancel()
            owner.daily_status.fail(http_failure(403, phase='daily'))
            self.assertEqual('unavailable', owner._build_projection(now_ms=80_005_002).daily_state)

    def test_native_weekly_primary_matches_cli_population_and_is_not_duplicated(self):
        payload = {"plan_type": "pro_lite", "rate_limit": {"primary_window": {
            "limit_window_seconds": 604800, "used_percent": 42, "reset_after_seconds": 1000}},
            "additional_rate_limits": [{"limit_name": "Model", "model_id": "test",
                "rate_limit": {"primary_window": {"limit_window_seconds": 18000, "used_percent": 99}}}]}
        snapshot = convert_usage_payload(payload, fetched_at_ms=1000)
        native = normalize_quota(snapshot, AccountRef("fixture", "openai", account_id="weekly"), "OpenAI Pro Lite")
        projection = replace(summary_watch().quota.accounts[0], account=native)

        wire = watch_account(projection).to_json()

        self.assertEqual("weekly", native.primary_quota_label)
        self.assertTrue(native.quotas[0].primary)
        self.assertIs(primary_quota(native), native.quotas[0])
        self.assertEqual("weekly", wire['primary']['quota']['label'])
        self.assertEqual("42%", wire['primary']['used_percent'])
        self.assertEqual(["Model 5-hour"], [item['quota']['label'] for item in wire['secondary']])
        self.assertEqual(["weekly"], [item.label for item in native.quotas if item.scope == "account"])
        self.assertEqual(1001000, wire['primary']['quota']['reset_at_ms'])
        cli = " ".join(str(part) for part in account_capacity_parts(replace(projection, pace=()), "UTC", now_ms=1000))
        self.assertIn("Week", cli)
        self.assertNotIn("5h", cli)
        # Provider identity and depletion never invent/promote an account window.
        self.assertEqual("weekly", primary_quota(replace(native, primary_quota_label=None, quotas=tuple(reversed(native.quotas)))).label)
        self.assertEqual("Primary quota", primary_quota(replace(native, primary_quota_label=None, quotas=(native.quotas[1],))).label)

    def test_native_primary_order_and_partial_error_contract_stability(self):
        def native(rate, when):
            return normalize_quota(convert_usage_payload({"rate_limit": rate}, fetched_at_ms=when),
                AccountRef("fixture", "openai", account_id="both"), "OpenAI")
        five = {"limit_window_seconds": 18000, "used_percent": 10}
        weekly = {"limit_window_seconds": 604800, "used_percent": 90}
        prior = native({"primary_window": five, "secondary_window": weekly}, 1000)
        partial = native({"secondary_window": weekly}, 2000)

        reconciled, _, _ = reconcile_accounts((prior,), (partial,), {prior.key: 1000}, now_ms=2000)

        self.assertEqual("partial", partial.availability)
        self.assertEqual(("5-hour", None), (primary_quota(reconciled[0]).label, primary_quota(reconciled[0]).remaining_fraction))
        self.assertEqual("weekly", reconciled[0].quotas[0].label)
        error = replace(partial, quotas=(), primary_quota_label=None, availability="error")
        failed, _, _ = reconcile_accounts(reconciled, (error,), {prior.key: 1000}, now_ms=3000)
        self.assertEqual(("5-hour", None), (primary_quota(failed[0]).label, primary_quota(failed[0]).remaining_fraction))
        # A newly explicit native contract wins, even if its usage is missing.
        changed = native({"primary_window": {"limit_window_seconds": 604800}}, 4000)
        updated, _, _ = reconcile_accounts(failed, (changed,), {prior.key: 1000}, now_ms=4000)
        self.assertEqual("weekly", primary_quota(updated[0]).label)
        self.assertEqual("5-hour", primary_quota(replace(prior, quotas=tuple(reversed(prior.quotas)))).label)
        self.assertEqual("5-hour", primary_quota(replace(prior, primary_quota_label=None, quotas=tuple(reversed(prior.quotas)))).label)

    @unittest.skipUnless(shutil.which('node'), 'node unavailable')
    def test_daily_and_account_dom_uses_canonical_display_units_and_warning_footers(self):
        payload = {'state': 'running', 'view': project_live(summary_watch()).to_json()}
        result = subprocess.run([shutil.which('node'), 'development/tests/integration/web_watch_summary.cjs'],
            cwd=ROOT, input=json.dumps(payload), text=True, capture_output=True, timeout=15)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
