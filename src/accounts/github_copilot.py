"""GitHub Copilot account/quota provider using OpenCode's existing OAuth credential.

The refresh token is read only in memory and is never placed in URLs, logs,
exceptions or returned domain objects.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable, Mapping

from src.version import DISPLAY_VERSION
from src.domain import (
    AccountRef,
    AccountUsageStatus,
    BillingComponent,
    IntegrationHealth,
    ProviderCapabilities,
    QuotaSnapshot,
    QuotaWindow,
    QuotaWindowKind,
)
from .base import normalize_quota
from .credentials import configured_credentials

ENTITLEMENT_URL = "https://github.com/github-copilot/chat/entitlement"
INTERNAL_USER_URL = "https://api.github.com/copilot_internal/user"


@dataclass(frozen=True, slots=True)
class OAuthCredential:
    available: bool
    provider: str = ""
    token: str = field(default="", repr=False)
    reason: str = ""


@dataclass(frozen=True, slots=True)
class JsonResponse:
    succeeded: bool
    status_code: int = 0
    payload: object | None = None
    network_error: bool = False


JsonGet = Callable[[str, str, bool, int], JsonResponse]


def resolve_auth_json_path(override: str | None, *, home: Path | None = None) -> Path:
    if override is not None and override.strip():
        expanded = os.path.expandvars(os.path.expanduser(override.strip()))
        return Path(expanded)
    base = home or Path.home()
    return base / ".local" / "share" / "opencode" / "auth.json"


def credential_from_auth_object(auth: object) -> OAuthCredential:
    if not isinstance(auth, Mapping):
        return OAuthCredential(False, reason="OpenCode auth.json is empty or invalid")
    found = non_oauth = missing_refresh = False
    for provider_id in ("github-copilot", "github-copilot-enterprise"):
        entry = auth.get(provider_id)
        if not isinstance(entry, Mapping):
            continue
        found = True
        if str(entry.get("type") or "") != "oauth":
            non_oauth = True
            continue
        refresh = str(entry.get("refresh") or "")
        if not refresh.strip():
            missing_refresh = True
            continue
        return OAuthCredential(True, provider_id, refresh, "")
    if not found:
        reason = "GitHub Copilot OAuth credential not found in OpenCode auth.json"
    elif missing_refresh:
        reason = "GitHub Copilot OAuth credential has no refresh token"
    elif non_oauth:
        reason = "GitHub Copilot credential in OpenCode auth.json is not OAuth"
    else:
        reason = "GitHub Copilot OAuth credential is unavailable"
    return OAuthCredential(False, reason=reason)


def load_opencode_copilot_credential(path: Path) -> OAuthCredential:
    if not path.is_file():
        return OAuthCredential(False, reason="OpenCode auth.json not found")
    try:
        auth = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return OAuthCredential(False, reason="OpenCode auth.json could not be parsed")
    return credential_from_auth_object(auth)


def _default_json_get(url: str, token: str, copilot_headers: bool, timeout_seconds: int) -> JsonResponse:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if copilot_headers:
        headers.update({
            "User-Agent": "GitHubCopilotChat/0.26.7",
            "Editor-Version": "vscode/1.99.3",
            "Editor-Plugin-Version": "copilot-chat/0.26.7",
            "Copilot-Integration-Id": "vscode-chat",
            "X-GitHub-Api-Version": "2025-05-01",
        })
    else:
        headers["User-Agent"] = f"CostGuard/{DISPLAY_VERSION}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=max(1, timeout_seconds)) as response:  # noqa: S310 - fixed HTTPS URLs
            status = int(getattr(response, "status", 200))
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return JsonResponse(False, int(exc.code), None, False)
    except (urllib.error.URLError, TimeoutError, OSError):
        return JsonResponse(False, 0, None, True)
    if not body.strip():
        return JsonResponse(False, status, None, False)
    try:
        return JsonResponse(True, status, json.loads(body), False)
    except json.JSONDecodeError:
        return JsonResponse(False, status, None, False)


def _usage_status(value: object) -> AccountUsageStatus:
    if not isinstance(value, Mapping):
        return AccountUsageStatus.UNKNOWN
    statuses: list[bool] = []
    for key in ("hasQuota", "has_quota"):
        if key not in value:
            continue
        current = value.get(key)
        if not isinstance(current, bool):
            return AccountUsageStatus.UNKNOWN
        statuses.append(current)
    if not statuses or (True in statuses and False in statuses):
        return AccountUsageStatus.UNKNOWN
    return AccountUsageStatus.AVAILABLE if statuses[0] else AccountUsageStatus.BLOCKED


def _copilot_plan(payload: object) -> str | None:
    if not isinstance(payload, Mapping):
        return None
    value = payload.get("copilot_plan")
    if not isinstance(value, str):
        return None
    plan = value.strip().lower()
    if plan == "individual_pro" and payload.get("access_type_sku") == "plus_monthly_subscriber_quota":
        return "Pro+"
    # The internal endpoint can identify a broad subscription family; do not
    # infer a more specific paid tier from quota size or an unrecognized SKU.
    return {
        "individual": "Individual", "individual_pro": "Individual",
        "business": "Business", "enterprise": "Enterprise",
        "free": "Free", "pro": "Pro", "pro_plus": "Pro+", "max": "Max",
        "organization": "Organization",
    }.get(plan)


def _unavailable(
    reason: str, status: AccountUsageStatus = AccountUsageStatus.UNKNOWN, *, fetched_at_ms: int | None = None,
) -> QuotaSnapshot:
    return QuotaSnapshot(
        provider="github-copilot", fetched_at_ms=fetched_at_ms if fetched_at_ms is not None else int(time.time() * 1000),
        capabilities=ProviderCapabilities(account_quota=True), available=False,
        reason=reason, usage_status=status,
    )


def _number(value: object) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal, str)):
        return None
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        return None
    return result if result.is_finite() and result >= 0 else None


def _reset_at_ms(payload: object) -> int | None:
    """Provider-reported quota period end; an unknown boundary stays unknown."""
    if not isinstance(payload, Mapping):
        return None
    for key, suffix in (("quota_reset_date_utc", ""), ("quota_reset_date", "T00:00:00+00:00")):
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00") + suffix)
        except ValueError:
            continue
        if parsed.tzinfo is not None:
            return int(parsed.timestamp() * 1000)
    return None


def _extra_credit_limits(premium: object) -> tuple[BillingComponent, ...]:
    """Keep an explicitly reported overage limit separate from included capacity.

    A spending allowance is not proof of a purchased/remaining balance. Do not
    manufacture a remaining amount or include it in the fixed-period Pace.
    """
    if not isinstance(premium, Mapping):
        return ()
    limit = _number(premium.get("overage_entitlement"))
    if limit is None or limit == 0:
        return ()
    status = "paused" if premium.get("overage_permitted") is False else "unknown"
    return (BillingComponent("Extra credit limit", limit, "AI credits", kind="budget", status=status),)


def _quota_snapshot(
    *, used: Decimal | None, total: Decimal | None, remaining_percentage: Decimal | None,
    status: AccountUsageStatus, fetched_at_ms: int, plan: str | None = None, unlimited: bool = False,
    reset_at_ms: int | None = None,
) -> QuotaSnapshot:
    denominator_usable = bool(not unlimited and total is not None and total > 0 and (used is None or used <= total))
    numeric_usable = denominator_usable and used is not None
    remaining = total - used if numeric_usable else None
    fraction = remaining / total if numeric_usable else None
    if fraction is None and remaining_percentage is not None and 0 <= remaining_percentage <= 100:
        fraction = remaining_percentage / 100
    window = QuotaWindow(
        name="monthly_ai_credits", kind=QuotaWindowKind.FIXED,
        used_fraction=1 - fraction if fraction is not None else None, remaining_fraction=fraction,
        native_used=used, native_limit=total if denominator_usable else None,
        native_unit="AI credits", unlimited=unlimited, reset_at_ms=reset_at_ms,
    )
    reason = "" if numeric_usable or unlimited else ("usage_unavailable" if denominator_usable else "denominator_unusable")
    return QuotaSnapshot(
        provider="github-copilot", fetched_at_ms=fetched_at_ms,
        capabilities=ProviderCapabilities(account_quota=True),
        plan=plan, windows=(window,), available=True, usage_status=status,
        availability="available" if numeric_usable or unlimited else "partial",
        reason=reason,
        observations={
            "provider": "github-copilot", "plan": plan,
            "has_quota": None if status is AccountUsageStatus.UNKNOWN else status is AccountUsageStatus.AVAILABLE,
            "unlimited": unlimited, "credits_used": None if used is None else str(used),
            "entitlement": None if total is None else str(total),
            "remaining": None if remaining is None else str(remaining),
            "remaining_fraction": None if fraction is None else str(fraction),
            "numeric_quota_usable": numeric_usable, "parser_reason": reason,
        },
        warnings=(("⚠  COPILOT PAUSED: GitHub reported hasQuota=false.",)
                  if status is AccountUsageStatus.BLOCKED else ()),
    )


def convert_entitlement_payload(payload: object, *, fetched_at_ms: int | None = None) -> QuotaSnapshot:
    now = fetched_at_ms or int(time.time() * 1000)
    if not isinstance(payload, Mapping):
        return replace(_unavailable("GitHub Copilot entitlement returned no quota data", fetched_at_ms=now),
                       availability="error", observations={"parser_reason": "parser_failure"})
    quotas = payload.get("quotas")
    quotas = quotas if isinstance(quotas, Mapping) else {}
    premium = quotas.get("premiumInteractionsQuota")
    status = _usage_status(premium)
    if not isinstance(premium, Mapping) or not any(key in premium for key in ("hasQuota", "has_quota")):
        status = _usage_status(payload)
    total: object | None = premium.get("total") if isinstance(premium, Mapping) else None
    if total is None and isinstance(quotas.get("limits"), Mapping):
        total = quotas["limits"].get("premiumInteractions")
    used = premium.get("creditsUsed") if isinstance(premium, Mapping) else None
    if not premium and not _copilot_plan(payload):
        return replace(_unavailable("GitHub Copilot entitlement did not return quota data", fetched_at_ms=now),
                       availability="error", observations={"parser_reason": "parser_failure"})
    snapshot = _quota_snapshot(used=_number(used), total=_number(total), remaining_percentage=None, status=status, fetched_at_ms=now,
                              plan=_copilot_plan(payload), reset_at_ms=_reset_at_ms(payload))
    return replace(snapshot, billing_components=_extra_credit_limits(premium))


def convert_internal_user_payload(payload: object, *, fetched_at_ms: int | None = None) -> QuotaSnapshot:
    now = fetched_at_ms or int(time.time() * 1000)
    if not isinstance(payload, Mapping):
        return replace(_unavailable("GitHub Copilot user quota returned no data", fetched_at_ms=now),
                       availability="error", observations={"parser_reason": "parser_failure"})
    snapshots = payload.get("quota_snapshots")
    premium = snapshots.get("premium_interactions") if isinstance(snapshots, Mapping) else None
    if not isinstance(premium, Mapping):
        if not _copilot_plan(payload):
            return replace(_unavailable("GitHub Copilot premium_interactions quota was not returned", fetched_at_ms=now),
                           availability="error", observations={"parser_reason": "parser_failure"})
        premium = {}
    status = _usage_status(premium)
    if not any(key in premium for key in ("hasQuota", "has_quota")):
        status = _usage_status(payload)
    percent = premium.get("percent_remaining")
    remaining_percentage = _number(percent)
    total = premium.get("entitlement")
    used = premium.get("credits_used", premium.get("creditsUsed"))
    snapshot = _quota_snapshot(used=_number(used), total=_number(total), remaining_percentage=remaining_percentage, status=status, fetched_at_ms=now,
                              plan=_copilot_plan(payload), unlimited=premium.get("unlimited") is True,
                              reset_at_ms=_reset_at_ms(payload))
    return replace(snapshot, billing_components=_extra_credit_limits(premium))


def _combine_quota(entitlement: QuotaSnapshot, user: QuotaSnapshot) -> QuotaSnapshot:
    data = entitlement if entitlement.available and entitlement.availability == "available" else user
    if not data.available and entitlement.available:
        data = entitlement
    status = entitlement.usage_status if entitlement.usage_status is not AccountUsageStatus.UNKNOWN else user.usage_status
    plan = entitlement.plan or user.plan
    return replace(data, plan=plan, usage_status=status,
                   billing_components=entitlement.billing_components or user.billing_components,
                   warnings=(("⚠  COPILOT PAUSED: GitHub reported hasQuota=false.",) if status is AccountUsageStatus.BLOCKED else ()),
                   observations={**data.observations, "plan": plan,
                       "has_quota": None if status is AccountUsageStatus.UNKNOWN else status is AccountUsageStatus.AVAILABLE,
                       "primary_has_quota": entitlement.observations.get("has_quota"),
                       "fallback_has_quota": user.observations.get("has_quota"),
                       "entitlement_http_status": entitlement.observations.get("http_status"),
                       "internal_http_status": user.observations.get("http_status"),
                   })


class GitHubCopilotAccountProvider:
    provider_id = "github-copilot"
    included_usage = False
    capabilities = ProviderCapabilities(account_quota=True)

    def __init__(
        self,
        *,
        enabled: bool = True,
        auth_json_path: str | None = None,
        credential_db_path: Path | None = None,
        home: Path | None = None,
        json_get: JsonGet = _default_json_get,
        now_ms: Callable[[], int] | None = None,
    ) -> None:
        self.enabled = enabled
        self.auth_json_path = resolve_auth_json_path(auth_json_path, home=home)
        self.credential_db_path = credential_db_path if not auth_json_path else None
        self.json_get = json_get
        self.now_ms = now_ms or (lambda: int(time.time() * 1000))

    def probe(self) -> IntegrationHealth:
        if not self.enabled:
            return IntegrationHealth(True, False, "disabled in config")
        records = configured_credentials(self.auth_json_path, self.credential_db_path,
                                         ("github-copilot", "github-copilot-enterprise"))
        return IntegrationHealth(bool(records), bool(records), "configured Copilot account" if records else "Copilot account not configured")

    def get_quota_snapshot(self) -> QuotaSnapshot:
        now = self.now_ms()
        if not self.enabled:
            snapshot = _unavailable("disabled in config")
            return _replace_fetched(snapshot, now)
        credential = load_opencode_copilot_credential(self.auth_json_path)
        if not credential.available:
            return _replace_fetched(_unavailable(credential.reason), now)
        return self._fetch(credential, now)

    def get_account_snapshots(self):
        if not self.enabled:
            return ()
        records = configured_credentials(self.auth_json_path, self.credential_db_path,
                                         ("github-copilot", "github-copilot-enterprise"))
        accounts = []
        for record in records:
            credential = credential_from_auth_object({record.ref.provider_id: record.value})
            snapshot = self._fetch(credential, self.now_ms()) if credential.available else _unavailable(credential.reason)
            ref = replace(record.ref, provider_id="github-copilot")
            account = normalize_quota(snapshot, ref, "GitHub Copilot")
            quotas = tuple(replace(component,
                remaining_money=component.remaining * Decimal("0.01") if component.remaining is not None else None,
                limit_money=component.limit * Decimal("0.01") if component.limit is not None else None,
            ) for component in account.quotas)
            accounts.append(replace(account, quotas=quotas))
        return tuple(accounts)

    def _fetch(self, credential: OAuthCredential, now: int) -> QuotaSnapshot:
        token = credential.token
        try:
            try:
                entitlement_probe = self.json_get(ENTITLEMENT_URL, token, False, 15)
            except Exception:
                entitlement_probe = JsonResponse(False, 0, None, True)
            entitlement_result: QuotaSnapshot | None = None
            if entitlement_probe.succeeded:
                entitlement_result = convert_entitlement_payload(entitlement_probe.payload, fetched_at_ms=now)
                entitlement_result = replace(entitlement_result, observations={
                    **entitlement_result.observations, "http_status": entitlement_probe.status_code,
                })
                if entitlement_result.available and entitlement_result.plan and entitlement_result.availability == "available":
                    return entitlement_result

            try:
                user_probe = self.json_get(INTERNAL_USER_URL, token, True, 20)
            except Exception:
                user_probe = JsonResponse(False, 0, None, True)
            if user_probe.succeeded:
                mapped = convert_internal_user_payload(user_probe.payload, fetched_at_ms=now)
                mapped = replace(mapped, observations={
                    **mapped.observations, "http_status": user_probe.status_code,
                    "entitlement_http_status": entitlement_probe.status_code,
                })
                return _combine_quota(entitlement_result, mapped) if entitlement_result is not None else mapped

            if entitlement_result is not None and entitlement_result.available:
                return entitlement_result
            if entitlement_result is not None and entitlement_result.usage_status is not AccountUsageStatus.UNKNOWN:
                return entitlement_result
            if user_probe.status_code in (401, 403):
                return replace(_unavailable("GitHub Copilot sign-in was rejected; sign in to GitHub Copilot again in OpenCode.", fetched_at_ms=now),
                               availability="unavailable", observations={
                                   "http_status": user_probe.status_code, "parser_reason": "auth_failure",
                                   "user_action": "Sign-in rejected; sign in to GitHub again in OpenCode"})
            if user_probe.network_error and entitlement_probe.network_error:
                return replace(_unavailable("GitHub Copilot quota request failed (network)", fetched_at_ms=now),
                               availability="error", observations={"http_status": 0, "parser_reason": "network_failure"})
            return replace(_unavailable("GitHub Copilot AI-credit quota request failed", fetched_at_ms=now),
                           availability="error", observations={"http_status": user_probe.status_code,
                               "parser_reason": "parser_failure" if 200 <= user_probe.status_code < 300 else "http_failure"})
        finally:
            token = ""
            credential = OAuthCredential(False)


def _replace_fetched(snapshot: QuotaSnapshot, fetched_at_ms: int) -> QuotaSnapshot:
    return replace(snapshot, fetched_at_ms=fetched_at_ms)
