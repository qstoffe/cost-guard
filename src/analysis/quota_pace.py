"""Forward-looking quota Pace from current provider quota state plus the calendar.

Pace never reads session history: it spreads the provider-reported remaining
included amount over the remaining days of the provider-reported period.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from src.domain import QuotaComponent

from .timezones import resolve_timezone, swedish_public_holidays


@dataclass(frozen=True, slots=True)
class QuotaPace:
    label: str
    unit: str
    per_day: Decimal
    days: int
    workdays: int
    per_workday: Decimal | None  # None when no configured workday remains


def is_workday(day: date, calendar_name: str) -> bool:
    if day.weekday() >= 5:
        return False
    return str(calendar_name or "").strip().upper() != "SE" or day not in swedish_public_holidays(day.year)


def quota_pace(
    component: QuotaComponent, *, now_ms: int, timezone_id: str, workday_calendar: str,
) -> QuotaPace | None:
    """Return Pace only for a fixed period with a known native balance and reset."""
    if (component.unlimited or component.period != "fixed" or component.duration_seconds
            or component.remaining is None or component.reset_at_ms is None or component.reset_at_ms <= now_ms):
        return None
    # The last instant before reset names the period's final (provider) day;
    # today is the user's local date and always counts as one remaining day.
    last_day = datetime.fromtimestamp((component.reset_at_ms - 1) / 1000, timezone.utc).date()
    today = datetime.fromtimestamp(now_ms / 1000, timezone.utc).astimezone(resolve_timezone(timezone_id)).date()
    if last_day < today:
        return None
    days = (last_day - today).days + 1
    workdays = sum(is_workday(today + timedelta(days=offset), workday_calendar) for offset in range(days))
    remaining = component.remaining
    return QuotaPace(component.label, component.unit or "units", remaining / days, days, workdays,
                     remaining / workdays if workdays else None)
