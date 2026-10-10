"""Shared OpenCode native error normalization at the session-source boundary."""
from __future__ import annotations

import re
import json
from collections.abc import Mapping
from typing import Any


_CANCELLATION_IDS = frozenset({
    "abort", "aborted", "aborterror", "abortederror", "messageabortederror",
    "cancelled", "canceled", "cancellederror", "cancelederror",
    "erraborted", "errcanceled", "errcancelled", "aborterr",
})
_CANCELLATION_MESSAGE = re.compile(
    r"(?:aborted|cancelled|canceled|"
    r"(?:the )?(?:request|operation|message|prompt|session) "
    r"(?:(?:was|has been) )?(?:aborted|cancelled|canceled))"
    r"(?: by (?:the )?user)?[.!]?",
    re.IGNORECASE,
)

_ABORT_REASONS = {
    "user": {"usercancelled", "usercanceled", "abortedbyuser", "cancelledbyuser", "canceledbyuser"},
    "quota_limit": {"insufficientquota", "quotaexceeded", "quotaexceedederror", "quotalimit", "quotalimitexceeded", "usagelimitreached", "usagelimit", "usagelimiterror"},
    "tool_call_limit": {"maxtoolcalls", "maxtoolcallserror", "toolcalllimit", "toolcalllimiterror", "toolcalllimitexceeded", "maximumtoolcalls"},
    "step_limit": {"maxsteps", "maxstepsexceeded", "maxstepserror", "steplimit", "steplimitexceeded"},
    "rate_limit": {"ratelimit", "ratelimiterror", "ratelimitexceeded"},
}
_REASON_MESSAGES = {
    "user": re.compile(r"(?:the )?(?:(?:request|operation|message|prompt|session) (?:(?:was|has been) )?)?"
                       r"(?:aborted|cancelled|canceled|interrupted) by (?:the )?user[.!]?", re.I),
    "quota_limit": re.compile(r"(?:you(?:['’]ve| have) (?:hit|reached|exceeded) (?:your|the) (?:usage|quota) limit|"
                              r"you (?:have )?exceeded your (?:current )?quota|"
                              r"(?:usage limit|quota(?: limit)?) (?:reached|exceeded|exhausted)|insufficient quota)"
                              r"(?:[.!:,].*)?", re.I),
    "tool_call_limit": re.compile(r"(?:(?:maximum|max) (?:number of )?tool[ -]?calls?|tool[ -]?call limit)"
                                  r"(?: \(?\d+\)?)? (?:reached|exceeded)"
                                  r"(?:[.!:].*)?", re.I),
    "step_limit": re.compile(r"(?:(?:maximum|max) (?:number of )?steps|step limit)"
                             r"(?: \(?\d+\)?)? (?:reached|exceeded)(?:[.!:].*)?", re.I),
    "rate_limit": re.compile(r"rate limit (?:reached|exceeded)(?:[.!:].*)?", re.I),
}


def _error_fields(value: Any) -> tuple[Any, ...]:
    """Inspect error envelopes and bounded JSON API error objects, never stacks."""
    if not isinstance(value, Mapping):
        return (value,)
    fields = [value, value.get("data")]
    response = value.get("response")
    body = response.get("body") if isinstance(response, Mapping) else None
    if isinstance(body, str) and len(body) <= 16_384:
        try:
            payload = json.loads(body)
        except (ValueError, RecursionError):
            pass
        else:
            if isinstance(payload, Mapping) and isinstance(payload.get("error"), Mapping):
                fields.append(payload["error"])
    return tuple(fields)


def normalize_abort_reason(value: Any) -> str:
    """Return only explicit native stop causes; generic aborts stay unspecified."""
    fields = _error_fields(value)
    for field in fields:
        if isinstance(field, Mapping):
            for key in ("name", "type", "code", "reason"):
                identifier = field.get(key)
                if isinstance(identifier, str):
                    normalized = re.sub(r"[ _.-]", "", identifier.strip().lower())
                    for reason, identifiers in _ABORT_REASONS.items():
                        if normalized in identifiers:
                            return reason
    # Specific structured codes outrank a generic outer provider description.
    for field in fields:
        message = field.get("message") if isinstance(field, Mapping) else field
        if isinstance(message, str):
            for reason, pattern in _REASON_MESSAGES.items():
                if pattern.fullmatch(message.strip()):
                    return reason
    return ""


def normalize_error_name(value: Any) -> str | None:
    """Keep genuine failure identity; map explicit cancellation to AbortedError.

    Only known error fields and the native data envelope are inspected. Do not
    search arbitrary payloads/stacks or substring-match failure descriptions:
    e.g. a provider timeout that mentions an aborted connection is not an abort.
    """
    if value is None:
        return None
    if normalize_abort_reason(value):
        return "AbortedError"
    fields = (value, value.get("data")) if isinstance(value, Mapping) else (value,)
    for field in fields:
        if isinstance(field, Mapping):
            for key in ("name", "type", "code"):
                identifier = field.get(key)
                if isinstance(identifier, str):
                    normalized = re.sub(r"[ _.-]", "", identifier.strip().lower())
                    if normalized in _CANCELLATION_IDS:
                        return "AbortedError"
            message = field.get("message")
        else:
            message = field
        if isinstance(message, str) and (
            message.strip().lower() in _CANCELLATION_IDS
            or _CANCELLATION_MESSAGE.fullmatch(message.strip())
        ):
            return "AbortedError"
    if isinstance(value, Mapping):
        for field in fields:
            if isinstance(field, Mapping):
                for key in ("name", "type", "code"):
                    identifier = field.get(key)
                    if isinstance(identifier, str) and identifier:
                        return identifier[:120]
    return value[:120] if isinstance(value, str) else type(value).__name__
