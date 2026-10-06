"""Provider-neutral CCost/accounts/quotas and Watch regression contracts."""
from __future__ import annotations

from contextlib import closing
from dataclasses import replace
from decimal import Decimal
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from development.tests.test_analysis_core import make_snapshot, message, MODEL
from development.tests.test_step7_reports_cli import FakePricingProvider, FakeSource
from development.tests.test_step8_watch import MutableSource, make_service
from src.accounts.anthropic import AnthropicAccountProvider, normalize_anthropic_usage
from src.accounts.credentials import configured_credentials
from src.accounts.diagnostics import sanitized_account_observation
from src.accounts.github_copilot import convert_internal_user_payload, GitHubCopilotAccountProvider, JsonResponse
from src.accounts.openai_subscription import convert_usage_payload, OpenAIAccountProvider, UsageResponse
from src.analysis.billing import actual_entry_cost
from src.analysis.causal import build_prompt_records, trace_entries
from src.analysis.valuation import billed_spend, comparison_cost, unique_usage
from src.domain import AccountRef, AccountSnapshot, AccountUsageStatus, BillingComponent, CostDisposition, IntegrationHealth, MessageRole, QuotaComponent, TokenUsage
from src.presentation import ReportRenderer, WatchRenderer
from src.presentation.accounts import capacity_lines
from src.presentation.terminal import AnsiStyler
from src.reports import ReportRequest
from src.reports.accounts import account_projections
from src.reports.models import AccountProjection
from src.watch import WatchCoordinator
from src.watch.accounts import reconcile_accounts

D = Decimal


def account(provider="openai", identity="a", *, label=None, plan="Plus", source="source"):
    return AccountSnapshot(AccountRef(source, provider, identity, account_label=label), 100_000,
                           {"openai": "OpenAI", "github-copilot": "GitHub Copilot", "anthropic": "Anthropic"}[provider],
                           plan, quotas=(QuotaComponent("5-hour", "rolling", remaining_fraction=D("0.75"),
                                                          duration_seconds=18_000, reset_at_ms=7_201_000),))


class NormalizedProvider:
    included_usage = False
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.provider_id = snapshot.ref.provider_id
    def probe(self):
        return IntegrationHealth(True, True)
    def get_account_snapshots(self):
        return (self.snapshot,)


