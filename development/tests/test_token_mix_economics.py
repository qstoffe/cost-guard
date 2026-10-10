"""Token Mix CCost, the --token-mix history report and Copilot quota Pace."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import io
import json
from pathlib import Path
import tempfile
import unittest

from development.fixtures.session_snapshots import make_snapshot
from src.reports.sampling import latest_token_prompts
from development.tests import test_compact_reports as compact_fixtures
from development.tests.test_compact_reports import Availability, rendered
from development.fixtures.pricing_catalog import catalog
from development.fixtures.watch_runtime import MutableSource, make_service
from development.tests.test_token_mix import observe
from src.accounts.base import normalize_quota
from src.accounts.github_copilot import (GitHubCopilotAccountProvider, JsonResponse,
                                        convert_entitlement_payload, convert_internal_user_payload)
from src.analysis import analyze_snapshot
from src.analysis.models import TraceEntry
from src.analysis.quota_pace import quota_pace
from src.analysis.token_mix import model_token_mixes, priced_token_mix
from src.analysis.valuation import comparison_cost, unique_usage
from src.cli import CliUsageError, CommandKind, help_text, parse_command
from src.domain import AccountRef, AccountSnapshot, ModelPricing, ModelRef, PricingTier, QuotaComponent, TokenUsage
from src.presentation import WatchRenderer
from src.presentation.accounts import capacity_lines, pace_text
from src.presentation.progress import StartupProgress
from src.presentation.terminal import AnsiStyler
from src.presentation.token_mix import compact_tokens, token_mix_lines
from src.numbers import ccost_amount
from src.pricing.catalog import PricingCatalog, price_token_categories
from src.reports.accounts import account_projections
from src.reports import ReportRequest
from src.reports.models import ReportKind
from src.reports.token_mix_history import HISTORY_NOTE
from src.watch import WatchCoordinator
from src.watch.models import WatchProjection
from src.watch.token_mix import WatchTokenMix


def ms(*args, tz=timezone.utc) -> int:
    return int(datetime(*args, tzinfo=tz).timestamp() * 1000)


RESET = ms(2026, 11, 1)
TIERED = ModelPricing(ModelRef("github-copilot", "tiered", "Tiered"), "USD", tiers=(
    PricingTier(max_input_tokens=1000, per_million_input=Decimal("1"), per_million_cache_read=Decimal("0.1"),
                per_million_cache_write=Decimal("1.25"), per_million_output=Decimal("4")),
    PricingTier(min_input_tokens=1001, per_million_input=Decimal("2"), per_million_cache_read=Decimal("0.2"),
                per_million_cache_write=Decimal("2.5"), per_million_output=Decimal("8")),
))
PRICES = PricingCatalog((*catalog().models, TIERED))


def entry(model: str, tokens: TokenUsage, order: int = 0, session: str = "s") -> TraceEntry:
    return TraceEntry(session, "p", f"m{order}", None, 1000 + order, order, ModelRef("github-copilot", model), None, tokens)


def copilot(remaining="7000", *, reset=RESET, **changes) -> QuotaComponent:
    values = dict(label="Monthly", period="fixed", used=Decimal(7000) - Decimal(remaining), limit=Decimal(7000),
                  remaining=Decimal(remaining), remaining_fraction=Decimal(remaining) / 7000, unit="AI credits",
                  reset_at_ms=reset, remaining_money=Decimal(remaining) / 100, limit_money=Decimal(70))
    values.update(changes)
    return QuotaComponent(**values)


def paced(component, now, calendar="SE", tz="Europe/Stockholm"):
    return quota_pace(component, now_ms=now, timezone_id=tz, workday_calendar=calendar)


class CategoryCostTests(unittest.TestCase):
    def test_request_level_tiers_reconcile_with_ccost_not_aggregate_pricing(self):
        entries = (entry("tiered", TokenUsage(input=500, cache_read=400, cache_write=50, output=100)),
                   entry("tiered", TokenUsage(input=900, cache_read=900, cache_write=0, output=50), 1),
                   entry("gpt-test", TokenUsage(input=200, cache_read=800, output=40), 2))
        mix = priced_token_mix(((e.model, e.tokens) for e in entries), PRICES.reference_category_valuation)
        self.assertEqual(comparison_cost(entries, PRICES.reference_valuation).known_ccost, sum(mix.costs))
        aggregate = TokenUsage(input=1400, cache_read=1300, cache_write=50, output=150)
        self.assertNotEqual(price_token_categories(PRICES.reference_prices("tiered"), aggregate, 2750), tuple(
            a + b for a, b in zip(*(PRICES.reference_category_valuation(e.model, e.tokens) for e in entries[:2]))),
            "aggregated tokens would select the long-context tier")
        self.assertTrue(mix.cost_complete)
        for one in entries:
            self.assertEqual(PRICES.reference_valuation(one.model, one.tokens),
                             sum(PRICES.reference_category_valuation(one.model, one.tokens)))

    def test_unpriceable_requests_are_partial_and_zero_usage_is_priced_zero(self):
        entries = (entry("gpt-test", TokenUsage(input=100)), entry("unknown-model", TokenUsage(output=100), 1),
                   entry("unknown-model", TokenUsage(), 2))
        mix = priced_token_mix(((e.model, e.tokens) for e in entries), PRICES.reference_category_valuation)
        self.assertEqual((3, 2), (mix.request_count, mix.priced_requests))
        self.assertFalse(mix.cost_complete)
        self.assertEqual(comparison_cost(entries, PRICES.reference_valuation).known_ccost, sum(mix.costs))
        self.assertIn("(?", token_mix_lines("3 prompts", mix)[0], "partial CCost is marked")

    def test_adaptive_ccost_and_compact_token_volume(self):
        for value, text in (("127", "127"), ("18", "18"), ("0.6", "0.6"), ("0.95", "1.0"),
                            ("0.04", "<0.1"), ("0", "0"), ("0.4999", "0.5")):
            self.assertEqual(text, ccost_amount(Decimal(value)))
        for value, text in ((999, "999"), (842_000, "842K"), (5_300_000, "5.3M"), (1_200_000_000, "1.2B")):
            self.assertEqual(text, compact_tokens(value))

    def test_line_shape_integer_shares_small_cost_visible_and_graceful_wrap(self):
        mix = replace(priced_token_mix((), PRICES.reference_category_valuation), totals=(3, 92, 3, 2),
                      percentages=(3, 92, 3, 2), request_count=4, priced_requests=4,
                      costs=(Decimal("18"), Decimal("31"), Decimal("0.6"), Decimal("0.027")))
        line = token_mix_lines("12 prompts", mix)[0]
        self.assertEqual("Token Mix % · 12 prompts · Input: 3% (18)   Cache: 92% (31)   "
                         "Write: 3% (0.6)   Output: 2% (<0.1)", line)
        for width in (80, 50):
            lines = token_mix_lines("12 prompts", mix, width=width)
            self.assertGreater(len(lines), 1)
            self.assertTrue(all(len(item) <= width for item in lines))

    def test_watch_counts_unique_prompts_prices_requests_and_omits_total(self):
        snapshot = make_snapshot()
        tracker = WatchTokenMix(1000)
        observe(tracker, snapshot)
        mix = tracker.project(PRICES.reference_category_valuation)
        bundle = analyze_snapshot(snapshot, now_ms=4000)
        self.assertEqual(len({p.prompt_id for p in bundle.prompts if p.entries}), mix.sample_size)
        self.assertEqual(comparison_cost(bundle.trace_entries, PRICES.reference_valuation).known_ccost, sum(mix.costs))
        stream = io.StringIO()
        WatchRenderer({"timezone": "UTC"}, stream=stream, interactive=False, terminal_width=200)._render_quota(
            WatchProjection("Watch", "V2", (), token_mix=mix, now_ms=4000))
        first = stream.getvalue().splitlines()[0]
        self.assertTrue(first.startswith(f"Token Mix % · {mix.sample_size} prompts · Input: "))
        self.assertNotIn("tokens", first)
        self.assertEqual(["Watch total CCost: " + ccost_amount(sum(mix.costs))], stream.getvalue().splitlines()[1:],
                         "the mix line has no total; only the dedicated Watch total row follows")

    def test_coordinator_watch_mix_reconciles_with_report_ccost(self):
        with tempfile.TemporaryDirectory() as td:
            config, selection, service, _ = make_service(td, MutableSource(make_snapshot()))
            projection = WatchCoordinator(selection=selection, report_service=service, config=config,
                                          clock_ms=lambda: 1000).initialize().projection
            bundle = analyze_snapshot(make_snapshot(), now_ms=4000)
            reference = service._load_comparison_catalog()
            self.assertEqual(comparison_cost(bundle.trace_entries, reference.reference_valuation).known_ccost,
                             sum(projection.token_mix.costs))

    def test_normal_report_mix_shows_volume_and_reconciling_costs(self):
        service = compact_fixtures.CompactReportTests.service(self, MutableSource(make_snapshot()))
        report = service.build(ReportRequest())
        prompts = latest_token_prompts(tuple(service._analyzed.values()))
        entries = unique_usage(e for p in prompts for e in p.entries)
        reference = service._load_comparison_catalog()
        self.assertEqual(comparison_cost(entries, reference.reference_valuation).known_ccost, sum(report.token_mix.costs))
        self.assertIn(f"totaling {compact_tokens(report.token_mix.total_tokens)} tokens.", rendered(report))


class ModelHistoryTests(unittest.TestCase):
    def test_prompts_unique_per_model_calls_count_requests(self):
        a, b = "gpt-test", "claude-test"
        one = [entry(a, TokenUsage(input=10), i) for i in range(3)] + [entry(b, TokenUsage(input=10), 3)]
        two = [entry(a, TokenUsage(input=10), 4 + i) for i in range(2)]
        compaction = entry(a, TokenUsage(input=10), 9)
        prompt_of = {**{e: ("s", "p1") for e in one}, **{e: ("s", "p2") for e in two}}
        rows = {row.model.model: row for row in model_token_mixes(
            (*one, *two, compaction), prompt_of, PRICES.reference_category_valuation, model_key=lambda m: m.model)}
        self.assertEqual((2, 6), (rows[a].prompts, rows[a].calls))
        self.assertEqual((1, 1), (rows[b].prompts, rows[b].calls))

    def service(self, availability):
        return compact_fixtures.CompactReportTests.service(self, MutableSource(make_snapshot()), availability=availability)

    def test_history_report_scans_all_roots_filters_and_renders_table(self):
        service = self.service(Availability(("github-copilot/gpt-test",)))
        calls = []
        report = service.build_token_mix_history(lambda label, percent: calls.append((label, percent)))
        self.assertEqual(ReportKind.TOKEN_MIX, report.kind)
        (row,) = report.model_token_mix
        bundle = analyze_snapshot(make_snapshot(), now_ms=4000)
        self.assertEqual(("GPT Test", 2, len(bundle.trace_entries)), (row.model, row.prompts, row.calls))
        self.assertEqual(HISTORY_NOTE, report.notes[0])
        self.assertFalse(service._analyzed, "deep scan must not retain snapshots")
        self.assertIn(("Analyzing usage history...", 5), calls)
        self.assertEqual(sorted(p for _l, p in calls), [p for _l, p in calls])
        text = rendered(report)
        for heading in ("Model", "Prompts", "Calls", "Input", "Cache", "Write", "Output", "CCost", "not actual billing"):
            self.assertIn(heading, text)
        self.assertNotIn("Accounts Overview", text)

    def test_non_selectable_models_omitted_and_unknown_availability_fails_open(self):
        hidden = self.service(Availability(("openai/other",))).build_token_mix_history()
        self.assertEqual((), hidden.model_token_mix)
        self.assertIn("1 other historically used model(s) omitted", hidden.notes[1])
        unknown = self.service(Availability(None)).build_token_mix_history()
        self.assertEqual(1, len(unknown.model_token_mix))
        self.assertTrue(any("Could not verify currently selectable" in w for w in unknown.source_warnings))

    def test_cli_help_and_standalone_shape(self):
        self.assertIs(CommandKind.TOKEN_MIX, parse_command(["--token-mix"]).kind)
        for argv in (["--token-mix", "--watch"], ["--token-mix", "2026-01-01"]):
            with self.assertRaises(CliUsageError):
                parse_command(argv)
        self.assertIn("--token-mix", help_text())

    def test_progress_heading_is_transient_and_redirect_is_quiet(self):
        stream = io.StringIO()
        progress = StartupProgress(stream, interactive=True, animate=False, heading="Cost Guard — Token Mix")
        progress.update("Analyzing usage history...", 40)
        self.assertIn("Cost Guard — Token Mix\n\r", stream.getvalue())
        progress.stop()
        self.assertTrue(stream.getvalue().endswith("\x1b[1A\x1b[2K"))
        quiet = io.StringIO()
        plain = StartupProgress(quiet, interactive=False, heading="Cost Guard — Token Mix")
        for percent in range(5, 90, 5):
            plain.update("Analyzing usage history...", percent)
        self.assertEqual(1, quiet.getvalue().count("\n"))
        self.assertNotIn("Token Mix", quiet.getvalue())


class QuotaPaceTests(unittest.TestCase):
    def test_calendar_and_workday_pace_include_today(self):
        pace = paced(copilot(), ms(2026, 10, 5, 8))
        self.assertEqual((27, 20), (pace.days, pace.workdays))
        self.assertEqual("259/day · 350/workday", pace_text(pace))

    def test_weekend_today_not_a_workday_and_swedish_holidays(self):
        self.assertEqual((22, 15), (lambda p: (p.days, p.workdays))(paced(copilot(), ms(2026, 10, 10, 8))))
        reset = ms(2027, 1, 1)
        self.assertEqual(8, paced(copilot(reset=reset), ms(2026, 12, 21, 8)).workdays)
        self.assertEqual(9, paced(copilot(reset=reset), ms(2026, 12, 21, 8), calendar="").workdays)

    def test_zero_workdays_and_final_day_are_safe(self):
        pace = paced(copilot(reset=ms(2026, 10, 12)), ms(2026, 10, 10, 8))
        self.assertEqual((2, 0, None), (pace.days, pace.workdays, pace.per_workday))
        self.assertIn("no workdays left", pace_text(pace))
        self.assertEqual(1, paced(copilot(), ms(2026, 10, 31, 21)).days)
        self.assertIsNone(paced(copilot(), ms(2026, 10, 31, 23, 30)), "local Nov 1 is after the period's final day")
        self.assertEqual("0/day · 0/workday", pace_text(paced(copilot("0"), ms(2026, 10, 5, 8))))
        self.assertEqual("2/day", pace_text(paced(copilot("50"), ms(2026, 10, 12, 8))).split(" · ")[0])

    def test_no_misleading_pace_without_boundary_or_native_balance(self):
        now = ms(2026, 10, 5, 8)
        for component in (copilot(reset=None), replace(copilot(), used=None, limit=None, remaining=None),
                          copilot(unlimited=True), copilot(period="rolling", duration_seconds=3600),
                          copilot(reset=now - 1)):
            self.assertIsNone(paced(component, now))

    def test_copilot_reset_boundary_and_extra_credits_excluded(self):
        payload = {"copilot_plan": "individual_pro", "access_type_sku": "plus_monthly_subscriber_quota",
                   "quota_reset_date": "2026-11-01", "quota_reset_date_utc": "2026-11-01T00:00:00.000Z",
                   "quota_snapshots": {"premium_interactions": {
                       "entitlement": 7000, "credits_used": 93, "remaining": 6906, "percent_remaining": 98.6,
                       "overage_entitlement": 500, "overage_permitted": True, "has_quota": True, "unlimited": False}}}
        window = convert_internal_user_payload(payload, fetched_at_ms=1).windows[0]
        self.assertEqual(RESET, window.reset_at_ms)
        self.assertEqual(Decimal(7000), window.native_limit)
        date_only = convert_internal_user_payload({**payload, "quota_reset_date_utc": None}, fetched_at_ms=1)
        self.assertEqual(RESET, date_only.windows[0].reset_at_ms)
        unknown = convert_internal_user_payload({**payload, "quota_reset_date_utc": "soon", "quota_reset_date": None}, fetched_at_ms=1)
        self.assertIsNone(unknown.windows[0].reset_at_ms)

    def test_pace_needs_no_usage_history_and_renders_compact_and_vertical(self):
        account = AccountSnapshot(AccountRef("opencode", "github-copilot", "1"), 1, "GitHub Copilot", "Pro+",
                                  quotas=(copilot(),))
        now = ms(2026, 10, 5, 8)
        (projection,) = account_projections((account,), (), PRICES, now_ms=now, today_start_ms=now, month_start_ms=now,
                                            timezone_id="Europe/Stockholm", workday_calendar="SE")
        self.assertEqual(1, len(projection.pace))
        styler = AnsiStyler({}, enabled=False)
        wide = capacity_lines(projection, styler, "UTC", width=240, now_ms=now, watch=True, primary_label_width=5)
        self.assertEqual("GitHub Copilot Pro+   Month  ██████████ 100% · 7000/7000 · Remaining: 259/day · 350/workday", wide[0])
        tall = capacity_lines(projection, styler, "UTC", width=60, force_vertical=True, now_ms=now)
        self.assertIn("  Remaining  259/day · 350/workday", tall)

    def test_extra_credit_limit_stays_separate_and_never_becomes_remaining(self):
        now = ms(2026, 10, 5, 8)
        premium = {"entitlement": 7000, "credits_used": 7000, "percent_remaining": 0,
                   "overage_entitlement": 500, "overage_permitted": True, "has_quota": True}
        snapshot = convert_internal_user_payload({"copilot_plan": "pro_plus", "quota_reset_date": "2026-11-01",
            "quota_snapshots": {"premium_interactions": premium}}, fetched_at_ms=now)
        account = normalize_quota(snapshot, AccountRef("fixture", "github-copilot", "a"), "GitHub Copilot")
        (projection,) = account_projections((account,), (), PRICES, now_ms=now, today_start_ms=now, month_start_ms=now)
        self.assertEqual(Decimal(0), projection.pace[0].per_day)
        styler = AnsiStyler({}, enabled=False)
        watch = "\n".join(capacity_lines(projection, styler, "UTC", width=200, watch=True, now_ms=now,
                                        primary_label_width=5))
        self.assertIn("0/7000 · Remaining: 0/day · 0/workday | Extra credit limit 500", watch)
        self.assertNotIn("AI credits", watch)
        self.assertNotIn("$", watch)
        report = "\n".join(capacity_lines(projection, styler, "UTC", width=120, force_vertical=True, now_ms=now))
        self.assertIn("Extra credit limit 500 AI credits", report)
        for value in (None, 0, -1, True, "invalid"):
            changed = {**premium, "overage_entitlement": value}
            result = convert_internal_user_payload({"quota_snapshots": {"premium_interactions": changed}}, fetched_at_ms=now)
            self.assertFalse(result.billing_components)
        paused = convert_entitlement_payload({"quotas": {"premiumInteractionsQuota": {
            "total": 7000, "creditsUsed": 7000, "overage_entitlement": 500, "overage_permitted": False}}}, fetched_at_ms=now)
        self.assertEqual("paused", paused.billing_components[0].status)

    def test_report_keeps_credit_units_money_reset_and_separate_remaining(self):
        now = ms(2026, 10, 5, 8)
        account = AccountSnapshot(AccountRef("fixture", "other", "a"), now, "Any subscription", quotas=(copilot(),))
        (projection,) = account_projections((account,), (), PRICES, now_ms=now, today_start_ms=now, month_start_ms=now)
        text = "\n".join(capacity_lines(projection, AnsiStyler({}, enabled=False), "UTC", width=160,
                                       force_vertical=True, now_ms=now))
        self.assertIn("100% · 7000/7000 AI credits ($70.00/$70.00)", text)
        self.assertIn("Reset at 2026-11-01 00:00", text)
        self.assertIn("\n  Remaining  259/day · 350/workday", text)
        self.assertNotIn("Native", text)

    def test_provider_exhausted_quota_and_extra_limit_use_existing_single_fetch(self):
        payload = {"copilot_plan": "pro_plus", "quota_reset_date": "2026-11-01", "quotas": {
            "premiumInteractionsQuota": {"total": 7000, "creditsUsed": 7000, "hasQuota": True,
                                          "overage_entitlement": 500, "overage_permitted": True}}}
        calls = []
        def fetch(url, *_args):
            calls.append(url)
            return JsonResponse(True, 200, payload)
        with tempfile.TemporaryDirectory() as td:
            auth = Path(td) / "auth.json"
            auth.write_text(json.dumps({"github-copilot": {"type": "oauth", "refresh": "fixture-only"}}))
            baseline = auth.read_bytes()
            provider = GitHubCopilotAccountProvider(auth_json_path=str(auth), json_get=fetch, now_ms=lambda: ms(2026, 10, 5))
            (account,) = provider.get_account_snapshots()
            self.assertEqual(baseline, auth.read_bytes())
        self.assertEqual(1, len(calls), "presentation must not add a provider fetch")
        self.assertEqual(Decimal(0), account.quotas[0].remaining)
        self.assertIsInstance(account.quotas[0].remaining, Decimal)
        self.assertEqual(Decimal(0), account.quotas[0].remaining_money)
        self.assertEqual(Decimal(500), account.billing[0].amount)
        self.assertEqual("budget", account.billing[0].kind, "a limit is not a purchased balance")


if __name__ == "__main__":
    unittest.main()
