"""Claude-owned account discovery, separate from experimental plan quotas."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
from typing import Callable, Mapping
import time

from src.domain import AccountRef, AccountSnapshot, AccountUsageStatus, IntegrationHealth, ProviderCapabilities, QuotaComponent
from .claude_transport import ClaudeUsageResult, read_claude_auth, read_claude_usage
from src.runtime_errors import recoverable, recovered

# The Claude CLI renews its own login; only an explicit sign-in needs the user.
SIGNED_OUT_REASON = "Claude CLI is signed out; run 'claude auth login' to restore quotas."
REJECTED_REASON = "Claude sign-in was rejected; run 'claude auth login' to restore quotas."


def _plan(value: object) -> str | None:
    return {"pro": "Pro", "max": "Max", "team": "Team", "enterprise": "Enterprise"}.get(
        str(value).lower().removeprefix("claude "))


def _identity(email: object, organization: object) -> str | None:
    if not isinstance(email, str) or not email.strip():
        return None
    return hashlib.sha256((email.strip().lower() + "\0" + str(organization or "")).encode()).hexdigest()


def _reset(value: object) -> int | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return int(parsed.timestamp() * 1000) if parsed.tzinfo is not None else None
    except (ValueError, OverflowError, OSError):
        return None


def _window(label: str, value: Mapping, seconds: int, scope: str) -> QuotaComponent:
    try:
        used = Decimal(str(value.get("utilization")))
        if isinstance(value.get("utilization"), bool) or not used.is_finite() or not 0 <= used <= 100:
            used = None
    except InvalidOperation:
        used = None
    # An unused rolling window has no reset time until its first request; that
    # explicit zero/null pair is a complete idle observation, not missing data.
    idle = used == 0 and value.get("resets_at", ...) is None
    return QuotaComponent(label, "rolling", remaining_fraction=1 - used / 100 if used is not None else None,
        duration_seconds=seconds, reset_at_ms=_reset(value.get("resets_at")), scope=scope,
        status=AccountUsageStatus.BLOCKED if used == 100 else AccountUsageStatus.UNKNOWN,
        window_active=False if idle else None)


def normalize_claude_usage(account: AccountSnapshot, payload: Mapping[str, object]) -> AccountSnapshot:
    """SDK percentage/ISO windows become native quotas, never dollar estimates."""
    rates = payload.get("rate_limits")
    available = payload.get("rate_limits_available")
    if available is False:
        return replace(account, quotas=(), availability="unavailable", reason="Claude subscription quotas unavailable",
                       observations={**account.observations, "parser_reason": "quota_unavailable"})
    if available is not True or not isinstance(rates, Mapping):
        return replace(account, quotas=(), availability="error", reason="Experimental Claude quota format unavailable",
                       observations={**account.observations, "parser_reason": "format_changed"})
    components = []
    for key, label, seconds, scope in (
        ("five_hour", "5-hour", 18_000, "account"), ("seven_day", "weekly", 604_800, "account"),
        ("seven_day_sonnet", "Sonnet weekly", 604_800, "model"), ("seven_day_opus", "Opus weekly", 604_800, "model"),
        ("seven_day_oauth_apps", "OAuth apps weekly", 604_800, "surface"),
    ):
        if isinstance(rates.get(key), Mapping):
            components.append(_window(label, rates[key], seconds, scope))
    scoped = rates.get("model_scoped")
    if isinstance(scoped, list):
        for value in scoped:
            if isinstance(value, Mapping) and isinstance(value.get("display_name"), str):
                label = value["display_name"]
                if label and len(label) <= 80 and all(c.isprintable() for c in label):
                    components.append(_window(label + " weekly", value, 604_800, "model"))
    partial = not {"5-hour", "weekly"}.issubset({c.label for c in components}) or any(
        c.remaining_fraction is None or (c.reset_at_ms is None and c.window_active is not False) for c in components)
    return replace(account, plan=_plan(payload.get("subscription_type")) or account.plan,
        quotas=tuple(components), availability="partial" if partial else "available",
        reason="Partial Claude quota observations" if partial else "",
        status=AccountUsageStatus.BLOCKED if any(c.status is AccountUsageStatus.BLOCKED and c.scope == "account"
                                               for c in components) else account.status)


class ClaudeCodeAccountProvider:
    provider_id = "claude-code"
    included_usage = False  # Current login never supplies historical billing evidence.
    capabilities = ProviderCapabilities(account_quota=True, reset_windows=True)

    def __init__(self, *, enabled: bool = True, auth_reader: Callable = read_claude_auth,
                 usage_reader: Callable = read_claude_usage, now_ms: Callable | None = None):
        self.enabled, self.auth_reader, self.usage_reader = enabled, auth_reader, usage_reader
        self.now_ms = now_ms or (lambda: int(time.time() * 1000))
        self._last: AccountSnapshot | None = None
        self._pending: AccountSnapshot | None = None
        self._pending_loaded = False
        self._quota_identity: str | None = None

    def _discover(self) -> AccountSnapshot | None:
        self._quota_identity = None
        if not self.enabled:
            return None
        try:
            metadata = self.auth_reader()
        except (OSError, ValueError):
            return replace(self._last, quotas=(), availability="error", reason="Claude account metadata unavailable",
                           observations={**self._last.observations, "auth_status": "unknown",
                                         "parser_reason": "discovery_failure"}) if self._last else None
        # Transport's expected failures are handled above, not around internal
        # identity/normalization code (where even ValueError is a software fault).
        if not isinstance(metadata, Mapping) or metadata.get("loggedIn") is not True:
            return replace(self._last, quotas=(), availability="unavailable", reason=SIGNED_OUT_REASON,
                           observations={"parser_reason": "auth_failure",
                                         "user_action": "Signed out; run 'claude auth login'"}) if self._last else None
        backend = metadata.get("apiProvider")
        subscription = backend == "firstParty" and metadata.get("authMethod") == "claude.ai"
        identity = _identity(metadata.get("email"), metadata.get("orgId"))
        # Compare organization NAME to name, never auth status.orgId to name.
        self._quota_identity = _identity(metadata.get("email"), metadata.get("orgName"))
        locator = hashlib.sha256(str(metadata.get("configDirectory", "default")).encode()).hexdigest()
        ref = AccountRef("claude-cli:" + locator, "claude-code", account_id=identity, source_account="current-login")
        api = backend == "firstParty" and metadata.get("authMethod") in {"api_key", "api-key", "api"}
        return AccountSnapshot(ref, self.now_ms(), "Claude Code",
            plan=_plan(metadata.get("subscriptionType")) if subscription else ("API pay as you go" if api else None),
            availability="unavailable", reason="Claude subscription quotas unavailable",
            observations={"auth_status": "authenticated", "backend_status": "first_party" if backend == "firstParty" else "external",
                          "account_kind": "subscription" if subscription else "api_or_external"})

    def probe(self):
        self._pending = self._discover()
        self._pending_loaded = True
        detected = self._pending is not None
        return IntegrationHealth(detected, detected, "Claude CLI account" if detected else "Claude CLI account not detected")

    def get_account_snapshots(self):
        if not self.enabled:
            return ()
        account = self._pending if self._pending_loaded else self._discover()
        self._pending = None
        self._pending_loaded = False
        if account is None:
            return ()
        if account.observations.get("account_kind") == "subscription" and account.observations.get("auth_status") == "authenticated":
            try:
                result = self._usage_result()
                if result.availability != "available" and result.reason == "auth_failure":
                    account = replace(account, availability="unavailable", reason=REJECTED_REASON,
                                      observations={**account.observations, "parser_reason": result.reason,
                                                    "user_action": "Sign-in rejected; run 'claude auth login'"})
                elif result.availability != "available":
                    account = replace(account, availability=result.availability,
                                      reason="ERROR: Claude metadata reader failed internally" if result.reason == "software_failure" else "Experimental Claude quota source unavailable",
                                      observations={**account.observations, "parser_reason": result.reason})
                elif (result.account.get("apiProvider") != "firstParty" or self._quota_identity is None
                      or self._quota_identity != _identity(result.account.get("email"), result.account.get("organization"))):
                    account = replace(account, reason="Claude quota account provenance unavailable",
                                      observations={**account.observations, "parser_reason": "account_mismatch"})
                elif isinstance(result.usage, Mapping):
                    account = normalize_claude_usage(account, result.usage)
                else:
                    account = replace(account, availability="error", reason="Experimental Claude quota format unavailable",
                                      observations={**account.observations, "parser_reason": "format_changed"})
                recovered("claude-quota")
            except Exception as exc:
                recoverable(exc, "claude-quota")
                account = replace(account, quotas=(), availability="error", reason="ERROR: Claude quota refresh failed internally",
                                  observations={**account.observations, "parser_reason": "software_failure"})
        self._last = account
        return (account,)

    def _usage_result(self):
        try:
            return self.usage_reader()
        except (OSError, ValueError):
            # Expected metadata/transport contract only, not normalization code.
            return ClaudeUsageResult(availability="error", reason="transport_failure")
