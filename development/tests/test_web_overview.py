"""Normal CLI / rendered Overview parity, including exact ranking and fallback."""
from dataclasses import replace
from decimal import Decimal as D
import json
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace
import unittest

from development.tests.fixtures.compact_reports import rendered
from development.tests.fixtures.quota_rendering import quotas, rolling
from src.analysis.comparisons import model_comparison_rows
from src.analysis.token_mix import TokenMix
from src.analysis.valuation import ComparisonCost
from src.application.projection import project
from src.domain import ModelPricing, ModelRef, PricingTier
from src.pricing.catalog import PricingCatalog
from src.reports.models import ModelComparisonProjection, ReportKind, ReportProjection

ROOT = Path(__file__).resolve().parents[2]


def tier(price, minimum=None):
    return PricingTier(min_input_tokens=minimum, per_million_input=D(price),
        per_million_cache_read=D(price), per_million_cache_write=D(price),
        per_million_output=D(price), input_threshold_operator=">" if minimum else None)


@unittest.skipUnless(shutil.which("node"), "optional JS VM unavailable")
class OverviewTests(unittest.TestCase):
    def test_normal_table_keeps_exact_cli_ranking_tiers_notices_and_account_scope(self):
        # Distinct raw values round to the same text; equal bases need tier ranking.
        models = tuple(ModelPricing(ModelRef("github-copilot", name, name), "USD", tiers=levels,
            metadata={"publisher": "Test"}) for name, levels in (
                ("A", (tier("8.01"),)), ("Z", (tier("8.04"),)),
                ("TierLow", (tier("8"), tier("16", 200001))),
                ("TierHigh", (tier("8"), tier("20", 1000001))),
                ("Reference", (tier("1"),))))
        sample = (SimpleNamespace(input_tokens=20, cache_read_tokens=60,
                                  cache_write_tokens=10, output_tokens=10),)
        for fallback in (False, True):
            rows = model_comparison_rows(() if fallback else sample, PricingCatalog(models))
            self.assertEqual(["Z", "A", "TierHigh", "TierLow", "Reference"], [r.model_name for r in rows])
            items = tuple(ModelComparisonProjection(r.publisher, r.model_name, r.relative_to_lowest,
                "1/1/1/1", None, promotion_marker=1 if r.model_name == "TierLow" else None,
                promotional=r.model_name == "TierLow", relative_levels=r.relative_levels) for r in rows)
            account = replace(rolling(), ccost_scopes=(("today", ComparisonCost(D("1.01"))),),
                ccost_account_unknown=True, ccost_notes=("Attribution incomplete",), billed_month=D("2.345"))
            report = ReportProjection(ReportKind.NORMAL, "Report", "V2", model_comparison=items,
                model_comparison_sample_size=0 if fallback else 1, accounts_quotas=quotas(account),
                token_mix=TokenMix() if fallback else TokenMix((20, 60, 10, 10), (20, 60, 10, 10),
                    sample_size=1, request_count=1, costs=(D("2"), D("6"), D("1"), D("1")), priced_requests=1),
                model_comparison_promotion_notes=("Promotion terms",), recent_model_notice="New models",
                notes=("Final note",))
            cli = rendered(report)
            dto = project(report).to_json()
            cli_rows = [line.split("|")[2].strip() for line in cli.splitlines() if line.startswith("| Test")]
            self.assertEqual(["Z", "A", "TierHigh", "TierLow", "Reference"], cli_rows)
            if not fallback:
                self.assertIn("8.0x", cli)
                for expected in ("16.0x", "(>200K)", "20.0x", "(>1M)"):
                    self.assertIn(expected, cli)
                self.assertEqual("8.0x → 16.0x (>200K)", dto["model_comparison"][3]["display"]["relative_cost"])
            self.assertIn("Accounts Overview", cli)
            self.assertIn("Billed month: $2.34", cli)
            self.assertIn("CCost today: 2", cli)
            result = subprocess.run(["node", "development/tests/integration/web_overview.cjs"],
                input=json.dumps(dict(view=dto, order=cli_rows, fallback=fallback)), text=True,
                capture_output=True, timeout=10, cwd=ROOT)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
