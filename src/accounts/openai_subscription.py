"""Fail-soft ChatGPT/Codex subscription quota reader.

OpenAI's open-source Codex client reads the same HTTPS usage surface. The REST
shape is not a public compatibility contract, so every parse failure remains an
unavailable account panel and credentials are never refreshed or written here.
"""
from __future__ import annotations

import base64
import json
import os
import re
import sqlite3
import time
import urllib.error
import urllib.request
from contextlib import closing
from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable, Mapping

from src.version import VERSION
from src.domain import (
    AccountUsageStatus,
    BillingComponent,
    IntegrationHealth,
    ProviderCapabilities,
    QuotaSnapshot,
    QuotaWindow,
    QuotaWindowKind,
)
from .base import normalize_quota
from .credentials import configured_credentials, resolve_auth_path

USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
# OpenCode renews the OAuth token when it next calls OpenAI; Cost Guard never does.
EXPIRED_REASON = "OpenAI token expired; it renews automatically on your next OpenAI prompt in OpenCode."


@dataclass(frozen=True, slots=True)
class OpenAICredential:
    available: bool
    access_token: str = field(default="", repr=False)
    account_id: str = field(default="", repr=False)
    reason: str = ""


@dataclass(frozen=True, slots=True)
class UsageResponse:
    succeeded: bool
    status_code: int = 0
    payload: object | None = field(default=None, repr=False)
    network_error: bool = False


UsageGet = Callable[[str, str, str, int], UsageResponse]


def _auth_path(override: str | None, *, home: Path | None = None) -> Path:
    return resolve_auth_path(override, home=home)


def _jwt_account_id(token: str) -> str:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        value = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
    except (ValueError, IndexError, UnicodeError):
        return ""
    if not isinstance(value, Mapping):
        return ""
    auth = value.get("https://api.openai.com/auth")
    if isinstance(auth, Mapping):
        candidate = auth.get("chatgpt_account_id") or auth.get("account_id")
        if candidate:
            return str(candidate)
    candidate = value.get("chatgpt_account_id") or value.get("account_id")
    return str(candidate) if candidate else ""


def credential_from_auth_object(value: object) -> OpenAICredential:
    if not isinstance(value, Mapping):
        return OpenAICredential(False, reason="OpenCode auth.json is empty or invalid")
    candidates: list[Mapping[str, object]] = []
    for provider in ("openai", "openai-codex", "codex"):
        item = value.get(provider)
        if isinstance(item, Mapping) and str(item.get("type") or "").lower() == "oauth":
            candidates.append(item)
    for item in candidates:
        nested = item.get("tokens") if isinstance(item.get("tokens"), Mapping) else item
        assert isinstance(nested, Mapping)
        access = nested.get("access_token") or nested.get("access") or item.get("access")
        if not isinstance(access, str) or not access.strip():
            continue
        metadata = item.get("metadata") if isinstance(item.get("metadata"), Mapping) else {}
        account = (
            nested.get("account_id") or nested.get("accountId")
            or item.get("account_id") or item.get("accountId")
            or metadata.get("accountID")
            or _jwt_account_id(access)
        )
        return OpenAICredential(True, access.strip(), str(account or ""))
    return OpenAICredential(False, reason="OpenAI ChatGPT OAuth credential not found in OpenCode auth.json")


def load_credential(path: Path) -> OpenAICredential:
    if not path.is_file():
        return OpenAICredential(False, reason="OpenCode auth.json not found")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return OpenAICredential(False, reason="OpenCode auth.json could not be parsed")
    return credential_from_auth_object(value)


