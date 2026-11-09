"""Bounded reference aliases, not availability or actual billing evidence.

Anthropic's models overview pins Haiku 4.5 to 20251001. Claude Code's model
configuration documents [1m] as context capacity, not another model/version.
Only explicitly reviewed versions use that mapping; other suffixes stay unknown.
https://platform.claude.com/docs/en/about-claude/models/overview
https://code.claude.com/docs/en/model-config#extended-context
"""
from __future__ import annotations

from functools import lru_cache
import re

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
CONTEXT_MODELS = frozenset({
    "claude-opus-4-6", "claude-opus-4-7", "claude-opus-4-8", "claude-opus-5", "claude-opus-5-5",
    "claude-sonnet-4-5", "claude-sonnet-4-6", "claude-sonnet-5", "claude-sonnet-5-5",
    "claude-fable-5", "claude-fable-5-1",
})
DATED_ALIASES = {"claude-haiku-4-5-20251001": "claude-haiku-4-5"}

# Per-entry semantic admission, not a global pricing/cache generation. Old
# unaffected entries remain reusable; alias-derived conclusions rebuild lazily.
MODEL_IDENTITY_SEMANTICS = 1
_CLAUDE_ROUTES = frozenset({"claude-agent", "claude-code", "anthropic", "github-copilot",
    "amazon-bedrock", "google-vertex-anthropic", "openrouter"})
_FAMILY_ALIAS = re.compile(r"^(?:claude-)?(sonnet|opus|haiku|fable)(?:-latest)?(?:\[1m\])?$")


@lru_cache(maxsize=8192)
def unverified_alias(value: str, provider: str = "") -> str | None:
    """Moving selections are never concrete execution or reference-rate proof.

    A familiar word on an unknown/custom route does not prove its publisher.
    Neither today's provider catalog nor SDK default can resolve past requests.
    """
    raw = (value or "").strip().lower()
    if "/" in raw:
        provider, raw = raw.split("/", 1)
    route = provider.strip().lower()
    match = _FAMILY_ALIAS.fullmatch(raw)
    if match:
        family = match[1].title()
        name = f"Claude {family}" if raw.startswith("claude-") or route in _CLAUDE_ROUTES else raw
        return f"{name} (version unverified)"
    if route in _CLAUDE_ROUTES and raw in {"default", "best", "opusplan"}:
        return f"Claude {raw} (version unverified)"
    return None


def identity_cache_current(semantics, models) -> bool:
    """Admit legacy derived entries only when no moving selection influenced them.

    ``models`` contains original (provider, model) pairs, never display labels.
    Source snapshots themselves do not need invalidation or rewriting.
    """
    if semantics == MODEL_IDENTITY_SEMANTICS:
        return True
    for provider, model in models:
        if not isinstance(provider, str) or not isinstance(model, str) or unverified_alias(model, provider):
            return False
    return True


@lru_cache(maxsize=8192)
def reference_identity(value: str) -> str:
    value = (value or "").strip().lower().split("/", 1)[-1]
    if value.endswith("[1m]") and value[:-4] in CONTEXT_MODELS:
        value = value[:-4]
    value = DATED_ALIASES.get(value, value)
    # Existing catalog display punctuation equivalence, never substring matching.
    return _NON_ALNUM.sub("", value)
