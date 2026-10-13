"""Single-prompt report/Watch projections carrying one Next-Ictx price-warning severity."""
from __future__ import annotations

from decimal import Decimal

from src.analysis.context import PriceWarningSeverity
from src.reports.models import PromptProjection, ReportKind, ReportProjection, SessionPromptBlock
from src.watch.models import WatchProjection, WatchRow


def warning_prompt(severity: PriceWarningSeverity, text: str = "Localized economic warning") -> PromptProjection:
    tokens = 80_000 if severity == PriceWarningSeverity.APPROACHING else 120_000
    return PromptProjection(
        at_ms=2_000, prompt_number=1, label="prompt", preview="Normal prompt", model_effort="Test (Default)",
        ccost=Decimal("12"), cost_estimated=False, unresolved_cost=False, calls=1,
        incoming_context_tokens=76_000, incoming_context_ccost=Decimal("1"), extra_ccost=Decimal("11"),
        token_mix_percent=(90, 0, 0, 10), delta_context_tokens=4_000, next_context_tokens=tokens,
        next_context_warning=text, next_context_warning_severity=severity,
        watch_delta_context_tokens=4_000, watch_next_context_tokens=tokens,
        watch_next_context_warning=text, watch_next_context_warning_severity=severity,
        watch_next_context_cached_ccost=Decimal("1"), watch_next_context_fresh_ccost=Decimal("12"),
    )


def warning_watch_projection(item: PromptProjection, title: str = "Normal session") -> WatchProjection:
    return WatchProjection("Cost Guard Watch", "V2", (WatchRow("root", title, item),),
                           session_warnings={"root": item.watch_next_context_warning})


def warning_report_projection(item: PromptProjection, kind: ReportKind = ReportKind.SESSION) -> ReportProjection:
    block = SessionPromptBlock(
        "root", "Normal session", (item,), item.ccost, item.calls,
        next_context_tokens=item.next_context_tokens, next_context_warning=item.next_context_warning,
        next_context_warning_severity=item.next_context_warning_severity,
    )
    return ReportProjection(kind, "Test report", "V2", prompt_blocks=(block,))
