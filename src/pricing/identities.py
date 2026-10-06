"""Bounded reference aliases, not availability or actual billing evidence.

Anthropic's models overview pins Haiku 4.5 to 20251001. Claude Code's model
configuration documents [1m] as context capacity, not another model/version.
Only explicitly reviewed versions use that mapping; other suffixes stay unknown.
https://platform.claude.com/docs/en/about-claude/models/overview
https://code.claude.com/docs/en/model-config#extended-context
"""
from __future__ import annotations

import re

CONTEXT_MODELS = frozenset({
    "claude-opus-4-6", "claude-opus-4-7", "claude-opus-4-8", "claude-opus-5", "claude-opus-5-5",
    "claude-sonnet-4-5", "claude-sonnet-4-6", "claude-sonnet-5", "claude-sonnet-5-5",
    "claude-fable-5", "claude-fable-5-1",
})
DATED_ALIASES = {"claude-haiku-4-5-20251001": "claude-haiku-4-5"}


def reference_identity(value: str) -> str:
    value = (value or "").strip().lower().split("/", 1)[-1]
    if value.endswith("[1m]") and value[:-4] in CONTEXT_MODELS:
        value = value[:-4]
    value = DATED_ALIASES.get(value, value)
    # Existing catalog display punctuation equivalence, never substring matching.
    return re.sub(r"[^a-z0-9]+", "", value)
