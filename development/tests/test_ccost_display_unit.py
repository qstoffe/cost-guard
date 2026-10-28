"""Reference USD presentation, isolation and unchanged native/canonical values."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from development.tests.fixtures.compact_reports import rendered, report_service
from development.tests.fixtures.package_copy import make_package
from development.tests.fixtures.warning_projections import warning_prompt, warning_watch_projection
from src.analysis.context import PriceWarningSeverity
from src.application.contracts import record
from src.application.display import with_display
from src.application.live_projection import project_live
from src.application.projection import project
from src.cli import CliUsageError, parse_command
from src.config import ConfigError, load_configuration
from src.display import native_amount, relative_cost, unaccounted_usage
from src.numbers import ccost_amount, ccost_display, ccost_range, reference_rate
from src.presentation import WatchRenderer
from src.presentation.report import _MetricProfile
from src.reports import ReportKind, ReportRequest

ROOT = Path(__file__).resolve().parents[2]


class CCostDisplayUnitTests(unittest.TestCase):
    def test_usd_goldens_preserve_exact_raw_values_and_unknowns(self):
        cases = [(None, "N/A"), ("0", "$0.00"), ("0.000001", "$0.00"),
                 ("0.5", "$0.01"), ("1", "$0.01"), ("395", "$3.95"),
                 ("10742", "$107.42"), ("-395", "$-3.95"), ("-0.01", "$0.00"),
                 ("123456789012345678901234567890", "$1234567890123456789012345678.90")]
        for raw, expected in cases:
            value = None if raw is None else Decimal(raw)
            dto = with_display(record(ccost=value), ccost_display_unit="usd").to_json()
            with self.subTest(raw=raw):
                self.assertEqual(raw, dto["ccost"])
                self.assertEqual(expected, dto["display"]["ccost"])
        partial = with_display(record(ccost=Decimal("395"), unresolved_cost=True),
                               ccost_display_unit="usd").to_json()
        self.assertEqual("?$3.95", partial["display"]["ccost"])
        self.assertEqual("N/A", ccost_amount(Decimal(0), unresolved=True, unit="usd"))

    def test_render_scope_is_nested_exception_safe_and_thread_local(self):
        with ccost_display("usd"):
            self.assertEqual("$0.00–$3.95", ccost_range(Decimal("0.01"), Decimal(395)))
            self.assertEqual("0", ccost_amount(Decimal(0), unit="credits"))
            with self.assertRaises(RuntimeError):
                with ccost_display("credits"):
                    raise RuntimeError("render failed")
            self.assertEqual("$3.95", ccost_amount(Decimal(395)))
        self.assertEqual("395", ccost_amount(Decimal(395)))
        def export(unit):
            return with_display(record(ccost=Decimal(395)), ccost_display_unit=unit).to_json()["display"]["ccost"]
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(["395", "$3.95"] * 20, list(pool.map(export, ["credits", "usd"] * 20)))

    def test_cli_override_combines_with_every_supported_scope(self):
        for args in ([], ["--watch"], ["--all-models"], ["--token-mix"], ["--sessions", "all"],
                     ["ses_example"], ["ses_example", "--watch"], ["2026-10-28"], ["2026-10-01:2026-10-28"]):
            for unit in ("credits", "usd"):
                command = parse_command(["--ccost-unit", unit, *args])
                self.assertEqual(replace(parse_command(args), ccost_unit=unit), command)
                self.assertEqual(command, parse_command([*args, "--ccost-unit", unit]))
        for args in (["--ccost-unit"], ["--ccost-unit", "USD"], ["--ccost-unit", "sek"],
                     ["--ccost-unit", "usd", "--ccost-unit", "credits"]):
            with self.assertRaises(CliUsageError):
                parse_command(args)
        result = subprocess.run([sys.executable, "cost-guard.py", "--ccost-unit", "invalid"],
                                cwd=ROOT, capture_output=True, timeout=10)
        self.assertEqual(2, result.returncode)
        self.assertIn(b"--ccost-unit credits|usd", result.stdout)

    def test_legacy_config_inherits_credits_and_invalid_units_fail_startup(self):
        with tempfile.TemporaryDirectory() as tmp:
            package = make_package(tmp)
            self.assertEqual("credits", load_configuration(package).values["ccostDisplayUnit"])
            path = package / "config/user-config.jsonc"
            for value in ("usd", "credits", None, 1, [], "USD", "sek"):
                path.write_text(json.dumps({"ccostDisplayUnit": value}), encoding="utf-8")
                if value in ("usd", "credits"):
                    self.assertEqual(value, load_configuration(package).values["ccostDisplayUnit"])
                else:
                    with self.assertRaisesRegex(ConfigError, "ccostDisplayUnit"):
                        load_configuration(package)

    def test_all_report_modes_keep_raw_totals_order_and_thresholds(self):
        service = report_service(self)
        self.addCleanup(service.close_accounts)
        for kind in ReportKind:
            request = ReportRequest(kind, session_id="root" if kind is ReportKind.SESSION else None,
                                    date_text="1970-01-01" if kind is ReportKind.DATE else None)
            report = service.build_token_mix_history() if kind is ReportKind.TOKEN_MIX else service.build(request)
            credits = project(report).to_json()
            usd = project(report, ccost_display_unit="usd").to_json()
            text = rendered(report, {"ccostDisplayUnit": "usd", "timezone": "UTC"})
            with self.subTest(kind=kind):
                self.assertEqual("usd", usd["ccost_display_unit"])
                self.assertIn("reference USD, not billing", text)
                self.assertEqual([row["model"] for row in credits["model_comparison"]],
                                 [row["model"] for row in usd["model_comparison"]])
                for block in usd["prompt_blocks"]:
                    self.assertIn(block["display"]["total_ccost"], text)
                    for row in block["rows"]:
                        self.assertIn(row["display"]["ccost"], text)
                for row in usd["session_usage"]:
                    self.assertIn(row["display"]["ccost"], text)
            def raw(value):
                if isinstance(value, dict):
                    return {key: raw(item) for key, item in value.items() if key not in {"display", "ccost_display_unit"}}
                return [raw(item) for item in value] if isinstance(value, list) else value
            self.assertEqual(raw(credits), raw(usd))
        profile = _MetricProfile([Decimal("0.01"), Decimal("0.02"), Decimal("0.03")], {"promptCostMinSamples": 2})
        before = [profile.role(value) for value in (Decimal("0.01"), Decimal("0.03"))]
        with ccost_display("usd"):
            self.assertEqual(before, [profile.role(value) for value in (Decimal("0.01"), Decimal("0.03"))])

    def test_watch_progress_aborted_context_and_large_values_are_not_truncated(self):
        for state in ({"in_progress": True}, {"aborted": True}, {"unresolved_cost": True}):
            prompt = replace(warning_prompt(PriceWarningSeverity.NONE), ccost=Decimal("123456789.12"),
                             incoming_context_ccost=Decimal(395), extra_ccost=Decimal("0.01"), **state)
            frame = warning_watch_projection(prompt)
            stream = io.StringIO()
            WatchRenderer({"ccostDisplayUnit": "usd"}, stream=stream, interactive=False).render(frame)
            dto = project_live(frame, ccost_display_unit="usd").to_json()
            self.assertIn(dto["rows"][0]["prompt"]["display"]["ccost"], stream.getvalue())
            self.assertIn("$1234567.89", stream.getvalue())
            self.assertEqual("$3.95", dto["rows"][0]["prompt"]["display"]["incoming_context_ccost"])
            self.assertEqual("$0.00", dto["rows"][0]["prompt"]["display"]["extra_ccost"])

    def test_native_quotas_billing_residual_rates_and_relative_cost_stay_independent(self):
        value = record(known_ccost=Decimal(395), observed_requests=1, priced_requests=1,
                       used=Decimal(395), remaining=Decimal(395), limit=Decimal(1000), unit="AI credits",
                       billed_cost=Decimal(395), unaccounted_usage=Decimal(395),
                       relative_cost=Decimal(395), price_summary="395/0/0/1")
        credits = with_display(value).to_json()
        usd = with_display(value, ccost_display_unit="usd").to_json()
        self.assertEqual("$3.95", usd["display"]["account_ccost"])
        for key in ("used", "remaining", "limit", "billed_cost", "unaccounted_usage", "relative_cost", "price_summary"):
            self.assertEqual(credits["display"][key], usd["display"][key])
        with ccost_display("usd"):
            self.assertEqual("395", native_amount(Decimal(395), "AI credits", kind="consumed"))
            self.assertEqual("+395", unaccounted_usage(Decimal(395)))
            self.assertEqual("395.0x", relative_cost(Decimal(395)))
            self.assertEqual("395", reference_rate(Decimal(395)))

    def test_date_note_uses_effective_unit_without_revaluing_range(self):
        service = report_service(self)
        self.addCleanup(service.close_accounts)
        request = ReportRequest(ReportKind.DATE, date_text="1970-01-01")
        credits = service.build(request)
        service.config["ccostDisplayUnit"] = "usd"
        usd = service.build(request)
        self.assertEqual(credits.prompt_blocks, usd.prompt_blocks)
        self.assertTrue(usd.notes[0].startswith("CCost for range: $"))
        self.assertNotEqual(credits.notes[0], usd.notes[0])

    def test_empty_watch_has_explicit_zero_dollars_without_changing_unknowns(self):
        from src.watch.models import WatchProjection
        stream = io.StringIO()
        WatchRenderer({"ccostDisplayUnit": "usd"}, stream=stream, interactive=False).render(
            WatchProjection("Watch", "V2", (), now_ms=2000))
        self.assertIn("Watch: $0.00", stream.getvalue())
        self.assertEqual("N/A", ccost_amount(None, unit="usd"))
        self.assertEqual("0", ccost_amount(Decimal(0)))


if __name__ == "__main__":
    unittest.main()
