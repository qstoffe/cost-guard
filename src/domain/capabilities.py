"""Provider-neutral capability declarations used at runtime boundaries."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SessionCapabilities:
    exact_input_tokens: bool = True
    exact_output_tokens: bool = True
    exact_reasoning_tokens: bool = True
    exact_cache_read_tokens: bool = True
    exact_cache_write_tokens: bool = True
    native_cost: bool = False
    child_sessions: bool = True
    compaction_events: bool = False
    live_changes: bool = False


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    account_quota: bool = False
    reset_windows: bool = False
    model_pricing: bool = False
    long_context_pricing: bool = False
