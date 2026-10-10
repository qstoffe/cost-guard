"""Shared V1/V2 OpenCode token-counter normalization and field availability."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.domain import TokenUsage
from .errors import SourceDataError


def token_usage(value: Any, *, context: str, source: str) -> TokenUsage | None:
    if not isinstance(value, Mapping):
        return None
    cache = value.get("cache")
    cache = cache if isinstance(cache, Mapping) else {}
    raw = {"input": value.get("input"), "cache_read": cache.get("read"),
           "cache_write": cache.get("write"), "output": value.get("output"),
           "reasoning": value.get("reasoning")}
    fields = {}
    for key, number in raw.items():
        try:
            fields[key] = int(number)
        except (TypeError, ValueError, OverflowError):
            fields[key] = 0
    if any(number < 0 for number in fields.values()):
        raise SourceDataError(f"{source} {context} contains negative token counts")
    known = tuple(key for key, number in raw.items() if key != "reasoning"
                  and isinstance(number, int) and not isinstance(number, bool) and number >= 0)
    return TokenUsage(**fields, known_fields=known)