def load_v2_credential(path: Path, *, now_ms: int) -> OpenAICredential | None:
    """Read the active V2 OAuth account without changing OpenCode storage.

    None permits legacy auth.json fallback only when no V2 account exists.
    A present but unusable account must not switch to a different identity.
    """
    if not path.is_file():
        return None
    try:
        with closing(sqlite3.connect(path.resolve(strict=False).as_uri() + "?mode=ro", uri=True, timeout=1)) as conn:
            conn.execute("PRAGMA query_only=ON")
            if conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='credential'"
            ).fetchone() is None:
                return None
            row = conn.execute(
                "SELECT value FROM credential WHERE integration_id=? AND active=1 "
                "ORDER BY time_updated DESC LIMIT 1", ("openai",),
            ).fetchone()
    except (sqlite3.Error, OSError):
        return OpenAICredential(False, reason="OpenCode V2 account storage could not be read")
    if row is None:
        return None
    try:
        value = json.loads(row[0])
    except (TypeError, ValueError):
        return OpenAICredential(False, reason="OpenCode V2 OpenAI OAuth credential is invalid")
    credential = credential_from_auth_object({"openai": value})
    if not credential.available:
        return OpenAICredential(False, reason="Active OpenCode V2 OpenAI account is not usable OAuth")
    expires = value.get("expires") if isinstance(value, Mapping) else None
    if isinstance(expires, (int, float)) and not isinstance(expires, bool):
        expiration_ms = expires if expires > 10_000_000_000 else expires * 1000
        if expiration_ms <= now_ms:
            return OpenAICredential(False, reason=EXPIRED_REASON)
    return credential


def _default_usage_get(url: str, token: str, account_id: str, timeout_seconds: int) -> UsageResponse:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": f"CostGuard/{VERSION}",
    }
    if account_id:
        headers["ChatGPT-Account-ID"] = account_id
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=max(1, timeout_seconds)) as response:  # noqa: S310 - fixed HTTPS URL
            status = int(getattr(response, "status", 200))
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return UsageResponse(False, int(exc.code))
    except (urllib.error.URLError, TimeoutError, OSError):
        return UsageResponse(False, network_error=True)
    try:
        return UsageResponse(True, status, json.loads(body))
    except (UnicodeError, json.JSONDecodeError):
        return UsageResponse(False, status)


def _decimal(value: object) -> Decimal | None:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return result if result.is_finite() else None


def _reset_ms(window: Mapping[str, object], now_ms: int) -> int | None:
    raw = window.get("reset_at", window.get("reset_time_ms"))
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        number = int(raw)
        return number if number > 10_000_000_000 else number * 1000
    if isinstance(raw, str) and raw.strip():
        try:
            return int(datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp() * 1000)
        except ValueError:
            pass
    after = window.get("reset_after_seconds")
    if isinstance(after, (int, float)) and not isinstance(after, bool):
        return now_ms + int(after * 1000)
    return None


def _window_name(seconds: int | None, fallback: str) -> str:
    if seconds is not None:
        if 4 * 3600 <= seconds <= 6 * 3600:
            return "5-hour"
        if 6 * 86400 <= seconds <= 8 * 86400:
            return "weekly"
        if seconds % 86400 == 0:
            return f"{seconds // 86400}-day"
        if seconds % 3600 == 0:
            return f"{seconds // 3600}-hour"
    return fallback.replace("_", " ")


def _convert_window(name: str, value: object, now_ms: int) -> QuotaWindow | None:
    if not isinstance(value, Mapping):
        return None
    used = _decimal(value.get("used_percent"))
    if used is None:
        left = _decimal(value.get("percent_left"))
        used = Decimal(100) - left if left is not None else None
    used_fraction = max(Decimal(0), min(Decimal(1), used / Decimal(100))) if used is not None else None
    duration_raw = value.get("limit_window_seconds")
    duration = int(duration_raw) if isinstance(duration_raw, (int, float)) and not isinstance(duration_raw, bool) and duration_raw > 0 else None
    return QuotaWindow(
        name=_window_name(duration, name),
        kind=QuotaWindowKind.ROLLING,
        used_fraction=used_fraction,
        remaining_fraction=Decimal(1) - used_fraction if used_fraction is not None else None,
        reset_at_ms=_reset_ms(value, now_ms),
        duration_seconds=duration,
    )


