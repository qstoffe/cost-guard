"""Source-qualified mutable model estimates, separate from recorded execution."""
from dataclasses import dataclass
from functools import lru_cache
import re

_CLAUDE_ROUTES = frozenset({"claude-agent", "claude-code", "anthropic", "github-copilot",
    "amazon-bedrock", "google-vertex-anthropic", "openrouter"})
_FAMILY_ALIAS = re.compile(r"^(?:claude-)?(sonnet|opus|haiku|fable)(?:-latest)?(?:\[1m\])?$")


@lru_cache(maxsize=8192)
def unverified_alias(value: str, provider: str = "") -> str | None:
    """Recognize moving selections without asserting a release or publisher."""
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


@dataclass(frozen=True, slots=True)
class ModelResolution:
    selected_model: str
    scope: str
    signature: str
    kind: str = "desktop-catalog-estimate"


CATALOG_ESTIMATE_HELP = ("Model and reference cost based on current OpenCode catalog; "
                         "historic executed version unconfirmed.")
