"""Source-neutral analysis records for Cost Guard.

These values intentionally sit above Session Source normalization and below
presentation.  They contain Cost Guard semantics, never native OpenCode rows.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Mapping

from src.domain import AccountRef, CostDisposition, ModelRef, TokenUsage


@dataclass(frozen=True, slots=True)
class TraceEntry:
    session_id: str
    parent_event_id: str | None
    message_id: str | None
    step_part_id: str | None
    completed_at_ms: int
    sort_order: int
    model: ModelRef
    variant: str | None
    tokens: TokenUsage
    reported_cost: Decimal = Decimal("0")
    summary: bool = False
    finish_reason: str | None = None
    error_name: str | None = None
    cost_disposition: CostDisposition = CostDisposition.UNKNOWN
    source_instance: str | None = None
    account_ref: AccountRef | None = None

    @property
    def request_input_approx(self) -> int:
        return self.tokens.input + self.tokens.cache_read + self.tokens.cache_write


@dataclass(frozen=True, slots=True)
class CostEvaluation:
    dollars: Decimal
    fallback: bool = False
    estimated: bool = False
    unresolved: bool = False
    zero_usage: bool = False


@dataclass(frozen=True, slots=True)
class PromptReference:
    session_id: str
    prompt_id: str
    prompt_time_ms: int
    prompt_number: int
    prompt_kind: str
    prompt_text: str
    model_id: str = ""
    provider_id: str = ""
    variant: str = ""


@dataclass(frozen=True, slots=True)
class PromptRecord:
    session_id: str
    prompt_id: str
    prompt_time_ms: int
    prompt_number: int
    prompt_kind: str
    prompt_text: str
    session_title: str
    main_model_id: str
    main_provider_id: str
    main_variant: str
    first_request_time_ms: int
    last_request_time_ms: int
    terminal_time_ms: int
    entries: tuple[TraceEntry, ...]
    root_entry_count: int
    cost: Decimal
    main_cost: Decimal
    subagent_cost: Decimal
    breakdown_known: bool
    has_cost_breakdown: bool
    main_estimated: bool
    subagent_estimated: bool
    fallback_requests: int
    estimated_fallback_requests: int
    unresolved_fallback_requests: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    input_context_tokens: int
    total_token_volume: int
    model_costs: Mapping[str, Decimal] = field(default_factory=dict)
    duration_ms: int = 0
    local_duration_ms: int = 0
    model_wait_ms: int = 0
    prompt_context_tokens_approx: int = 0
    previous_entry: TraceEntry | None = None
    pre_prompt_entry: TraceEntry | None = None
    previous_entry_is_compaction: bool = False
    last_root_entry: TraceEntry | None = None
    aborted: bool = False
    watch_error: bool = False
    abort_time_ms: int = 0
    in_progress: bool = False
    completed_successfully: bool = False
    # Outstanding background work keeping a running prompt active (kinds only).
    background_kinds: tuple[str, ...] = ()
    background_started_ms: int = 0
    background_only: bool = False
    abort_reason: str = ""
    ended_after_tool_calls: bool = False

    @property
    def model_calls(self) -> int:
        return len(self.entries)


@dataclass(frozen=True, slots=True)
class CompactionRecord:
    session_id: str
    user_message_id: str
    summary_message_id: str
    created_at_ms: int
    completed_at_ms: int
    automatic: bool
    model_id: str
    provider_id: str
    variant: str
    entries: tuple[TraceEntry, ...]
    cost: Decimal
    estimated_fallback_requests: int
    unresolved_fallback_requests: int
    input_context_tokens: int
    input_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    output_tokens: int
    result_context_tokens: int | None = None
    in_progress: bool = False

    @property
    def model_calls(self) -> int:
        return len(self.entries)


@dataclass(frozen=True, slots=True)
class RootAnalysisBundle:
    root_session_id: str
    source_revision: str
    trace_entries: tuple[TraceEntry, ...]
    prompts: tuple[PromptRecord, ...]
    compactions: tuple[CompactionRecord, ...]
    cacheable: bool


@dataclass(frozen=True, slots=True)
class LocalUsageSummary:
    dollars: Decimal
    requests: int
    sessions: int
    fallback_requests: int
    estimated_fallback_requests: int
    unresolved_fallback_requests: int
    deduplicated_clone_requests: int
    deduplicated_clone_dollars: Decimal
    by_model: Mapping[str, Decimal] = field(default_factory=dict)
    by_day_utc: Mapping[str, Decimal] = field(default_factory=dict)
    included_subscription_requests: int = 0