class ValuationTests(unittest.TestCase):
    def test_subscription_ccost_is_positive_but_billed_zero(self):
        entry = replace(trace_entries(make_snapshot())[0], tokens=TokenUsage(input=1_000_000),
                        reported_cost=D(0), cost_disposition=CostDisposition.INCLUDED_SUBSCRIPTION)
        catalog = FakePricingProvider().catalog
        self.assertEqual(D(0), actual_entry_cost(entry, catalog.estimate).dollars)
        self.assertEqual(D(100), comparison_cost((entry,), catalog.reference_valuation).ccost)
        self.assertEqual(D(0), billed_spend((entry,)))

    def test_payg_ccost_and_billing_are_independent(self):
        entry = replace(trace_entries(make_snapshot())[0], tokens=TokenUsage(input=1_000_000), reported_cost=D("2.04"))
        self.assertEqual(D(100), comparison_cost((entry,), FakePricingProvider().catalog.reference_valuation).ccost)
        self.assertEqual(D("2.04"), billed_spend((entry,)))

    def test_unpriced_usage_never_substitutes_reported_cost_or_fuzzy_model(self):
        entries = trace_entries(make_snapshot())
        unknown = replace(entries[0], model=replace(entries[0].model, model="gpt-test-unknown"), reported_cost=D(99))
        value = comparison_cost((entries[0], unknown), FakePricingProvider().catalog.reference_valuation)
        self.assertFalse(value.complete)
        self.assertIsNone(value.ccost)
        self.assertEqual(1, value.priced_requests)
        self.assertLess(value.known_ccost, D(99))

    def test_clones_deduplicate_within_source_but_not_across_sources(self):
        entry = trace_entries(make_snapshot())[0]
        clone = replace(entry, session_id="fork")
        other_source = replace(clone, source_instance="another-installation")
        self.assertEqual(2, len(unique_usage((entry, clone, other_source))))

    def test_prompt_report_projects_ccost_not_subscription_billing(self):
        with tempfile.TemporaryDirectory() as td:
            snapshot = make_snapshot()
            invocations = tuple(replace(i, cost=replace(i.cost, amount=D(0)),
                                       cost_disposition=CostDisposition.INCLUDED_SUBSCRIPTION) for i in snapshot.invocations)
            source = MutableSource(replace(snapshot, invocations=invocations))
            config, _, service, _ = make_service(td, source, now_ms=4000)
            from src.reports import ReportKind
            report = service.build(ReportRequest(ReportKind.SESSION, session_id="root"))
            row = next(r for r in report.prompt_blocks[0].rows if r.calls)
            self.assertGreater(row.comparison_cost.ccost, 0)
            self.assertEqual(0, row.billed_cost)
            self.assertEqual(row.comparison_cost.ccost, row.ccost)
            stream = io.StringIO()
            ReportRenderer(config, stream=stream, color_enabled=False).render(report)
            self.assertIn("CCost", stream.getvalue())
            self.assertNotIn("~CmpCost", stream.getvalue())

    def test_comparison_catalog_can_be_replaced_without_replacing_billing(self):
        with tempfile.TemporaryDirectory() as td:
            _, _, service, _ = make_service(td, MutableSource(make_snapshot()), now_ms=4000)
            original = service.build_watch_quota()
            reference = FakePricingProvider()
            reference.catalog = replace(reference.catalog, models=tuple(replace(model, tiers=tuple(
                replace(tier, per_million_input=tier.per_million_input * 3,
                        per_million_cache_read=tier.per_million_cache_read * 3,
                        per_million_output=tier.per_million_output * 3)
                for tier in model.tiers)) for model in reference.catalog.models))
            service.comparison_pricing_provider = reference
            service.comparison_pricing_catalog = None
            changed = service.build_watch_quota()
            self.assertGreater(original.comparison_month.ccost, 0)
            self.assertEqual(original.comparison_month.ccost * 3, changed.comparison_month.ccost)
            self.assertEqual(original.billed_month, changed.billed_month)


