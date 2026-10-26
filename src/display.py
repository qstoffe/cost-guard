"""Pure CLI-owned display primitives shared by terminal and application exports.

Never round canonical values here: callers retain raw values alongside tokens.
"""
from decimal import Decimal, ROUND_HALF_UP
import re

from src.numbers import consumed_capacity, exact_number, remaining_capacity


def money(value: Decimal | None) -> str:
    return "N/A" if value is None else f"${value:.2f}"


def native_amount(value: Decimal, unit: str | None, *, kind: str = "exact") -> str:
    if unit == "USD":
        return money(value)
    if (unit or "").casefold() == "ai credits":
        if kind == "remaining":
            return remaining_capacity(value)
        if kind == "consumed":
            return consumed_capacity(value)
    return exact_number(value)


def unaccounted_usage(value: Decimal | None) -> str:
    if value is None:
        return "—"
    return "0" if value == 0 else ("+" if value > 0 else "-") + consumed_capacity(abs(value))


def compact_threshold(value: int) -> str:
    divisor, suffix = (1_000_000, "M") if value >= 1_000_000 else (1000, "K") if value >= 1000 else (1, "")
    return exact_number(Decimal(value) / divisor) + suffix


def relative_cost(value: Decimal | None) -> str:
    return "N/A" if value is None else f"{value:.1f}x"


def price_summary(value: str | None) -> str:
    """Only shorten tier labels; quoted native rate digits remain byte-exact."""
    return re.sub(r"\(([>≥])(\d+)\)", lambda match:
                  f"({match[1]}{compact_threshold(int(match[2]))})", str(value or "N/A")).replace(" -> ", "→")


def compact_tokens(value: int) -> str:
    for size, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if value >= size:
            return f"{Decimal(value) / size:.1f}".removesuffix(".0") + suffix
    return str(value)


def context_tokens(value: int | None) -> str:
    if value is None:
        return "N/A"
    if value <= 0:
        return "0k"
    rounded = int((Decimal(value) / 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return f"{max(1, rounded)}k"


def context_delta(value: int | None) -> str:
    if value is None:
        return "N/A"
    if abs(value) < 500:
        return "0k"
    return ("+" if value > 0 else "-") + context_tokens(abs(value))


def duration_text(ms: int | None) -> str:
    if ms is None:
        return "N/A"
    seconds = max(0, int((Decimal(ms) / 1000).to_integral_value(rounding=ROUND_HALF_UP)))
    if seconds < 60:
        return f"{seconds}s"
    minutes, remaining_seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m" if remaining_seconds == 0 else f"{minutes}m{remaining_seconds}s"
    hours, remaining_minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}h" if remaining_minutes == 0 else f"{hours}h{remaining_minutes}m"
    days, remaining_hours = divmod(hours, 24)
    return f"{days}d" if remaining_hours == 0 else f"{days}d{remaining_hours}h"
