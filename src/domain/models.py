"""Canonical Cost Guard domain values.

Concrete OpenCode/provider formats must be normalized into these values before
ordinary analysis sees them.  The model intentionally keeps usage, valuation
and account quota as separate semantic dimensions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Mapping, TYPE_CHECKING

if TYPE_CHECKING:
    from .accounts import AccountRef, BillingComponent

from .capabilities import ProviderCapabilities, SessionCapabilities


class EventKind(str, Enum):
    USER_PROMPT = "user_prompt"
    SUBTASK = "subtask"
    COMPACTION = "compaction"
    SYNTHETIC_CONTINUATION = "synthetic_continuation"
    # Source-generated notice that background work ended and the model resumes.
    BACKGROUND_COMPLETION = "background_completion"
    OTHER = "other"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    OTHER = "other"


class TerminalOutcome(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLATION = "cancellation"


@dataclass(frozen=True, slots=True)
class TerminalEvidence:
    """Persisted end of a logical attempt, independent of inference completion.

    Sources bind this to the attempt's final assistant message, not to an entire
    session. Native completion/usage timestamps remain untouched. An optional
    live actor may supplement this evidence, but its analysis is not persisted.
    """

    completed_at_ms: int
    outcome: TerminalOutcome
    abort_reason: str = ""
    # A live actor supplements a persisted terminal; never persist its analysis.
    observed_live: bool = False


class CostKind(str, Enum):
    PROVIDER_REPORTED = "provider_reported"
    LOCALLY_CALCULATED = "locally_calculated"
    ESTIMATED_EQUIVALENT = "estimated_equivalent"


class CostDisposition(str, Enum):
    BILLED = "billed"
    INCLUDED_SUBSCRIPTION = "included_subscription"
    ESTIMATED_EQUIVALENT = "estimated_equivalent"
    UNKNOWN = "unknown"


class QuotaWindowKind(str, Enum):
    FIXED = "fixed"
    ROLLING = "rolling"
    UNKNOWN = "unknown"


class AccountUsageStatus(str, Enum):
    BLOCKED = "blocked"
    AVAILABLE = "available"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Provenance:
    source_type: str
    source_generation: str
    source_instance: str | None = None
    source_session_id: str | None = None
    source_event_id: str | None = None


@dataclass(frozen=True, slots=True)
class ModelRef:
    provider: str
    model: str
    display_name: str | None = None


@dataclass(frozen=True, slots=True)
class TokenUsage:
    input: int = 0
    cache_read: int = 0
    cache_write: int = 0
    output: int = 0
    reasoning: int = 0
    # Numeric defaults preserve valuation semantics; mix telemetry distinguishes
    # an explicitly observed zero from an absent source field.
    known_fields: tuple[str, ...] = ("input", "cache_read", "cache_write", "output")

    def __post_init__(self) -> None:
        for name in ("input", "cache_read", "cache_write", "output", "reasoning"):
            if getattr(self, name) < 0:
                raise ValueError(f"TokenUsage.{name} cannot be negative")

    @property
    def total(self) -> int:
        return self.input + self.cache_read + self.cache_write + self.output + self.reasoning


@dataclass(frozen=True, slots=True)
class CostObservation:
    amount: Decimal
    currency: str
    kind: CostKind
    estimated: bool = False

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValueError("CostObservation.amount cannot be negative")
        if not self.currency.strip():
            raise ValueError("CostObservation.currency cannot be empty")


@dataclass(frozen=True, slots=True)
class NormalizedSession:
    session_id: str
    title: str
    created_at_ms: int
    updated_at_ms: int
    provenance: Provenance
    capabilities: SessionCapabilities
    parent_session_id: str | None = None
    archived_at_ms: int | None = None
    active: bool | None = None


@dataclass(frozen=True, slots=True)
class NormalizedPart:
    """Source-neutral message part.

    ``data`` contains the semantic part payload after source row identities have
    been lifted into explicit fields.  Adapters must map equivalent source
    concepts to the same canonical keys; analysis must never depend on a native
    database row wrapper or on an OpenCode generation discriminator.
    """

    part_id: str
    message_id: str
    session_id: str
    kind: str
    created_at_ms: int
    updated_at_ms: int
    provenance: Provenance
    data: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class NormalizedMessage:
    """Canonical persisted message plus its normalized parts.

    Keeping message/part structure in the domain is deliberate: v77 causal,
    compaction, context and tool semantics depend on more than flattened token
    totals.  Source adapters normalize this shape once so later analysis can be
    shared by V1, V2 and future generations.
    """

    message_id: str
    session_id: str
    role: MessageRole
    created_at_ms: int
    provenance: Provenance
    parts: tuple[NormalizedPart, ...] = ()
    completed_at_ms: int | None = None
    parent_message_id: str | None = None
    model: ModelRef | None = None
    variant: str | None = None
    agent: str | None = None
    summary: bool = False
    finish_reason: str | None = None
    error_name: str | None = None
    tokens: TokenUsage | None = None
    cost: CostObservation | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    termination: TerminalEvidence | None = None
    # Source-normalized cause only; never raw provider errors or response text.
    abort_reason: str = ""


@dataclass(frozen=True, slots=True)
class NormalizedEvent:
    event_id: str
    session_id: str
    kind: EventKind
    created_at_ms: int
    provenance: Provenance
    text: str | None = None
    parent_event_id: str | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ModelInvocation:
    invocation_id: str
    session_id: str
    created_at_ms: int
    model: ModelRef
    tokens: TokenUsage
    provenance: Provenance
    completed_at_ms: int | None = None
    cost: CostObservation | None = None
    initiating_event_id: str | None = None
    provider_request_id: str | None = None
    message_id: str | None = None
    step_part_id: str | None = None
    variant: str | None = None
    summary: bool = False
    finish_reason: str | None = None
    error_name: str | None = None
    cost_disposition: CostDisposition = CostDisposition.UNKNOWN
    # Optional proven request account identity, not the currently active login.
    account_ref: AccountRef | None = None


@dataclass(frozen=True, slots=True)
class ContextBoundary:
    """Non-billable start of a new context epoch, e.g. a session location move.

    Carries no usage and no filesystem location; identity remains the session.
    """

    session_id: str
    boundary_id: str
    at_ms: int


@dataclass(frozen=True, slots=True)
class BackgroundActivity:
    """Verified work a model detached from its turn, e.g. a background shell.

    ``activity_id`` is an opaque source-scoped identity, never a native job ID.
    ``running`` stays True until native evidence ends it: a completion notice
    (``ended_at_ms``/``outcome`` where known) or the native registry no longer
    listing it (outcome unknown). Inactivity or elapsed time never ends it.
    """

    activity_id: str
    session_id: str
    kind: str
    started_at_ms: int
    owner_message_id: str
    running: bool = True
    ended_at_ms: int | None = None
    outcome: TerminalOutcome | None = None
    completion_event_id: str | None = None


@dataclass(frozen=True, slots=True)
class SessionSnapshot:
    root: NormalizedSession
    sessions: tuple[NormalizedSession, ...]
    messages: tuple[NormalizedMessage, ...]
    parts: tuple[NormalizedPart, ...]
    events: tuple[NormalizedEvent, ...]
    invocations: tuple[ModelInvocation, ...]
    source_revision: str
    context_boundaries: tuple[ContextBoundary, ...] = ()
    background: tuple[BackgroundActivity, ...] = ()


@dataclass(frozen=True, slots=True)
class PricingTier:
    name: str = "Default"
    min_input_tokens: int | None = None
    max_input_tokens: int | None = None
    per_million_input: Decimal | None = None
    per_million_cache_read: Decimal | None = None
    per_million_cache_write: Decimal | None = None
    per_million_output: Decimal | None = None
    # Preserve the published lower-bound notation; min_input_tokens remains
    # inclusive for request valuation (a published >N is normalized to N+1).
    input_threshold_operator: str | None = None

    def matches(self, request_input_tokens: int) -> bool:
        if self.min_input_tokens is not None and request_input_tokens < self.min_input_tokens:
            return False
        if self.max_input_tokens is not None and request_input_tokens > self.max_input_tokens:
            return False
        return True


@dataclass(frozen=True, slots=True)
class QuotaWindow:
    name: str
    kind: QuotaWindowKind
    used_fraction: Decimal | None = None
    remaining_fraction: Decimal | None = None
    reset_at_ms: int | None = None
    duration_seconds: int | None = None
    native_used: Decimal | None = None
    native_limit: Decimal | None = None
    native_unit: str | None = None
    unlimited: bool = False
    model_id: str | None = None
    scope: str = "account"
    # Window-specific native evidence only; account availability stays on the snapshot.
    status: AccountUsageStatus = AccountUsageStatus.UNKNOWN

    def __post_init__(self) -> None:
        for name in ("used_fraction", "remaining_fraction"):
            value = getattr(self, name)
            if value is not None and not (Decimal("0") <= value <= Decimal("1")):
                raise ValueError(f"QuotaWindow.{name} must be between 0 and 1")
        if self.duration_seconds is not None and self.duration_seconds <= 0:
            raise ValueError("QuotaWindow.duration_seconds must be positive")


@dataclass(frozen=True, slots=True)
class QuotaSnapshot:
    provider: str
    fetched_at_ms: int
    capabilities: ProviderCapabilities
    plan: str | None = None
    windows: tuple[QuotaWindow, ...] = ()
    credit_balance: Decimal | None = None
    credit_unit: str | None = None
    available: bool = True
    reason: str = ""
    usage_status: AccountUsageStatus = AccountUsageStatus.UNKNOWN
    account_ref: AccountRef | None = None
    availability: str = "available"
    observations: Mapping[str, object] = field(default_factory=dict)
    billing_components: tuple[BillingComponent, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ModelPricing:
    model: ModelRef
    currency: str
    per_million_input: Decimal | None = None
    per_million_cache_read: Decimal | None = None
    per_million_cache_write: Decimal | None = None
    per_million_output: Decimal | None = None
    tiers: tuple[PricingTier, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)

    def selected_tier(self, request_input_tokens: int) -> PricingTier | None:
        if self.tiers:
            for tier in self.tiers:
                if tier.matches(request_input_tokens):
                    return tier
            return self.tiers[0]
        if any(value is not None for value in (
            self.per_million_input, self.per_million_cache_read,
            self.per_million_cache_write, self.per_million_output,
        )):
            return PricingTier(
                per_million_input=self.per_million_input,
                per_million_cache_read=self.per_million_cache_read,
                per_million_cache_write=self.per_million_cache_write,
                per_million_output=self.per_million_output,
            )
        return None
