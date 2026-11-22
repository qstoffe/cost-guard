"""Presentation of strictly measured, cached AI Stats subtotals."""
from datetime import date

from src.analysis.timezones import DateTimeMode, format_date_time
from src.display import duration_text


def measured_stats(row):
    if row is None or row.working_ms is None:
        return {}
    result = {"working": duration_text(row.working_ms)}
    if row.calendar is not None:
        calendar = row.calendar
        day = format_date_time(date.fromordinal(calendar.busiest_local_day), DateTimeMode.DATE)
        result.update(busiest=f"{day} · {duration_text(calendar.busiest_ms)}",
                      overnight=duration_text(calendar.night_ms), streak=str(calendar.streak_days))
    if row.roots is not None:
        result.update(longest=duration_text(row.roots.longest_ms), parallel=str(row.roots.peak_roots))
    return result
