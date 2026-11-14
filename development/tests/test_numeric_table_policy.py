"""Plain numeric table tokens retain canonical precision and coverage evidence."""
from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace
import unittest

from src.analysis.token_mix import TokenMix
from src.analysis.valuation import ComparisonCost
from src.application.contracts import record
from src.application.display import with_display
from src.application.projection import token_mix
from src.display import token_volume
from src.numbers import ccost_amount, ccost_display, remaining_capacity
from src.presentation.token_mix import comparison_cost_text, mix_cells, total_cost_text
from src.presentation.watch import WatchRenderer


class NumericTablePolicyTests(unittest.TestCase):
    def test_cli_account_observation_rescopes_on_day_and_account(self):
        renderer = WatchRenderer({"timezone": "UTC"}, interactive=False)
        projection = SimpleNamespace(source_label="fixture", now_ms=1_000)
        account = SimpleNamespace(account=SimpleNamespace(key="account-a", quotas=()))
        known = ComparisonCost(Decimal(125), 2, 1)
        text = renderer._account_cost_text(projection, account)
        self.assertEqual("125", text("today", known))
        self.assertEqual("125", text("today", None))
        self.assertEqual("125", text("today", ComparisonCost(Decimal(0), 2, 0)))
        projection.now_ms += 86_400_000
        self.assertEqual("0", renderer._account_cost_text(projection, account)("today", None))
        account.account.key = "account-b"
        self.assertEqual("0", renderer._account_cost_text(projection, account)("today", None))

    def test_cli_cost_observations_retain_only_qualified_same_scope_values(self):
        renderer = WatchRenderer({}, interactive=False)
        for unit, expected in (("credits", "125"), ("usd", "$1.25")):
            with ccost_display(unit):
                scope = ("source", "session", unit, "prompt")
                self.assertEqual("0" if unit == "credits" else "$0.00",
                                 renderer._cost_text(scope, None, complete=False))
                self.assertEqual(expected, renderer._cost_text(scope, Decimal(125), complete=False))
                for amount in (None, Decimal(0), None):
                    self.assertEqual(expected, renderer._cost_text(scope, amount, complete=False))
                self.assertEqual("100" if unit == "credits" else "$1.00",
                                 renderer._cost_text(scope, Decimal(100), complete=True))
                self.assertEqual("0" if unit == "credits" else "$0.00",
                                 renderer._cost_text(scope, Decimal(0), complete=True))
                self.assertEqual("0" if unit == "credits" else "$0.00",
                                 renderer._cost_text((*scope, "new"), None, complete=False))

    def test_unknown_amounts_are_only_display_zero_in_both_units(self):
        keys = ("ccost", "total_ccost", "known_ccost", "incoming_context_ccost", "extra_ccost")
        source = record(**dict.fromkeys(keys, None), unresolved_cost=True, complete=False,
                        billed_cost=None, context_tokens=None)
        for unit, zero in (("credits", "0"), ("usd", "$0.00")):
            wire = with_display(source, ccost_display_unit=unit).to_json()
            for key in keys:
                self.assertIsNone(wire[key])
                self.assertEqual(zero, wire["display"][key])
            self.assertFalse(wire["complete"])
            self.assertTrue(wire["unresolved_cost"])
            self.assertEqual("N/A", wire["display"]["billed_cost"])
            self.assertEqual("N/A", wire["display"]["context_tokens"])

    def test_partial_amount_matrix_matches_complete_without_mutating_raw_facts(self):
        # These keys feed prompt/session/date/model/group totals and cost breakdowns.
        keys = ("ccost", "total_ccost", "known_ccost", "main_ccost", "subagent_ccost",
                "total_main_ccost", "total_subagent_ccost", "incoming_context_ccost", "extra_ccost",
                "next_context_cached_ccost", "next_context_fresh_ccost",
                "watch_next_context_cached_ccost", "watch_next_context_fresh_ccost")
        flags = dict(unresolved_cost=True, complete=False, comparison_cost_complete=False,
                     main_estimated=True, subagent_estimated=True,
                     total_main_estimated=True, total_subagent_estimated=True)
        for raw, credits, usd in (("123.001", "124", "$1.23"), ("0.001", "<0.1", "$0.00")):
            source = record(**dict.fromkeys(keys, Decimal(raw)), **flags)
            for unit, expected in (("credits", credits), ("usd", usd)):
                with self.subTest(raw=raw, unit=unit):
                    wire = with_display(source, ccost_display_unit=unit).to_json()
                    for key in keys:
                        self.assertEqual(expected, wire["display"][key], key)
                        self.assertEqual(raw, wire[key])
                    for key, value in flags.items():
                        self.assertEqual(value, wire[key])
                    self.assertEqual(source.to_json(), {key: wire[key] for key, _ in source.fields})
                    complete_flags = {key: not value for key, value in flags.items()}
                    complete = with_display(record(**dict.fromkeys(keys, Decimal(raw)), **complete_flags),
                                            ccost_display_unit=unit).to_json()
                    self.assertEqual([complete["display"][key] for key in keys],
                                     [wire["display"][key] for key in keys])

    def test_comparison_run_keeps_incomplete_identity_and_plain_cost(self):
        source = record(match_run=True, started_at_ms=1000, completed_at_ms=2000,
                        cost_complete=False, ccost=Decimal("123.001"), next_context_tokens=None,
                        token_totals=(1, 0, 0, 2))
        for unit, expected in (("credits", "124"), ("usd", "$1.23")):
            wire = with_display(source, ccost_display_unit=unit).to_json()
            self.assertEqual(expected, wire["display"]["ccost"])
            self.assertFalse(wire["cost_complete"])
            self.assertEqual("123.001", wire["ccost"])

    def test_priced_zero_unknown_and_rounded_positive_are_distinct(self):
        for unit, zero in (("credits", "0"), ("usd", "$0.00")):
            self.assertEqual(zero, ccost_amount(Decimal(0), unit=unit))
            self.assertEqual(zero, ccost_amount(None, unit=unit))
            self.assertEqual(zero, ccost_amount(Decimal(0), unresolved=True, unit=unit))
        self.assertEqual("$0.00", ccost_amount(Decimal("0.001"), unresolved=True, unit="usd"))
        self.assertEqual("842K", token_volume(None, 842_000))
        self.assertEqual("0", token_volume(None, 0))
        self.assertEqual("N/A", token_volume(None, None))
        # Ordinary quota capacity rounding remains independent of CCost units.
        self.assertEqual("123", remaining_capacity(Decimal("123.99")))

    def test_partial_mix_categories_totals_and_watch_footer_are_plain_in_both_units(self):
        partial = TokenMix(totals=(100, 0, 0, 100), percentages=(50, 0, 0, 50),
                          costs=(Decimal(100), Decimal(0), Decimal(0), Decimal(23)),
                          request_count=3, priced_requests=2)
        for unit, costs, total in (("credits", ("100", "0", "0", "23"), "123"),
                                  ("usd", ("$1.00", "$0.00", "$0.00", "$0.23"), "$1.23")):
            with self.subTest(unit=unit), ccost_display(unit):
                wire = with_display(token_mix(partial), ccost_display_unit=unit).to_json()
                self.assertFalse(wire["cost_complete"])
                self.assertEqual(2, wire["priced_requests"])
                self.assertEqual(total, total_cost_text(partial))
                self.assertEqual(total, comparison_cost_text(ComparisonCost(Decimal(123), 3, 2)))
                for name, amount, cell in zip(("input", "cache", "write", "output"), costs,
                                               mix_cells(partial, labels=False)):
                    self.assertEqual(amount, wire["display"]["mix_" + name + "_cost"])
                    self.assertEqual(cell, wire["display"][name])
                self.assertEqual(total, wire["display"]["mix_total_cost"])
                self.assertEqual(total, total_cost_text(replace(partial, priced_requests=0)))
                self.assertEqual(costs[1], comparison_cost_text(ComparisonCost(Decimal(0), 3, 0)))
                self.assertEqual(costs[1], total_cost_text(replace(partial, costs=(Decimal(0),) * 4)))
                watch = with_display(record(run_ccost=Decimal(123), run_total=token_mix(partial)),
                                     ccost_display_unit=unit).to_json()
                self.assertEqual(total, watch["display"]["run_ccost"])


if __name__ == "__main__":
    unittest.main()
