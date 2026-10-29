"""CLI-derived Web display goldens, exact raw retention and scope inventory."""
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import shutil
import subprocess
import unittest

from development.tests.fixtures.compact_reports import rendered, report_service
from development.tests.fixtures.warning_projections import warning_prompt, warning_watch_projection
from src.analysis.context import PriceWarningSeverity
from src.application.contracts import record
from src.application.display import with_display
from src.application.live_projection import project_live
from src.application.projection import project
from src.presentation.accounts import money, _native_amount
from src.presentation.duration import duration_text
from src.presentation.model_comparison import aligned_relative_costs
from src.presentation.token_mix import compact_tokens
from src.numbers import ccost_amount
from src.reports import ReportKind, ReportRequest
from src.reports.models import ModelComparisonProjection, RelativePriceLevel

ROOT = Path(__file__).resolve().parents[2]


class WebDisplayTests(unittest.TestCase):
    def test_both_prepared_units_match_independent_cli_exports_for_every_scope(self):
        service = report_service(self)
        self.addCleanup(service.close_accounts)
        def compare_units(credits, usd):
            if isinstance(credits, dict):
                if "display" in credits:
                    variants = credits.get("display_units", {})
                    self.assertEqual(credits["display"], {**usd["display"], **variants.get("credits", {})})
                    self.assertEqual(usd["display"], {**credits["display"], **variants.get("usd", {})})
                    self.assertEqual(variants, usd.get("display_units", {}))
                for key in credits.keys() - {"display", "display_units", "ccost_display_unit"}:
                    compare_units(credits[key], usd[key])
            elif isinstance(credits, list):
                for left, right in zip(credits, usd, strict=True):
                    compare_units(left, right)
            else:
                self.assertEqual(credits, usd)
        for kind in ReportKind:
            request = ReportRequest(kind, session_id="root" if kind is ReportKind.SESSION else None,
                                    date_text="1970-01-01" if kind is ReportKind.DATE else None)
            report = service.build_token_mix_history() if kind is ReportKind.TOKEN_MIX else service.build(request)
            with self.subTest(kind=kind):
                compare_units(project(report).to_json(), project(report, ccost_display_unit="usd").to_json())
        compare_units(project_live(warning_watch_projection(warning_prompt(PriceWarningSeverity.NONE))).to_json(),
                      project_live(warning_watch_projection(warning_prompt(PriceWarningSeverity.NONE)), ccost_display_unit="usd").to_json())

    def test_dual_tokens_exclude_native_values_and_preserve_partial_sparse_markers(self):
        dto = with_display(record(ccost=Decimal("395"), unresolved_cost=True,
            used=Decimal("395"), unit="AI credits", billed_cost=Decimal("395"),
            unaccounted_usage=Decimal("395"), relative_cost=Decimal("395"))).to_json()
        self.assertEqual({"credits": {"ccost": "?395"}, "usd": {"ccost": "?$3.95"}}, dto["display_units"])
        for value in (None, Decimal(0)):
            unknown = with_display(record(ccost=value, unresolved_cost=True)).to_json()
            self.assertEqual("N/A", unknown["display"]["ccost"])
            self.assertNotIn("display_units", unknown)
        sparse = with_display(record(ccost=Decimal(0), calls=0, is_compaction=True)).to_json()
        self.assertEqual("", sparse["display"]["ccost"])
        self.assertNotIn("display_units", sparse)

    def test_ccost_money_and_duration_goldens_keep_exact_raw_values(self):
        cases = [(None, "N/A"), ("0", "0"), ("0.00000000001", "<0.1"),
                 ("0.1234567890123456789", "0.2"), ("1.000000000001", "2"), ("-0.12", "-0.1")]
        for raw, expected in cases:
            value = None if raw is None else Decimal(raw)
            dto = with_display(record(ccost=value, billed_cost=value, duration_ms=59_500)).to_json()
            with self.subTest(raw=raw):
                self.assertEqual(None if value is None else str(value), dto["ccost"])
                self.assertEqual(expected, dto["display"]["ccost"])
                self.assertEqual(ccost_amount(value), dto["display"]["ccost"])
                self.assertEqual(money(value), dto["display"]["billed_cost"])
                self.assertEqual("1m", dto["display"]["duration_ms"])
                self.assertEqual(duration_text(59_500), dto["display"]["duration_ms"])
        for value, unresolved, expected in (("0", True, "N/A"), ("0.12", True, "?0.2"), ("0.12", False, "0.2")):
            dto = with_display(record(ccost=Decimal(value), unresolved_cost=unresolved)).to_json()
            self.assertEqual(expected, dto["display"]["ccost"])

    def test_native_quotas_and_pace_follow_cli_direction_and_units(self):
        for unit, expected in (("AI credits", ("2", "1", "1.23456789")),
                               ("USD", ("$1.23", "$1.23", "$1.23")),
                               ("requests", ("1.23456789",) * 3)):
            raw = Decimal("1.23456789")
            dto = with_display(record(unit=unit, used=raw, remaining=raw, limit=raw,
                remaining_fraction=Decimal("0.755"), per_day=raw, per_workday=None)).to_json()
            self.assertEqual(expected, tuple(dto["display"][key] for key in ("used", "remaining", "limit")))
            for key, kind in (("used", "consumed"), ("remaining", "remaining"), ("limit", "exact")):
                self.assertEqual(_native_amount(raw, unit, kind=kind), dto["display"][key])
            self.assertEqual("76%", dto["display"]["remaining_fraction"])
            self.assertEqual("1", dto["display"]["per_day"])
            self.assertEqual("N/A", dto["display"]["per_workday"])

    def test_relative_tiers_and_native_reference_precision_match_cli(self):
        # The same row feeds the existing terminal renderer and immutable exporter.
        from src.reports.models import ReportProjection
        row = ModelComparisonProjection("Publisher", "model", Decimal("8.0000000000001"),
            "0.000000123456789/0/0/1.23456789 → 0.1/0/0/2 (>200000)", "2026-10-26",
            relative_levels=(RelativePriceLevel(Decimal("8.0000000000001")),
                             RelativePriceLevel(Decimal("16.0000000000001"), 200_000, ">")))
        report = ReportProjection(ReportKind.ALL_MODELS, "Models", "V2", model_comparison=(row,))
        dto = project(report).to_json()["model_comparison"][0]
        self.assertEqual("8.0x → 16.0x (>200K)", dto["display"]["relative_cost"])
        self.assertEqual(dto["display"]["relative_cost"], " ".join(aligned_relative_costs((row,))[0].split()))
        self.assertIn("0.000000123456789", dto["display"]["price_summary"])
        self.assertIn("(>200K)", dto["display"]["price_summary"])
        self.assertEqual("8.0000000000001", dto["relative_cost"])
        self.assertIn("8.0x", rendered(report))

    def test_all_report_scopes_inventory_uses_identical_cli_inputs(self):
        service = report_service(self)
        self.addCleanup(service.close_accounts)
        for kind in ReportKind:
            request = ReportRequest(kind, session_id="root" if kind is ReportKind.SESSION else None,
                                    date_text="1970-01-01" if kind is ReportKind.DATE else None)
            report = service.build_token_mix_history() if kind is ReportKind.TOKEN_MIX else service.build(request)
            text = rendered(report)
            dto = project(report, service.timezone_id).to_json()
            with self.subTest(kind=kind):
                self.assertEqual(report.kind.value, dto["kind"])
                self.assertEqual([row.model for row in report.model_comparison],
                                 [row["model"] for row in dto["model_comparison"]])
                for native, exported in zip(report.prompt_blocks, dto["prompt_blocks"], strict=True):
                    self.assertIn(exported["display"]["total_ccost"], text)
                    self.assertEqual([row.event_id for row in native.rows], [row["event_id"] for row in exported["rows"]])
                for row in dto["session_usage"]:
                    self.assertIn(row["display"]["ccost"], text)
                json.dumps(dto, allow_nan=False)

    def test_watch_roles_partial_mix_unknown_and_configured_timestamp(self):
        prompt = replace(warning_prompt(PriceWarningSeverity.EXCEEDED), in_progress=True,
                         cost_estimated=True, unresolved_cost=True, duration_ms=1500)
        dto = project_live(warning_watch_projection(prompt), "Europe/Stockholm").to_json()
        row = dto["rows"][0]["prompt"]
        self.assertEqual(["running", "estimated", "partial", "threshold"], row["display_roles"])
        self.assertEqual("?12", row["display"]["ccost"])
        self.assertEqual("2s", row["display"]["duration_ms"])
        self.assertEqual("+4k → 120k", row["display"]["incoming_context_tokens"])
        self.assertEqual("--/--/--/--", dto["token_mix"]["display"]["percentages"])
        stamp = with_display(record(observed_at_ms=1_793_052_000_000), "Europe/Stockholm").to_json()
        self.assertEqual("2026-10-26 23:00", stamp["display"]["observed_at_ms"])
        self.assertEqual("1.2M", compact_tokens(1_234_567))

    def test_opaque_maps_compaction_sparsity_and_account_unknown_are_not_zero(self):
        dto = with_display(record(by_model=record(run_ccost=Decimal("1"), duration_ms=Decimal("2")),
            rows=(record(is_compaction=True, calls=0, ccost=Decimal(0), token_mix_percent=None),),
            accounts=(record(known_ccost=Decimal(0), observed_requests=2, priced_requests=0, complete=False),),
            unaccounted_usage=Decimal("-1.23456789"))).to_json()
        self.assertEqual({"run_ccost": "1", "duration_ms": "2"}, dto["by_model"])
        self.assertEqual("", dto["rows"][0]["display"]["ccost"])
        self.assertEqual("", dto["rows"][0]["display"]["calls"])
        self.assertEqual("—", dto["accounts"][0]["display"]["account_ccost"])
        self.assertEqual("N/A", dto["accounts"][0]["display"]["known_ccost"])
        self.assertEqual("-2", dto["display"]["unaccounted_usage"])

    def test_watch_uses_latest_progress_model_and_observation_duration_not_snapshot_duration(self):
        prompt = replace(warning_prompt(PriceWarningSeverity.NONE), in_progress=True, at_ms=1000, duration_ms=1000,
                         watch_model_effort="latest-model (high)")
        frame = replace(warning_watch_projection(prompt), now_ms=4500)
        row = project_live(frame).to_json()["rows"][0]
        self.assertEqual("latest-model (high)", row["watch_model_effort"])
        self.assertEqual(3500, row["watch_duration_ms"])
        self.assertEqual("4s", row["display"]["watch_duration_ms"])
        self.assertEqual(1000, row["prompt"]["duration_ms"], "snapshot evidence stays unchanged")
        # Native compaction sparsity must never hide an observed nonzero charge.
        charged = with_display(record(is_compaction=True, calls=0, ccost=Decimal("2"))).to_json()
        self.assertEqual("2", charged["display"]["ccost"])

    @unittest.skipUnless(shutil.which("node"), "optional JS VM unavailable")
    def test_browser_uses_tokens_not_raw_values_and_places_notices_after_models(self):
        dto = with_display(record(kind="all-models", source_label="V2", source_warning_count=0,
            session_usage=(), prompt_blocks=(), accounts_quotas=None, token_mix=None, model_token_mix=(),
            notes=("Tail note",), recent_model_notice="New notice", model_comparison_promotion_notes=("Promo notice",),
            model_comparison_sample_size=2, pricing_retrieved_at_ms=None, model_comparison=(record(
                publisher="P", model="M", relative_cost=Decimal("0.123456789012345"),
                relative_levels=(), recent=True, promotional=True, promotion_marker="a", superseded=False,
                price_summary="0.000000123456789/0/0/2", release_date=None),))).to_json()
        result = subprocess.run(["node", str(ROOT / "development/tests/integration/web_display.cjs")],
            input=json.dumps(dto), text=True, capture_output=True, timeout=10, cwd=ROOT)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
