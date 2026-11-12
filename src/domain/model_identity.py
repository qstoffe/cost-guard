"""Source-qualified mutable model estimates, separate from recorded execution."""
from dataclasses import dataclass
from functools import lru_cache
import re

_CLAUDE_ROUTES = frozenset({"claude-agent", "claude-code", "anthropic", "github-copilot",
    "amazon-bedrock", "google-vertex-anthropic", "openrouter"})
_FAMILY_ALIAS = re.compile(r"^(?:claude-)?(sonnet|opus|haiku|fable)(?:-latest)?(?:\[1m\])?$")


def desktop_catalog_candidate(value: str, provider: str) -> bool:
    """Opaque Agent selections may use the catalog; recorded releases stay fixed.

    This does not assign a family/version or price to an unknown selection.
    Only an exact location/provider/selection catalog observation can resolve it.
    """
    return provider == 'claude-agent' and not re.match(r'^claude-.+-\d', value or '', re.I)


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


def catalog_display_name(provider, label):
    """Restore branding on exact catalog labels, without inferring a release."""
    if provider == 'claude-agent' and label and re.match(r'^(Sonnet|Opus|Haiku|Fable)\b', label):
        return 'Claude ' + label
    return label