class AccountsTests(unittest.TestCase):
    def test_same_provider_accounts_coexist_in_service_and_watch(self):
        accounts = (account(identity="personal", label="Personal"), account(identity="work", label="Work"),
                    account("github-copilot", "c1", plan="Max"), account("github-copilot", "c2", plan="Business"),
                    account("anthropic", "claude", plan="Pro"))
        with tempfile.TemporaryDirectory() as td:
            source = MutableSource(make_snapshot())
            config, selection, service, _ = make_service(td, source)
            service.account_providers = tuple(NormalizedProvider(a) for a in accounts)
            projection = WatchCoordinator(selection=selection, report_service=service, config=config,
                                          clock_ms=lambda: 100_000).initialize().projection
            self.assertEqual(5, len(projection.quota.accounts))
            self.assertEqual(5, len({a.account.key for a in projection.quota.accounts}))
            for row in projection.quota.accounts:
                self.assertIsNone(row.ccost_scopes[0][1])
            stream = io.StringIO()
            WatchRenderer(config, stream=stream, interactive=False, terminal_width=240).render(projection)
            text = stream.getvalue()
            self.assertIn("OpenAI Plus · Personal", text)
            self.assertIn("OpenAI Plus · Work", text)
            self.assertIn("Anthropic Pro", text)
            for line in text.splitlines():
                self.assertLessEqual(sum(label in line for label in ("OpenAI Plus · Personal", "OpenAI Plus · Work", "GitHub Copilot Max", "GitHub Copilot Business", "Anthropic Pro")), 1)

    def test_service_constructor_does_not_deduplicate_on_provider_id(self):
        from src.reports import ReportService
        from src.cache import CacheDatabase, CacheRepository
        from src.sources.selection import SourceSelection
        with tempfile.TemporaryDirectory() as td:
            source = FakeSource()
            db = CacheDatabase(Path(td)); db.initialize()
            providers = (NormalizedProvider(account(identity="one")), NormalizedProvider(account(identity="two")))
            service = ReportService(selection=SourceSelection(source, "v1", (), source.probe()),
                                    pricing_provider=FakePricingProvider(), account_provider=None, account_providers=providers,
                                    cache_repository=CacheRepository(db), config={"timezone": "UTC"}, now_ms=4000)
            self.assertEqual(2, len(service.account_quota_snapshots()))

    def test_attribution_is_proven_not_inferred_from_active_account(self):
        a, b = account(identity="a"), account(identity="b")
        base = trace_entries(make_snapshot())[0]
        entry = replace(base, model=replace(base.model, provider="openai"), completed_at_ms=100_000,
                        tokens=TokenUsage(input=1_000_000), account_ref=a.ref)
        rows = account_projections((a, b), (entry,), FakePricingProvider().catalog,
                                   now_ms=100_000, today_start_ms=0, month_start_ms=0)
        self.assertEqual(D(100), rows[0].ccost_scopes[0][1].ccost)
        self.assertIsNone(rows[1].ccost_scopes[0][1])
        unknown = replace(entry, account_ref=None, completed_at_ms=100_001)
        rows = account_projections((a, b), (entry, unknown), FakePricingProvider().catalog,
                                   now_ms=100_001, today_start_ms=0, month_start_ms=0)
        self.assertTrue(all(row.ccost_scopes[0][1] is None for row in rows))

    def test_no_account_id_preserves_source_account_locator(self):
        refs = (AccountRef("one", "openai", source_account="credential:1"),
                AccountRef("one", "openai", source_account="credential:2"),
                AccountRef("two", "openai", source_account="credential:1"))
        self.assertEqual(3, len({ref.key for ref in refs}))
        with self.assertRaises(ValueError):
            AccountRef("one", "openai").key

    def test_wide_narrow_layouts_use_same_components_and_never_merge_accounts(self):
        a = AccountProjection(account(), "OpenAI Plus")
        styler = AnsiStyler({}, enabled=False)
        wide = capacity_lines(a, styler, "UTC", width=200, now_ms=100_000)
        narrow = capacity_lines(a, styler, "UTC", width=45, now_ms=100_000)
        self.assertEqual(1, len(wide))
        self.assertGreater(len(narrow), 1)
        self.assertTrue(all(len(line) <= 45 for line in narrow))
        for text in ("OpenAI Plus", "75%", "█" * 8 + "░" * 2):
            self.assertIn(text, "\n".join(wide))
            self.assertIn(text, "\n".join(narrow))

    def test_used_only_limit_only_and_blocked_unknown_are_renderable(self):
        a = replace(account(), status=AccountUsageStatus.BLOCKED,
                    quotas=(QuotaComponent("Usage", used=D(18953), unit="credits"),
                            QuotaComponent("Budget", limit=D(200), unit="USD")))
        lines = capacity_lines(AccountProjection(a, "Account"), AnsiStyler({}, enabled=False), "UTC", width=200)
        text = "\n".join(lines)
        self.assertIn("BLOCKED", text)
        self.assertIn("18953 credits used", text)
        self.assertIn("limit unavailable", text)
        self.assertIn("Limit $200.00 USD", text)

    def test_native_budget_preserves_fractional_money_and_scope_labels(self):
        a = replace(account(), quotas=(QuotaComponent("Team budget", remaining=D("18.40"), limit=D(200), unit="USD"),
                                      QuotaComponent("Model credits", used=D("2.75"), unit="credits")))
        text = "\n".join(capacity_lines(AccountProjection(a, "Account"), AnsiStyler({}, enabled=False), "UTC", width=200))
        self.assertIn("Team budget    $18.40/$200.00 USD", text)
        self.assertIn("Model credits 2.75 credits used", text)


