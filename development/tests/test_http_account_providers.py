"""Documentation-based OpenRouter/DeepSeek/MiniMax fixtures and shared lifecycle."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from development.tests.test_analysis_core import make_snapshot
from development.tests.test_step7_reports_cli import FakePricingProvider
from development.tests.test_step8_watch import MutableSource, make_service
from src.accounts.credentials import CredentialRecord
from src.accounts.diagnostics import sanitized_account_observation
from src.accounts.http_transport import AccountHttpResponse
from src.accounts.minimax import MiniMaxAccountProvider, GLOBAL_ENDPOINT, CN_ENDPOINT, normalize_minimax_account
from src.accounts.simple_http import DEEPSEEK, OPENROUTER, SIMPLE_HTTP_PROVIDERS, SimpleHttpAccountProvider
from src.accounts.simple_http_mapping import normalize_simple_account
from src.bootstrap import _account_providers
from src.config import ConfigError, load_configuration, read_jsonc, validate_configuration
from src.domain import AccountRef, AccountSnapshot, AccountUsageStatus
from src.presentation import ReportRenderer, WatchRenderer
from src.presentation.accounts import capacity_lines
from src.presentation.terminal import AnsiStyler
from src.reports import ReportRequest
from src.reports.models import AccountProjection
from src.watch import WatchCoordinator
from src.watch.accounts import MAX_STALE_MS, reconcile_accounts

D = Decimal
ROOT = Path(__file__).resolve().parents[2]
NOW = 1_790_856_000_000
BASE = AccountSnapshot(AccountRef("source", "test", source_account="credential:1"), NOW, "Test")
STYLER = AnsiStyler({}, enabled=False)


def router(**kwargs):
    return {"data": {"usage": "99", "usage_daily": "1.42", "usage_weekly": "8.75", "usage_monthly": "32.10",
                     "limit": "50", "limit_remaining": "17.90", "limit_reset": "monthly", **kwargs}}


def seek(rows=None, available=True):
    return {"is_available": available, "balance_infos": rows if rows is not None else [{"currency": "USD",
        "total_balance": "42.73", "granted_balance": "2.73", "topped_up_balance": "40.00"}]}


def bucket(name="general", **kwargs):
    return {"model_name": name, "current_interval_total_count": 100, "current_interval_usage_count": 72,
            "current_weekly_total_count": 200, "current_weekly_usage_count": 108,
            "start_time": NOW, "end_time": NOW + 18_000_000,
            "weekly_start_time": NOW, "weekly_end_time": NOW + 604_800_000, **kwargs}


def minimax(*rows, **kwargs):
    return {"base_resp": {"status_code": 0, "status_msg": "success"}, "model_remains": list(rows), **kwargs}


def normalize(definition, payload):
    return normalize_simple_account(replace(BASE, provider_label=definition.display_label), payload, definition)


def text(account, width=200, watch=False):
    return "\n".join(capacity_lines(AccountProjection(account, account.provider_label), STYLER, "UTC",
                                  width=width, now_ms=NOW, watch=watch, force_vertical=True))


class OpenRouterTests(unittest.TestCase):
    def test_current_key_spend_and_limit_native_semantics(self):
        account = normalize(OPENROUTER, router())
        quota = account.quotas[0]
        self.assertEqual("Month", quota.label)
        self.assertEqual(D(".358"), quota.remaining_fraction)
        self.assertEqual(D("32.10"), quota.used)
        self.assertEqual(D("17.90"), quota.remaining)
        self.assertEqual(D(50), quota.limit)
        self.assertEqual("USD", quota.unit)
        self.assertEqual([D("1.42"), D("8.75"), D("32.10")], [b.amount for b in account.billing])
        self.assertIn("36%", text(account))
        self.assertIn("$17.90/$50.00", text(account))
        self.assertIsNone(account.plan)
        self.assertFalse(account.usage_attribution_complete)

    def test_reset_periods_no_guessed_month_or_reset_timestamp(self):
        for reset, label in (("daily", "Day"), ("weekly", "Week"), ("monthly", "Month"), (None, "Limit")):
            account = normalize(OPENROUTER, router(limit_reset=reset))
            self.assertEqual(label, account.quotas[0].label)
            self.assertIsNone(account.quotas[0].reset_at_ms)
        unknown = normalize(OPENROUTER, router(limit_reset="annually-secret"))
        self.assertEqual("Limit", unknown.quotas[0].label)
        self.assertEqual("partial", unknown.availability)
        self.assertNotIn("annually-secret", repr(unknown))

    def test_no_limit_no_bar_no_organization_or_byok_inference(self):
        account = normalize(OPENROUTER, router(limit=None, limit_remaining=None,
            byok_usage_monthly=8000, organization_usage=9000, is_free_tier=False))
        self.assertFalse(account.quotas)
        self.assertNotIn("█", text(account))
        self.assertEqual(3, len(account.billing))
        self.assertIn("Spend: Day $1.42", text(account))
        self.assertIsNone(account.plan)
        self.assertNotIn("8000", repr(account))
        self.assertNotIn("9000", repr(account))

    def test_native_limit_remaining_is_authoritative_not_all_time_spend(self):
        account = normalize(OPENROUTER, router(usage=900, usage_monthly=80, include_byok_in_limit=True))
        self.assertEqual(D("17.90"), account.quotas[0].remaining)
        self.assertEqual(D("32.10"), account.quotas[0].used)
        self.assertEqual(D(80), account.billing[-1].amount)

    def test_missing_malformed_usage_and_limit_are_partial_not_zero(self):
        account = normalize(OPENROUTER, router(usage_weekly=None, usage_daily="bad", limit_remaining="bad"))
        self.assertEqual("partial", account.availability)
        self.assertEqual(1, len(account.billing))
        self.assertIsNone(account.quotas[0].remaining_fraction)
        self.assertIsNone(account.quotas[0].remaining)


class DeepSeekTests(unittest.TestCase):
    def test_balance_parts_are_billing_without_denominator_or_deposit_history(self):
        account = normalize(DEEPSEEK, seek())
        self.assertEqual("available", account.availability)
        self.assertFalse(account.quotas)
        self.assertEqual([D("42.73"), D("2.73"), D(40)], [b.amount for b in account.billing])
        self.assertTrue(all(b.kind == "balance" for b in account.billing))
        self.assertIn("Balance $42.73", text(account))
        self.assertNotIn("█", text(account))
        self.assertNotIn("%", text(account))

    def test_multiple_native_currencies_remain_separate(self):
        usd = seek()["balance_infos"][0]
        account = normalize(DEEPSEEK, seek([usd, {**usd, "currency": "CNY", "total_balance": "200"}]))
        self.assertEqual(6, len(account.billing))
        self.assertEqual(["USD"] * 3 + ["CNY"] * 3, [b.currency for b in account.billing])
        self.assertIn("Balance 200 CNY", text(account))
        self.assertFalse(account.quotas)

    def test_availability_false_and_malformed_numbers_are_retained_as_evidence(self):
        row = {**seek()["balance_infos"][0], "granted_balance": "invalid"}
        account = normalize(DEEPSEEK, seek([row], available=False))
        self.assertEqual(AccountUsageStatus.BLOCKED, account.status)
        self.assertEqual("partial", account.availability)
        self.assertEqual(2, len(account.billing))
        self.assertNotIn("Granted 0", text(account))
        self.assertIn("BLOCKED", text(account))


class MiniMaxTests(unittest.TestCase):
    def test_five_hour_week_and_reset_timestamps(self):
        account = normalize_minimax_account(BASE, minimax(bucket()))
        self.assertEqual("MiniMax Token Plan", account.provider_label)
        self.assertEqual("available", account.availability)
        self.assertEqual(["5h", "Week"], [q.label for q in account.quotas])
        self.assertEqual([D(".72"), D(".54")], [q.remaining_fraction for q in account.quotas])
        self.assertEqual([NOW + 18_000_000, NOW + 604_800_000], [q.reset_at_ms for q in account.quotas])
        self.assertIsNone(account.plan)
        self.assertIn("72%", text(account))

    def test_relative_reset_offsets_are_explicit_milliseconds(self):
        row = bucket(start_time=None, end_time=None, weekly_start_time=None, weekly_end_time=None,
                     remains_time=123_000, weekly_remains_time=234_000)
        account = normalize_minimax_account(BASE, minimax(row))
        self.assertEqual([NOW + 123_000, NOW + 234_000], [q.reset_at_ms for q in account.quotas])

    def test_count_remaining_and_new_count_used_forms_match_explicit_percent(self):
        for count in (72, 28):
            account = normalize_minimax_account(BASE, minimax(bucket(current_interval_usage_count=count,
                current_interval_remaining_percent=72, current_weekly_remaining_percent=54)))
            self.assertEqual(D(72), account.quotas[0].remaining)
            self.assertEqual(D(28), account.quotas[0].used)
            self.assertEqual(D(".72"), account.quotas[0].remaining_fraction)
        legacy = normalize_minimax_account(BASE, minimax(bucket(current_interval_usage_count=28)))
        self.assertEqual(D(".28"), legacy.quotas[0].remaining_fraction)

    def test_percentage_only_fallback_never_fabricates_count_denominator(self):
        row = bucket(current_interval_total_count=None, current_interval_usage_count=None,
                     current_weekly_total_count=None, current_weekly_usage_count=None,
                     usage_percent=72, current_weekly_remaining_percent=54)
        account = normalize_minimax_account(BASE, minimax(row))
        self.assertEqual([D(".72"), D(".54")], [q.remaining_fraction for q in account.quotas])
        self.assertTrue(all(q.limit is None for q in account.quotas))

    def test_conflicting_counts_keep_authoritative_percentage_not_false_capacity(self):
        row = bucket(current_interval_usage_count=20, current_interval_remaining_percent=72)
        account = normalize_minimax_account(BASE, minimax(row))
        self.assertEqual("partial", account.availability)
        self.assertIsNone(account.quotas[0].remaining)
        self.assertIsNone(account.quotas[0].used)
        self.assertEqual(D(".72"), account.quotas[0].remaining_fraction)

    def test_shared_general_pool_avoids_chat_duplicates_independent_buckets_survive(self):
        independent = bucket("video", start_time=NOW, end_time=NOW + 86_400_000)
        account = normalize_minimax_account(BASE, minimax(bucket(), bucket("MiniMax-M*"), independent))
        self.assertEqual(["5h", "Week", "Video Day", "Video Week"], [q.label for q in account.quotas])
        self.assertTrue(all(q.model_id is None for q in account.quotas))
        self.assertEqual(4, len(account.quotas))
        distinct = normalize_minimax_account(BASE, minimax(bucket(), bucket("MiniMax-M2.7", current_interval_total_count=200)))
        self.assertEqual(4, len(distinct.quotas))
        self.assertEqual(D(200), distinct.quotas[2].limit)
        self.assertIsNone(distinct.quotas[2].model_id)

    def test_only_explicit_native_status_proves_unlimited_no_entitlement_variant(self):
        no_plan = bucket(current_interval_total_count=0, current_interval_usage_count=0,
                         current_weekly_total_count=0, current_weekly_usage_count=0,
                         current_interval_status=3, current_weekly_status=3)
        account = normalize_minimax_account(BASE, minimax(no_plan))
        self.assertFalse(account.quotas)
        self.assertEqual("MiniMax", account.provider_label)
        self.assertEqual("unavailable", account.availability)
        unlimited = normalize_minimax_account(BASE, minimax(bucket(current_weekly_status=3)))
        self.assertTrue(unlimited.quotas[1].unlimited)

    def test_unknown_schema_malformed_rows_and_boost_are_actionable_partial(self):
        unknown = normalize_minimax_account(BASE, {"unexpected": "raw-secret"})
        self.assertEqual("error", unknown.availability)
        rejected = normalize_minimax_account(BASE, {"base_resp": {"status_code": 1004, "status_msg": "raw-secret"}})
        self.assertEqual("unavailable", rejected.availability)
        mixed = normalize_minimax_account(BASE, minimax(None, bucket(), {"model_name": "secret-model"}))
        self.assertEqual("partial", mixed.availability)
        self.assertEqual(2, len(mixed.quotas))
        boosted = normalize_minimax_account(BASE, minimax(bucket(weekly_boost_permille=1500)))
        self.assertEqual("partial", boosted.availability)
        self.assertNotIn("raw-secret", repr(unknown))
        self.assertNotIn("secret-model", repr(mixed))

    def test_native_error_codes_preserve_transient_recovery_and_auth_remedies(self):
        healthy = normalize_minimax_account(BASE, minimax(bucket()))
        for code in (1000, 1001, 1002, 1024, 1033, 1039):
            failed = normalize_minimax_account(BASE, {"base_resp": {"status_code": code, "status_msg": "raw-secret"}})
            self.assertEqual("error", failed.availability)
            values, _, stale = reconcile_accounts((healthy,), (failed,), {healthy.key: NOW}, now_ms=NOW + 1)
            self.assertTrue(stale)
            self.assertEqual(healthy.quotas, values[0].quotas)
            self.assertNotIn("raw-secret", repr(failed))
        for code in (1004, 2049):
            failed = normalize_minimax_account(BASE, {"base_resp": {"status_code": code}})
            self.assertEqual("auth_failure", failed.observations["parser_reason"])
            self.assertEqual("unavailable", failed.availability)
            self.assertIn("Reconnect", failed.observations["user_action"])
        for code in (1008, 2056):
            failed = normalize_minimax_account(BASE, {"base_resp": {"status_code": code}})
            self.assertEqual(AccountUsageStatus.BLOCKED, failed.status)
            self.assertFalse(failed.quotas)

    def test_bucket_iteration_is_bounded_and_native_plan_mapped_only(self):
        account = normalize_minimax_account(BASE, minimax(*(bucket() for _ in range(30)), plan="plus"))
        self.assertEqual("Plus", account.plan)
        self.assertEqual("partial", account.availability)
        self.assertLessEqual(len(account.quotas), 16)
        unknown_plan = normalize_minimax_account(BASE, minimax(bucket(), plan="secret-plan"))
        self.assertIsNone(unknown_plan.plan)
        self.assertNotIn("secret-plan", repr(unknown_plan))

    def test_subscription_route_not_generic_key_or_oauth_proves_permission_to_read(self):
        provider = MiniMaxAccountProvider()
        def record(provider_id, kind="api"):
            return CredentialRecord(AccountRef("source", provider_id, source_account="auth:" + provider_id), {"type": kind, "key": "synthetic"})
        self.assertEqual(GLOBAL_ENDPOINT, provider.endpoint_for(record("minimax-coding-plan")))
        self.assertEqual(CN_ENDPOINT, provider.endpoint_for(record("minimax-cn-coding-plan")))
        self.assertIsNone(provider.endpoint_for(record("minimax")))
        reader = MagicMock(return_value=AccountHttpResponse(minimax(bucket()), 200))
        provider.http_get = reader
        with patch.object(provider, "records", return_value=(record("minimax"), record("minimax-coding-plan", "oauth"),
                                                            record("minimax-coding-plan"))):
            accounts = provider.get_account_snapshots()
        self.assertEqual(["unavailable", "unavailable", "available"], [a.availability for a in accounts])
        reader.assert_called_once_with(GLOBAL_ENDPOINT, "synthetic")


class WiringAndLifecycleTests(unittest.TestCase):
    def test_standard_ids_and_multiple_provider_keys_discovered_per_record(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            auth = root / "auth.json"
            auth.write_text("{}")
            db = root / "opencode.db"
            conn = sqlite3.connect(db)
            try:
                conn.execute("CREATE TABLE credential(id TEXT, integration_id TEXT, value TEXT, active INTEGER)")
                conn.executemany("INSERT INTO credential VALUES (?,?,?,?)", [(str(index), provider_id,
                    json.dumps({"type": "api", "key": "synthetic"}), index % 2) for index, provider_id in enumerate(
                        ("openrouter", "openrouter", "deepseek", "deepseek", "minimax-coding-plan", "minimax-cn-coding-plan"))])
                conn.commit()
            finally:
                conn.close()
            providers = [SimpleHttpAccountProvider(d, credential_db_path=db, home=root,
                http_get=lambda endpoint, key, d=d: AccountHttpResponse(router() if d == OPENROUTER else seek(), 200))
                for d in SIMPLE_HTTP_PROVIDERS]
            providers.append(MiniMaxAccountProvider(credential_db_path=db, home=root,
                             http_get=lambda endpoint, key: AccountHttpResponse(minimax(bucket()), 200)))
            for provider in providers:
                provider.auth_json_path = auth
                values = provider.get_account_snapshots()
                self.assertEqual(2, len(values))
                self.assertEqual(2, len({a.key for a in values}))
                self.assertTrue(all(a.availability == "available" for a in values))

    def test_composition_and_config_expose_only_enabled_auth_path_controls(self):
        defaults = read_jsonc(ROOT / "config/default-config.jsonc")
        providers = _account_providers(defaults, "v2")
        self.assertEqual({"github-copilot", "openai", "anthropic", "claude-code", "minimax", "deepseek", "openrouter"},
                         {p.provider_id for p in providers})
        for group in ("openrouterQuota", "deepseekQuota", "minimaxQuota"):
            self.assertEqual({"enabled", "authJsonPath"}, set(defaults[group]))
            for forbidden in ("url", "method", "headers", "cookies", "body", "script", "authentication"):
                config = {**defaults, group: {**defaults[group], forbidden: "secret"}}
                with self.assertRaises(ConfigError):
                    validate_configuration(config, defaults, {group: {forbidden: "secret"}})

    def test_shared_renderers_align_variable_labels_balance_no_bar_narrow_fallback(self):
        account = normalize(OPENROUTER, router())
        other = normalize_minimax_account(BASE, minimax(bucket()))
        for watch in (True, False):
            rows = text(other, watch=watch).splitlines()
            bars = [row.index("█") for row in rows if "█" in row]
            self.assertEqual(1, len(set(bars)))
            narrow = text(account, width=40, watch=watch)
            self.assertTrue(all(len(row) <= 40 for row in narrow.splitlines()))
            self.assertIn("$17.90/$50.00", narrow)
            self.assertNotIn("█", text(normalize(DEEPSEEK, seek()), watch=watch))
        combined = replace(account, quotas=tuple(replace(account.quotas[0], label=label)
                            for label in ("5h", "Day", "Week", "Month", "Limit")))
        self.assertEqual(1, len({row.index("█") for row in text(combined).splitlines() if "█" in row}))

    def test_report_watch_share_observations_and_failure_does_not_affect_usage(self):
        good = normalize(DEEPSEEK, seek())
        bad = replace(normalize(OPENROUTER, router()), ref=replace(BASE.ref, source_account="credential:2"),
                      quotas=(), billing=(), availability="error", observations={"parser_reason": "timeout"})
        class Provider:
            provider_id = "test"
            def probe(self):
                from src.domain import IntegrationHealth
                return IntegrationHealth(True, True)
            def get_account_snapshots(self):
                return good, bad
        with tempfile.TemporaryDirectory() as td:
            config, selection, service, _ = make_service(td, MutableSource(make_snapshot()))
            baseline = service.build(ReportRequest())
            service.account_providers = (Provider(),)
            report = service.build(ReportRequest())
            coordinator = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: NOW)
            watch = coordinator.initialize().projection
            self.assertEqual([good, bad], [a.account for a in report.accounts_quotas.accounts])
            self.assertEqual([good, bad], [a.account for a in watch.quota.accounts])
            self.assertEqual(baseline.accounts_quotas.comparison_today, report.accounts_quotas.comparison_today)
            self.assertEqual(baseline.model_comparison, report.model_comparison)
            for renderer, projection in ((ReportRenderer(config, stream=io.StringIO(), color_enabled=False), report),
                                         (WatchRenderer(config, stream=io.StringIO(), interactive=False), watch)):
                renderer.render(projection)

    def test_existing_stale_ttl_auth_failure_and_per_account_recovery_reused(self):
        good = normalize(OPENROUTER, router())
        other = replace(normalize(DEEPSEEK, seek()), ref=replace(BASE.ref, source_account="credential:2"))
        timed_out = replace(good, quotas=(), billing=(), availability="error", observations={"parser_reason": "timeout"})
        values, seen, stale = reconcile_accounts((good, other), (timed_out, other), {good.key: NOW, other.key: NOW}, now_ms=NOW + 1000)
        self.assertTrue(stale)
        self.assertEqual("stale", values[0].availability)
        self.assertEqual(other, values[1])
        expired, _, _ = reconcile_accounts(values, (timed_out, other), seen, now_ms=NOW + MAX_STALE_MS + 1)
        self.assertFalse(expired[0].quotas)
        auth = replace(timed_out, availability="unavailable", observations={"parser_reason": "auth_failure"})
        result, _, _ = reconcile_accounts((good,), (auth,), {good.key: NOW}, now_ms=NOW + 1)
        self.assertEqual(auth, result[0])

    def test_minimax_diagnostics_are_sanitized_equivalent_provider_evidence(self):
        provider = MiniMaxAccountProvider(http_get=lambda endpoint, key: AccountHttpResponse(minimax(bucket()), 200))
        record = CredentialRecord(AccountRef("source", "minimax-coding-plan", source_account="credential:42"),
                                  {"type": "api", "key": "synthetic-key"})
        with patch.object(provider, "records", return_value=(record,)):
            account = provider.get_account_snapshots()[0]
        diagnostic = sanitized_account_observation(account)
        self.assertEqual("model_remains", diagnostic["quota_shape"]["response_form"])
        self.assertEqual(("5h", "Week"), diagnostic["quota_shape"]["quota_windows"])
        self.assertTrue(diagnostic["quota_shape"]["request_attempted"])
        for secret in ("synthetic-key", "credential:42", "model_remains\": ["):
            self.assertNotIn(secret, json.dumps(diagnostic))


if __name__ == "__main__":
    unittest.main()
