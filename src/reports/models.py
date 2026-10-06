"""Provider/source-neutral report projections.

These types are the handoff between one-shot report orchestration and terminal
presentation. They contain already-derived display semantics and never expose
native OpenCode/provider payloads.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Mapping

from src.analysis.quota_pace import QuotaPace
from src.analysis.context import PriceWarningSeverity
from src.analysis.valuation import ComparisonCost
from src.analysis.token_mix import TokenMix
from src.domain import AccountSnapshot


class ReportKind(str, Enum):
    NORMAL = "normal"
    ALL_MODELS = "all-models"
    SESSIONS = "sessions"
    SESSION = "session"
    DATE = "date"
    TOKEN_MIX = "token-mix"


@dataclass(frozen=True, slots=True)
class PromptProjection:
    at_ms: int
    prompt_number: int
    label: str
    preview: str
    model_effort: str
    ccost: Decimal
    cost_estimated: bool
    unresolved_cost: bool
    calls: int
    incoming_context_tokens: int | None
    incoming_context_ccost: Decimal | None
    extra_ccost: Decimal | None
    token_mix_percent: tuple[int, int, int, int] | None
    in_progress: bool = False
    aborted: bool = False
    is_compaction: bool = False
    delta_context_tokens: int | None = None
    next_context_tokens: int | None = None
    next_context_cached_ccost: Decimal | None = None
    next_context_fresh_ccost: Decimal | None = None
    next_context_warning: str = ""
    event_id: str = ""
    duration_ms: int | None = None
    watch_error: bool = False
    main_ccost: Decimal = Decimal(0)
    subagent_ccost: Decimal = Decimal(0)
    breakdown_known: bool = False
    has_cost_breakdown: bool = False
    main_estimated: bool = False
    subagent_estimated: bool = False
    has_additional_model: bool = False
    abort_at_ms: int = 0
    running_cost_warning: bool = False
    ictx_price_threshold: bool = False
    watch_model_effort: str = ""
    watch_delta_context_tokens: int | None = None
    watch_next_context_tokens: int | None = None
    watch_next_context_cached_ccost: Decimal | None = None
    watch_next_context_fresh_ccost: Decimal | None = None
    watch_next_context_warning: str = ""
    # Reference CCost and actual billed money remain independent projections.
    comparison_cost: ComparisonCost | None = None
    billed_cost: Decimal | None = None
    completed_successfully: bool = False
    next_context_warning_severity: PriceWarningSeverity = PriceWarningSeverity.NONE
    watch_next_context_warning_severity: PriceWarningSeverity = PriceWarningSeverity.NONE
    # Outstanding background work of a running prompt; never usage or cost.
    background_kinds: tuple[str, ...] = ()
    background_started_ms: int = 0
    background_only: bool = False


@dataclass(frozen=True, slots=True)
class SessionPromptBlock:
    session_id: str
    title: str
    rows: tuple[PromptProjection, ...]
    total_ccost: Decimal
    total_calls: int
    total_ictx_cost_text: str = ""
    total_extra_cost_text: str = ""
    total_mix_text: str = ""
    current_context_tokens: int | None = None
    current_context_sources: Mapping[str, int] = field(default_factory=dict)
    next_context_tokens: int | None = None
    next_context_cached_ccost: Decimal | None = None
    next_context_fresh_ccost: Decimal | None = None
    next_context_warning: str = ""
    event_id: str = ""
    duration_ms: int | None = None
    watch_error: bool = False
    total_main_ccost: Decimal = Decimal(0)
    total_subagent_ccost: Decimal = Decimal(0)
    total_breakdown_known: bool = False
    total_has_cost_breakdown: bool = False
    total_main_estimated: bool = False
    total_subagent_estimated: bool = False
    comparison_cost_complete: bool = True
    billed_cost: Decimal | None = None
    next_context_warning_severity: PriceWarningSeverity = PriceWarningSeverity.NONE


@dataclass(frozen=True, slots=True)
class SessionUsageRow:
    session_id: str
    title: str
    model: str
    multiple_models: bool
    ccost: Decimal
    prompt_count: int
    complete: bool = True


@dataclass(frozen=True, slots=True)
class ModelComparisonProjection:
    publisher: str
    model: str
    relative_cost: Decimal | None
    price_summary: str
    release_date: str | None
    promotional: bool = False
    recent: bool = False
    promotion_marker: int | None = None


@dataclass(frozen=True, slots=True)
class ModelTokenMixProjection:
    model: str
    prompts: int
    calls: int
    mix: TokenMix


@dataclass(frozen=True, slots=True)
class AccountProjection:
    account: AccountSnapshot
    label: str
    ccost_scopes: tuple[tuple[str, ComparisonCost | None], ...] = ()
    billed_today: Decimal | None = None
    billed_month: Decimal | None = None
    pace: tuple[QuotaPace, ...] = ()


@dataclass(frozen=True, slots=True)
class AccountsQuotasProjection:
    comparison_today: ComparisonCost
    comparison_month: ComparisonCost
    accounts: tuple[AccountProjection, ...] = ()
    billed_today: Decimal | None = None
    billed_month: Decimal | None = None
    today_prompt_count: int = 0
    today_session_count: int = 0
    today_request_count: int = 0
    included_subscription_requests: int = 0
    now_ms: int = 0


@dataclass(frozen=True, slots=True)
class ReportProjection:
    kind: ReportKind
    title: str
    source_label: str
    source_warnings: tuple[str, ...] = ()
    model_comparison: tuple[ModelComparisonProjection, ...] = ()
    model_comparison_sample_size: int = 0  # completed prompts behind Rel CCost; 0 leaves it blank
    pricing_retrieved_at_ms: int = 0
    model_comparison_promotion_notes: tuple[str, ...] = ()
    session_usage: tuple[SessionUsageRow, ...] = ()
    prompt_blocks: tuple[SessionPromptBlock, ...] = ()
    accounts_quotas: AccountsQuotasProjection | None = None
    notes: tuple[str, ...] = ()
    recent_model_notice: str = ""
    pricing_diagnostics: Mapping[str, object] = field(default_factory=dict)
    token_mix: TokenMix = field(default_factory=TokenMix)
    model_token_mix: tuple[ModelTokenMixProjection, ...] = ()