def convert_usage_payload(payload: object, *, fetched_at_ms: int) -> QuotaSnapshot:
    if not isinstance(payload, Mapping):
        return replace(_unavailable("OpenAI usage returned no quota data", fetched_at_ms), availability="error",
                       observations={"parser_reason": "parser_failure"})
    rate = payload.get("rate_limit", payload.get("rate_limits"))
    rate_map = rate if isinstance(rate, Mapping) else {}
    windows: list[QuotaWindow] = []
    for name in ("primary_window", "secondary_window", "five_hour", "weekly"):
        item = _convert_window(name, rate_map.get(name), fetched_at_ms)
        if item is not None and not any(existing.name == item.name for existing in windows):
            windows.append(item)
    additional = payload.get("additional_rate_limits")
    if isinstance(additional, list):
        for index, raw in enumerate(additional, start=1):
            if isinstance(raw, Mapping) and isinstance(raw.get("rate_limit"), Mapping):
                label = str(raw.get("limit_name") or "Model quota")
                if not re.fullmatch(r"[\w ./-]{1,80}", label):
                    label = "Model quota"
                for key in ("primary_window", "secondary_window"):
                    item = _convert_window(key, raw["rate_limit"].get(key), fetched_at_ms)
                    if item is not None:
                        model_id = raw.get("model_id")
                        windows.append(replace(item, name=label + " " + item.name,
                                               model_id=model_id if isinstance(model_id, str) else None, scope="model"))
                continue
            item = _convert_window(f"additional {index}", raw, fetched_at_ms)
            if item is not None:
                windows.append(item)
    credits = payload.get("credits")
    credit_map = credits if isinstance(credits, Mapping) else {}
    balance = _decimal(credit_map.get("balance"))
    allowed = rate_map.get("allowed")
    reached = rate_map.get("limit_reached")
    if allowed is False or reached is True:
        status = AccountUsageStatus.BLOCKED
    elif allowed is True or windows:
        status = AccountUsageStatus.AVAILABLE
    else:
        status = AccountUsageStatus.UNKNOWN
    plan_raw = str(payload.get("plan_type") or "").lower()
    plan = plan_raw if plan_raw in {"plus", "pro", "free", "team", "business", "enterprise", "edu"} else None
    billing = ()
    if (balance is not None and balance >= 0) or credit_map.get("has_credits") is True or credit_map.get("unlimited") is True:
        currency = "USD" if credit_map.get("currency") == "USD" else "credits"
        billing = (BillingComponent("Extra credits", balance if balance is not None and balance >= 0 else None, currency, kind="balance",
                                    status="ACTIVE" if credit_map.get("has_credits") is True or credit_map.get("unlimited") is True else "unknown"),)
    elif balance is not None:
        balance = None
    partial = not windows or any(w.remaining_fraction is None for w in windows)
    return QuotaSnapshot(
        provider="openai",
        fetched_at_ms=fetched_at_ms,
        capabilities=ProviderCapabilities(account_quota=True, reset_windows=True),
        plan=plan,
        windows=tuple(windows),
        credit_balance=balance,
        credit_unit="credits" if balance is not None else None,
        available=True,
        usage_status=status,
        billing_components=billing,
        availability="partial" if partial else "available",
        reason="unsupported_or_partial_windows" if partial else "",
        observations={"provider": "openai", "plan": plan, "has_quota": allowed if isinstance(allowed, bool) else None,
                      "limit_reached": reached if isinstance(reached, bool) else None,
                      "parser_status": "partial" if partial else "available"},
    )


def _unavailable(reason: str, now_ms: int, *, plan: str | None = None) -> QuotaSnapshot:
    return QuotaSnapshot(
        provider="openai", fetched_at_ms=now_ms,
        capabilities=ProviderCapabilities(account_quota=True, reset_windows=True),
        plan=plan, available=False, reason=reason,
    )


def _expired(now_ms: int) -> QuotaSnapshot:
    return replace(_unavailable(EXPIRED_REASON, now_ms), observations={
        "parser_reason": "credential_expired", "user_action": "Token expired; your next prompt with this account renews it"})


