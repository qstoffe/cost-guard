"""AI Stats calendar normalization and fictional shifts over already-prepared facts."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from .active_hour import HOUR_MS
from .ai_stats_buckets import effort_values, providers, selected_effort
from .ai_stats_models import ModelStanding
from .ai_stats_responses import call_key
from .effort_defaults import effort_evidence
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


@dataclass(frozen=True, slots=True)
class MeasuredRates:
    cost: Decimal
    duration_ms: int
    podium: tuple
    partial: bool


def model_hourly_rates(groups, entries, values, union):
    """Use only requests with both cost and observed execution for rates."""
    costs = {call_key(entry): value for entry, value in zip(entries, values)}
    candidates = []
    measured = {}
    for name, observations in groups.items():
        rows = [(entry, pair) for entry, pair in observations
                if pair is not None and costs[call_key(entry)] is not None]
        evidence = [entry for entry, _pair in rows]
        duration = sum(b - a for a, b in union(pair for _entry, pair in rows))
        if not duration:
            continue
        total, efforts = Decimal(0), {}
        for entry, pair in rows:
            key = call_key(entry)
            value = costs[key]
            measured[key] = pair
            total += value
            cost, pairs = efforts.setdefault(selected_effort(entry), [Decimal(0), []])
            efforts[selected_effort(entry)][0] = cost + value
            pairs.append(pair)
        rates = {effort: cost * HOUR_MS / sum(b - a for a, b in union(pairs))
                 for effort, (cost, pairs) in efforts.items()}
        if name:
            row = ModelStanding(providers(evidence), name, total * HOUR_MS / duration,
                tuple(sorted({entry.model.recorded_model for entry in evidence})), effort_evidence(evidence),
                display_name=name, by_effort=effort_values(rates))
            candidates.append((duration, row))
    order = lambda row: (-row.value, row.model, row.provider)
    primary = sorted((row for duration, row in candidates if duration >= 60_000), key=order)
    short = sorted((row for duration, row in candidates if duration < 60_000), key=order)
    selected = primary[:3] if len(primary) >= 3 else primary + short[:3 - len(primary)]
    return MeasuredRates(sum((costs[key] for key in measured), Decimal(0)),
                         sum(b - a for a, b in union(measured.values())),
                         tuple(sorted(selected, key=order)), len(measured) < len(costs))
