"""Two-session Watch frame with quota, warnings and activity for rendering tests."""
from dataclasses import replace
from decimal import Decimal

from src.domain import AccountRef, AccountSnapshot, QuotaComponent
from src.reports.models import AccountProjection, AccountsQuotasProjection, PromptProjection
from src.watch.models import ToolObservation, WatchProjection, WatchRow

STATUS = "Idle · Next prompt check: 00:30"


def tall_projection():
    prompt = PromptProjection(
        at_ms=1000, prompt_number=1, event_id="event", label="#1", preview="work",
        model_effort="model", ccost=Decimal(0), cost_estimated=False,
        unresolved_cost=False, calls=0, incoming_context_tokens=None,
        incoming_context_ccost=None, extra_ccost=None, token_mix_percent=None,
        in_progress=True,
    )
    account = AccountProjection(AccountSnapshot(
        AccountRef("fixture", "provider", "account"), 2000, "Provider", "Plan",
        quotas=(QuotaComponent("weekly", "rolling", remaining_fraction=Decimal("0.5")),),
    ), "Provider Plan")
    return WatchProjection(
        "Watch", "V2", (
            WatchRow("A", "Session A", prompt, tool=ToolObservation(2, 1, 2, "current task")),
            WatchRow("B", "Session B", replace(prompt, in_progress=False)),
        ),
        source_warnings=("source warning",),
        quota=AccountsQuotasProjection((account,), ()),
        quota_stale=True, session_warnings={"A": "[context threshold exceeded]"},
        recent_model_notice="new model notice", now_ms=2000, status=STATUS,
    )
