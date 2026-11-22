"""Presentation of strictly observed, cached AI Stats subtotals."""
from datetime import date
from decimal import Decimal

from src.analysis.timezones import DateTimeMode, format_date_time
from src.display import compact_tokens, duration_text
from src.numbers import ccost_amount


def cached_stats(row, token_row):
    result = _measured_stats(row)
    if token_row is not None:
        if token_row.observed is not None:
            result["tokens"] = compact_tokens(token_row.observed)
        result.update(_costs(token_row, "credits"))
    return result


def cached_stats_units(token_row):
    costs = _costs(token_row, "usd") if token_row is not None else {}
    return {"usd": costs} if costs else {}


def _costs(row, unit):
    return {field: ccost_amount(value, unit=unit) for field, value in (
        ("referenceCost", row.reference_ccost), ("subagentReferenceCost", row.subagent_reference_ccost)
    ) if value is not None}


def _measured_stats(row):
    if row is None or row.working_ms is None:
        return {}
    result = {"working": duration_text(row.working_ms)}
    if row.calendar is not None:
        calendar = row.calendar
        day = format_date_time(date.fromordinal(calendar.busiest_local_day), DateTimeMode.DATE)
        result.update(busiest=f"{day} · {duration_text(calendar.busiest_ms)}",
                      overnight=duration_text(calendar.night_ms),
                      overnightShare=f"{Decimal(calendar.night_ms) * 100 / row.working_ms:.0f}%",
                      streak=str(calendar.streak_days))
    if row.roots is not None:
        result.update(longest=duration_text(row.roots.longest_ms), parallel=str(row.roots.peak_roots))
    return result
