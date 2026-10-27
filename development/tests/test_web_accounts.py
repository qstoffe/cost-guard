"""Normal account display parity and privacy; no provider acquisition."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

from development.tests.fixtures.account_views import NOW, account_report
from development.tests.fixtures.compact_reports import rendered
from src.application.projection import project
from src.presentation.accounts import account_ccost_text, format_reset, pace_text

ROOT = Path(__file__).resolve().parents[2]


class AccountsViewTests(unittest.TestCase):
    def test_normal_values_native_units_periods_and_reset_match_cli(self):
        report = account_report()
        dto = project(report, "Europe/Stockholm").to_json()
        cli = rendered(report)
        accounts = dto["accounts_quotas"]["accounts"]
        first = accounts[0]
        self.assertEqual("$0.00", first["display"]["billed_today"])
        self.assertEqual("$1.23", first["display"]["billed_month"])
        self.assertEqual("-0.2", first["display"]["unaccounted_usage"])
        self.assertIn("$1.23", cli)
        for native, exported in zip(report.accounts_quotas.accounts, accounts, strict=True):
            for (_, cost), scope in zip(native.ccost_scopes, exported["ccost_scopes"], strict=True):
                self.assertEqual(account_ccost_text(cost), scope["cost"]["display"]["account_ccost"])
            for quota, value in zip(native.account.quotas, exported["observation"]["quotas"], strict=True):
                expected = "Window not started" if quota.window_active is False else format_reset(quota.reset_at_ms, "Europe/Stockholm", now_ms=NOW)
                self.assertEqual(expected, value["display"]["reset"])
                self.assertEqual(None if quota.remaining_fraction is None else str(quota.remaining_fraction), value["remaining_fraction"])
        quota = first["observation"]["quotas"][0]
        self.assertEqual(("90%", "89", "11", "$8.99"), tuple(quota["display"][key] for key in ("remaining_fraction", "remaining", "used", "remaining_money")))
        self.assertEqual("29/day · no workdays left", pace_text(report.accounts_quotas.accounts[0].pace[0]))
        self.assertEqual("29", first["pace"][0]["display"]["per_day"])
        self.assertNotIn("PRIVATE", json.dumps(dto))
        self.assertEqual("—", accounts[3]["ccost_scopes"][0]["cost"]["display"]["account_ccost"])

    @unittest.skipUnless(shutil.which("node"), "optional JS VM unavailable")
    def test_rendered_cards_known_unknown_zero_unlimited_and_sanitized_errors(self):
        dto = project(account_report(), "Europe/Stockholm").to_json()
        result = subprocess.run(["node", "development/tests/integration/web_accounts.cjs"], input=json.dumps(dto),
            text=True, capture_output=True, timeout=10, cwd=ROOT)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
