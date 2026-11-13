"""Reviewed, exact-route vendor estimates. No fuzzy names, pricing tiers or I/O."""
from src.domain.effort import EffortEvidence, bounded_evidence

REVISION = "vendor-defaults-1-2026-11-13"
SOURCES = {
    "anthropic": "https://platform.claude.com/docs/en/build-with-claude/effort",
    "openai": "https://developers.openai.com/api/docs/guides/reasoning",
    "google": "https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/thinking",
    "xai": "https://docs.x.ai/developers/model-capabilities/text/reasoning",
    "moonshotai": "https://github.com/MoonshotAI/Kimi-K3",
}
# All 31 baseline roster entries are represented, including the three unknowns
# and three conditional entries. Conditional defaults require package evidence.
DEFAULTS = {
    "openai": {
        "gpt-5.3-codex": "", "gpt-5.4-nano": "none",
        "gpt-5.6-luna": "medium", "gpt-5.6-sol": "medium", "gpt-5.6-terra": "medium",
        "gpt-6-astra": "", "gpt-6-luna": "medium", "gpt-6-sol": "medium",
        "gpt-6.1-sol": "medium", "gpt-6.1-terra": "medium",
    },
    "anthropic": {
        "claude-haiku-4-5": "", "claude-haiku-5-5": "medium", "claude-sonnet-4": "",
        "claude-sonnet-4-6": "high", "claude-opus-4-8": "high", "claude-opus-5": "high",
        "claude-opus-5-5": "medium", "claude-sonnet-5": "high", "claude-sonnet-5-5": "high",
        "claude-opus-4-8-fast": "", "claude-fable-5": "high", "claude-fable-5-1": "high",
        "claude-fable-5-2": "high",
    },
    "google": {"gemini-3.8-flash": "medium", "gemini-4-argon": "medium", "gemini-4-carbon": "medium"},
    "microsoft": {"mai-code-1.1-flash": ""},
    "xai": {"grok-4.5": "high", "grok-4.6": "high", "grok-4.7": "high"},
    "moonshotai": {"kimi-k3": "max"},
}
PACKAGES = {
    "openai": ("@opencode/ai/providers/openai", "@opencode/ai/providers/openai/responses",
               "@opencode/ai/providers/openai-compatible-responses"),
    "anthropic": ("@opencode/ai/providers/anthropic", "aisdk:@opencode/claude-agent"),
    "google": ("@opencode/ai/providers/google", "@opencode/ai/providers/google-vertex",
               "@opencode/ai/providers/openai-compatible"),
    "xai": ("@opencode/ai/providers/xai", "@opencode/ai/providers/openai-compatible-responses"),
    "moonshotai": ("@opencode/ai/providers/moonshotai", "@opencode/ai/providers/openai-compatible"),
}


def documented_default(model):
    observed = model.effort_default
    identity = observed.model_id if observed else model.model
    if model.provider == "claude-agent" and model.resolution and model.display_name:
        identity = {
            "Opus 5.5": "claude-opus-5-5", "Haiku 5.5": "claude-haiku-5-5",
            "Sonnet 5.5": "claude-sonnet-5-5", "Fable 5.1": "claude-fable-5-1",
        }.get(model.display_name, identity)
    # Claude's API uses hyphens; Copilot uses dots. Only these exact IDs qualify.
    candidates = (identity, identity.replace(".", "-")) if identity.startswith("claude-") else (identity,)
    for vendor, models in DEFAULTS.items():
        route = model.provider == vendor or model.provider == "claude-agent" and vendor == "anthropic"
        if model.provider == "github-copilot":
            route = observed is not None and observed.package in PACKAGES.get(vendor, ())
        if route and (observed is None or observed.package in PACKAGES.get(vendor, ())):
            for candidate in candidates:
                if models.get(candidate):
                    return models[candidate]
    return ""


def request_effort(entry):
    selected = entry.selected_effort
    if selected is None:
        selected = entry.variant if entry.variant is not None else ("" if not entry.summary else None)
    if selected is None:
        return EffortEvidence(None)
    if selected and selected.lower() != "default":
        return EffortEvidence(selected)
    actual = (entry.variant or "").lower()
    if actual and actual != "default":
        return EffortEvidence(selected, actual, "request", "recorded-variant")
    observed = entry.model.effort_default
    if observed and observed.level:
        return EffortEvidence(selected, observed.level, observed.source, observed.signature)
    level = documented_default(entry.model)
    return EffortEvidence(selected, level or "unknown", "documentation" if level else "unknown", REVISION)


def effort_evidence(entries):
    return bounded_evidence(request_effort(entry) for entry in entries)
