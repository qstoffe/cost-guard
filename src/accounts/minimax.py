"""First-class MiniMax Token Plan adapter with explicit native window semantics.

The official FAQ documents Bearer GET /v1/token_plan/remains. The official
MiniMax CLI's quota schema/fixtures document model_remains, millisecond reset
offsets and ambiguous legacy counts. Unknown shapes fail closed, not inferred.
"""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Mapping

from src.domain import AccountUsageStatus, QuotaComponent
from .http_account import HttpAccountProvider
from .http_transport import MaintainedEndpoint, finite_number
from .simple_http_mapping import timestamp_ms

GLOBAL_ENDPOINT = MaintainedEndpoint("https://www.minimax.io/v1/token_plan/remains")
CN_ENDPOINT = MaintainedEndpoint("https://www.minimax.cn/v1/token_plan/remains")
SUBSCRIPTION_IDS = {"minimax-coding-plan": GLOBAL_ENDPOINT, "minimax-cn-coding-plan": CN_ENDPOINT}
MAX_BUCKETS = 8
_BUCKETS = {"general": "", "MiniMax-M*": "", "video": "Video", "speech-hd": "Speech", "image-01": "Image"}
_BUCKETS.update({name: name for name in ("MiniMax-M2", "MiniMax-M2.1", "MiniMax-M2.5", "MiniMax-M2.7", "MiniMax-M3")})
_PLANS = {name.lower(): name for name in ("Plus", "Max", "Ultra", "Starter", "Plus-hs", "Max-hs", "Ultra-hs")}


def _remaining_percent(row, weekly):
    names = ("current_weekly_remaining_percent",) if weekly else (
        "current_interval_remaining_percent", "usage_percent", "usagePercent")
    supplied = [finite_number(row[name]) for name in names if name in row and row[name] is not None]
    if not supplied:
        return None, False
    if any(value is None or value > 100 for value in supplied) or len(set(supplied)) != 1:
        return None, True
    return supplied[0], False


def _window(row: Mapping, *, weekly: bool, now_ms: int, bucket: str):
    prefix = "current_weekly_" if weekly else "current_interval_"
    label, seconds = ("Week", 604_800) if weekly else ("5h", 18_000)
    malformed = False
    start_field, end_field, offset_field = ("weekly_start_time", "weekly_end_time", "weekly_remains_time") if weekly else (
        "start_time", "end_time", "remains_time")
    start = timestamp_ms(row.get(start_field), "unix_milliseconds")
    end = timestamp_ms(row.get(end_field), "unix_milliseconds")
    if start is not None and end is not None:
        duration = end - start
        if not weekly and duration == 86_400_000:
            label, seconds = "Day", 86_400
        elif duration != seconds * 1000:
            label, seconds, malformed = "Limit", None, True
    elif row.get(start_field) not in (None, 0) or row.get(end_field) not in (None, 0):
        malformed = start is None or end is None
    reset = end
    if reset is None and row.get(offset_field) is not None:
        offset = finite_number(row[offset_field])
        if offset is not None and offset == offset.to_integral_value() and offset <= (seconds or 604_800) * 1000:
            reset = now_ms + int(offset)
        else:
            malformed = True
    native_status = finite_number(row.get(prefix + "status"))
    if row.get(prefix + "status") is not None and native_status not in (Decimal(1), Decimal(2), Decimal(3)):
        malformed = True
    percent, bad_percent = _remaining_percent(row, weekly)
    malformed |= bad_percent
    raw_total = row.get(prefix + "total_count")
    raw_count = row.get(prefix + "usage_count")
    total, count = finite_number(raw_total), finite_number(raw_count)
    used = remaining = fraction = None
    if total is not None and total > 0 and count is not None and count <= total:
        remaining = count  # The documented legacy usage_count means remaining.
        if percent is not None:
            possibilities = (count, total - count)
            distances = tuple(abs(value / total * 100 - percent) for value in possibilities)
            if min(distances) > 1:
                remaining = None
                malformed = True
            else:
                remaining = possibilities[0 if distances[0] <= distances[1] else 1]
        if remaining is not None:
            used, fraction = total - remaining, remaining / total
    elif (raw_total is not None and total is None) or (raw_count is not None and count is None) or (
            total is not None and total > 0 and (count is None or count > total)):
        malformed = True
    if fraction is None and percent is not None:
        fraction = percent / 100
    unlimited = native_status == 3
    if unlimited:
        # Only an explicit native status proves unlimited, not zero counters.
        fraction = None
    if weekly and row.get("weekly_boost_permille") is not None:
        boost = finite_number(row["weekly_boost_permille"])
        if boost != 1000:
            # A boosted display share is not a new allocation denominator.
            fraction = used = remaining = None
            malformed = True
    blocked = native_status == 2 or fraction == 0
    if native_status == 2 and fraction not in (None, Decimal(0)):
        fraction = used = remaining = None
        malformed = True
    if fraction is None and not unlimited and not blocked and remaining is None:
        return None, malformed or total not in (None, Decimal(0)) or bad_percent or raw_total is None
    component = QuotaComponent((bucket + " " if bucket else "") + label, "rolling",
        used=used, remaining=remaining, limit=total if total is not None and total > 0 else None,
        remaining_fraction=fraction, unit="plan units" if total is not None and total > 0 else None,
        reset_at_ms=reset, duration_seconds=seconds, unlimited=unlimited,
        status=AccountUsageStatus.BLOCKED if blocked else AccountUsageStatus.UNKNOWN)
    return component, malformed


