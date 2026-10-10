"""Shared Next-Ictx economic warning emphasis, independent of warning prose."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from src.analysis.context import PriceWarningSeverity
from src.numbers import ccost_range

from .terminal import AnsiStyler, wrap_prose

WARNING_ROLE = "nextIctxWarning"
CONTEXT_WARNING_LABEL = "Context:"


def context_warning_text(text: str) -> str:
    clean = text[1:-1] if text.startswith("[") and text.endswith("]") else text
    return f"{CONTEXT_WARNING_LABEL} {clean}"


def next_ictx_ccost(cached: Decimal | None, fresh: Decimal | None) -> str:
    """Explicitly labelled estimated CCost range of the next input context."""
    return f"(Next Ictx CCost {ccost_range(cached, fresh)})"


def threshold_multiplier_text(multiplier: Decimal) -> str:
    """Model-table Relative CCost ratio across the warned threshold, at most one decimal."""
    value = multiplier.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"({value:f}".removesuffix(".0") + "x more expensive)"


def warning_cost_suffix(multiplier: Decimal | None, cached: Decimal | None, fresh: Decimal | None) -> str:
    """Warnings prefer the threshold multiplier; unknown pricing keeps the CCost range."""
    if multiplier is not None:
        return threshold_multiplier_text(multiplier)
    return next_ictx_ccost(cached, fresh) if cached is not None and fresh is not None else ""


def warning_explanation_lines(
    marker: str, text: str, severity: PriceWarningSeverity, styler: AnsiStyler,
    *, width: int | None = None,
) -> list[str]:
    prefix = marker + " "
    lines = (wrap_prose(text, width, initial_prefix=prefix, continuation_prefix=" " * len(prefix))
             if width is not None else [prefix + text])
    if severity == PriceWarningSeverity.EXCEEDED:
        return [styler.apply(line, WARNING_ROLE) for line in lines]
    if lines and severity == PriceWarningSeverity.APPROACHING:
        lines[0] = styler.apply(marker, WARNING_ROLE) + lines[0][len(marker):]
    return lines
