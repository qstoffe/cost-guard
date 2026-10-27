"""Remaining report cells compared to the same frozen CLI projections."""
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import shutil
import subprocess
import unittest

from development.tests.fixtures.compact_reports import rendered
from development.tests.fixtures.remaining_views import remaining_reports, result, ZONE
from src.application.contracts import record
from src.application.display import with_display
from src.presentation.token_mix import mix_cells, total_cost_text

ROOT = Path(__file__).resolve().parents[2]


class RemainingViewTests(unittest.TestCase):
    def test_history_mix_cells_match_cli_for_complete_partial_unknown_and_empty(self):
        mix = remaining_reports(self)["token-mix"].token_mix
        for native in (mix, replace(mix, priced_requests=mix.priced_requests - 1), replace(mix, costs=None),
                       replace(mix, priced_requests=0), replace(mix, totals=(0, 0, 0, 0))):
            from src.application.projection import token_mix
            dto = with_display(token_mix(native)).to_json()
            self.assertEqual(mix_cells(native, labels=False),
                tuple(dto["display"][name] for name in ("input", "cache", "write", "output")))
            self.assertEqual(total_cost_text(native), dto["display"]["total_cost"])
            self.assertEqual(None if native.costs is None else str(sum(native.costs, Decimal(0))), dto["total_cost"])

    def test_configured_prompt_clock_and_threshold_guidance_never_change_raw_values(self):
        dto = with_display(record(at_ms=1_793_052_000_000, next_context_tokens=120_000,
            next_context_cost_multiplier=Decimal("2.149"), next_context_warning_severity="exceeded"), ZONE).to_json()
        self.assertEqual("23:00", dto["display"]["clock"])
        self.assertEqual("Next Ictx: ~120k (2.1x more expensive)", dto["display"]["next_context"])
        self.assertEqual("2.149", dto["next_context_cost_multiplier"])

    @unittest.skipUnless(shutil.which("node"), "optional JS VM unavailable")
    def test_visible_date_and_history_columns_match_frozen_cli(self):
        reports = remaining_reports(self)
        cases = {}
        for kind in ("date", "token-mix"):
            report = reports[kind]
            cases[kind] = result(report)
            text = rendered(report, {"timezone": ZONE}, width=300)
            for block in cases[kind]["view"]["prompt_blocks"]:
                self.assertIn(block["display"]["total_ccost"], text)
                self.assertIn(block["display"]["next_context"], text)
            for row in cases[kind]["view"]["model_token_mix"]:
                self.assertIn(row["mix"]["display"]["total_cost"], text)
        check = subprocess.run(["node", "development/tests/integration/web_remaining.cjs"],
            input=json.dumps(cases), text=True, capture_output=True, timeout=10, cwd=ROOT)
        self.assertEqual(0, check.returncode, check.stdout + check.stderr)


if __name__ == "__main__":
    unittest.main()
