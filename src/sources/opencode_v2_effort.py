"""Allowlisted current catalog options, not historical execution observations."""
import hashlib
import json

from src.domain.effort import DefaultEffort

LEVELS = frozenset(("none", "minimal", "low", "medium", "high", "xhigh", "max"))
PATHS = (("reasoningEffort",), ("reasoning_effort",), ("reasoning", "effort"),
         ("effort",), ("thinkingLevel",), ("thinkingConfig", "thinkingLevel"),
         ("thinking_config", "thinking_level"), ("output_config", "effort"))
PACKAGE_PATHS = {
    "@opencode/ai/providers/openai": PATHS[:3],
    "@opencode/ai/providers/openai/responses": PATHS[:3],
    "@opencode/ai/providers/openai-compatible-responses": PATHS[:3],
    "@opencode/ai/providers/anthropic": (PATHS[3], PATHS[7]),
    "aisdk:@opencode/claude-agent": (PATHS[3],),
    "@opencode/ai/providers/google": PATHS[4:7],
    "@opencode/ai/providers/google-vertex": PATHS[4:7],
    "@opencode/ai/providers/openai-compatible": (*PATHS[:3], *PATHS[4:7]),
    "@opencode/ai/providers/xai": PATHS[:3],
    "@opencode/ai/providers/moonshotai": PATHS[:3],
}


def option_level(value, paths=PATHS):
    found = []
    for path in paths:
        item = value
        for key in path:
            item = item.get(key) if isinstance(item, dict) else None
        if item is not None:
            found.append(item.lower() if isinstance(item, str) and item.lower() in LEVELS else "unknown")
    return next(iter(set(found))) if len(set(found)) == 1 else "unknown" if found else ""


def observation(directory, selected, provider, model):
    provider, model = provider or {}, model or {}
    package = model.get("package") or provider.get("package") or ""
    upstream = model.get("modelID") or selected
    if any(not isinstance(value, str) or len(value) > 1024 or value and not value.isprintable()
           for value in (package, upstream)):
        package, upstream = "", selected
    level = ""
    # Model overrides provider; body overlays are applied after package options.
    for options in (provider.get("settings"), model.get("settings"), provider.get("body"), model.get("body")):
        configured = option_level(options)
        supported = option_level(options, PACKAGE_PATHS.get(package, ()))
        level = (supported or "unknown" if configured else "") or level
    source = "current-configuration" if level and level != "unknown" else "unknown"
    # Reviewed OpenCode package source (2026-11-13); compatible proxies do NOT
    # receive this facade's GPT-5 defaults. This is a current-package estimate.
    if not level and package in ("@opencode/ai/providers/openai", "@opencode/ai/providers/openai/responses"):
        if "gpt-5" in upstream and "gpt-5-chat" not in upstream and "gpt-5-pro" not in upstream:
            level, source = "medium", "current-package"
    signature = hashlib.sha256(json.dumps(
        [1, selected, upstream, package, level, source], ensure_ascii=True).encode()).hexdigest()
    return DefaultEffort(directory, selected, upstream, package, level, source, signature)
