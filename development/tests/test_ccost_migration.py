"""Domain-unit migration, conservative numbers and shared startup/quota UX."""
from __future__ import annotations

from dataclasses import replace
import ast
from decimal import Decimal as D
import io
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest
from unittest.mock import patch

from development.fixtures.session_snapshots import make_snapshot
from src import bootstrap
from src.analysis import analyze_snapshot
from src.analysis.cache import AnalysisDependencies, DerivedAnalysisCache
from src.analysis.comparisons import model_comparison_rows
from src.analysis.context import estimate_next_context
from src.analysis.quota_pace import QuotaPace
from src.analysis.token_mix import priced_token_mix
from src.analysis.valuation import comparison_cost, billed_spend
from src.cache import CacheDatabase, CacheRepository, CACHE_FILENAME
from src.cli import parse_command, startup_mode
from src.config import ConfigError, load_configuration
from src.domain import AccountRef, AccountSnapshot, CostDisposition, ModelPricing, ModelRef, PricingTier, QuotaComponent, TokenUsage
from src.domain.ccost import CCOST_PER_REFERENCE_USD, reference_usd_to_ccost
from src.numbers import ccost_amount, ccost_range, consumed_capacity, remaining_capacity, exact_number, reference_rate
from src.presentation import ReportRenderer, StartupProgress, WatchRenderer
from src.presentation.accounts import capacity_lines
from src.presentation.terminal import AnsiStyler
from src.presentation.token_mix import compact_tokens, token_mix_lines
from src.pricing.catalog import PricingCatalog, price_token_categories, price_token_usage
from src.reports.model_comparison import price_summary
from src.reports.models import AccountProjection, AccountsQuotasProjection, ModelTokenMixProjection, ReportKind, ReportProjection
from src.reports.prompts import build_prompt_block
from src.version import mode_heading
from src.watch.models import WatchProjection

ROOT = Path(__file__).resolve().parents[2]
MODEL = ModelRef("github-copilot", "gpt-test", "Test")
NATIVE = ModelPricing(MODEL, "USD", D(2), D("0.2"), D("2.5"), D(10))


