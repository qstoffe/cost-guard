"""Shared Next-Ictx economic warning emphasis, independent of warning prose."""
from __future__ import annotations

from decimal import Decimal

from src.analysis.context import PriceWarningSeverity
from src.numbers import ccost_range

from .terminal import AnsiStyler, wrap_prose

WARNING_ROLE = "nextIctxWarning"


def next_ictx_ccost(cached: Decimal | None, fresh: Decimal | None) -> str:
    """Explicitly labelled estimated CCost range of the next input context."""
    return f"(Next Ictx CCost {ccost_range(cached, fresh)})"


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
