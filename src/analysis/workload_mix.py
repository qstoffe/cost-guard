"""Bounded distinct-prompt evidence and Decimal workload-profile priors.

Only canonical completed prompt entries enter this layer. Each compact prompt
retains pooled eligible volumes per exact catalog identity, not raw requests.
"""
from dataclasses import dataclass
from decimal import Decimal
from collections import defaultdict

from src.pricing.catalog import PricingCatalog
from src.pricing.publishers import model_publisher
from .models import PromptRecord
from .token_mix import MIX_FIELDS, priceable_request
from .valuation import unique_usage

Mix = tuple[Decimal, Decimal, Decimal, Decimal, int]


@dataclass(frozen=True, slots=True)
class PromptMix:
    at_ms: int
    session: str
    prompt: str
    # catalog model ID, verified publisher (or empty), I/C/W/O volumes
    groups: tuple[tuple[str, str, tuple[int, int, int, int]], ...]

    @property
    def key(self):
        return self.at_ms, self.session, self.prompt


@dataclass(frozen=True, slots=True)
class MixEvidence:
    model_prompts: int = 0
    publisher_prompts: int = 0
    generic_prior_weight: int = 100
    global_prompts: int = 0
    history_exhausted: bool = True

    @property
    def observed_prompts(self):
        return self.model_prompts + self.publisher_prompts


def prompt_mix(prompt: PromptRecord, catalog: PricingCatalog) -> PromptMix | None:
    if prompt.in_progress or prompt.aborted:
        return None
    groups = {}
    for entry in dict.fromkeys(unique_usage(prompt.entries)):
        if not priceable_request(entry.model, entry.tokens, catalog.reference_category_valuation):
            continue
        model = catalog.resolve_reference(entry.model.model)
        if model is None:
            continue
        key = model.model.model, model_publisher(model) or ""
        totals = groups.setdefault(key, [0] * 4)
        for index, field in enumerate(MIX_FIELDS):
            totals[index] += getattr(entry.tokens, field)
        totals[3] += entry.tokens.reasoning
    return (PromptMix(prompt.prompt_time_ms, prompt.session_id, prompt.prompt_id,
                      tuple((m, p, tuple(v)) for (m, p), v in sorted(groups.items()))) if groups else None)


class WorkloadSamples:
    """At most 100/model + 200/publisher + 100 generic compact prompts.

    A publisher needs 200 candidates: at most 100 may be excluded because they
    already supplied the target model. Full groups preserve mixed-model prompts.
    """
    def __init__(self):
        self.models = defaultdict(dict)
        self.publishers = defaultdict(dict)
        self.generic = {}

    @staticmethod
    def _add(group, item, limit):
        group[item.key] = item
        if len(group) > limit:
            del group[min(group)]

    def add(self, item: PromptMix):
        self._add(self.generic, item, 100)
        for model, publisher, _volumes in item.groups:
            self._add(self.models[model], item, 100)
            if publisher:
                self._add(self.publishers[publisher], item, 200)

    def compact(self):
        groups = (self.generic, *self.models.values(), *self.publishers.values())
        return tuple(sorted({k: v for group in groups for k, v in group.items()}.values(), key=lambda p: p.key))

    def effective(self, model_id: str, publisher: str | None) -> tuple[Mix, MixEvidence]:
        own = self.models.get(model_id, {})
        family = sorted((p for k, p in self.publishers.get(publisher, {}).items() if k not in own),
                        key=lambda p: p.key, reverse=True)[:100 - len(own)]
        n, p = len(own), len(family)
        global_count = len(self.generic)
        evidence = MixEvidence(n, p, 100 - n - p, global_count)
        if not global_count:
            return (Decimal(0),) * 4 + (0,), evidence
        pools = ((own.values(), lambda m, pub: m == model_id, n),
                 (family, lambda m, pub: pub == publisher and m != model_id, p),
                 (self.generic.values(), lambda m, pub: True, 100 - n - p))
        shares = [Decimal(0)] * 4
        for prompts, include, weight in pools:
            if not weight:
                continue
            volumes = [0] * 4
            for prompt in prompts:
                for model, pub, tokens in prompt.groups:
                    if include(model, pub):
                        for i, value in enumerate(tokens):
                            volumes[i] += value
            total = sum(volumes)
            for i, value in enumerate(volumes):
                shares[i] += Decimal(weight) * value / (100 * total)
        # Avoid Decimal division residue in the invariant before display rounding.
        largest = max(range(4), key=lambda i: shares[i])
        shares[largest] += Decimal(1) - sum(shares)
        return (*shares, global_count), evidence
