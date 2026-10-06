"""Synthetic Claude login/quota metadata, without credentials or model prompts."""
from dataclasses import replace
from decimal import Decimal as D
import io
import tempfile
import unittest
from unittest.mock import Mock

from src.accounts.claude_code import ClaudeCodeAccountProvider, normalize_claude_usage
from src.accounts.claude_transport import ClaudeUsageResult
from src.watch.accounts import reconcile_accounts


LOGIN = {"loggedIn": True, "authMethod": "claude.ai", "apiProvider": "firstParty",
         "subscriptionType": "pro", "email": "synthetic@example.invalid", "orgId": "synthetic-org-id",
         "orgName": "Synthetic organization"}
ACCOUNT = {"email": LOGIN["email"], "organization": LOGIN["orgName"],
           "subscriptionType": "Claude Pro", "apiProvider": "firstParty"}


def usage(**overrides):
    return {"subscription_type": "pro", "rate_limits_available": True, "rate_limits": {
        "five_hour": {"utilization": 25, "resets_at": "2026-10-04T20:00:00Z"},
        "seven_day": {"utilization": 50, "resets_at": "2026-10-11T20:00:00+00:00"}}, **overrides}


def provider(result=None, login=None):
    return ClaudeCodeAccountProvider(auth_reader=Mock(return_value=LOGIN if login is None else login),
        usage_reader=Mock(return_value=result or ClaudeUsageResult(ACCOUNT, usage())), now_ms=lambda: 1000)