class CCostDomainTests(unittest.TestCase):
    def test_canonical_rates_native_billing_and_conversion_are_separate(self):
        catalog = PricingCatalog((NATIVE,))
        tokens = TokenUsage(input=1_000_000, cache_read=1_000_000, cache_write=1_000_000, output=1_000_000)
        self.assertEqual(D(100), CCOST_PER_REFERENCE_USD)
        self.assertEqual(D(437), reference_usd_to_ccost(D("4.37")))
        self.assertEqual((D(200), D(20), D(250), D(1000)), catalog.reference_category_valuation(MODEL, tokens))
        self.assertEqual(D(1470), catalog.reference_valuation(MODEL, tokens))
        self.assertEqual(D("14.7"), catalog.estimate(MODEL, tokens))
        self.assertIs(NATIVE, catalog.models[0])
        self.assertEqual("2/0.2/2.5/10", price_summary(catalog, "gpt-test"))
        self.assertIs(catalog.ccost_models[0], catalog.reference_prices("gpt-test"))

    def test_conversion_relationship_has_one_authority(self):
        with patch("src.domain.ccost.CCOST_PER_REFERENCE_USD", D(125)):
            catalog = PricingCatalog((NATIVE,))
            self.assertEqual(D(250), catalog.reference_valuation(MODEL, TokenUsage(input=1_000_000)))
            self.assertEqual("2/0.2/2.5/10", price_summary(catalog, "gpt-test"))
        # Rates already converted in the boundary are not scaled again later.
        self.assertEqual(D(250), catalog.reference_valuation(MODEL, TokenUsage(input=1_000_000)))

    def test_native_currency_cannot_be_guessed_or_double_converted(self):
        for currency in ("EUR", "CCost", "unknown"):
            catalog = PricingCatalog((replace(NATIVE, currency=currency),))
            self.assertIsNone(catalog.reference_valuation(MODEL, TokenUsage(input=100)))
            self.assertIsNone(catalog.reference_input_context(MODEL, input_tokens=100,
                cache_read_tokens=0, cache_write_tokens=0, request_input_tokens=100))

    def test_request_tiers_categories_precision_and_relative_multipliers(self):
        tiers = (PricingTier(max_input_tokens=1000, per_million_input=D("2.123456789"),
                            per_million_cache_read=D("0.0123456789"), per_million_cache_write=D("2.5"), per_million_output=D("10.001")),
                 PricingTier(min_input_tokens=1001, per_million_input=D("4.123456789"),
                            per_million_cache_read=D("0.0234567891"), per_million_cache_write=D("5.5"), per_million_output=D("20.002")))
        native = replace(NATIVE, tiers=tiers)
        catalog = PricingCatalog((native, replace(native, model=ModelRef("github-copilot", "other", "Other"),
            tiers=tuple(replace(t, **{n: getattr(t, n) * 3 for n in
                ("per_million_input", "per_million_cache_read", "per_million_cache_write", "per_million_output")}) for t in tiers))))
        requests = (TokenUsage(input=500, cache_read=200, cache_write=5, output=9, reasoning=3),
                    TokenUsage(input=900, cache_read=900, output=11))
        mix = priced_token_mix(((MODEL, t) for t in requests), catalog.reference_category_valuation)
        expected = sum((price_token_usage(native, t, t.input + t.cache_read + t.cache_write) for t in requests), D(0)) * 100
        self.assertEqual(expected, sum(mix.costs, D(0)))
        self.assertNotEqual(expected, D(ccost_amount(expected)))
        self.assertEqual("2.123456789/0.0123456789/2.5/10.001→4.123456789/0.0234567891/5.5/20.002 (>1000)", price_summary(catalog, "Test"))
        records = analyze_snapshot(make_snapshot(), now_ms=4000).prompts
        rows = model_comparison_rows(records, catalog)
        # Repeating token-share division retains Decimal context precision;
        # no display rounding enters analysis, and shown multipliers are unchanged.
        self.assertLess(abs(rows[0].relative_to_lowest - D(3)), D("1e-24"))
        self.assertEqual(("3.0x", "1.0x"), tuple(f"{row.relative_to_lowest:.1f}x" for row in rows))

    def test_prompt_context_session_and_subscription_billing_reconcile(self):
        snapshot = make_snapshot()
        snapshot = replace(snapshot, invocations=tuple(replace(i, cost=replace(i.cost, amount=D(0)),
            cost_disposition=CostDisposition.INCLUDED_SUBSCRIPTION) for i in snapshot.invocations))
        bundle = analyze_snapshot(snapshot, now_ms=4000)
        catalog = PricingCatalog((NATIVE,))
        block = build_prompt_block(session_id="root", title="Synthetic", bundle=bundle, snapshot=snapshot,
                                   catalog=catalog, config={})
        self.assertEqual(D(0), block.billed_cost)
        self.assertEqual(comparison_cost(bundle.trace_entries, catalog.reference_valuation).ccost, block.total_ccost)
        self.assertEqual(block.total_ccost, block.total_main_ccost + block.total_subagent_ccost)
        for row in block.rows:
            self.assertEqual(row.ccost, row.comparison_cost.known_ccost)
            if row.incoming_context_ccost is not None:
                self.assertEqual(row.ccost, row.incoming_context_ccost + row.extra_ccost)
        record = next(p for p in bundle.prompts if p.last_root_entry is not None)
        estimate = estimate_next_context(record, catalog)
        self.assertGreater(estimate.fresh_ccost, estimate.cached_ccost)
        self.assertEqual(D(0), billed_spend(bundle.trace_entries))
        report = ReportProjection(ReportKind.SESSION, "Session", "V2", prompt_blocks=(block,))
        stream = io.StringIO()
        ReportRenderer({}, stream=stream, color_enabled=False, terminal_width=180).render(report)
        self.assertNotIn("$", stream.getvalue())
        self.assertIn("~Ictx CCost", stream.getvalue())
        self.assertIn("~Extra CCost", stream.getvalue())

    def test_running_threshold_compares_unrounded_ccost_at_economic_boundary(self):
        snapshot = make_snapshot(running=True)
        snapshot = replace(snapshot, invocations=tuple(replace(i, tokens=TokenUsage(input=9000000))
            if i.message_id == "a_next" else i for i in snapshot.invocations))
        bundle = analyze_snapshot(snapshot, now_ms=2200)
        def row(config):
            return next(r for r in build_prompt_block(session_id="root", title="S", bundle=bundle, snapshot=snapshot,
                catalog=PricingCatalog((NATIVE,)), config=config).rows if r.in_progress)
        self.assertEqual(D(1800), row({}).ccost)
        self.assertTrue(row({}).running_cost_warning)
        self.assertFalse(row({"runningPromptWarningCCost": 1800.01}).running_cost_warning)
        self.assertFalse(row({"runningPromptWarningCCost": 0}).running_cost_warning)


