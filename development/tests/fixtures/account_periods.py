"""Fixed native windows and canonical requests for account-period regressions."""
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal as D

from development.tests.fixtures.accounts import account
from development.tests.fixtures.report_runtime import FakePricingProvider
from development.tests.fixtures.session_snapshots import make_snapshot
from src.analysis.causal import trace_entries
from src.analysis.timezones import local_day_start_ms, local_month_start_ms
from src.domain import ModelRef, QuotaComponent, TokenUsage
from src.reports.accounts import account_projections

HOUR = 3_600_000
NOW = int(datetime(2026, 10, 25, 12, tzinfo=timezone.utc).timestamp() * 1000)
DAY = local_day_start_ms("Europe/Stockholm", now_ms=NOW)
MONTH = local_month_start_ms("Europe/Stockholm", now_ms=NOW)


def request(name, when, *, provider="claude-code", amount=1_000_000, ref=None, model="gpt-test"):
    return replace(trace_entries(make_snapshot())[0], session_id="root", message_id=name, step_part_id=None,
                    completed_at_ms=when, model=ModelRef(provider, model), tokens=TokenUsage(input=amount),
                    account_ref=ref, root_session_id=None, parent_session_id=None, invocation_id=name)


def subscription(provider="claude-code", identity="one"):
    return replace(account(provider, identity=identity), fetched_at_ms=NOW, quotas=(
        QuotaComponent("5-hour", "rolling", remaining_fraction=D(1), duration_seconds=18_000,
                       window_active=True, reset_at_ms=NOW + HOUR),
        QuotaComponent("weekly", "rolling", remaining_fraction=D("0.57"), duration_seconds=604_800,
                       reset_at_ms=NOW + HOUR),))


def project(accounts, entries, *, watch=False, observed_start_ms=None, now_ms=NOW):
    return account_projections(accounts, entries, FakePricingProvider().catalog, now_ms=now_ms,
        today_start_ms=DAY, month_start_ms=MONTH, timezone_id="Europe/Stockholm", watch=watch,
        observed_start_ms=observed_start_ms)
