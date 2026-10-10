"""Provider-neutral tiered pricing catalog and estimators."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from functools import lru_cache
from typing import Iterable

from src.domain import ModelPricing, ModelRef, PricingTier, TokenUsage
from src.domain.ccost import CCostPricing, ccost_pricing
from .identities import reference_identity

_COPILOT_PREFIX = re.compile(r"^github-copilot/")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_UNRESOLVED = object()


@lru_cache(maxsize=8192)
def canonical_model_name(value: str) -> str:
    value = (value or "").strip().lower()
    return _NON_ALNUM.sub("", _COPILOT_PREFIX.sub("", value))


@dataclass(frozen=True, slots=True)
class PricingCatalog:
    """Immutable catalog; identity lookups are memoized per instance.

    Every request/row resolves its model repeatedly, so name matching is
    computed once per distinct model string rather than per lookup.
    """

    models: tuple[ModelPricing, ...]
    retrieved_at_ms: int = 0
    source_revision: str = ""
    refresh_not_after_ms: int | None = None
    ccost_models: tuple[CCostPricing, ...] = field(init=False, repr=False, compare=False)
    _ccost_by_model: dict[int, CCostPricing] = field(init=False, repr=False, compare=False)
    _reference_memo: dict[str, ModelPricing | None] = field(init=False, repr=False, compare=False)
    _resolve_memo: dict[str, ModelPricing | None] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        ccost_models = tuple(ccost_pricing(model) for model in self.models)
        object.__setattr__(self, "ccost_models", ccost_models)
        object.__setattr__(self, "_ccost_by_model", {id(m): c for m, c in zip(self.models, ccost_models)})
        object.__setattr__(self, "_reference_memo", {})
        object.__setattr__(self, "_resolve_memo", {})

    def reference_prices(self, name: str, *, exact: bool = True) -> CCostPricing | None:
        native = self.resolve_reference(name) if exact else self.resolve(name)
        if native is None:
            return None
        return self._ccost_by_model[id(native)]

    def resolve_reference(self, model_id_or_name: str) -> ModelPricing | None:
        """Exact/verified reference identity; ambiguous prices remain unknown."""
        key = model_id_or_name or ""
        cached = self._reference_memo.get(key, _UNRESOLVED)
        if cached is _UNRESOLVED:
            cached = self._reference_memo[key] = self._match_reference(key)
        return cached  # type: ignore[return-value]

    def _match_reference(self, model_id_or_name: str) -> ModelPricing | None:
        exact = canonical_model_name(model_id_or_name.split("/", 1)[-1])
        target = reference_identity(model_id_or_name)
        # An explicitly priced variant takes precedence over a base alias. Never
        # collapse two catalog rate sets merely because context capacity aliases.
        for identity in dict.fromkeys((exact, target)):
            matches = [item for item in self.models if identity and identity in {
                canonical_model_name(item.model.model.split("/", 1)[-1]),
                canonical_model_name(item.model.display_name or "")
            }]
            if matches:
                return matches[0] if len(matches) == 1 else None
        return None

    def resolve(self, model_id_or_name: str) -> ModelPricing | None:
        key = model_id_or_name or ""
        cached = self._resolve_memo.get(key, _UNRESOLVED)
        if cached is _UNRESOLVED:
            cached = self._resolve_memo[key] = self._match_closest(key)
        return cached  # type: ignore[return-value]

    def _match_closest(self, model_id_or_name: str) -> ModelPricing | None:
        exact = self.resolve_reference(model_id_or_name)
        if exact is not None or reference_identity(model_id_or_name).startswith("claude"):
            return exact
        target = canonical_model_name(model_id_or_name)
        if not target:
            return None
        best: ModelPricing | None = None
        best_score = -1
        for model in self.models:
            candidates = (model.model.model, model.model.display_name or "")
            for candidate in candidates:
                current = canonical_model_name(candidate)
                if not current:
                    continue
                score = -1
                if current == target:
                    score = 100
                elif target in current or current in target:
                    score = 80 - abs(len(target) - len(current))
                if score > best_score:
                    best_score = score
                    best = model
        return best if best_score >= 0 else None

    def select_tier(self, model: ModelPricing | CCostPricing, request_input_tokens: int) -> PricingTier | None:
        return model.selected_tier(max(0, int(request_input_tokens)))

    def estimate(self, model_ref: ModelRef, tokens: TokenUsage) -> Decimal | None:
        """Legacy monetary billing fallback; never used for CCost analysis."""
        model = self.resolve(model_ref.model)
        if model is None:
            return None
        return price_token_usage(model, tokens, tokens.input + tokens.cache_read + tokens.cache_write)

    def reference_valuation(self, model_ref: ModelRef, tokens: TokenUsage) -> Decimal | None:
        """CCost permits only exact or explicitly verified reference identities."""
        model = self.reference_prices(model_ref.model)
        if model is None:
            return None
        return price_token_usage(model, tokens, tokens.input + tokens.cache_read + tokens.cache_write)

    def reference_category_valuation(
        self, model_ref: ModelRef, tokens: TokenUsage,
    ) -> tuple[Decimal, Decimal, Decimal, Decimal] | None:
        """The same CCost as reference_valuation, split into I/C/W/O components."""
        model = self.reference_prices(model_ref.model)
        if model is None:
            return None
        return price_token_categories(model, tokens, tokens.input + tokens.cache_read + tokens.cache_write)

    def reference_usage(self, model_ref: ModelRef, tokens: TokenUsage) -> Decimal | None:
        """Diagnostic reference usage, preserving the context resolver's selection."""
        model = self.reference_prices(model_ref.model, exact=False)
        return None if model is None else price_token_usage(model, tokens, tokens.input + tokens.cache_read + tokens.cache_write)

    def reference_input_context(
        self,
        model_ref: ModelRef,
        *,
        input_tokens: int,
        cache_read_tokens: int,
        cache_write_tokens: int,
        request_input_tokens: int,
    ) -> Decimal | None:
        model = self.reference_prices(model_ref.model, exact=False)
        if model is None:
            return None
        tier = self.select_tier(model, request_input_tokens)
        if tier is None or tier.per_million_input is None or tier.per_million_cache_read is None:
            return None
        write_rate = tier.per_million_cache_write
        if write_rate is None:
            write_rate = tier.per_million_input
        million = Decimal(1_000_000)
        return (
            Decimal(input_tokens) / million * tier.per_million_input
            + Decimal(cache_read_tokens) / million * tier.per_million_cache_read
            + Decimal(cache_write_tokens) / million * write_rate
        )


