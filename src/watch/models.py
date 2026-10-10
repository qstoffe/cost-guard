"""Source-neutral Watch projections and observation state."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Mapping

from src.reports.models import AccountsQuotasProjection, PromptProjection
from src.analysis.token_mix import TokenMix
from src.analysis.context import PriceWarningSeverity


@dataclass(frozen=True, slots=True)
class ToolObservation:
    tool_count: int = 0
    todo_completed: int = 0
    todo_total: int = 0
    active_todo: str = ""
    tool_counts: tuple[tuple[str, int], ...] = ()
    failed_count: int = 0
    running_tool: str = ""
    running_ms: int = 0
    background_kinds: tuple[str, ...] = ()
    background_ms: int = 0

    @property
    def has_open_todo(self) -> bool:
        return self.todo_total > 0 and self.todo_completed < self.todo_total

    @property
    def has_status_row(self) -> bool:
        return bool(self.running_tool) or bool(self.background_kinds) or self.has_open_todo


@dataclass(frozen=True, slots=True)
class WatchRow:
    session_id: str
    session_title: str
    prompt: PromptProjection
    marker: str = ""
    tool: ToolObservation | None = None
    is_latest_session_event: bool = True

    @property
    def next_context_warning(self) -> str:
        """Return the Watch-active warning for this session event only.

        Watch warnings are current session guidance, not historical annotations.
        A newer prompt/compaction therefore suppresses warnings on older rows.
        When Watch has a concrete live context value, its warning state is
        authoritative even when that state is empty after context shrinks.
        """
        if not self.is_latest_session_event:
            return ""
        if self.prompt.watch_next_context_tokens is not None:
            return self.prompt.watch_next_context_warning
        return self.prompt.watch_next_context_warning or self.prompt.next_context_warning

    @property
    def next_context_warning_severity(self) -> PriceWarningSeverity:
        """Select structured severity with the same live/expiry rules as text."""
        if not self.is_latest_session_event:
            return PriceWarningSeverity.NONE
        if self.prompt.watch_next_context_tokens is not None or self.prompt.watch_next_context_warning:
            return self.prompt.watch_next_context_warning_severity
        return self.prompt.next_context_warning_severity


@dataclass(frozen=True, slots=True)
class WatchSessionSubtotal:
    """CCost of the selected Watch rows in one displayed session block."""
    ccost: Decimal = Decimal(0)
    unresolved_cost: bool = False


@dataclass(frozen=True, slots=True)
class WatchProjection:
    title: str
    source_label: str
    rows: tuple[WatchRow, ...]
    source_warnings: tuple[str, ...] = ()
    quota: AccountsQuotasProjection | None = None
    quota_stale: bool = False
    active_count: int = 0
    status: str = ""
    status_active: bool = False
    now_ms: int = 0
    session_warnings: Mapping[str, str] | None = None
    recent_model_notice: str = ""
    quota_recovering_accounts: tuple[tuple[str, str, str], ...] = ()
    token_mix: TokenMix = field(default_factory=TokenMix)
    recent_promotion_notices: tuple[str, ...] = ()
    session_subtotals: Mapping[str, WatchSessionSubtotal] = field(default_factory=dict)
