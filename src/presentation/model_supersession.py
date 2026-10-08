"""Conservative, table-local presentation classification; never pricing truth."""
from __future__ import annotations

import re
from typing import Sequence

_VERSION = r"(\d+(?:\.\d+)*)"
_WORD = r"[a-z]+"
# Channel/lifecycle words never name a stable variant; such rows stay untouched.
_UNSTABLE = frozenset({"alpha", "beta", "deprecated", "exp", "experimental", "fast", "latest",
                       "legacy", "mode", "nightly", "preview", "test"})
_MAKERS = {"openai": "openai", "anthropic": "anthropic", "google": "google", "xai": "xai"}


def _normalized(text: str) -> str:
    text = re.sub(r"[‐-―−]", "-", text.casefold())
    return re.sub(r"\s+", " ", text).strip()


def model_version(publisher: str, name: str) -> tuple[tuple[str, ...], tuple[int, ...]] | None:
    """Only recognized manufacturers and unambiguous stable name grammars qualify.

    A variant is one plain word (Sol, Luna, Fable, Flash Lite, ...) compared only
    with the same manufacturer/family/variant. Unknown shapes, dated or
    parenthesized suffixes and channel words (preview, experimental, fast, ...)
    stay untouched. A version is an integer tuple, not a decimal or lexical string.
    """
    maker = _MAKERS.get(re.sub(r"[^a-z]", "", _normalized(publisher)))
    text = _normalized(name)
    if maker == "openai":
        match = re.fullmatch(rf"gpt-{_VERSION}(?:[ -]({_WORD}))?", text)
        family, version, variant = "gpt", match and match[1], match and (match[2] or "standard")
    elif maker == "anthropic":
        match = (re.fullmatch(rf"claude ({_WORD}) {_VERSION}", text)
                 or re.fullmatch(rf"claude {_VERSION} ({_WORD})", text))
        if match and match[1][0].isdigit():
            version, variant = match[1], match[2]
        else:
            version, variant = match and match[2], match and match[1]
        family = "claude"
    elif maker == "google":
        match = re.fullmatch(rf"gemini {_VERSION} ({_WORD}(?:[ -]{_WORD})?)", text)
        family, version, variant = "gemini", match and match[1], match and match[2].replace(" ", "-")
    elif maker == "xai":
        match = re.fullmatch(rf"grok {_VERSION}", text)
        family, version, variant = "grok", match and match[1], "standard"
    else:
        return None
    if not match or len(version) > 32 or _UNSTABLE.intersection(variant.split("-")):
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
