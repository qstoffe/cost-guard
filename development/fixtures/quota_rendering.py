"""Fixed-time rolling quota projections and report/Watch account-section rendering."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import io
from pathlib import Path

from development.fixtures.accounts import account
from src.analysis.valuation import ComparisonCost
from src.config import read_jsonc
from src.domain import QuotaComponent
from src.presentation import ReportRenderer, WatchRenderer
from src.reports.models import AccountProjection, AccountsQuotasProjection, ReportKind, ReportProjection
from src.watch.models import WatchProjection

ROOT = Path(__file__).resolve().parents[2]
D = Decimal
NOW = int(datetime(2026, 9, 30, 20, tzinfo=timezone.utc).timestamp() * 1000)


def rolling(identity="a", label="OpenAI Plus"):
    snapshot = replace(account(identity=identity), fetched_at_ms=NOW, quotas=(
        QuotaComponent("5-hour", remaining_fraction=D("0.64"), reset_at_ms=NOW + 126 * 60_000, duration_seconds=18_000),
        QuotaComponent("weekly", remaining_fraction=D("0.48"), reset_at_ms=NOW + 74 * 3_600_000, duration_seconds=604_800),
    ))
    return AccountProjection(snapshot, label)


def quotas(*accounts):
    return AccountsQuotasProjection(ComparisonCost(D(999)), ComparisonCost(D(9999)), tuple(accounts),
                                    billed_today=D(88), billed_month=D(888), now_ms=NOW)


def report_text(quota, *, width=160):
    stream = io.StringIO()
    config = read_jsonc(ROOT / "config/default-config.jsonc")
    ReportRenderer(config, stream=stream, color_enabled=False, terminal_width=width)._render_accounts_quotas(
        ReportProjection(ReportKind.NORMAL, "Report", "V2", accounts_quotas=quota))
    return stream.getvalue()


def watch_text(quota, *, width):
    stream = io.StringIO()
    config = read_jsonc(ROOT / "config/default-config.jsonc")
    config["timezone"] = "UTC"
    WatchRenderer(config, stream=stream, interactive=False, terminal_width=width).render(
        WatchProjection("Watch", "V2", (), quota=quota, now_ms=NOW, status="Next refresh: 00:04"))
    return stream.getvalue().split("Token Mix % · 0 prompts · no token data yet", 1)[1].split("\n", 1)[1]
