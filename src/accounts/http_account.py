"""Shared per-CredentialRecord acquisition behind the Account Provider protocol."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import time

from src.domain import AccountSnapshot, IntegrationHealth, ProviderCapabilities
from .credentials import configured_credentials, resolve_auth_path
from .http_transport import bearer_key, get_account_json, validate_json_tree


class HttpAccountProvider:
    included_usage = False  # A current key never proves historical attribution.
    capabilities = ProviderCapabilities(account_quota=True, reset_windows=True)

    def __init__(self, *, enabled=True, auth_json_path=None, credential_db_path: Path | None = None,
                 home: Path | None = None, http_get=None, clock_ms=None):
        self.enabled = enabled
        self.auth_json_path = resolve_auth_path(auth_json_path, home=home)
        self.credential_db_path = credential_db_path if not auth_json_path else None
        self.http_get = http_get or get_account_json
        self.clock_ms = clock_ms or (lambda: time.time_ns() // 1_000_000)

    def records(self):
        return configured_credentials(self.auth_json_path, self.credential_db_path, self.integration_ids) if self.enabled else ()

    def diagnostic_inventory(self):
        records = self.records()
        return {"provider": self.provider_id, "enabled": self.enabled, "configured_records": len(records),
                "api_records": sum(r.value.get("type") == "api" for r in records),
                "oauth_records": sum(r.value.get("type") == "oauth" for r in records),
                "qualifying_records": sum(bearer_key(r.value) is not None and self.endpoint_for(r) is not None for r in records)}

    def probe(self):
        detected = bool(self.records())
        return IntegrationHealth(detected, detected, "configured account" if detected else "account not configured")

    def unsupported_credential_reason(self, record):
        return "Supported API-key credential required"

    def get_account_snapshots(self):
        accounts = []
        for record in self.records():
            now = self.clock_ms()
            category = "api" if record.value.get("type") == "api" else "oauth"
            key = bearer_key(record.value)
            endpoint = self.endpoint_for(record)
            evidence = {"provider": self.provider_id, "credential_category": category,
                        "credential_discovered": True, "credential_active": record.active,
                        "credential_qualifying": key is not None and endpoint is not None,
                        "request_attempted": False}
            account = AccountSnapshot(record.ref, now, self.display_label)
            if key is None or endpoint is None:
                accounts.append(replace(account, availability="unavailable", reason=self.unsupported_credential_reason(record),
                                        observations={**evidence, "parser_reason": "credential_unsupported", "parser_status": "unavailable"}))
                continue
            evidence["request_attempted"] = True
            try:
                response = self.http_get(endpoint, key)
                evidence["http_status"] = response.http_status
                if response.classification:
                    auth = response.classification in {"auth_failure", "credential_invalid"}
                    accounts.append(replace(account, availability="unavailable" if auth else "error",
                        reason="Provider rejected the credential; reconnect this account in OpenCode." if auth else "Account request failed",
                        observations={**evidence, "parser_reason": response.classification,
                                      "parser_status": "unavailable" if auth else "error",
                                      **({"user_action": "Reconnect this account in OpenCode"} if auth else {})}))
                    continue
                validate_json_tree(response.payload)
                normalized = self.normalize_response(account, response.payload)
                accounts.append(replace(normalized, observations={**evidence, **normalized.observations}))
            except Exception:
                # Never persist exception strings; injected/changed parsers may include keys/payloads.
                accounts.append(replace(account, availability="error", reason="Account response could not be normalized",
                                        observations={**evidence, "parser_reason": "parser_failure", "parser_status": "error"}))
        return tuple(accounts)
