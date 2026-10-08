"""Conservative, table-local presentation classification; never pricing truth."""
from __future__ import annotations

import re
from typing import Sequence


def model_version(publisher: str, name: str) -> tuple[tuple[str, ...], tuple[int, ...]] | None:
    """Only recognized manufacturers and unambiguous stable name grammars qualify.

    Unknown suffixes (including dated previews, experimental and fast modes) stay
    untouched. A version is an integer tuple, not a decimal or lexical string.
    """
    maker = publisher.casefold().strip()
    text = name.casefold().strip()
    if maker == "openai":
        match = re.fullmatch(r"gpt-(\d+(?:\.\d+)*)(?: (sol|codex|mini|nano|pro|turbo))?", text)
        if not match:
            return None
        family, version, variant = "gpt", match[1], match[2] or "standard"
    elif maker == "anthropic":
        match = re.fullmatch(r"claude (opus|sonnet|haiku) (\d+(?:\.\d+)*)", text)
        if not match:
            return None
        family, version, variant = "claude", match[2], match[1]
    elif maker == "google":
        match = re.fullmatch(r"gemini (\d+(?:\.\d+)*) (flash|pro|flash-lite|flash lite)", text)
        if not match:
            return None
        family, version, variant = "gemini", match[1], match[2]
    elif maker == "xai":
        match = re.fullmatch(r"grok (\d+(?:\.\d+)*)", text)
        if not match:
            return None
        family, version, variant = "grok", match[1], "standard"
    else:
        return None
    if len(version) > 32:
        return None
    numbers = tuple(int(part) for part in version.split("."))
    while len(numbers) > 1 and numbers[-1] == 0:
        numbers = numbers[:-1]
    return (maker, family, variant), numbers


def superseded_rows(models: Sequence[tuple[str, str]]) -> tuple[int, ...]:
    identities = [model_version(publisher, name) for publisher, name in models]
    latest: dict[tuple[str, ...], tuple[int, ...]] = {}
    for item in identities:
        if item is not None:
            family, version = item
            latest[family] = max(latest.get(family, version), version)
    return tuple(index for index, item in enumerate(identities)
                 if item is not None and item[1] < latest[item[0]])