class NumericSemanticsTests(unittest.TestCase):
    def test_presentation_and_tool_format_specs_never_request_grouping(self):
        files = (*ROOT.joinpath("src").rglob("*.py"), *ROOT.joinpath("development/tools").glob("*.py"))
        for path in files:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.FormattedValue) and node.format_spec is not None:
                    spec = "".join(v.value for v in node.format_spec.values if isinstance(v, ast.Constant))
                    self.assertNotIn(",", spec, f"grouping in {path.relative_to(ROOT)}")
                    self.assertNotIn("_", spec, f"grouping in {path.relative_to(ROOT)}")
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "format" and len(node.args) > 1:
                    spec = node.args[1]
                    if isinstance(spec, ast.Constant) and isinstance(spec.value, str):
                        self.assertNotIn(",", spec.value, str(path))
                        self.assertNotIn("_", spec.value, str(path))

    def test_adaptive_consumed_amount_boundaries(self):
        for raw, expected in (("0", "0"), ("0.000001", "<0.1"), ("0.099999", "<0.1"),
                ("0.1", "0.1"), ("0.100001", "0.2"), ("0.4", "0.4"), ("0.9999", "1.0"),
                ("1", "1"), ("1.01", "2"), ("6.7", "7"), ("437.1", "438"), ("5300000", "5300000")):
            with self.subTest(raw=raw):
                self.assertEqual(expected, ccost_amount(D(raw)))
                self.assertEqual(expected, consumed_capacity(D(raw)))
        self.assertEqual("?438", ccost_amount(D("437.1"), unresolved=True))
        self.assertEqual("N/A", ccost_amount(D(0), unresolved=True))
        self.assertEqual("38–217", ccost_range(D("37.01"), D("216.4")))

    def test_remaining_never_rounds_up_and_preserves_small_positives(self):
        for raw, expected in (("0", "0"), ("0.009", "<0.1"), ("0.1", "0.1"), ("0.19", "0.1"),
                              ("0.9999", "0.9"), ("1.999", "1"), ("6993.7", "6993")):
            self.assertEqual(expected, remaining_capacity(D(raw)))
            if not expected.startswith("<"):
                self.assertLessEqual(D(expected), D(raw))

    def test_exact_rates_limits_and_large_counters_have_no_grouping(self):
        for raw, expected in (("2.5000", "2.5"), ("0.000000123456789", "0.000000123456789"),
                              ("1000", "1000"), ("6993.70", "6993.7")):
            self.assertEqual(expected, reference_rate(D(raw)))
            self.assertEqual(expected, exact_number(D(raw)))
        self.assertEqual("100000000000000000001", exact_number(100000000000000000001))
        self.assertEqual("5.3M", compact_tokens(5300000))

    def test_native_capacity_keeps_money_and_exact_limits_separate(self):
        quota = QuotaComponent("Monthly", remaining=D("6993.7"), limit=D("7000.125"),
            remaining_fraction=D("0.999"), unit="AI credits", remaining_money=D("69.937"), limit_money=D("70.00125"))
        account = AccountProjection(AccountSnapshot(AccountRef("fixture", "generic", "1"), 1, "Any", quotas=(quota,)), "Any")
        styler = AnsiStyler({}, enabled=False)
        text = "\n".join(capacity_lines(account, styler, "UTC", width=180, force_vertical=True))
        self.assertIn("6993/7000.125 AI credits ($69.94/$70.00)", text)
        used = replace(quota, remaining=None, remaining_fraction=None, used=D("6993.7"))
        account = replace(account, account=replace(account.account, quotas=(used,)))
        text = "\n".join(capacity_lines(account, styler, "UTC", width=180, force_vertical=True))
        self.assertIn("6994 AI credits used / 7000.125", text)

    def test_historical_counts_mix_cost_and_session_numbers_are_ungrouped(self):
        mix = priced_token_mix(((MODEL, TokenUsage(input=1000000)),), PricingCatalog((NATIVE,)).reference_category_valuation)
        projection = ReportProjection(ReportKind.TOKEN_MIX, "Token Mix", "V2",
            model_token_mix=(ModelTokenMixProjection("Test", 10000, 5300000, mix),))
        stream = io.StringIO()
        ReportRenderer({}, stream=stream, color_enabled=False, terminal_width=180).render(projection)
        self.assertIn("10000", stream.getvalue())
        self.assertIn("5300000", stream.getvalue())
        self.assertNotRegex(stream.getvalue(), r"\d[, ]\d{3}(?:\D|$)")
        self.assertNotIn("$", stream.getvalue())
        self.assertIn("(200)", stream.getvalue())
        self.assertIn("(200)", token_mix_lines("10000 prompts", mix)[0])


