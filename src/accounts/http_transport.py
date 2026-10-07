"""Bounded Bearer GET transport for maintained account endpoints only.

No ambient proxies, redirects, cookies, bodies or credential persistence. Wire
payloads and exception text never become diagnostics or user-visible reasons.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import http.client
import json
import re
import time
from urllib.parse import urlsplit

MAX_BODY_BYTES = 131_072
MAX_JSON_DEPTH = 16
MAX_JSON_NODES = 4096
TIMEOUT_SECONDS = 8


@dataclass(frozen=True, slots=True)
class MaintainedEndpoint:
    url: str

    def __post_init__(self):
        parts = urlsplit(self.url)
        if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password
                or parts.port not in (None, 443) or parts.query or parts.fragment
                or not re.fullmatch(r"[a-z0-9.-]+", parts.hostname)
                or not re.fullmatch(r"/[a-zA-Z0-9_./-]+", parts.path)):
            raise ValueError("Account endpoint must be a fixed HTTPS URL")


@dataclass(frozen=True, slots=True)
class AccountHttpResponse:
    payload: object | None = field(default=None, repr=False)
    http_status: int = 0
    classification: str = ""


def finite_number(value: object) -> Decimal | None:
    """Decimal-compatible provider numbers, never bool/null/NaN or coercion to 0."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        return None
    text = str(value)
    if len(text) > 64 or not re.fullmatch(r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d{1,3})?", text):
        return None
    try:
        result = Decimal(text)
    except (ValueError, InvalidOperation):
        return None
    return result if result.is_finite() and 0 <= result <= Decimal("1e18") else None


def validate_json_tree(payload: object) -> None:
    pending = [(payload, 0)]
    count = 0
    while pending:
        value, depth = pending.pop()
        count += 1
        if count > MAX_JSON_NODES or depth > MAX_JSON_DEPTH:
            raise ValueError("JSON bounds exceeded")
        if isinstance(value, dict):
            pending.extend((item, depth + 1) for item in value.values())
        elif isinstance(value, list):
            pending.extend((item, depth + 1) for item in value)
        elif value is not None and not isinstance(value, (str, bool, int, float, Decimal)):
            raise ValueError("Invalid JSON value")


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def decode_json(body: bytes) -> object:
    if len(body) > MAX_BODY_BYTES:
        raise ValueError("Response too large")
    text = body.decode("utf-8")
    # Reject excessive nesting BEFORE the recursive JSON decoder allocates it.
    quoted = escaped = False
    depth = 0
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > MAX_JSON_DEPTH:
                raise ValueError("JSON too deep")
        elif char in "]}":
            depth -= 1

    def reject_constant(_value):
        raise ValueError("Non-finite JSON number")

    payload = json.loads(text, parse_float=Decimal, parse_int=Decimal,
                         parse_constant=reject_constant, object_pairs_hook=_pairs)
    validate_json_tree(payload)
    return payload


def bearer_key(value: object) -> str | None:
    if not isinstance(value, Mapping):
        return None
    if value.get("type") != "api":
        return None
    key = value.get("key")
    if not isinstance(key, str) or not 1 <= len(key) <= 8192:
        return None
    return key if all(33 <= ord(char) <= 126 for char in key) else None


def get_account_json(endpoint: MaintainedEndpoint, key: str) -> AccountHttpResponse:
    """One request with a total body-read deadline; never retry or follow a 3xx."""
    if not bearer_key({"type": "api", "key": key}):
        return AccountHttpResponse(classification="credential_invalid")
    parts = urlsplit(endpoint.url)
    conn = http.client.HTTPSConnection(parts.hostname, timeout=TIMEOUT_SECONDS)
    status = 0
    deadline = time.monotonic() + TIMEOUT_SECONDS
    try:
        conn.request("GET", parts.path, headers={"Authorization": "Bearer " + key,
                                                "Accept": "application/json"})
        wire_socket = conn.sock
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError
        if wire_socket is not None:
            wire_socket.settimeout(remaining)
        response = conn.getresponse()
        status = response.status
        if not 200 <= status < 300:
            cause = "auth_failure" if status in (401, 403) else "redirect_rejected" if 300 <= status < 400 else "http_failure"
            return AccountHttpResponse(http_status=status, classification=cause)
        content_type = response.getheader("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json" and not (content_type.startswith("application/") and content_type.endswith("+json")):
            return AccountHttpResponse(http_status=status, classification="non_json")
        if response.getheader("Content-Encoding", "identity").lower() != "identity":
            return AccountHttpResponse(http_status=status, classification="encoding_rejected")
        length = response.getheader("Content-Length")
        if length is not None and (not length.isdigit() or len(length) > 9 or int(length) > MAX_BODY_BYTES):
            return AccountHttpResponse(http_status=status, classification="body_too_large")
        body = bytearray()
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            if wire_socket is not None:
                wire_socket.settimeout(remaining)
            chunk = response.read1(min(8192, MAX_BODY_BYTES + 1 - len(body)))
            if not chunk:
                break
            body.extend(chunk)
            if len(body) > MAX_BODY_BYTES:
                return AccountHttpResponse(http_status=status, classification="body_too_large")
        try:
            payload = decode_json(bytes(body))
        except (ValueError, UnicodeError, RecursionError, InvalidOperation):
            return AccountHttpResponse(http_status=status, classification="parser_failure")
        return AccountHttpResponse(payload, status)
    except TimeoutError:
        return AccountHttpResponse(http_status=status, classification="timeout")
    except (OSError, http.client.HTTPException, ValueError):
        return AccountHttpResponse(http_status=status, classification="network_failure")
    finally:
        conn.close()
