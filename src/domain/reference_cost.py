"""Allowlisted explanation facts, not an alternative valuation or diagnostic ledger."""
from dataclasses import dataclass
from typing import Callable, Iterable, Literal

from .models import ModelRef, TokenUsage

ReferenceCostReason = Literal["model_absent", "identity", "rate", "usage", "catalog", "unknown"]
REASONS = frozenset(("model_absent", "identity", "rate", "usage", "catalog", "unknown"))


@dataclass(frozen=True, slots=True, order=True)
class ReferenceCostIssue:
    reason: ReferenceCostReason
    model: str = ""
    detail: str = ""


ReferenceCostDiagnosis = Callable[[ModelRef, TokenUsage], ReferenceCostIssue]


def bounded_issues(issues: Iterable[ReferenceCostIssue]) -> tuple[ReferenceCostIssue, ...]:
    """Stable small scope summary; an omitted cause is never silently misattributed."""
    distinct = sorted(set(issues))
    return tuple(distinct if len(distinct) <= 6 else distinct[:5] + [ReferenceCostIssue("unknown")])