class OpenAIAccountProvider:
    provider_id = "openai"
    # A usable OAuth token for quota lookup does not establish which connection
    # handled a historical model invocation (API-key traffic shares this ID).
    included_usage = False
    capabilities = ProviderCapabilities(account_quota=True, reset_windows=True)

    def __init__(
        self,
        *,
        enabled: bool = True,
        auth_json_path: str | None = None,
        credential_db_path: Path | None = None,
        home: Path | None = None,
        usage_get: UsageGet = _default_usage_get,
        now_ms: Callable[[], int] | None = None,
    ) -> None:
        self.enabled = enabled
        self.auth_json_path = _auth_path(auth_json_path, home=home)
        self.credential_db_path = credential_db_path if not auth_json_path else None
        self.usage_get = usage_get
        self.now_ms = now_ms or (lambda: int(time.time() * 1000))

    def _credential(self, now_ms: int) -> OpenAICredential:
        if self.credential_db_path is not None:
            credential = load_v2_credential(self.credential_db_path, now_ms=now_ms)
            if credential is not None:
                return credential
        return load_credential(self.auth_json_path)

    def probe(self) -> IntegrationHealth:
        if not self.enabled:
            return IntegrationHealth(True, False, "disabled in config")
        records = configured_credentials(self.auth_json_path, self.credential_db_path, ("openai", "openai-codex", "codex"))
        return IntegrationHealth(bool(records), bool(records), "configured OpenAI account" if records else "OpenAI account not configured")

    def get_quota_snapshot(self) -> QuotaSnapshot:
        now = self.now_ms()
        if not self.enabled:
            return _unavailable("disabled in config", now)
        credential = self._credential(now)
        if not credential.available:
            return _expired(now) if credential.reason == EXPIRED_REASON else _unavailable(credential.reason, now)
        return self._fetch(credential, now)

    def get_account_snapshots(self):
        if not self.enabled:
            return ()
        accounts = []
        for index, record in enumerate(configured_credentials(self.auth_json_path, self.credential_db_path, ("openai", "openai-codex", "codex"))):
            ref = replace(record.ref, provider_id="openai")
            now = self.now_ms()
            if record.value.get("type") == "api":
                quota = replace(_unavailable("Provider billing/quota source unavailable", now, plan="Pay as you go"),
                                availability="unavailable")
            else:
                credential = credential_from_auth_object({"openai": record.value})
                if credential.account_id and ref.account_id is None:
                    ref = replace(ref, account_id=credential.account_id)
                expires = _decimal(record.value.get("expires"))
                expiration_ms = expires * 1000 if expires is not None and expires < 10_000_000_000 else expires
                if expiration_ms is not None and expiration_ms <= now:
                    quota = _expired(now)
                elif credential.available:
                    quota = self._fetch(credential, now, f"openai-account-refresh-{index}")
                else:
                    quota = _unavailable(credential.reason, now)
            account = normalize_quota(quota, ref, "OpenAI")
            plan = account.plan.title() if account.plan and account.plan != "Pay as you go" else account.plan
            accounts.append(replace(account, plan=plan))
        return tuple(accounts)

    def _fetch(self, credential: OpenAICredential, now: int, component="openai-account-refresh") -> QuotaSnapshot:
        from src.runtime_errors import recoverable, recovered
        try:
            result = self._request_quota(credential, now)
        except Exception as exc:
            recoverable(exc, component)
            return replace(_unavailable("ERROR: OpenAI account refresh failed internally", now),
                           availability="error", observations={"parser_reason": "software_failure"})
        recovered(component)
        return result

    def _request_quota(self, credential: OpenAICredential, now: int) -> QuotaSnapshot:
        token = credential.access_token
        try:
            try:
                response = self.usage_get(USAGE_URL, token, credential.account_id, 15)
            except OSError:
                response = UsageResponse(False, network_error=True)
            if response.succeeded:
                snapshot = convert_usage_payload(response.payload, fetched_at_ms=now)
                return replace(snapshot, observations={**snapshot.observations, "http_status": response.status_code})
            if response.status_code in (401, 403):
                return replace(_unavailable("OpenAI sign-in was rejected; reconnect OpenAI in OpenCode.", now),
                               observations={"http_status": response.status_code, "parser_reason": "auth_failure",
                                             "user_action": "Sign-in rejected; reconnect OpenAI in OpenCode"})
            if response.network_error:
                return replace(_unavailable("OpenAI usage request failed (network)", now), availability="error",
                               observations={"http_status": 0, "parser_reason": "network_failure"})
            return replace(_unavailable("OpenAI usage request failed", now), availability="error",
                           observations={"http_status": response.status_code,
                               "parser_reason": "parser_failure" if 200 <= response.status_code < 300 else "http_failure"})
        finally:
            token = ""
            credential = OpenAICredential(False)
