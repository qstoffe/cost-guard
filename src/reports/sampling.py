"""Bounded recent-prompt sampling: independent comparison and usage eligibility.

Both samples contain only prompts with at least one reference-priceable request
(see ``analysis.token_mix.priceable_request``). Unpriceable prompts are skipped,
so traversal continues into older history until each sample holds the latest
100 eligible prompts or history is exhausted.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from heapq import nlargest

from src.analysis.models import PromptRecord, RootAnalysisBundle, TraceEntry
from src.domain import NormalizedSession, SessionSnapshot

SAMPLE_SIZE = 100
RequestFilter = Callable[[TraceEntry], bool]


@dataclass(slots=True)
class AnalyzedRoot:
    session: NormalizedSession
    bundle: RootAnalysisBundle
    cache_hit: bool
    snapshot: SessionSnapshot | None = None


def _newest_first(prompt: PromptRecord) -> tuple[int, str, str]:
    return prompt.prompt_time_ms, prompt.session_id, prompt.prompt_id


def latest_prompts(roots: Sequence[AnalyzedRoot], priceable: RequestFilter) -> tuple[PromptRecord, ...]:
    """Relative CCost uses completed, non-aborted prompts with priceable usage."""
    return tuple(nlargest(SAMPLE_SIZE,
        (p for item in roots for p in item.bundle.prompts
         if not p.in_progress and not p.aborted and any(map(priceable, p.entries))),
        key=_newest_first,
    ))


def latest_token_prompts(roots: Sequence[AnalyzedRoot], priceable: RequestFilter) -> tuple[PromptRecord, ...]:
    """Token mix includes running/interrupted prompts with priceable usage."""
    return tuple(nlargest(SAMPLE_SIZE,
        (p for item in roots for p in item.bundle.prompts if any(map(priceable, p.entries))),
        key=_newest_first,
    ))


def recent_sample_roots(
    roots: Sequence[NormalizedSession], root_activity: Mapping[str, int],
    analyze: Callable[[NormalizedSession], AnalyzedRoot], priceable: RequestFilter,
) -> tuple[AnalyzedRoot, ...]:
    """Hydrate roots in descending tree activity until BOTH sample cutoffs hold.

    A recently touched root can contain old prompts. Collecting 100 alone is
    insufficient; equal timestamps must also be scanned for deterministic ties.
    Only eligible prompts fill a sample, so unpriceable history never satisfies
    the stop condition. Account acquisition, cache ownership and source I/O
    remain with the caller.
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
        sample = tuple(sorted((*sample, *latest_prompts((item,), priceable)),
                              key=_newest_first, reverse=True)[:SAMPLE_SIZE])
        mix_sample = tuple(sorted((*mix_sample, *latest_token_prompts((item,), priceable)),
                                  key=_newest_first, reverse=True)[:SAMPLE_SIZE])
    return tuple(analyzed)
