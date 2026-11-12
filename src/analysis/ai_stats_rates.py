"""AI Stats calendar normalization and fictional shifts over already-prepared facts."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from .active_hour import HOUR_MS
from .quota_pace import is_workday
from .timezones import resolve_timezone


@dataclass(frozen=True, slots=True)
class HourlyRates:
    total: Decimal
    calendar_days: int
    workdays: int
    calendar_hours: int
    workday_hours: int
    active_hours: Decimal
    calendar_rate: Decimal | None
    workday_rate: Decimal | None
    active_rate: Decimal | None
    robot_day: Decimal
    robot_period: Decimal


def hourly_rates(total, duration, *, period, now, zone, calendar, evidence_start):
    """Nominal local date slots never change rolling cost membership or active time."""
    tz = resolve_timezone(zone)
    today = datetime.fromtimestamp(now / 1000, timezone.utc).astimezone(tz).date()
    if period in ('7-days', '30-days'):
        first = today - timedelta(days=6 if period == '7-days' else 29)
    elif period == 'month':
        first = today.replace(day=1)
    elif period == 'today':
        first = today
    else:
        first = (datetime.fromtimestamp(evidence_start / 1000, timezone.utc).astimezone(tz).date()
                 if evidence_start is not None else None)
    days = max(0, (today - first).days + 1) if first is not None else 0
    workdays = sum(is_workday(first + timedelta(days=offset), calendar) for offset in range(days))
    calendar_hours, workday_hours = days * 24, workdays * 8
    active_hours = Decimal(duration) / HOUR_MS
    active_rate = total * HOUR_MS / duration if duration else Decimal(0)
    robot_day = active_rate * 8
    return HourlyRates(total, days, workdays, calendar_hours, workday_hours, active_hours,
        total / calendar_hours if calendar_hours else Decimal(0),
        total / workday_hours if workday_hours else None, active_rate, robot_day, robot_day * workdays)
