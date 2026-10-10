"""Bounded recent-prompt sampling: independent comparison and usage eligibility."""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from heapq import nlargest

from src.analysis.models import PromptRecord, RootAnalysisBundle
from src.domain import NormalizedSession, SessionSnapshot

SAMPLE_SIZE = 100


@dataclass(slots=True)
class AnalyzedRoot:
    session: NormalizedSession
    bundle: RootAnalysisBundle
    cache_hit: bool
    snapshot: SessionSnapshot | None = None


def latest_prompts(roots: Sequence[AnalyzedRoot]) -> tuple[PromptRecord, ...]:
    """Relative CCost uses completed, non-aborted visible prompts only."""
    return tuple(nlargest(SAMPLE_SIZE,
        (p for item in roots for p in item.bundle.prompts if not p.in_progress and not p.aborted),
        key=lambda p: (p.prompt_time_ms, p.session_id, p.prompt_id),
    ))


def latest_token_prompts(roots: Sequence[AnalyzedRoot]) -> tuple[PromptRecord, ...]:
    """Token mix includes running/interrupted prompts with observed telemetry."""
    return tuple(nlargest(SAMPLE_SIZE,
        (p for item in roots for p in item.bundle.prompts
         if any(entry.tokens.known_fields for entry in p.entries)),
        key=lambda p: (p.prompt_time_ms, p.session_id, p.prompt_id),
    ))


def recent_sample_roots(
    roots: Sequence[NormalizedSession], root_activity: Mapping[str, int],
    analyze: Callable[[NormalizedSession], AnalyzedRoot],
) -> tuple[AnalyzedRoot, ...]:
    """Hydrate roots in descending tree activity until BOTH sample cutoffs hold.

    A recently touched root can contain old prompts. Collecting 100 alone is
    insufficient; equal timestamps must also be scanned for deterministic ties.
    Account acquisition, cache ownership and source I/O remain with the caller.
    """
    analyzed: list[AnalyzedRoot] = []
    sample: tuple[PromptRecord, ...] = ()
    mix_sample: tuple[PromptRecord, ...] = ()
    for root in roots:
        if (len(sample) == len(mix_sample) == SAMPLE_SIZE
                and root_activity[root.session_id] < min(sample[-1].prompt_time_ms, mix_sample[-1].prompt_time_ms)):
            break
        item = analyze(root)
        analyzed.append(item)
        sample = tuple(sorted(
            (*sample, *latest_prompts((item,))),
            key=lambda p: (p.prompt_time_ms, p.session_id, p.prompt_id), reverse=True,
        )[:SAMPLE_SIZE])
        mix_sample = tuple(sorted(
            (*mix_sample, *latest_token_prompts((item,))),
            key=lambda p: (p.prompt_time_ms, p.session_id, p.prompt_id), reverse=True,
        )[:SAMPLE_SIZE])
    return tuple(analyzed)