def price_token_categories(
    model: ModelPricing | CCostPricing, tokens: TokenUsage, request_input_tokens: int,
) -> tuple[Decimal, Decimal, Decimal, Decimal] | None:
    """Price one request's I/C/W/O components with its own selected tier."""
    tier = model.selected_tier(request_input_tokens)
    if tier is None:
        return None
    if tier.per_million_input is None or tier.per_million_cache_read is None or tier.per_million_output is None:
        return None
    write_rate = tier.per_million_cache_write
    if write_rate is None:
        write_rate = tier.per_million_input
    million = Decimal(1_000_000)
    return (
        Decimal(tokens.input) / million * tier.per_million_input,
        Decimal(tokens.cache_read) / million * tier.per_million_cache_read,
        Decimal(tokens.cache_write) / million * write_rate,
        Decimal(tokens.output + tokens.reasoning) / million * tier.per_million_output,
    )


def price_token_usage(model: ModelPricing | CCostPricing, tokens: TokenUsage, request_input_tokens: int) -> Decimal | None:
    parts = price_token_categories(model, tokens, request_input_tokens)
    return None if parts is None else parts[0] + parts[1] + parts[2] + parts[3]


def normalized_average_token_mix(records: Iterable[object]) -> tuple[Decimal, Decimal, Decimal, Decimal, int]:
    i = c = w = o = Decimal(0)
    samples = 0
    for record in records:
        input_tokens = Decimal(int(getattr(record, "input_tokens", 0)))
        cache_read = Decimal(int(getattr(record, "cache_read_tokens", 0)))
        cache_write = Decimal(int(getattr(record, "cache_write_tokens", 0)))
        output = Decimal(int(getattr(record, "output_tokens", 0)))
        total = input_tokens + cache_read + cache_write + output
        if total <= 0:
            continue
        i += input_tokens
        c += cache_read
        w += cache_write
        o += output
        samples += 1
    total = i + c + w + o
    if samples == 0 or total <= 0:
        return Decimal(0), Decimal(0), Decimal(0), Decimal(0), 0
    return i / total, c / total, w / total, o / total, samples


def token_mix_unit_price(
    mix: tuple[Decimal, Decimal, Decimal, Decimal, int],
    model: CCostPricing | None,
) -> Decimal | None:
    if model is None or mix[4] <= 0:
        return None
    return token_mix_tier_price(mix, model.selected_tier(0))


def token_mix_tier_price(
    mix: tuple[Decimal, Decimal, Decimal, Decimal, int], tier: PricingTier | None,
) -> Decimal | None:
    """One tier under the shared I/C/W/O mix; never derive tier factors."""
    if mix[4] <= 0:
        return None
    if tier is None or tier.per_million_input is None or tier.per_million_cache_read is None or tier.per_million_output is None:
        return None
    write_rate = tier.per_million_cache_write if tier.per_million_cache_write is not None else tier.per_million_input
    return mix[0] * tier.per_million_input + mix[1] * tier.per_million_cache_read + mix[2] * write_rate + mix[3] * tier.per_million_output