class ConfigurationCacheTests(unittest.TestCase):
    def test_obsolete_keys_fail_before_any_runtime_and_user_file_is_unchanged(self):
        for override, setting in (({"runningPromptWarningUsd": "secret-value"}, "runningPromptWarningUsd"),
                ({"thresholds": {"watchCostDeltaDisplayUsd": None}}, "thresholds.watchCostDeltaDisplayUsd"),
                ({"watchCostDeltaDisplayUsd": 0.1}, "watchCostDeltaDisplayUsd")):
            with self.subTest(setting=setting), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                (root / "config").mkdir()
                shutil.copy2(ROOT / "config/default-config.jsonc", root / "config/default-config.jsonc")
                user = root / "config/user-config.jsonc"
                user.write_text(json.dumps(override), encoding="utf-8")
                before = user.read_bytes()
                with self.assertRaises(ConfigError) as error:
                    load_configuration(root)
                self.assertIn("config/user-config.jsonc", str(error.exception))
                self.assertIn(setting, str(error.exception))
                self.assertIn("recognized property", str(error.exception))
                self.assertNotIn("secret-value", str(error.exception))
                output = io.StringIO()
                with patch.object(bootstrap, "PACKAGE_ROOT", root), patch.object(bootstrap, "_select_source") as source, \
                     patch.object(bootstrap, "CacheDatabase") as cache, patch.object(bootstrap, "GitHubCopilotPricingProvider") as pricing, \
                     patch.object(bootstrap, "_account_providers") as accounts, patch("sys.stdout", output):
                    self.assertEqual(1, bootstrap.main([]))
                for integration in (source, cache, pricing, accounts):
                    integration.assert_not_called()
                self.assertIn("Configuration error", output.getvalue())
                self.assertEqual(before, user.read_bytes())
                self.assertFalse((root / "cache").exists())

    def test_defaults_new_config_and_legacy_non_conflicting_handling(self):
        values = load_configuration(ROOT).values
        self.assertEqual(1800, values["runningPromptWarningCCost"])
        self.assertNotIn("runningPromptWarningUsd", values)
        self.assertNotIn("watchCostDeltaDisplayUsd", values["thresholds"])
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "config").mkdir()
            shutil.copy2(ROOT / "config/default-config.jsonc", root / "config/default-config.jsonc")
            user = root / "config/user-config.jsonc"
            user.write_text(json.dumps({"runningPromptWarningCCost": 12.34, "monthlyAiCredits": 100,
                                        "pricingMaxAgeDays": 2}), encoding="utf-8")
            values = load_configuration(root).values
            self.assertEqual(12.34, values["runningPromptWarningCCost"])
            self.assertEqual(48, values["pricingMaxAgeHours"])
            self.assertNotIn("monthlyAiCredits", values)

    def test_new_cache_generation_and_algorithm_reject_old_derived_values(self):
        snapshot = make_snapshot()
        bundle = analyze_snapshot(snapshot, now_ms=4000)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            old_db = CacheDatabase(root, generation=1)
            old_db.initialize()
            old_cache = DerivedAnalysisCache(CacheRepository(old_db))
            old = AnalysisDependencies("same", "same", "v78-analysis-8")
            old_cache.store(bundle, provenance=snapshot.root.provenance, dependencies=old)
            before = old_db.paths.database.read_bytes()
            current_db = CacheDatabase(root)
            current_db.initialize()
            self.assertEqual("cost-guard-cache-v2.sqlite3", CACHE_FILENAME)
            self.assertNotEqual(old_db.paths.database, current_db.paths.database)
            args = dict(provenance=snapshot.root.provenance, root_session_id="root", source_revision=snapshot.source_revision,
                        dependencies=AnalysisDependencies("same", "same"))
            self.assertIsNone(DerivedAnalysisCache(CacheRepository(current_db)).load(**args))
            self.assertIsNone(old_cache.load(**args), "even copied old payloads must miss the algorithm key")
            self.assertEqual(before, old_db.paths.database.read_bytes())


