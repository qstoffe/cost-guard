"""Shared OpenCode native error normalization at the session-source boundary."""
from __future__ import annotations

import re
from typing import Any, Mapping


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


def normalize_error_name(value: Any) -> str | None:
    """Keep genuine failure identity; map explicit cancellation to AbortedError.

    Only known error fields and the native data envelope are inspected. Do not
    search arbitrary payloads/stacks or substring-match failure descriptions:
    e.g. a provider timeout that mentions an aborted connection is not an abort.
    """
    if value is None:
        return None
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
