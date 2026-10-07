"""Bounded declarative JSON-to-account normalization, not a presentation model."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from typing import Mapping

from src.domain import AccountSnapshot, AccountUsageStatus, BillingComponent, QuotaComponent
from .http_transport import MaintainedEndpoint, finite_number, validate_json_tree

MAX_COMPONENTS = 32
MAX_ROWS = 16
MAX_TIMESTAMP_MS = 253_402_300_799_999
Path = tuple[str, ...]
MISSING = object()


def at(value: object, path: Path) -> object:
    if len(path) > 8:
        return MISSING
    for key in path:
        if not isinstance(value, Mapping) or key not in value:
            return MISSING
        value = value[key]
    return value


def timestamp_ms(value: object, encoding: str) -> int | None:
    if encoding == "iso8601":
        if not isinstance(value, str) or len(value) > 40:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return None
            result = int(parsed.timestamp() * 1000)
        except (ValueError, OverflowError, OSError):
            return None
    elif encoding in {"unix_seconds", "unix_milliseconds"}:
        number = finite_number(value)
        if number is None:
            return None
        scaled = number * (1000 if encoding == "unix_seconds" else 1)
        if scaled != scaled.to_integral_value():
            return None
        result = int(scaled)
    else:
        return None
    return result if 0 < result <= MAX_TIMESTAMP_MS else None


@dataclass(frozen=True, slots=True)
class ComponentMapping:
    kind: str  # percentage_remaining/used, used_limit, remaining_limit, spend_budget, remaining_budget, balance/spend/budget
    label: str
    value_path: Path
    limit_path: Path = ()
    unit: str = "USD"
    unit_path: Path = ()
    allowed_units: tuple[str, ...] = ()
    period: str = "unknown"
    reset_path: Path = ()
    reset_encoding: str = ""
    optional: bool = False
    # A provider's explicit null limit means there is no capacity row, NOT zero.
    null_limit_absent: bool = False
    label_path: Path = ()
    label_values: tuple[tuple[str | None, str], ...] = ()
    period_values: tuple[tuple[str | None, str], ...] = ()

    def __post_init__(self):
        if self.kind not in {"percentage_remaining", "percentage_used", "used_limit", "remaining_limit",
                              "spend_budget", "remaining_budget", "balance", "spend", "budget"}:
            raise ValueError("Unsupported mapping primitive")
        if self.reset_path and self.reset_encoding not in {"iso8601", "unix_seconds", "unix_milliseconds"}:
            raise ValueError("Reset encoding must be explicitly declared")
        if any(len(path) > 8 for path in (self.value_path, self.limit_path, self.unit_path, self.reset_path, self.label_path)):
            raise ValueError("Mapping path too deep")


@dataclass(frozen=True, slots=True)
class SimpleHttpDefinition:
    provider_id: str
    display_label: str
    integration_ids: tuple[str, ...]
    endpoint: MaintainedEndpoint
    components: tuple[ComponentMapping, ...]
    root_path: Path = ()
    rows_path: Path = ()
    max_rows: int = 1
    plan_path: Path = ()
    plan_values: tuple[tuple[str, str], ...] = ()
    status_path: Path = ()
    status_values: tuple[tuple[object, AccountUsageStatus], ...] = ()

    def __post_init__(self):
        if not 1 <= self.max_rows <= MAX_ROWS or not 1 <= len(self.components) <= MAX_COMPONENTS:
            raise ValueError("Definition bounds exceeded")
        if any(len(path) > 8 for path in (self.root_path, self.rows_path, self.plan_path, self.status_path)):
            raise ValueError("Definition path too deep")


def _mapped(value, pairs):
    # Bool and 0/1 must not alias each other; no scripts or raw text pass-through.
    return next((result for expected, result in pairs if type(value) is type(expected) and value == expected), None)


def _component(spec: ComponentMapping, row: Mapping):
    raw = at(row, spec.value_path)
    raw_limit = at(row, spec.limit_path) if spec.limit_path else MISSING
    if spec.null_limit_absent and raw_limit is None:
        return None, raw not in (MISSING, None)
    if spec.optional and raw in (MISSING, None) and raw_limit in (MISSING, None):
        return None, False
    value = finite_number(raw)
    limit = finite_number(raw_limit) if spec.limit_path else None
    invalid = value is None or (bool(spec.limit_path) and limit is None)
    unit = spec.unit
    if spec.unit_path:
        native = at(row, spec.unit_path)
        if not isinstance(native, str) or native not in spec.allowed_units:
            return None, True
        unit = native
    label, period = spec.label, spec.period
    if spec.label_path:
        native = at(row, spec.label_path)
        label = _mapped(native, spec.label_values) or spec.label
        period = _mapped(native, spec.period_values) or spec.period
        invalid |= _mapped(native, spec.label_values) is None
    reset = None
    if spec.reset_path:
        native = at(row, spec.reset_path)
        if native not in (MISSING, None):
            reset = timestamp_ms(native, spec.reset_encoding)
            invalid |= reset is None
    if spec.kind in {"balance", "spend", "budget"}:
        return (BillingComponent(label, value, unit, period if period != "unknown" else "", kind=spec.kind)
                if value is not None else None), invalid
    used = remaining = fraction = None
    if spec.kind.startswith("percentage_"):
        if value is not None and value <= 100:
            fraction = value / 100 if spec.kind == "percentage_remaining" else 1 - value / 100
        else:
            invalid = True
    elif spec.kind in {"used_limit", "spend_budget"}:
        used = value
        if used is not None and limit is not None:
            remaining = max(Decimal(0), limit - used)
            fraction = remaining / limit if limit > 0 else None
    else:
        remaining = value
        if remaining is not None and limit is not None:
            if remaining <= limit:
                used = limit - remaining
                fraction = remaining / limit if limit > 0 else None
            else:
                invalid = True
    invalid |= spec.limit_path != () and (limit is None or limit == 0)
    if value is None and limit is None:
        return None, True
    return QuotaComponent(label, period, used=used, remaining=remaining, limit=limit,
                          remaining_fraction=fraction, unit=unit, reset_at_ms=reset,
                          status=AccountUsageStatus.BLOCKED if fraction == 0 else AccountUsageStatus.UNKNOWN), invalid


def normalize_simple_account(account: AccountSnapshot, payload: object, definition: SimpleHttpDefinition) -> AccountSnapshot:
    validate_json_tree(payload)
    root = at(payload, definition.root_path)
    errors = ignored = 0
    status = AccountUsageStatus.UNKNOWN
    plan = None
    if not isinstance(root, Mapping):
        return replace(account, availability="error", reason="Account response schema changed",
                       observations={"mapping_matched": False, "parser_status": "error", "parser_reason": "format_changed"})
    if definition.plan_path:
        raw = at(root, definition.plan_path)
        if raw not in (MISSING, None):
            plan = _mapped(raw, definition.plan_values)
            errors += plan is None
    if definition.status_path:
        status = _mapped(at(root, definition.status_path), definition.status_values)
        if status is None:
            status = AccountUsageStatus.UNKNOWN
            errors += 1
    rows = at(root, definition.rows_path) if definition.rows_path else [root]
    if not isinstance(rows, list):
        rows = []
        errors += 1
    ignored += max(0, len(rows) - definition.max_rows)
    quotas, billing = [], []
    for row in rows[:definition.max_rows]:
        if not isinstance(row, Mapping):
            errors += 1
            ignored += 1
            continue
        for spec in definition.components:
            if len(quotas) + len(billing) >= MAX_COMPONENTS:
                ignored += 1
                continue
            component, malformed = _component(spec, row)
            errors += bool(malformed)
            if isinstance(component, QuotaComponent):
                quotas.append(component)
            elif isinstance(component, BillingComponent):
                billing.append(component)
    produced = bool(quotas or billing)
    availability = "partial" if errors or ignored else "available"
    if not produced:
        availability = "error" if errors else "unavailable"
    return replace(account, plan=plan, quotas=tuple(quotas), billing=tuple(billing), status=status,
                   availability=availability, reason="Partial account observations" if errors or ignored else "" if produced else "No account values reported",
                   observations={"mapping_matched": not (errors or ignored), "malformed_fields": errors,
                                 "ignored_rows": ignored, "parser_status": availability,
                                 "parser_reason": "format_changed" if errors or ignored else "",
                                 "quota_components": len(quotas), "billing_components": len(billing)})
