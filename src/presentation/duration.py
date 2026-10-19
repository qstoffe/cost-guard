"""Compact wall-clock duration formatting shared by reports and Watch."""
from decimal import Decimal, ROUND_HALF_UP


def duration_text(ms: int | None) -> str:
    if ms is None:
        return "N/A"
    seconds = max(0, int((Decimal(ms) / Decimal(1000)).to_integral_value(rounding=ROUND_HALF_UP)))
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
