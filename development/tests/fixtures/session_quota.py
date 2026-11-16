"""Synthetic native/reference quota observations for the authenticated browser."""
from dataclasses import replace
from decimal import Decimal as D

from development.tests.fixtures.session_snapshots import one_request
from src.analysis.causal import trace_entries
from src.analysis.valuation import comparison_cost, ComparisonCost
from src.domain import AccountRef, AccountSnapshot, CostKind, CostObservation, QuotaComponent
from src.reports.models import AccountProjection, AccountsQuotasProjection, QuotaPeriodProjection


def configure(runtime, command):
    service = runtime.service
    ref = AccountRef("synthetic-detail", "github-copilot", "synthetic-account")
    if command == "quota-source":
        snapshot = one_request(running=False)
        request = replace(snapshot.invocations[0], account_ref=ref,
            cost=CostObservation(D(7), "AI credits", CostKind.PROVIDER_REPORTED))
        service.source.snapshots["root"] = replace(snapshot, invocations=(request,))
    snapshot = service.source.snapshots["root"]
    value = comparison_cost(trace_entries(snapshot), service._load_comparison_catalog().reference_valuation)
    capacity = value.known_ccost / D("2.35") * (2 if command == "quota-capacity" else 1)
    monthly = QuotaComponent("monthly", period="fixed", limit=D(70), used=D(7), remaining=D(63),
        unit="AI credits", reset_at_ms=service.now_ms + 86_400_000, status="available")
    weekly = QuotaComponent("weekly", period="rolling", remaining_fraction=D(".8"),
        duration_seconds=604800, reset_at_ms=service.now_ms + 1000, status="available")
    model = replace(weekly, label="Special", scope="model", model_id="special",
                    reference_ccost_capacity=D(100))
    account = AccountSnapshot(ref, service.now_ms, "GitHub Copilot", plan="Plan", quotas=(monthly, weekly, model))
    periods = tuple(QuotaPeriodProjection(q,
                     None if q is weekly and command == "quota-source" else ComparisonCost(capacity * D(".2"), 1, 1), None)
                    for q in account.quotas)
    second = AccountSnapshot(AccountRef("synthetic-detail", "claude-code", "second"),
        service.now_ms, "Claude", quotas=(QuotaComponent("Weekly"),))
    items = (AccountProjection(account, "GitHub Copilot Plan · account 1", quota_periods=periods),
             AccountProjection(second, "Claude · account 2"))
    if command == "quota-remove":
        items = items[1:]
    runtime.quota_fixture = AccountsQuotasProjection(ComparisonCost(), ComparisonCost(), items,
                                                   now_ms=service.now_ms)