def normalize_minimax_account(account, payload):
    errors = ignored = 0
    if not isinstance(payload, Mapping):
        payload = {}
    base = payload.get("base_resp")
    if not isinstance(base, Mapping) or finite_number(base.get("status_code")) is None:
        return replace(account, availability="error", reason="MiniMax response schema changed",
            observations={"parser_reason": "format_changed", "parser_status": "error", "mapping_matched": False})
    provider_status = finite_number(base["status_code"])
    if provider_status != provider_status.to_integral_value() or provider_status > 100_000:
        return replace(account, availability="error", reason="MiniMax response schema changed",
            observations={"parser_reason": "format_changed", "parser_status": "error", "mapping_matched": False})
    if provider_status != 0:
        # Documented MiniMax API codes, not status_msg/prose. Transient backend
        # rejections must retain the ordinary Watch recovery path even at HTTP 200.
        auth = provider_status in (1004, 2049)
        blocked = provider_status in (1008, 2056)
        availability = "unavailable" if auth or blocked else "error"
        cause = "auth_failure" if auth else "provider_rejected" if blocked else "timeout" if provider_status == 1001 else "http_failure"
        return replace(account, availability=availability,
            status=AccountUsageStatus.BLOCKED if blocked else AccountUsageStatus.UNKNOWN,
            reason="MiniMax rejected the credential; reconnect this subscription account in OpenCode." if auth else "MiniMax Token Plan request failed",
            observations={"parser_reason": cause, "parser_status": availability, "mapping_matched": True,
                          "response_form": "base_resp", "provider_status": int(provider_status),
                          **({"user_action": "Reconnect this subscription account in OpenCode"} if auth else {})})
    rows = payload.get("model_remains")
    if not isinstance(rows, list):
        rows = []
        errors += 1
    ignored += max(0, len(rows) - MAX_BUCKETS)
    rows = rows[:MAX_BUCKETS]
    # Prefer general only when a repeated chat bucket's full native window
    # evidence agrees. Different limits/resets are not combined or discarded.
    general = next((row for row in rows if isinstance(row, Mapping) and row.get("model_name") == "general"), None)
    quotas = []
    seen = set()
    for row in rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("model_name"), str) or row["model_name"] not in _BUCKETS:
            errors += 1
            ignored += 1
            continue
        name = row["model_name"]
        if general and name.startswith("MiniMax-M"):
            evidence = ("start_time", "end_time", "remains_time", "weekly_start_time", "weekly_end_time", "weekly_remains_time",
                        "current_interval_total_count", "current_interval_usage_count", "current_interval_remaining_percent",
                        "current_weekly_total_count", "current_weekly_usage_count", "current_weekly_remaining_percent",
                        "current_interval_status", "current_weekly_status", "weekly_boost_permille", "usage_percent", "usagePercent")
            if all(row.get(key) == general.get(key) for key in evidence):
                continue
        if name in seen:
            errors += 1
            ignored += 1
            continue
        seen.add(name)
        if all(finite_number(row.get(field)) == 0 for field in (
                "current_interval_total_count", "current_weekly_total_count")) and all(
                finite_number(row.get(field)) == 3 for field in ("current_interval_status", "current_weekly_status")):
            continue  # The native no-bucket form, NOT unlimited entitlement.
        for weekly in (False, True):
            component, malformed = _window(row, weekly=weekly, now_ms=account.fetched_at_ms, bucket=_BUCKETS[name])
            errors += malformed
            if component is not None:
                quotas.append(component)
    plan = None
    raw_plan = payload.get("plan")
    if isinstance(raw_plan, str):
        plan = _PLANS.get(raw_plan.lower())
        errors += plan is None
    availability = "partial" if errors or ignored else "available"
    if not quotas:
        availability = "error" if errors else "unavailable"
    return replace(account, provider_label="MiniMax Token Plan" if quotas else "MiniMax", plan=plan,
        quotas=tuple(quotas), availability=availability,
        reason="Partial MiniMax quota observations" if errors or ignored else "" if quotas else "Token Plan quota entitlement not reported",
        observations={"mapping_matched": not (errors or ignored), "response_form": "model_remains",
                      "provider_status": 0,
                      "malformed_fields": errors, "ignored_rows": ignored, "quota_components": len(quotas),
                      "billing_components": 0, "parser_status": availability,
                      "parser_reason": "format_changed" if errors or ignored else "",
                      "quota_windows": tuple(sorted({q.label.rsplit(" ", 1)[-1] for q in quotas}))})


class MiniMaxAccountProvider(HttpAccountProvider):
    provider_id = "minimax"
    display_label = "MiniMax"
    integration_ids = ("minimax-coding-plan", "minimax-cn-coding-plan", "minimax", "minimax-cn")

    def endpoint_for(self, record):
        # The explicit subscription integration permits a read, not an inferred
        # paid plan. Generic pay-as-you-go keys remain visible with no quota claim.
        return SUBSCRIPTION_IDS.get(record.ref.provider_id)

    def unsupported_credential_reason(self, record):
        if self.endpoint_for(record) is None:
            return "Token Plan quota requires a MiniMax subscription integration in OpenCode; a generic API key does not prove entitlement."
        return super().unsupported_credential_reason(record)

    def normalize_response(self, account, payload):
        return normalize_minimax_account(account, payload)
