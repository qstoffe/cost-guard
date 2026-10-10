"""Application-owned Simple HTTP provider registry. Not user configuration."""
from __future__ import annotations

from src.domain import AccountUsageStatus
from .http_account import HttpAccountProvider
from .http_transport import MaintainedEndpoint
from .simple_http_mapping import ComponentMapping as C, SimpleHttpDefinition, normalize_simple_account

# Official contracts: https://api-docs.deepseek.com/api/get-user-balance
# and https://openrouter.ai/docs/api/reference/limits (GET current key only).
DEEPSEEK = SimpleHttpDefinition(
    "deepseek", "DeepSeek", ("deepseek",), MaintainedEndpoint("https://api.deepseek.com/user/balance"),
    tuple(C("balance", label, (field,), unit_path=("currency",), allowed_units=("USD", "CNY"))
          for label, field in (("Balance", "total_balance"), ("Granted", "granted_balance"), ("Topped up", "topped_up_balance"))),
    rows_path=("balance_infos",), max_rows=8, status_path=("is_available",),
    status_values=((True, AccountUsageStatus.AVAILABLE), (False, AccountUsageStatus.BLOCKED)),
)

OPENROUTER = SimpleHttpDefinition(
    "openrouter", "OpenRouter", ("openrouter",), MaintainedEndpoint("https://openrouter.ai/api/v1/key"),
    (C("remaining_budget", "Limit", ("limit_remaining",), limit_path=("limit",), null_limit_absent=True,
       label_path=("limit_reset",), label_values=(("daily", "Day"), ("weekly", "Week"), ("monthly", "Month"), (None, "Limit")),
       period_values=(("daily", "fixed"), ("weekly", "fixed"), ("monthly", "fixed"), (None, "non_resetting"))),
     C("spend", "Spend: Day", ("usage_daily",), period="day"),
     C("spend", "Spend: Week", ("usage_weekly",), period="week"),
     C("spend", "Spend: Month", ("usage_monthly",), period="month")),
    root_path=("data",),
)

SIMPLE_HTTP_PROVIDERS = (DEEPSEEK, OPENROUTER)


class SimpleHttpAccountProvider(HttpAccountProvider):
    capacity_kind = "credit"
    def __init__(self, definition: SimpleHttpDefinition, **kwargs):
        self.definition = definition
        self.provider_id = definition.provider_id
        self.display_label = definition.display_label
        self.integration_ids = definition.integration_ids
        super().__init__(**kwargs)

    def endpoint_for(self, record):
        return self.definition.endpoint

    def normalize_response(self, account, payload):
        return normalize_simple_account(account, payload, self.definition)
