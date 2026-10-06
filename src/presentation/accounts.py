"""Shared account/quota formatting for report and responsive Watch layouts."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import math
import textwrap
import time

from src.analysis.quota_pace import QuotaPace
from src.analysis.timezones import resolve_timezone
from src.analysis.valuation import ComparisonCost
from src.domain import AccountUsageStatus, BillingComponent, QuotaComponent
from src.reports.models import AccountProjection
from src.numbers import ccost_amount, consumed_capacity, remaining_capacity, exact_number
from .terminal import AnsiStyler, StyledText

QUOTA_BAR_WIDTH = 10
# Provider-normalized transient causes; never raw provider/stderr text.
_FAILURE_CAUSES = {"timeout": "timed out", "transport_failure": "connection failed",
                   "network_failure": "network unavailable", "http_failure": "service unavailable",
                   "format_changed": "format changed", "parser_failure": "unreadable response",
                   "discovery_failure": "account metadata unavailable"}
_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def format_reset(reset_at_ms: object, timezone_id: str, *, now_ms: int, compact: bool = False) -> str:
    """Choose a tier by elapsed UTC time; render its target in the configured zone."""
    if isinstance(reset_at_ms, bool) or not isinstance(reset_at_ms, (int, float)):
        return "Reset unknown"
    try:
        if not math.isfinite(reset_at_ms) or reset_at_ms <= 0:
            return "Reset unknown"
        target = datetime.fromtimestamp(reset_at_ms / 1000, timezone.utc).astimezone(resolve_timezone(timezone_id))
        remaining = reset_at_ms - now_ms
    except (OverflowError, OSError, ValueError):
        return "Reset unknown"
    if remaining <= 0:
        return "Reset expired"
    clock = target.strftime("%H:%M")
    if remaining < 86_400_000:
        return f"Reset@{clock}" if compact else f"Reset in {int(remaining // 60_000)}min, {clock}"
    if remaining < 604_800_000:
        when = _WEEKDAYS[target.weekday()] + " " + clock
        return "Reset@" + when if compact else f"Reset in {int(remaining // 3_600_000)}h, {when}"
    return ("Reset@" if compact else "Reset at ") + target.strftime("%Y-%m-%d %H:%M")


def format_quota_bar(fraction: Decimal) -> StyledText:
    filled = int((fraction * QUOTA_BAR_WIDTH).to_integral_value(rounding="ROUND_HALF_UP"))
    return StyledText((("█" * filled, "dailyCostFilled"),
                       ("░" * (QUOTA_BAR_WIDTH - filled), "dailyCostEmpty"),
                       (f" {fraction * 100:3.0f}%", None)))


def quota_label(label: str) -> str:
    return {"5-hour": "5h", "weekly": "Week", "monthly": "Month", "Monthly": "Month"}.get(label, label)


def ccost_text(value: ComparisonCost | None) -> str:
    if value is None or (not value.complete and not value.priced_requests):
        return "N/A"
    return ccost_amount(value.known_ccost, unresolved=not value.complete)


def money(value: Decimal | None) -> str:
    return "N/A" if value is None else f"${value:.2f}"


def _native_amount(value: Decimal, unit: str | None, *, kind: str = "exact") -> str:
    if unit == "USD":
        return money(value)
    if (unit or "").casefold() == "ai credits":
        if kind == "remaining":
            return remaining_capacity(value)
        if kind == "consumed":
            return consumed_capacity(value)
    return exact_number(value)


def quota_parts(component: QuotaComponent, timezone_id: str, *, now_ms: int,
                compact: bool = False, label_width: int = 4, watch: bool = False,
                omit_reset: bool = False) -> tuple[StyledText, ...]:
    parts = []
    label = quota_label(component.label)

    def prefix(text: str) -> str:
        return text + " " if compact and not label_width else text.ljust(label_width) + "  "

    fraction = component.remaining_fraction
    if component.unlimited:
        parts.append(StyledText(((prefix(label) + "Unlimited", None),)))
    elif fraction is not None:
        parts.append(StyledText(((prefix(label), None),) + format_quota_bar(fraction).parts))
    elif component.remaining is None and component.used is None and component.limit is None:
        if component.status is not AccountUsageStatus.BLOCKED:
            parts.append(StyledText(((prefix(label) + "N/A", None),)))
    if component.status is AccountUsageStatus.BLOCKED:
        if parts:
            parts[-1] = StyledText(parts[-1].parts + ((" · BLOCKED", "copilotPausedWarning"),))
        else:
            parts.append(StyledText(((prefix(label) + "BLOCKED", "copilotPausedWarning"),)))
    if component.remaining is not None:
        native = _native_amount(component.remaining, component.unit, kind="remaining") + (
            "/" + _native_amount(component.limit, component.unit) if component.limit is not None else "")
        if not watch or (component.unit or "").casefold() != "ai credits":
            native += " " + (component.unit or "units")
        if fraction is None:
            native += " remaining"
    elif component.used is not None:
        unit = "" if watch and (component.unit or "").casefold() == "ai credits" else " " + (component.unit or "units")
        native = _native_amount(component.used, component.unit, kind="consumed") + unit + " used"
        native += " / " + _native_amount(component.limit, component.unit) if component.limit is not None else " · limit unavailable"
    elif component.limit is not None:
        native = "Limit " + _native_amount(component.limit, component.unit)
        if not watch or (component.unit or "").casefold() != "ai credits":
            native += " " + (component.unit or "units")
    else:
        native = ""
    if native:
        if not watch and component.remaining_money is not None:
            native += " (" + money(component.remaining_money)
            if component.limit_money is not None:
                native += "/" + money(component.limit_money)
            native += ")"
        if parts:
            parts[-1] = StyledText(parts[-1].parts + ((" · " + native, None),))
        else:
            parts.append(StyledText(((prefix(label) + native, None),)))
    reset = None
    if component.reset_at_ms is not None:
        reset = format_reset(component.reset_at_ms, timezone_id, now_ms=now_ms, compact=compact)
    elif component.window_active is False:
        reset = "not started"
    if reset is not None and not omit_reset:
        if parts:
            first = parts[0]
            parts[0] = StyledText(first.parts + ((" · " + reset, None),))
    return tuple(parts)


def billing_text(component: BillingComponent, *, watch: bool = False) -> str:
    value = "N/A" if component.amount is None else _native_amount(component.amount, component.currency,
        kind="remaining" if component.kind == "balance" else "consumed" if component.kind == "spend" else "exact")
    if (component.currency != "USD" and component.amount is not None
            and not (watch and component.currency.casefold() == "ai credits")):
        value += " " + component.currency
    status = component.status + " · " if component.status.lower() not in {"unknown", "active"} else ""
    return component.label + " " + status + value + (" remaining" if component.kind == "balance" else "")


def billing_visible(component: BillingComponent) -> bool:
    if component.amount is not None:
        return component.kind != "balance" or component.amount > 0
    return component.status.lower() in {"blocked", "paused", "error", "stale", "unavailable"}


def pace_text(pace: QuotaPace, *, qualified: bool = False) -> str:
    workday = ("no workdays left" if pace.per_workday is None
               else remaining_capacity(pace.per_workday) + "/workday")
    return (quota_label(pace.label) + " " if qualified else "") + f"{remaining_capacity(pace.per_day)}/day · {workday}"


def account_capacity_parts(account: AccountProjection, timezone_id: str, *, now_ms: int,
                           compact: bool = False, recovering: bool = False, watch: bool = False,
                           primary_label_width: int = 0) -> tuple[StyledText, ...]:
    snapshot = account.account
    parts = []
    labels = [quota_label(item.label) for item in snapshot.quotas] + (["Remaining"] if account.pace else [])
    label_width = max([4] + [len(label) for label in labels])
    if not watch and not compact:
        label_width = max(label_width, primary_label_width)
    merged_pace = set()
    for index, component in enumerate(snapshot.quotas):
        pace = next((item for item in account.pace if item.label == component.label), None)
        merge = watch and compact and pace is not None and sum(q.label == component.label for q in snapshot.quotas) == 1
        components = quota_parts(component, timezone_id, now_ms=now_ms, compact=compact,
                                 label_width=(primary_label_width or label_width) if index == 0 else (0 if compact else label_width),
                                 watch=watch, omit_reset=merge)
        if merge and components:
            components = (*components[:-1], StyledText(components[-1].parts + ((" · Remaining: " + pace_text(pace), None),)))
            merged_pace.add(pace)
        parts.extend(components)
    for pace in account.pace:
        if pace in merged_pace:
            continue
        prefix = "Remaining: " if compact else "Remaining".ljust(label_width) + "  "
        parts.append(StyledText(((prefix + pace_text(pace, qualified=len(account.pace) > 1), None),)))
    parts.extend(StyledText(((billing_text(item, watch=watch), None),)) for item in snapshot.billing if billing_visible(item))
    if snapshot.status is AccountUsageStatus.BLOCKED:
        parts.append(StyledText((("BLOCKED", "copilotPausedWarning"),)))
    if not snapshot.quotas and not snapshot.billing:
        state = "Quota temporarily unavailable" if recovering else "Quota " + snapshot.availability
        cause = _FAILURE_CAUSES.get(str(snapshot.observations.get("parser_reason")))
        if cause and snapshot.availability in {"error", "stale"}:
            state += f" ({cause})"
        state += " · Retrying..." if recovering else ""
        parts.append(StyledText(((state, "costQuotaWarning"),)))
    elif recovering:
        parts.append(StyledText((("STALE / RECONNECTING", "costQuotaWarning"),)))
    elif snapshot.availability in {"error", "stale", "unavailable", "partial"}:
        parts.append(StyledText(((snapshot.availability.upper(), "costQuotaWarning"),)))
    return tuple(parts)


def _styled(value: StyledText, styler: AnsiStyler) -> str:
    return "".join(styler.apply(text, role) for text, role in value.parts)


def _wrapped(value: StyledText, styler: AnsiStyler, width: int) -> list[str]:
    plain = str(value)
    position = 0
    result = []
    for line in textwrap.wrap(plain, width=max(10, width), break_long_words=True, break_on_hyphens=False):
        start = plain.find(line, position)
        end = start + len(line)
        cursor = 0
        spans = []
        for text, role in value.parts:
            left, right = max(start, cursor), min(end, cursor + len(text))
            if right > left:
                spans.append((text[left - cursor:right - cursor], role))
            cursor += len(text)
        result.append(_styled(StyledText(tuple(spans)), styler))
        position = end
    return result


def capacity_lines(account: AccountProjection, styler: AnsiStyler, timezone_id: str, *, width: int,
                   force_vertical: bool = False, include_label: bool = True,
                   now_ms: int | None = None, account_label_width: int = 0,
                   recovering: bool = False, watch: bool = False,
                   primary_label_width: int = 0) -> list[str]:
    """One account per row/block; vertical fallback regenerates verbose components."""
    now_ms = time.time_ns() // 1_000_000 if now_ms is None else now_ms
    prefix = account.label.ljust(account_label_width) + "   "
    lines = None
    if not force_vertical:
        components = account_capacity_parts(account, timezone_id, now_ms=now_ms, compact=True, recovering=recovering,
                                            watch=watch, primary_label_width=primary_label_width)
        plain = prefix + " | ".join(str(item) for item in components)
        if len(plain) <= width:
            lines = [prefix + " | ".join(_styled(item, styler) for item in components)]
    if lines is None:
        components = account_capacity_parts(account, timezone_id, now_ms=now_ms, recovering=recovering,
                                            watch=watch, primary_label_width=primary_label_width)
        lines = textwrap.wrap(account.label, width=max(10, width)) if include_label else []
        for component in components:
            if len(str(component)) <= width - 2:
                lines.append("  " + _styled(component, styler))
            else:
                lines.extend("  " + line for line in _wrapped(component, styler, width - 2))
    for warning in account.account.warnings:
        lines.extend("  " + line for line in _wrapped(
            StyledText(((warning, "copilotPausedWarning"),)), styler, width - 2))
    return lines