class StartupQuotaGeometryTests(unittest.TestCase):
    def test_actual_modes_share_canonical_heading(self):
        for args, label in (([], "Report"), (["--watch"], "Watch"), (["--token-mix"], "Token Mix"),
                (["--all-models"], "All Models"), (["--sessions", "all"], "Sessions"), (["ses_example"], "Session"),
                (["ses_example", "--watch"], "Watch"), (["2026-10-05"], "Date"),
                (["2026-10-01:2026-10-05"], "Date Range")):
            self.assertEqual(label, startup_mode(parse_command(args)))
            stream = io.StringIO()
            progress = StartupProgress(stream, interactive=True, animate=False, heading=mode_heading(label))
            progress.update("Analyzing", 57)
            text = stream.getvalue()
            self.assertTrue(text.startswith(mode_heading(label) + "\n\r["))
            self.assertNotIn("\n\n", text)
            progress.stop()
            self.assertEqual(1, stream.getvalue().count("\x1b[1A\x1b[2K"))
        from development.tools.collect_diagnostics import _diagnostic_header
        self.assertEqual(mode_heading("Diagnostics"), _diagnostic_header())

    def test_watch_startup_transitions_to_unchanged_dashboard(self):
        stream = io.StringIO()
        renderer = WatchRenderer({}, stream=stream, interactive=True)
        renderer.render_initializing()
        progress = StartupProgress(stream, mode="watch", interactive=True, animate=False, line_sink=renderer.render_startup_status)
        progress.update("Selecting OpenCode source", 5)
        progress.stop()
        self.assertIn(mode_heading("Watch") + "\n", stream.getvalue())
        self.assertNotIn("\n\n", stream.getvalue())
        before = len(stream.getvalue())
        renderer.render(WatchProjection("Watch", "V2", ()))
        final = stream.getvalue()[before:]
        self.assertTrue(final.startswith("\x1b[2J\x1b[3J\x1b[H"))
        self.assertIn("Session / prompt", final)
        self.assertIn("Token Mix %", final)
        self.assertNotIn("Initializing", final)

    def test_redirected_output_has_no_animated_or_transient_heading(self):
        stream = io.StringIO()
        progress = StartupProgress(stream, interactive=False, heading=mode_heading("Token Mix"))
        for percent in (5, 20, 60, 90):
            progress.update("Analyzing history", percent)
        progress.stop()
        self.assertEqual("Cost Guard: Analyzing history\n", stream.getvalue())
        self.assertNotIn("\x1b", stream.getvalue())

    def test_all_report_bars_share_column_but_watch_secondary_does_not(self):
        accounts = tuple(AccountProjection(AccountSnapshot(AccountRef("fixture", "generic", str(i)), 1, label,
            quotas=tuple(QuotaComponent(q, remaining_fraction=D("0.8")) for q in quotas)), label)
            for i, (label, quotas) in enumerate((("One", ("5-hour", "weekly")), ("Two", ("5-hour", "Long window")),
                                               ("Three", ("Monthly",)))))
        quota = AccountsQuotasProjection(comparison_cost((), lambda *_: D(0)), comparison_cost((), lambda *_: D(0)), accounts)
        pace = QuotaPace("Monthly", "AI credits", D("6993.7"), 1, 1, D("6993.7"))
        report_quota = replace(quota, accounts=(*accounts[:2], replace(accounts[2], pace=(pace,))))
        for color in (False, True):
            stream = io.StringIO()
            ReportRenderer({}, stream=stream, color_enabled=color, terminal_width=160)._render_accounts_quotas(
                ReportProjection(ReportKind.NORMAL, "Report", "V2", accounts_quotas=report_quota))
            lines = re.sub(r"\x1b\[[0-9;]*m", "", stream.getvalue()).splitlines()
            bars = [line.index("█") for line in lines if "█" in line]
            self.assertEqual(5, len(bars))
            self.assertEqual(1, len(set(bars)))
            remaining = next(line for line in lines if line.lstrip().startswith("Remaining"))
            self.assertEqual(bars[0], remaining.index("6993/day"))
        stream = io.StringIO()
        WatchRenderer({}, stream=stream, interactive=False, terminal_width=240)._render_quota(WatchProjection("Watch", "V2", (), quota=quota))
        rows = [line for line in stream.getvalue().splitlines() if "█" in line]
        self.assertEqual(1, len({line.index("█") for line in rows}))
        self.assertIn("| Week █", rows[0])
        self.assertIn("| Long window █", rows[1])
        for width in (30, 45, 80):
            for account in accounts:
                lines = capacity_lines(account, AnsiStyler({}, enabled=False), "UTC", width=width,
                                       force_vertical=True, primary_label_width=11)
                self.assertTrue(all(len(line) <= width for line in lines))


if __name__ == "__main__":
    unittest.main()
