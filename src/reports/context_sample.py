"""Bounded context-guidance sample: canonical membership, compact token volumes.

This is guidance input, never source-wide Earlier proof. The comparison and token
populations keep their independent eligibility and strict activity cutoffs.
"""
from dataclasses import dataclass
from heapq import nlargest

from src.analysis.token_mix import PricedUsage
from src.pricing.catalog import normalized_average_token_mix
from .sampling import SAMPLE_SIZE, _newest_first, latest_prompts, latest_token_prompts


@dataclass(frozen=True, slots=True)
class ComparisonCandidate:
    order: tuple[int, str, str]
    usage: PricedUsage


@dataclass(frozen=True, slots=True)
class ContextSample:
    comparison: tuple[ComparisonCandidate, ...]
    token_order: tuple[tuple[int, str, str], ...]
    scanned_roots: int

    @property
    def mix(self):
        return normalized_average_token_mix(candidate.usage for candidate in self.comparison)


def _reduce(service, item, priceable, comparison, token_order):
    prompts = latest_prompts((item,), priceable)
    additions = tuple(ComparisonCandidate(_newest_first(prompt), usage)
        for prompt, usage in zip(prompts, service._relative_usage(prompts)))
    comparison = tuple(nlargest(SAMPLE_SIZE, (*comparison, *additions), key=lambda item: item.order))
    token_order = tuple(nlargest(SAMPLE_SIZE, (*token_order,
        *(_newest_first(prompt) for prompt in latest_token_prompts((item,), priceable)))))
    return comparison, token_order


def collect_context_sample(service, roots, activity, *, check=None):
    """Release only sampler-owned analyses; retain no PromptRecord/TraceEntry graph."""
    comparison, token_order, scanned = (), (), 0
    priceable = service._priceable()
    for root in roots:
        if check is not None:
            check()
        if (len(comparison) == len(token_order) == SAMPLE_SIZE and
                activity[root.session_id] < min(comparison[-1].order[0], token_order[-1][0])):
            break
        owned = root.session_id not in service._analyzed
        item = service._analyze(root)
        try:
            if check is not None:
                check()
            with service.metrics.measure('context_sample_reduction'):
                comparison, token_order = _reduce(service, item, priceable, comparison, token_order)
            scanned += 1
            service.metrics.add('context_warning_sample_roots')
            peak = service.metrics.counts.get('context_sample_peak_analysis_roots', 0)
            service.metrics.counts['context_sample_peak_analysis_roots'] = max(peak, len(service._analyzed))
        finally:
            if owned:
                service._acquisition.release(root.session_id, item)
            del item  # Do not keep the prior heavy tree while acquiring the next one.
    if check is not None:
        check()
    return ContextSample(comparison, token_order, scanned)