class ClaudeAccountTests(unittest.TestCase):
    def test_report_watch_account_visibility_and_minute_cadence_with_other_providers(self):
        from development.tests.test_accounts_ccost import NormalizedProvider, account
        from development.tests.test_analysis_core import make_snapshot
        from development.tests.test_step8_watch import MutableSource, make_service
        from src.presentation import ReportRenderer, WatchRenderer
        from src.reports import ReportRequest
        from src.watch import WatchCoordinator
        for result in (ClaudeUsageResult(ACCOUNT, usage()), ClaudeUsageResult(ACCOUNT, None, "unavailable", "method_missing")):
            with tempfile.TemporaryDirectory() as td:
                source = MutableSource(make_snapshot(running=False))
                config, selection, service, _ = make_service(td, source, now_ms=1000)
                p = provider(result)
                service.account_providers = (p, NormalizedProvider(account()),
                    NormalizedProvider(account("github-copilot", "copilot", plan="Business")),
                    NormalizedProvider(account("anthropic", "api", plan="API pay as you go")))
                report = service.build(ReportRequest())
                out = io.StringIO(); ReportRenderer(config, stream=out, color_enabled=False).render(report)
                self.assertIn("Claude Code Pro", out.getvalue())
                self.assertNotIn(LOGIN["email"], out.getvalue())
                clock = [1000]
                watch = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: clock[0])
                cycle = watch.initialize()
                out = io.StringIO(); WatchRenderer(config, stream=out, interactive=False, terminal_width=240).render(cycle.projection)
                self.assertIn("Claude Code Pro", out.getvalue())
                self.assertEqual(4, len(cycle.projection.quota.accounts))
                calls = p.usage_reader.call_count
                for tick in (2000, 4000, 9000):
                    clock[0] = tick; watch.poll_once()
                self.assertEqual(calls, p.usage_reader.call_count, "redraw/source work cannot launch Claude quota helpers")
                clock[0] = 62000; watch.poll_once()
                self.assertEqual(calls + 1, p.usage_reader.call_count)

    def test_discovery_failure_and_logout_do_not_start_quota_process(self):
        p = provider(); p.get_account_snapshots(); p.usage_reader.reset_mock()
        p.auth_reader.side_effect = TimeoutError("private")
        account, = p.get_account_snapshots()
        self.assertEqual("error", account.availability); p.usage_reader.assert_not_called()
        p.auth_reader.side_effect = None; p.auth_reader.return_value = {**LOGIN, "loggedIn": False}
        account, = p.get_account_snapshots()
        self.assertEqual("unavailable", account.availability); p.usage_reader.assert_not_called()

    def test_discovery_separate_from_quota_and_probe_does_not_fetch_usage(self):
        p = provider()
        self.assertTrue(p.probe().healthy)
        p.usage_reader.assert_not_called()
        account, = p.get_account_snapshots()
        p.auth_reader.assert_called_once()
        self.assertEqual("Pro", account.plan)
        self.assertEqual("Claude Code", account.provider_label)
        self.assertEqual("claude-code", account.ref.provider_id)
        self.assertFalse(account.usage_attribution_complete)
        self.assertNotIn(LOGIN["email"], repr(account))
        self.assertEqual([D(".75"), D(".5")], [q.remaining_fraction for q in account.quotas])
        self.assertEqual(1791144000000, account.quotas[0].reset_at_ms)

    def test_login_not_inferred_from_registration_or_third_party_plan(self):
        for login in ({}, {"provider": "claude-code"}, {**LOGIN, "loggedIn": False}):
            p = provider(login=login)
            self.assertFalse(p.probe().healthy)
            self.assertFalse(p.get_account_snapshots())
            p.usage_reader.assert_not_called()
        p = provider(login={**LOGIN, "apiProvider": "bedrock"})
        account, = p.get_account_snapshots()
        self.assertIsNone(account.plan)
        self.assertEqual("unavailable", account.availability)
        p.usage_reader.assert_not_called()
        p = provider(login={**LOGIN, "authMethod": "api_key"})
        account, = p.get_account_snapshots()
        self.assertEqual("API pay as you go", account.plan)
        self.assertEqual("api_or_external", account.observations["account_kind"])
        p.usage_reader.assert_not_called()

    def test_capability_format_timeout_and_auth_failures_retain_account(self):
        for state, reason in (("unavailable", "method_missing"), ("error", "timeout"),
                              ("error", "format_changed"), ("unavailable", "auth_failure")):
            p = provider(ClaudeUsageResult(ACCOUNT, None, state, reason))
            account, = p.get_account_snapshots()
            self.assertEqual("Pro", account.plan)
            self.assertFalse(account.quotas)
            self.assertEqual(state, account.availability)
            self.assertEqual(reason, account.observations["parser_reason"])
        p = provider(); p.usage_reader.side_effect = TimeoutError("private secret")
        account, = p.get_account_snapshots()
        self.assertEqual("error", account.availability)
        self.assertNotIn("private", repr(account))

    def test_account_swap_and_backend_mismatch_do_not_attach_quota(self):
        for metadata in ({**ACCOUNT, "email": "other@example.invalid"}, {**ACCOUNT, "apiProvider": "vertex"}, {}):
            account, = provider(ClaudeUsageResult(metadata, usage())).get_account_snapshots()
            self.assertFalse(account.quotas)
            self.assertEqual("unavailable", account.availability)

    def test_missing_windows_and_bad_values_are_partial_not_invented(self):
        account, = provider().get_account_snapshots()
        for rates in ({"five_hour": {"utilization": True}}, {"five_hour": {"utilization": 101}},
                      {"five_hour": {"utilization": "NaN"}}, {"five_hour": {"utilization": 2, "resets_at": "bad"}}):
            value = normalize_claude_usage(account, usage(rate_limits=rates))
            self.assertEqual("partial", value.availability)
            self.assertEqual(1, len(value.quotas))
        for payload in ({}, usage(rate_limits_available=False), usage(rate_limits=None), usage(rate_limits=[])):
            value = normalize_claude_usage(account, payload)
            self.assertFalse(value.quotas)
            self.assertIn(value.availability, {"error", "unavailable"})

    def test_unstarted_zero_window_is_complete_and_renders_not_started(self):
        from src.presentation.accounts import capacity_lines
        from src.presentation.terminal import AnsiStyler
        from src.reports.models import AccountProjection
        account, = provider().get_account_snapshots()
        idle = {**usage()["rate_limits"], "five_hour": {"utilization": 0, "resets_at": None}}
        value = normalize_claude_usage(account, usage(rate_limits=idle))
        self.assertEqual("available", value.availability)
        self.assertIs(False, value.quotas[0].window_active)
        self.assertIsNone(value.quotas[0].reset_at_ms)
        self.assertEqual(D(1), value.quotas[0].remaining_fraction)
        text = "\n".join(capacity_lines(AccountProjection(value, "Claude Code Pro"), AnsiStyler({}, enabled=False),
                                        "UTC", width=200, now_ms=1000))
        self.assertIn("100% · not started", text)
        self.assertNotIn("PARTIAL", text)
        # Only the explicit zero/null pair proves an idle window.
        for window in ({"utilization": 0}, {"utilization": 3, "resets_at": None}):
            value = normalize_claude_usage(account, usage(rate_limits={**idle, "five_hour": window}))
            self.assertEqual("partial", value.availability)
            self.assertIsNone(value.quotas[0].window_active)

    def test_scopes_and_iso_reset_preserve_identity_without_dollar_extrapolation(self):
        account, = provider().get_account_snapshots()
        payload = usage(rate_limits={**usage()["rate_limits"],
            "seven_day_sonnet": {"utilization": 30, "resets_at": "2026-10-10T20:00:00Z"},
            "seven_day_oauth_apps": {"utilization": 10, "resets_at": "2026-10-10T20:00:00Z"},
            "model_scoped": [{"display_name": "Fable", "utilization": 12, "resets_at": "2026-10-10T20:00:00Z"}]})
        value = normalize_claude_usage(account, payload)
        self.assertEqual(["account", "account", "model", "surface", "model"], [q.scope for q in value.quotas])
        self.assertTrue(all(q.model_id is None for q in value.quotas), "family labels do not prove a request model")
        self.assertFalse(value.billing)
        self.assertTrue(all(q.remaining_money is None for q in value.quotas))
        self.assertEqual("Max", normalize_claude_usage(account, usage(subscription_type="max")).plan)

    def test_watch_stale_expiry_and_auth_rejection_use_existing_reconciliation(self):
        p = provider(); good, = p.get_account_snapshots()
        error = replace(good, quotas=(), availability="error")
        values, seen, stale = reconcile_accounts((good,), (error,), {good.key: 1000}, now_ms=2000)
        self.assertTrue(stale); self.assertEqual(1000, values[0].fetched_at_ms)
        self.assertEqual(1000, seen[good.key])
        values, _, stale = reconcile_accounts((good,), (error,), seen, now_ms=302000)
        self.assertFalse(stale); self.assertFalse(values[0].quotas)
        rejected = replace(error, observations={"parser_reason": "auth_failure"})
        values, _, stale = reconcile_accounts((good,), (rejected,), seen, now_ms=2000)
        self.assertFalse(stale); self.assertFalse(values[0].quotas)


if __name__ == "__main__":
    unittest.main()
