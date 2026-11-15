"""Whole-session/current-capacity math, conservative attribution and no new IO."""
from dataclasses import replace
from decimal import Decimal as D
import json
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from development.tests.fixtures.session_snapshots import make_snapshot, one_request
from src.analysis.valuation import ComparisonCost
from src.application.session_quota import session_quota_evidence, session_quota_usage, source_scope
from src.domain import AccountRef, AccountSnapshot, CostKind, CostObservation, ModelRef, QuotaComponent, TokenUsage
from src.reports.models import AccountProjection, AccountsQuotasProjection, QuotaPeriodProjection

ROOT = Path(__file__).resolve().parents[2]
NOW = 100_000


class SessionQuotaTests(unittest.TestCase):
    def setUp(self):
        self.ref = AccountRef("instance-v1", "github-copilot", "synthetic-account")
        self.source = SimpleNamespace(source_id="synthetic", source_instance="instance-v1", observation_epoch="epoch")
        self.valuation = Mock(side_effect=lambda model, tokens: D(tokens.input))
        self.catalog = SimpleNamespace(diagnostic_signature="price-1", reference_valuation=self.valuation)
        self.service = SimpleNamespace(source=self.source, _load_comparison_catalog=lambda: self.catalog)
        self.monthly = QuotaComponent("Monthly", period="fixed", limit=D(70), used=D(7),
            remaining=D(63), unit="AI credits", reset_at_ms=200_000, status="available")

    def evidence(self, snapshot=None):
        history = SimpleNamespace(snapshot=snapshot or one_request(running=False), retained=False)
        return session_quota_evidence(history, self.service), history

    def accounts(self, quotas=None, refs=None, *, availability="available", period_cost=None):
        items = []
        for ref in refs or (self.ref,):
            native = AccountSnapshot(ref, NOW, "Provider", plan="Plan", quotas=quotas or (self.monthly,),
                                     availability=availability)
            periods = tuple(QuotaPeriodProjection(quota, period_cost, None) for quota in native.quotas)
            items.append(AccountProjection(native, "Provider Plan · safe suffix", quota_periods=periods))
        return AccountsQuotasProjection(ComparisonCost(), ComparisonCost(), tuple(items), now_ms=NOW)

    def usage(self, evidence, accounts, **kwargs):
        return session_quota_usage(evidence, accounts, source_scope(self.source), NOW, **kwargs)

    def percent(self, evidence, accounts, **kwargs):
        return self.usage(evidence, accounts, **kwargs)["accounts"][0]["quotas"][0]["percent"]

    def test_same_unit_account_proven_native_7_of_70_is_exact_not_reference_or_plan_fee(self):
        snapshot = one_request(running=False)
        invocation = replace(snapshot.invocations[0], account_ref=self.ref,
            cost=CostObservation(D(7), "AI credits", CostKind.PROVIDER_REPORTED))
        evidence, _ = self.evidence(replace(snapshot, invocations=(invocation,)))

        self.assertEqual("10%", self.percent(evidence, self.accounts()))
        usd = replace(invocation, cost=CostObservation(D(7), "USD", CostKind.PROVIDER_REPORTED))
        other, _ = self.evidence(replace(snapshot, invocations=(usd,)))
        self.assertEqual("~42.9%", self.percent(other, self.accounts()), "reference amount 30 is not a native debit")
        arbitrary_fee = replace(self.monthly, unit="USD", limit=None)
        self.assertEqual("—", self.percent(other, self.accounts((arbitrary_fee,))))

    def test_ratio_raw_precision_long_session_all_windows_children_compaction_and_price_cache(self):
        quota = QuotaComponent("5-hour", period="rolling", duration_seconds=18000, reset_at_ms=200_000,
            remaining_fraction=D(".8"), status="available")
        # Current capacity = 200 / .2 = 1000; requests predate this window.
        period_cost = ComparisonCost(D(200), 1, 1)
        snapshot = make_snapshot()
        invocations = tuple(replace(item, tokens=TokenUsage(input=470), account_ref=self.ref, cost=None)
                            for item in snapshot.invocations)
        evidence, history = self.evidence(replace(snapshot, invocations=invocations))

        self.assertEqual("~235%", self.percent(evidence, self.accounts((quota,), period_cost=period_cost)))
        valued = self.valuation.call_count
        self.assertIs(evidence, session_quota_evidence(history, self.service))
        self.assertEqual(valued, self.valuation.call_count, "unchanged snapshot has no repeated request valuation")
        for _ in range(100):
            self.usage(evidence, self.accounts((quota,), period_cost=period_cost))
        self.assertEqual(valued, self.valuation.call_count, "quota refresh projects aggregates only")
        self.assertEqual("~117.5%", self.percent(evidence, self.accounts((quota,),
            period_cost=ComparisonCost(D(400), 1, 1))))
        self.assertEqual("—", self.percent(evidence, self.accounts((replace(quota, reset_at_ms=NOW),),
            period_cost=period_cost)))

    def test_unique_route_estimate_ambiguous_accounts_explicit_identity_and_foreign_account(self):
        evidence, _ = self.evidence()
        second = replace(self.ref, account_id="another")
        self.assertEqual("~42.9%", self.percent(evidence, self.accounts()))
        ambiguous = self.usage(evidence, self.accounts(refs=(self.ref, second)))
        self.assertEqual(["—", "—"], [card["quotas"][0]["percent"] for card in ambiguous["accounts"]])
        snapshot = one_request(running=False)
        invocation = replace(snapshot.invocations[0], account_ref=self.ref)
        proven, _ = self.evidence(replace(snapshot, invocations=(invocation,)))
        split = self.usage(proven, self.accounts(refs=(self.ref, second)))
        self.assertEqual(["~42.9%", "0%"], [card["quotas"][0]["percent"] for card in split["accounts"]])
        foreign, _ = self.evidence(replace(snapshot, invocations=(replace(invocation,
            account_ref=replace(self.ref, source_instance="foreign")),)))
        self.assertEqual("0%", self.percent(foreign, self.accounts()))

    def test_model_scope_zero_matching_aliases_unknown_models_and_publisher_is_not_route(self):
        scoped = replace(self.monthly, label="Special", scope="model", model_id="special",
                         reference_ccost_capacity=D(70))
        evidence, _ = self.evidence()
        self.assertEqual("0%", self.percent(evidence, self.accounts((scoped,))))
        snapshot = one_request(running=False)
        invocation = replace(snapshot.invocations[0], model=ModelRef("github-copilot", "special"))
        matched, _ = self.evidence(replace(snapshot, invocations=(invocation,)))
        self.assertEqual("~42.9%", self.percent(matched, self.accounts((scoped,))))
        unknown, _ = self.evidence(replace(snapshot, invocations=(replace(invocation,
            model=ModelRef("github-copilot", "")),)))
        self.assertEqual("—", self.percent(unknown, self.accounts((scoped,))))
        publisher, _ = self.evidence(replace(snapshot, invocations=(replace(invocation,
            model=ModelRef("openai", "special")),)))
        self.assertEqual("0%", self.percent(publisher, self.accounts((scoped,))))

    def test_partial_unpriced_missing_capacity_unlimited_stale_and_source_isolation(self):
        snapshot = one_request(running=False)
        evidence, _ = self.evidence(replace(snapshot, complete=False))
        self.assertEqual("—", self.percent(evidence, self.accounts()))
        complete, _ = self.evidence(snapshot)
        self.assertEqual("—", self.percent(complete, self.accounts(availability="stale")))
        self.assertEqual("—", self.percent(complete, self.accounts(), stale=True))
        self.assertEqual("Unlimited", self.percent(complete, self.accounts((replace(self.monthly, unlimited=True),))))
        self.assertIsNone(session_quota_usage(complete, self.accounts(), ("foreign", "source", "epoch"), NOW))
        self.valuation.side_effect = lambda *_: None
        unpriced, _ = self.evidence(snapshot)
        self.assertEqual("—", self.percent(unpriced, self.accounts()))
        missing = replace(self.monthly, limit=D(0), used=D(0), remaining=D(0))
        self.assertEqual("—", self.percent(complete, self.accounts((missing,))))
        wire = json.dumps(self.usage(complete, self.accounts()))
        self.assertNotIn("synthetic-account", wire)
        self.assertNotIn("instance-v1", wire)
        self.assertNotIn("native", wire)

    def test_overlapping_quotas_alias_route_deduplication_and_partial_native_units(self):
        snapshot = one_request(running=False)
        ref = replace(self.ref, provider_id="openai")
        request = replace(snapshot.invocations[0], model=ModelRef("codex", "special"), account_ref=ref,
                          cost=None, tokens=TokenUsage(input=200))
        evidence, _ = self.evidence(replace(snapshot, invocations=(request, request)))
        five = QuotaComponent("5-hour", period="rolling", duration_seconds=18000,
            reset_at_ms=200_000, remaining_fraction=D(".8"), status="available")
        weekly = replace(five, label="Weekly", duration_seconds=604800)
        scoped = replace(five, label="Special", scope="model", model_id="special")

        result = self.usage(evidence, self.accounts((five, weekly, scoped), refs=(ref,),
            period_cost=ComparisonCost(D(200), 1, 1)))

        self.assertEqual(["~20%", "~20%", "~20%"], [row["percent"] for row in result["accounts"][0]["quotas"]])
        self.assertEqual(1, sum(part.requests for part in evidence.contributions), "physical duplicate counted once")
        self.assertEqual(1, self.valuation.call_count)
        # A partial native amount cannot become an exact per-session debit.
        first = replace(request, model=ModelRef("github-copilot", "gpt-test"), account_ref=self.ref,
            cost=CostObservation(D(7), "AI credits", CostKind.PROVIDER_REPORTED))
        second = replace(first, invocation_id="second", cost=None)
        mixed, _ = self.evidence(replace(snapshot, invocations=(first, second)))
        self.assertEqual("~571.4%", self.percent(mixed, self.accounts()))

    def test_contribution_membership_uses_raw_usage_not_capacity_or_formatted_percent(self):
        evidence, _ = self.evidence()
        tiny = replace(evidence, contributions=(replace(evidence.contributions[0], amount=D("1e-20")),))
        missing = replace(self.monthly, limit=D(0), used=D(0), remaining=D(0))

        normal = self.usage(tiny, self.accounts())["accounts"][0]["quotas"][0]
        unknown = self.usage(tiny, self.accounts((missing,)))["accounts"][0]["quotas"][0]
        partial = self.usage(replace(tiny, complete=False), self.accounts())["accounts"][0]["quotas"][0]

        self.assertEqual("positive", normal["contribution"])
        self.assertNotEqual("~0%", normal["percent"])
        self.assertEqual(("positive", "—"), (unknown["contribution"], unknown["percent"]))
        self.assertEqual(("positive", "—"), (partial["contribution"], partial["percent"]))
        self.assertEqual("positive", self.usage(evidence, self.accounts(), stale=True)
            ["accounts"][0]["quotas"][0]["contribution"])

    def test_zero_unknown_and_model_membership_remain_distinct_from_display(self):
        evidence, _ = self.evidence()
        scoped = replace(self.monthly, scope="model", model_id="special")
        unused = self.usage(evidence, self.accounts((scoped,)))["accounts"][0]["quotas"][0]
        ambiguous = self.usage(evidence, self.accounts(refs=(self.ref, replace(self.ref, account_id="other"))))
        unknown_model = replace(evidence, contributions=(replace(evidence.contributions[0], model=None),))
        native_unpriced = replace(evidence, contributions=(replace(evidence.contributions[0], amount=D(0), complete=False),))
        unpriced = replace(native_unpriced, contributions=(replace(native_unpriced.contributions[0], native=()),))

        self.assertEqual(("zero", "0%"), (unused["contribution"], unused["percent"]))
        self.assertEqual(["unknown", "unknown"],
            [card["quotas"][0]["contribution"] for card in ambiguous["accounts"]])
        self.assertEqual("unknown", self.usage(unknown_model, self.accounts((scoped,)))
            ["accounts"][0]["quotas"][0]["contribution"])
        self.assertEqual("unknown", self.usage(unpriced, self.accounts())["accounts"][0]["quotas"][0]["contribution"])
        self.assertEqual("positive", self.usage(native_unpriced, self.accounts())["accounts"][0]["quotas"][0]["contribution"],
            "positive native consumption proves membership even without reference pricing")
        self.assertEqual("positive", self.usage(evidence, self.accounts((replace(self.monthly, unlimited=True),)))
            ["accounts"][0]["quotas"][0]["contribution"])

    def test_proven_account_and_native_zero_never_cross_assign_cards(self):
        snapshot = one_request(running=False)
        request = replace(snapshot.invocations[0], account_ref=self.ref,
            cost=CostObservation(D(0), "AI credits", CostKind.PROVIDER_REPORTED))
        zero, _ = self.evidence(replace(snapshot, invocations=(request,)))
        positive, _ = self.evidence(replace(snapshot, invocations=(replace(request,
            cost=CostObservation(D(7), "AI credits", CostKind.PROVIDER_REPORTED)),)))
        refs = (self.ref, replace(self.ref, account_id="other"), replace(self.ref, provider_id="openai"))

        native_zero = self.usage(zero, self.accounts())["accounts"][0]["quotas"][0]
        cards = self.usage(positive, self.accounts(refs=refs))["accounts"]

        self.assertEqual(("zero", "0%"), (native_zero["contribution"], native_zero["percent"]))
        self.assertEqual(["positive", "zero", "zero"], [card["quotas"][0]["contribution"] for card in cards])

    @unittest.skipUnless(shutil.which("node"), "Node required")
    def test_shipped_navigation_memory_controller(self):
        result = subprocess.run(["node", "development/tests/fixtures/session_return_vm.cjs"],
            cwd=ROOT, text=True, capture_output=True, timeout=20)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