class AdapterTests(unittest.TestCase):
    def test_business_degraded_quota_keeps_plan_usage_blocked_and_diagnostics(self):
        for entitlement in (0, 10, None, "unavailable", float("nan")):
            with self.subTest(entitlement=entitlement):
                snapshot = convert_internal_user_payload({"copilot_plan": "business", "quota_snapshots": {
                    "premium_interactions": {"entitlement": entitlement, "credits_used": 18953, "has_quota": False},
                }}, fetched_at_ms=1)
                self.assertTrue(snapshot.available)
                self.assertEqual("Business", snapshot.plan)
                self.assertEqual(AccountUsageStatus.BLOCKED, snapshot.usage_status)
                self.assertEqual(D(18953), snapshot.windows[0].native_used)
                self.assertIsNone(snapshot.windows[0].native_limit)
                self.assertEqual("denominator_unusable", snapshot.observations["parser_reason"])
                self.assertIn("⚠", snapshot.warnings[0])

    def test_openai_subscription_and_extra_credit_balance_coexist(self):
        snapshot = convert_usage_payload({"plan_type": "plus", "rate_limit": {"allowed": False,
            "primary_window": {"used_percent": 100, "limit_window_seconds": 18000}},
            "credits": {"balance": "32.60", "currency": "USD", "has_credits": True}}, fetched_at_ms=1)
        self.assertEqual(AccountUsageStatus.BLOCKED, snapshot.usage_status)
        self.assertEqual(1, len(snapshot.windows))
        self.assertEqual("ACTIVE", snapshot.billing_components[0].status)
        self.assertEqual(D("32.60"), snapshot.billing_components[0].amount)
        degraded = convert_usage_payload({"plan_type": "pro", "rate_limit": {"allowed": False}}, fetched_at_ms=1)
        self.assertEqual("pro", degraded.plan)
        self.assertEqual(AccountUsageStatus.BLOCKED, degraded.usage_status)

    def test_openai_payg_is_detected_without_subscription_placeholders(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "auth.json"
            path.write_text(json.dumps({"openai": {"type": "api", "key": "SECRET"}}))
            provider = OpenAIAccountProvider(auth_json_path=str(path), usage_get=lambda *_: self.fail("API credential must not call subscription usage"))
            snapshots = provider.get_account_snapshots()
            self.assertEqual(1, len(snapshots))
            self.assertEqual("Pay as you go", snapshots[0].plan)
            self.assertFalse(snapshots[0].quotas)
            self.assertNotIn("SECRET", repr(snapshots))

    def test_model_specific_components_do_not_value_other_models(self):
        a = replace(account(), quotas=(QuotaComponent("Model weekly", "rolling", duration_seconds=604_800,
                                                    scope="model", model_id="claude-test"),))
        entries = tuple(replace(e, model=replace(e.model, provider="openai"), account_ref=a.ref) for e in trace_entries(make_snapshot()))
        rows = account_projections((a,), entries, FakePricingProvider().catalog, now_ms=4000, today_start_ms=0, month_start_ms=0)
        self.assertIsNone(rows[0].ccost_scopes[0][1], "All observed requests use another model")
        a = replace(a, quotas=(replace(a.quotas[0], model_id=None),))
        rows = account_projections((a,), entries, FakePricingProvider().catalog, now_ms=4000, today_start_ms=0, month_start_ms=0)
        self.assertIsNone(rows[0].ccost_scopes[0][1], "Quota label alone cannot prove model scope")

    def test_v2_inventory_reads_multiple_accounts_without_mutation_or_secrets(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); db = root / "opencode.db"
            with closing(sqlite3.connect(db)) as conn:
                conn.execute("CREATE TABLE credential (id TEXT, integration_id TEXT, active INT, value TEXT)")
                for identity, active in (("personal", 1), ("work", 0)):
                    conn.execute("INSERT INTO credential VALUES (?, 'openai', ?, ?)", (identity, active,
                                 json.dumps({"type": "oauth", "access": "SECRET", "accountId": identity,
                                             "metadata": {"accountLabel": identity}})))
                conn.execute("INSERT INTO credential VALUES ('api', 'anthropic', 1, ?)", (json.dumps({"type": "api", "key": "SECRET"}),))
                conn.commit()
            baseline = db.read_bytes()
            records = configured_credentials(root / "auth.json", db, ("openai", "anthropic"))
            self.assertEqual(3, len(records))
            self.assertNotIn("SECRET", repr(records))
            provider = OpenAIAccountProvider(home=root, credential_db_path=db, now_ms=lambda: 1000,
                       usage_get=lambda *_: UsageResponse(True, 200, {"plan_type": "plus", "rate_limit": {
                           "primary_window": {"used_percent": 25, "limit_window_seconds": 18000}}}))
            snapshots = provider.get_account_snapshots()
            self.assertEqual(2, len(snapshots))
            self.assertEqual({"personal", "work"}, {item.ref.account_id for item in snapshots})
            self.assertEqual(1, len(AnthropicAccountProvider(home=root, credential_db_path=db).get_account_snapshots()))
            self.assertEqual(baseline, db.read_bytes())

    def test_copilot_personal_and_enterprise_credentials_are_independent(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "auth.json"
            path.write_text(json.dumps({key: {"type": "oauth", "refresh": "SECRET", "accountId": key}
                                      for key in ("github-copilot", "github-copilot-enterprise")}))
            provider = GitHubCopilotAccountProvider(auth_json_path=str(path), json_get=lambda *_: JsonResponse(True, 200, {
                "copilot_plan": "business", "quota_snapshots": {"premium_interactions": {
                    "entitlement": 0, "credits_used": 18953, "has_quota": False}}}))
            snapshots = provider.get_account_snapshots()
            self.assertEqual(2, len(snapshots))
            self.assertEqual(2, len({s.key for s in snapshots}))
            diagnostics = [sanitized_account_observation(s) for s in snapshots]
            self.assertIn('"http_status": 200', json.dumps(diagnostics))
            self.assertNotIn("SECRET", json.dumps(diagnostics))
            self.assertNotIn("accountId", json.dumps(diagnostics))

    def test_anthropic_supported_source_normalizes_subscription_and_credits(self):
        snapshot = normalize_anthropic_usage(account("anthropic", "pro", plan=None), {
            "plan": "max", "five_hour": {"utilization": 29}, "seven_day": {"utilization": 44},
            "extra_usage": {"enabled": True, "currency": "USD", "remaining": "18.40"},
        })
        self.assertEqual("Max", snapshot.plan)
        self.assertEqual([D("0.71"), D("0.56")], [q.remaining_fraction for q in snapshot.quotas])
        self.assertEqual(D("18.40"), snapshot.billing[0].amount)


class RefreshTests(unittest.TestCase):
    def test_resume_retains_expired_network_or_ambiguous_failure_without_refreshing_age(self):
        a = account()
        for observations in ({"parser_reason": "network_failure"}, {"http_status": 503}, {}):
            error = replace(a, quotas=(), availability="error", observations=observations)
            values, seen, stale = reconcile_accounts((a,), (error,), {a.key: 100_000},
                                                     now_ms=700_000, recovering=True)
            self.assertTrue(stale)
            self.assertEqual(a.quotas, values[0].quotas)
            self.assertEqual(a.fetched_at_ms, values[0].fetched_at_ms)
            self.assertEqual(100_000, seen[a.key])
            expired, seen, stale = reconcile_accounts(values, (error,), seen, now_ms=760_000)
            self.assertFalse(stale)
            self.assertFalse(expired[0].quotas)
            self.assertEqual(100_000, seen[a.key])

    def test_resume_does_not_mask_auth_rejection_even_when_marked_error(self):
        a = account()
        for observations in ({"parser_reason": "auth_failure"}, {"http_status": 401}, {"http_status": 403}):
            error = replace(a, quotas=(), availability="error", observations=observations)
            values, seen, stale = reconcile_accounts((a,), (error,), {a.key: 100_000},
                                                     now_ms=700_000, recovering=True)
            self.assertEqual((error,), values)
            self.assertFalse(stale)
            self.assertEqual(100_000, seen[a.key])

    def test_resume_partial_retention_and_expiry_do_not_timestamp_replayed_success(self):
        a, b = account(identity="a"), account(identity="b")
        partial = replace(a, availability="partial", quotas=(replace(a.quotas[0], remaining_fraction=None),))
        values, seen, _ = reconcile_accounts((a, b), (partial, b), {a.key: 100_000, b.key: 100_000},
                                             now_ms=700_000, recovering=True)
        self.assertEqual("stale", values[0].availability)
        self.assertEqual(100_000, seen[a.key])
        self.assertEqual(700_000, seen[b.key])
        expired, seen, _ = reconcile_accounts(values, (partial, b), seen, now_ms=760_000, update_seen=False)
        self.assertIsNone(expired[0].quotas[0].remaining_fraction)
        self.assertEqual({a.key: 100_000, b.key: 700_000}, seen)

    def test_recovery_rendering_is_generic_and_no_duplicate_error_state(self):
        for provider in ("openai", "github-copilot", "anthropic"):
            a = account(provider)
            for width in (35, 180):
                for quotas in (a.quotas, ()):
                    snapshot = replace(a, availability="stale" if quotas else "error", quotas=quotas)
                    row = AccountProjection(snapshot, snapshot.provider_label)
                    text = "\n".join(capacity_lines(row, AnsiStyler({}, enabled=False), "UTC",
                                                   width=width, now_ms=700_000, recovering=True))
                    self.assertNotIn("ERROR", text)
                    self.assertNotIn("Quota error", text)
                    self.assertTrue(all(len(line) <= width for line in text.splitlines()))
                    if quotas:
                        self.assertIn("STALE / RECONNECTING", text)
                    else:
                        self.assertIn("temporarily unavailable", text)
                        self.assertIn("Retrying...", text)
            error = AccountProjection(replace(a, quotas=(), availability="error"), a.provider_label)
            text = "\n".join(capacity_lines(error, AnsiStyler({}, enabled=False), "UTC", width=180))
            self.assertEqual(1, text.lower().count("error"))

    def test_transient_missing_fraction_retains_bar_with_stale_state(self):
        a = account()
        partial = replace(a, availability="partial", quotas=(replace(a.quotas[0], remaining_fraction=None),))
        values, seen, stale = reconcile_accounts((a,), (partial,), {a.key: 100_000}, now_ms=160_000)
        self.assertTrue(stale)
        self.assertEqual(D("0.75"), values[0].quotas[0].remaining_fraction)
        self.assertEqual(100_000, seen[a.key])
        values, _, stale = reconcile_accounts(values, (partial,), seen, now_ms=500_000)
        self.assertFalse(stale)
        self.assertIsNone(values[0].quotas[0].remaining_fraction)

    def test_error_preserves_two_same_provider_accounts_independently(self):
        a, b = account(identity="a"), account(identity="b")
        error = replace(a, quotas=(), availability="error")
        changed = replace(b, quotas=(replace(b.quotas[0], remaining_fraction=D("0.5")),))
        values, _, stale = reconcile_accounts((a, b), (error, changed), {a.key: 100_000, b.key: 100_000}, now_ms=160_000)
        self.assertTrue(stale)
        self.assertEqual([D("0.75"), D("0.5")], [v.quotas[0].remaining_fraction for v in values])
        unavailable = replace(a, quotas=(), availability="unavailable")
        values, _, _ = reconcile_accounts((a,), (unavailable,), {a.key: 100_000}, now_ms=160_000)
        self.assertFalse(values[0].quotas)

    def test_successful_zero_token_final_is_not_aborted_and_same_timestamp_wins(self):
        snapshot = make_snapshot()
        invocations = tuple(replace(i, tokens=TokenUsage(), cost=replace(i.cost, amount=D(0))) for i in snapshot.invocations)
        final = next(m for m in snapshot.messages if m.message_id == "a_next")
        aborted_attempt = replace(final, message_id="zz-aborted", error_name="AbortedError")
        snapshot = replace(snapshot, invocations=invocations, messages=snapshot.messages + (aborted_attempt,))
        record = next(p for p in build_prompt_records(snapshot, now_ms=4000) if p.prompt_id == "u_next")
        self.assertFalse(record.aborted)
        self.assertTrue(record.completed_successfully)

    def test_observed_success_survives_an_incomplete_abort_reconstruction(self):
        with tempfile.TemporaryDirectory() as td:
            source = MutableSource(make_snapshot(running=True))
            config, selection, service, _ = make_service(td, source)
            clock = [2200]
            watch = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: clock[0])
            watch.initialize()
            source.snapshot = replace(make_snapshot(), source_revision="finished")
            clock[0] = 2400
            good = next(r for r in watch.poll_once().projection.rows if r.prompt.event_id == "u_next")
            self.assertTrue(good.prompt.completed_successfully)
            block = watch.blocks["root"]
            watch.blocks["root"] = replace(block, rows=tuple(
                replace(p, aborted=True, completed_successfully=False) if p.event_id == "u_next" else p for p in block.rows))
            clock[0] = 2500
            current = next(r for r in watch.status_projection().rows if r.prompt.event_id == "u_next")
            self.assertFalse(current.prompt.aborted)
            self.assertEqual("✓", current.marker)


if __name__ == "__main__":
    unittest.main()
